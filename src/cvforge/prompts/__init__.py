from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent), undefined=StrictUndefined, keep_trailing_newline=True
)


def render_prompt(name: str, **ctx) -> str:
    return _env.get_template(f"{name}.md.j2").render(**ctx)
