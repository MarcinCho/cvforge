from __future__ import annotations

from ..config import LLMConfig
from .base import LLMError, LLMProvider
from .command import CommandProvider
from .structured import ask_json

__all__ = ["LLMError", "LLMProvider", "ask_json", "make_provider"]


def make_provider(cfg: LLMConfig) -> LLMProvider:
    if cfg.provider == "command":
        return CommandProvider(cfg.command, cfg.timeout_s)
    if cfg.provider in ("openai", "http"):
        import os

        from .openai_compat import OpenAICompatProvider

        key = os.environ.get(cfg.api_key_env, "") or cfg.api_key
        return OpenAICompatProvider(cfg.base_url, cfg.model, key, cfg.timeout_s, cfg.vision)
    if cfg.provider == "manual":
        from pathlib import Path

        from .manual import ManualProvider

        return ManualProvider(Path(cfg.manual_dir).expanduser(), cfg.timeout_s)
    raise LLMError(f"unknown llm provider {cfg.provider!r} (use 'command', 'openai' or 'manual')")
