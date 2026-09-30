"""Text normalisation helpers shared by scoring, guard and checks."""

from __future__ import annotations

import re
import unicodedata

_THOUSANDS = re.compile(r"(?<=\d)[\s  ,.](?=\d{3}(?!\d))")
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("­", "").replace("‑", "-")
    return re.sub(r"\s+", " ", s).strip()


def fold(s: str) -> str:
    """norm() plus diacritics removal, for robust matching ("zarządzanie" ~ "zarzadzanie")."""
    s = norm(s).replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def numbers(s: str) -> set[str]:
    """Numbers in a text, with thousands separators removed ("3 000" -> "3000")."""
    s = _THOUSANDS.sub("", s)
    return {m.group(0).replace(",", ".") for m in _NUM.finditer(s)}


def contains_term(text: str, term: str) -> bool:
    """Whole-word, case/diacritics-insensitive containment."""
    t = fold(term)
    if not t:
        return False
    return re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", fold(text)) is not None
