"""Profile + JobOffer + style -> TailoredCV, with grounding-guard feedback loop."""

from __future__ import annotations

import json
import re

from ..llm import LLMError, LLMProvider, ask_json
from ..models import CVExperience, JobOffer, Profile, TailoredCV, TailoredDraft
from ..prompts import render_prompt
from .guard import check_draft
from .ingest import redact_for_prompt
from .job import language_name
from .styles import Style

GDPR_EN = (
    "I hereby consent to the processing of my personal data by {company} for the purposes of the "
    "recruitment process for the position I am applying for."
)


class GroundingError(LLMError):
    def __init__(self, problems: list[str], draft: TailoredDraft):
        super().__init__("CV failed grounding checks:\n- " + "\n- ".join(problems))
        self.problems = problems
        self.draft = draft


def gdpr_clause(profile: Profile, job: JobOffer, language: str) -> str:
    in_poland = language == "pl" or re.search(
        r"pol(and|ska)|warszawa|krak|wroc|pozna|gda|katow|łódź|lodz|bielsko", job.location, re.I
    )
    if not in_poland:
        return ""
    company = job.company or ("firmę" if language == "pl" else "the company")
    if language == "pl" and profile.gdpr_clause:
        clause = re.sub(r"\[[^\]]*(firm|company)[^\]]*\]", company, profile.gdpr_clause, flags=re.I)
        return clause.strip(' "„”')
    return GDPR_EN.format(company=job.company or "the company")


def assemble(draft: TailoredDraft, profile: Profile, job: JobOffer, style: str, language: str) -> TailoredCV:
    exps = profile.experience_map()
    experience = []
    for e in draft.experience:
        src = exps[e.experience_id]
        experience.append(
            CVExperience(
                title=e.title,
                company=src.company,
                location=src.location,
                start=src.start,
                end=src.end,
                bullets=e.bullets,
            )
        )
    return TailoredCV(
        language=language,
        style=style,
        contact=profile.contact,
        headline=draft.headline,
        summary=draft.summary,
        experience=experience,
        projects=draft.projects,
        skills=draft.skills,
        education=draft.education,
        certifications=draft.certifications,
        languages=draft.languages,
        section_titles=draft.section_titles,
        target_keywords=draft.target_keywords,
        gdpr_clause=gdpr_clause(profile, job, language),
    )


def tailor(
    profile: Profile,
    job: JobOffer,
    style: Style,
    provider: LLMProvider,
    language: str | None = None,
    max_pages: int = 2,
    years_back: int = 12,
    max_retries: int = 2,
) -> TailoredCV:
    language = (language or job.language or "en").lower()
    base = dict(
        style=style,
        language=language,
        language_name=language_name(language),
        redactions=profile.redactions,
        unconfirmed=profile.unconfirmed_keywords,
        max_pages=max_pages,
        years_back=years_back,
        job_json=json.dumps(job.model_dump(exclude={"raw_text"}), ensure_ascii=False, indent=1),
        profile_json=redact_for_prompt(profile),
    )
    feedback: list[str] = []
    previous = ""
    draft: TailoredDraft | None = None
    for _ in range(max_retries + 1):
        prompt = render_prompt("tailor", feedback=feedback, previous=previous, **base)
        draft = ask_json(provider, prompt, TailoredDraft, max_retries)
        feedback = check_draft(draft, profile)
        if not feedback:
            return assemble(draft, profile, job, style.name, language)
        previous = draft.model_dump_json(indent=1)
    assert draft is not None
    raise GroundingError(feedback, draft)
