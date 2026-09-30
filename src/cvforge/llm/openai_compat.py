"""OpenAI-compatible chat completions (OpenAI, OpenRouter, Ollama, LM Studio, vLLM...)."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from .base import LLMError


class OpenAICompatProvider:
    def __init__(self, base_url: str, model: str, api_key: str = "", timeout_s: int = 600, vision: bool = False):
        if not model:
            raise LLMError("[llm].model must be set for the openai provider")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.supports_images = vision
        self.name = f"openai:{model}@{self.base_url}"

    def complete(self, prompt: str, images: list[Path] | None = None) -> str:
        content: str | list = prompt
        if images and self.supports_images:
            content = [{"type": "text", "text": prompt}]
            for img in images:
                b64 = base64.b64encode(Path(img).read_bytes()).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {"model": self.model, "messages": [{"role": "user", "content": content}], "temperature": 0.4}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout_s)
        except httpx.HTTPError as e:
            raise LLMError(f"LLM HTTP request failed: {e}") from e
        if r.status_code >= 400:
            raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:2000]}")
        try:
            return r.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"Unexpected LLM response: {r.text[:2000]}") from e
