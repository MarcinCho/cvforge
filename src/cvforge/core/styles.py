"""Writing styles: YAML files with name/description/instructions, in user + built-in folders."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class Style(BaseModel):
    name: str
    description: str = ""
    instructions: str
    path: str = ""


def list_styles(dirs: list[Path]) -> dict[str, Style]:
    out: dict[str, Style] = {}
    for d in reversed(dirs):  # user dirs (first) override built-ins
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.y*ml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            data.setdefault("name", f.stem)
            out[data["name"]] = Style(**data, path=str(f))
    return out


def get_style(name: str, dirs: list[Path]) -> Style:
    styles = list_styles(dirs)
    if name not in styles:
        raise KeyError(f"unknown style {name!r}; available: {', '.join(styles)}")
    return styles[name]
