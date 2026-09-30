"""Run any LLM CLI as a subprocess: prompt goes in (stdin / file / argument), answer comes out on stdout."""

from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path

from .base import LLMError


class CommandProvider:
    supports_images = False

    def __init__(self, command: str, timeout_s: int = 600):
        self.command = command
        self.timeout_s = timeout_s
        self.name = f"command:{command}"

    def complete(self, prompt: str, images: list[Path] | None = None) -> str:
        args = shlex.split(self.command)
        stdin: str | None = prompt
        tmp: Path | None = None
        try:
            if any("{prompt_file}" in a for a in args):
                with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
                    f.write(prompt)
                    tmp = Path(f.name)
                args = [a.replace("{prompt_file}", str(tmp)) for a in args]
                stdin = None
            elif any("{prompt}" in a for a in args):
                args = [a.replace("{prompt}", prompt) for a in args]
                stdin = None
            try:
                proc = subprocess.run(
                    args,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_s,
                    stdin=subprocess.DEVNULL if stdin is None else None,
                )
            except FileNotFoundError as e:
                raise LLMError(f"LLM command not found: {args[0]!r}. Check [llm].command in cvforge.toml") from e
            except subprocess.TimeoutExpired as e:
                raise LLMError(f"LLM command timed out after {self.timeout_s}s") from e
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)
        if proc.returncode != 0:
            detail = (proc.stderr.strip() or proc.stdout.strip())[:2000]
            raise LLMError(f"LLM command failed ({proc.returncode}): {detail}")
        out = proc.stdout.strip()
        if not out:
            raise LLMError(f"LLM command returned no output. stderr: {proc.stderr.strip()[:2000]}")
        return out
