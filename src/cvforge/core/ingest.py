"""Source of truth (markdown) -> Profile.

Private notes are handled deterministically before anything reaches the LLM:
HTML comments are stripped, "do not include in CV" terms become redactions and
"unconfirmed" keyword lists become unconfirmed_keywords.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..llm import LLMProvider, ask_json
from ..models import Profile, ProfileDraft
from ..prompts import render_prompt

_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
_FORBID = re.compile(
    r"nie umieszcza|nie trafia do cv|nie wpisywa|do not include|don't include|not in (the )?cv|never in (the )?cv|keep out of (the )?cv",
    re.I,
)
_UNCONFIRMED_HEADING = re.compile(r"do potwierdzenia|nie używać|unconfirmed|do not use|don't use", re.I)
_PARENS = re.compile(r"\(([^()]{2,60})\)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_terms(s: str) -> list[str]:
    parts = re.split(r"[,;/]| i | and ", s)
    terms = [p.strip(" .*_`\"'„”") for p in parts]
    return [t for t in terms if t and not t.startswith("<")]  # skip template placeholders


def parse_private(text: str) -> tuple[str, list[str], list[str]]:
    """Return (text without comments, redactions, unconfirmed keywords)."""
    redactions: list[str] = []
    unconfirmed: list[str] = []

    # 1) comments / lines that say "do not put X in the CV": take the parenthesised names
    for chunk in [*_COMMENT.findall(text), *text.splitlines()]:
        if _FORBID.search(chunk):
            for inner in _PARENS.findall(chunk):
                redactions += [t for t in _split_terms(inner) if t[:1].isupper()]

    clean = _COMMENT.sub("", text)

    # 2) list items under headings like "... do potwierdzenia (NIE używać w CV ...)"
    # 3) explicit "## cvforge rules" section: "forbidden: a, b" / "unconfirmed: c, d"
    level_active: int | None = None
    mode = ""
    for line in clean.splitlines():
        if h := _HEADING.match(line.strip()):
            level, title = len(h.group(1)), h.group(2)
            if level_active is not None and level <= level_active:
                level_active, mode = None, ""
            if "cvforge rules" in title.lower():
                level_active, mode = level, "rules"
            elif _UNCONFIRMED_HEADING.search(title):
                level_active, mode = level, "unconfirmed"
            continue
        item = line.strip()
        if mode == "unconfirmed" and item.startswith(("-", "*")):
            unconfirmed += _split_terms(item.lstrip("-* "))
        elif mode == "rules":
            key, _, val = item.lstrip("-* ").partition(":")
            if key.strip().lower() in ("forbidden", "redact", "redactions", "never"):
                redactions += _split_terms(val)
            elif key.strip().lower() in ("unconfirmed", "unconfirmed_keywords"):
                unconfirmed += _split_terms(val)

    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean, _dedupe(redactions), _dedupe(unconfirmed)


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i and i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out


def ingest(
    source_path: Path, provider: LLMProvider, cache_path: Path | None = None, force: bool = False, max_retries: int = 2
) -> Profile:
    text = source_path.read_text(encoding="utf-8")
    digest = sha256(text)
    if cache_path and cache_path.exists() and not force:
        cached = Profile.model_validate_json(cache_path.read_text(encoding="utf-8"))
        if cached.source_hash == digest:
            return cached

    clean, redactions, unconfirmed = parse_private(text)
    for term in redactions:  # confidential names never reach the LLM or the cached profile text
        clean = re.sub(rf"(?<!\w){re.escape(term)}(?!\w)", "[REDACTED]", clean, flags=re.I)
    prompt = render_prompt("ingest", source=clean, redactions=redactions, unconfirmed=unconfirmed)
    draft = ask_json(provider, prompt, ProfileDraft, max_retries=max_retries)
    profile = Profile(**draft.model_dump(), source_hash=digest, source_text=clean)
    # deterministic findings always win over what the LLM kept or dropped
    profile.redactions = _dedupe(redactions + profile.redactions)
    profile.unconfirmed_keywords = _dedupe(unconfirmed + profile.unconfirmed_keywords)
    _assign_missing_ids(profile)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def _assign_missing_ids(profile: Profile) -> None:
    seen: set[str] = set()
    for i, exp in enumerate(profile.experience, 1):
        if not exp.id or exp.id in seen:
            exp.id = f"exp{i}"
        seen.add(exp.id)
        for j, b in enumerate(exp.bullets, 1):
            if not b.id or b.id in seen:
                b.id = f"{exp.id}.b{j}"
            seen.add(b.id)
    for i, proj in enumerate(profile.projects, 1):
        if not proj.id or proj.id in seen:
            proj.id = f"proj{i}"
        seen.add(proj.id)
        for j, b in enumerate(proj.bullets, 1):
            if not b.id or b.id in seen:
                b.id = f"{proj.id}.b{j}"
            seen.add(b.id)


def redact_for_prompt(profile: Profile) -> str:
    """Profile JSON for prompts: without the raw source text and with redacted terms masked."""
    data = profile.model_dump_json(exclude={"source_text", "source_hash"}, indent=1)
    for term in profile.redactions:
        data = re.sub(re.escape(term), "[REDACTED]", data, flags=re.I)
    return data
