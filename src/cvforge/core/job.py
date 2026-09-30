"""Job offer (text / file / URL) -> JobOffer."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import httpx
from langdetect import DetectorFactory, detect

from ..llm import LLMProvider, ask_json
from ..models import JobOffer
from ..prompts import render_prompt

DetectorFactory.seed = 0

LANGUAGE_NAMES = {
    "pl": "Polish",
    "en": "English",
    "de": "German",
    "no": "Norwegian",
    "nb": "Norwegian",
    "sv": "Swedish",
    "da": "Danish",
    "cs": "Czech",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "nl": "Dutch",
    "uk": "Ukrainian",
    "pt": "Portuguese",
    "fi": "Finnish",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


def html_to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr|section)>", "\n", page)
    page = re.sub(r"(?i)<li[^>]*>", "\n- ", page)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html.unescape(page)
    page = re.sub(r"[ \t ]+", " ", page)
    return re.sub(r"\n\s*\n+", "\n\n", page).strip()


def read_offer(source: str) -> str:
    """source: '-' (stdin), a URL, a file path, or the offer text itself."""
    if source == "-":
        return sys.stdin.read()
    if re.match(r"https?://", source.strip()):
        r = httpx.get(
            source.strip(),
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (cvforge job fetcher)"},
        )
        r.raise_for_status()
        return html_to_text(r.text) if "html" in r.headers.get("content-type", "html") else r.text
    p = Path(source)
    if len(source) < 400 and p.exists():
        text = p.read_text(encoding="utf-8")
        return html_to_text(text) if p.suffix.lower() in (".html", ".htm") else text
    return source


def detect_language(text: str) -> str:
    try:
        return detect(text[:5000])
    except Exception:
        return "en"


def parse_job(offer_text: str, provider: LLMProvider, max_retries: int = 2) -> JobOffer:
    offer_text = offer_text.strip()
    if len(offer_text) < 80:
        raise ValueError("job offer text is too short — pass the full offer text, a file or a URL")
    job = ask_json(provider, render_prompt("parse_job", offer=offer_text[:30000]), JobOffer, max_retries)
    job.raw_text = offer_text
    if not job.language or len(job.language) > 3:
        job.language = detect_language(offer_text)
    job.language = job.language.lower()
    return job
