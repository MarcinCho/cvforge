"""Manual provider: write each prompt to a file and wait for the answer file.

Lets anyone use a chat UI (ChatGPT, Claude.ai, Gemini web...) or another agent as the LLM:
copy prompt-N.md into the chat, save the reply as answer-N.md in the same folder.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from .base import LLMError


class ManualProvider:
    supports_images = False

    def __init__(self, directory: Path, timeout_s: int = 3600, poll_s: float = 1.0):
        self.dir = Path(directory)
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self.name = f"manual:{self.dir}"
        self._lock = threading.Lock()  # parallel style variants must not grab the same prompt number

    def _next_index(self) -> int:
        self.dir.mkdir(parents=True, exist_ok=True)
        nums = [int(p.stem.split("-")[1]) for p in self.dir.glob("prompt-*.md") if p.stem.split("-")[1].isdigit()]
        return max(nums, default=0) + 1

    def complete(self, prompt: str, images: list[Path] | None = None) -> str:
        with self._lock:
            n = self._next_index()
            prompt_file, answer_file = self.dir / f"prompt-{n}.md", self.dir / f"answer-{n}.md"
            prompt_file.write_text(prompt, encoding="utf-8")
        print(
            f"[cvforge] prompt written to {prompt_file}\n"
            f"[cvforge] paste it into your LLM chat and save the reply as {answer_file}",
            file=sys.stderr,
            flush=True,
        )
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if answer_file.exists() and answer_file.stat().st_size > 0:
                time.sleep(0.3)  # let the writer finish
                return answer_file.read_text(encoding="utf-8").strip()
            time.sleep(self.poll_s)
        raise LLMError(f"no answer in {answer_file} after {self.timeout_s}s")
