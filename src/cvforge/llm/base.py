"""LLM provider interface. Anything that turns a prompt into text can be a provider."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    name: str
    supports_images: bool

    def complete(self, prompt: str, images: list[Path] | None = None) -> str: ...
