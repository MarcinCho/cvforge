"""Grounding guard: rejects tailored CVs that invent facts or leak private terms."""

from __future__ import annotations

from rapidfuzz import fuzz

from ..models import Profile, TailoredCV, TailoredDraft
from .text import contains_term, fold, numbers

# numbers that are never "facts" (list markers, "1 page", C1/B2 levels are letters+digits and caught by the source)
_TRIVIAL = {"0", "1"}


def _profile_skill_corpus(profile: Profile) -> list[str]:
    items = [s.name for s in profile.skills] + profile.keywords
    for exp in profile.experience:
        items += exp.stack
    return items


def check_draft(draft: TailoredDraft, profile: Profile) -> list[str]:
    problems: list[str] = []
    bullets = profile.bullet_map()
    exps = profile.experience_map()
    source_all = profile.source_text + "\n" + profile.model_dump_json(exclude={"source_text"})
    source_nums = numbers(source_all)

    for e in draft.experience:
        if e.experience_id not in exps:
            problems.append(f"experience_id {e.experience_id!r} does not exist in the profile")
    for kind, groups in (
        ("experience", [(e.experience_id, e.bullets) for e in draft.experience]),
        ("project", [(p.name, p.bullets) for p in draft.projects]),
    ):
        for owner, bl in groups:
            for b in bl:
                ids = [i for i in b.source_ids if i in bullets]
                bad = [i for i in b.source_ids if i not in bullets]
                if bad:
                    problems.append(f"{kind} {owner!r}: unknown source_ids {bad} in bullet {b.text[:60]!r}")
                if not ids:
                    problems.append(f"{kind} {owner!r}: bullet has no valid source_ids: {b.text[:80]!r}")
                    continue
                allowed = numbers(" ".join(bullets[i] for i in ids))
                if kind == "experience":
                    # facts from the same role (other bullets, context line) may be combined
                    allowed |= numbers(role_text(profile, owner))
                extra = numbers(b.text) - allowed - _TRIVIAL
                if extra:
                    problems.append(
                        f"{kind} {owner!r}: numbers {sorted(extra)} not found in cited sources {ids}: {b.text[:80]!r}"
                    )

    extra = numbers(draft.summary + " " + draft.headline) - source_nums - _TRIVIAL
    if extra:
        problems.append(f"summary/headline: numbers {sorted(extra)} do not appear anywhere in the profile")

    corpus = _profile_skill_corpus(profile)
    folded_source = fold(profile.source_text)
    for g in draft.skills:
        for item in g.items:
            f = fold(item)
            if f in folded_source or any(fuzz.token_set_ratio(f, fold(c)) >= 88 for c in corpus):
                continue
            problems.append(f"skill {item!r} is not in the profile")

    problems += check_terms(draft.model_dump_json(), profile)
    return problems


def role_text(profile: Profile, exp_id: str) -> str:
    e = profile.experience_map().get(exp_id)
    if not e:
        return ""
    return " ".join([e.title, e.context, *e.stack, *(b.text for b in e.bullets)])


def check_terms(text: str, profile: Profile) -> list[str]:
    problems = []
    for term in profile.redactions:
        if contains_term(text, term):
            problems.append(f"forbidden term {term!r} appears in the CV — remove it")
    for term in profile.unconfirmed_keywords:
        if contains_term(text, term):
            problems.append(f"unconfirmed keyword {term!r} appears in the CV — remove it or rephrase without it")
    return problems


def check_cv(cv: TailoredCV, profile: Profile) -> list[str]:
    """Final safety net on a fully assembled (or externally supplied) CV."""
    return check_terms(cv.model_dump_json(exclude={"contact"}), profile)
