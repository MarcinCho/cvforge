"""Scripted provider for tests and dry runs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


class FakeProvider:
    name = "fake"
    supports_images = False

    def __init__(self, responses: list[str] | Callable[[str], str]):
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, prompt: str, images: list[Path] | None = None) -> str:
        self.prompts.append(prompt)
        if callable(self.responses):
            return self.responses(prompt)
        return self.responses.pop(0)
