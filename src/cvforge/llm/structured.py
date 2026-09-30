"""Ask an LLM for JSON matching a Pydantic model, with validation-error feedback retries."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .base import LLMError, LLMProvider

M = TypeVar("M", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> str:
    """Pull the JSON object out of a chatty answer (code fences, preamble, trailing notes)."""
    m = _FENCE.search(text)
    if m and "{" in m.group(1):
        text = m.group(1)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in LLM output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unterminated JSON object in LLM output")


def schema_instructions(model: type[BaseModel]) -> str:
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
    return (
        "\n\n## Output format\n"
        "Respond with ONE JSON object only (no prose, no markdown fences) that validates against this JSON Schema:\n"
        f"{schema}\n"
    )


def ask_json(provider: LLMProvider, prompt: str, model: type[M], max_retries: int = 2, images=None) -> M:
    full = prompt + schema_instructions(model)
    last_err = ""
    attempt_prompt = full
    for _ in range(max_retries + 1):
        raw = provider.complete(attempt_prompt, images=images)
        try:
            return model.model_validate_json(extract_json(raw))
        except (ValueError, ValidationError) as e:
            last_err = str(e)[:3000]
            attempt_prompt = (
                full
                + "\n\n## Your previous answer was invalid\n"
                + f"Error:\n{last_err}\n\nPrevious answer (fix it, return corrected JSON only):\n{raw[:20000]}"
            )
    raise LLMError(f"LLM did not return valid {model.__name__} JSON after {max_retries + 1} attempts: {last_err}")
