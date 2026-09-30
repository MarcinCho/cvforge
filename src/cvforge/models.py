"""Data models shared by every cvforge step. Each step reads/writes one of these as JSON."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field

# ---------------------------------------------------------------- profile (source of truth)


class Contact(BaseModel):
    name: str
    location: str = ""
    phone: str = ""
    email: str = ""
    links: list[str] = Field(default_factory=list, description="LinkedIn, GitHub, portfolio URLs")


class Bullet(BaseModel):
    id: str = Field(description="Stable id, e.g. 'exp1.b3' or 'proj2.b1'")
    text: str


class Experience(BaseModel):
    id: str = Field(description="Stable id, e.g. 'exp1'")
    title: str
    company: str
    location: str = ""
    start: str = Field(description="MM/YYYY")
    end: str = Field(description="MM/YYYY or 'present'")
    context: str = ""
    stack: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    bullets: list[Bullet] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    category: str = ""
    level: str = ""
    last_used: str = ""


class Education(BaseModel):
    degree: str
    institution: str
    start: str = ""
    end: str = ""
    notes: str = ""


class Certification(BaseModel):
    name: str
    date: str = ""


class Language(BaseModel):
    name: str
    level: str


class Story(BaseModel):
    title: str
    text: str


class ProfileDraft(BaseModel):
    """What the LLM extracts from the source-of-truth markdown."""

    contact: Contact
    positioning: dict[str, str] = Field(
        default_factory=dict, description="Target-role variant name -> positioning summary"
    )
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    keywords: list[str] = Field(
        default_factory=list,
        description="Confirmed ATS keywords, in the source language AND English equivalents",
    )
    stories: list[Story] = Field(default_factory=list, description="STAR / interview stories")
    gdpr_clause: str = Field("", description="Data-processing consent clause if present")
    redactions: list[str] = Field(
        default_factory=list, description="Terms the candidate says must never appear in a CV"
    )
    unconfirmed_keywords: list[str] = Field(
        default_factory=list, description="Keywords the candidate has not confirmed; never use"
    )


class Profile(ProfileDraft):
    source_hash: str = ""
    source_text: str = Field("", description="Source of truth with private comments stripped")

    def bullet_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for exp in self.experience:
            for b in exp.bullets:
                out[b.id] = b.text
        for proj in self.projects:
            for b in proj.bullets:
                out[b.id] = b.text
        return out

    def experience_map(self) -> dict[str, Experience]:
        return {e.id: e for e in self.experience}


# ---------------------------------------------------------------- job offer


class JobOffer(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    seniority: str = ""
    language: str = Field(description="ISO 639-1 code of the offer text, e.g. 'pl', 'en'")
    must_have_keywords: list[str] = Field(
        default_factory=list, description="Short (1-4 word) required skills/technologies"
    )
    nice_to_have_keywords: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list, description="Requirement sentences")
    responsibilities: list[str] = Field(default_factory=list)
    raw_text: str = ""


# ---------------------------------------------------------------- score


class LLMAssessment(BaseModel):
    seniority_fit: int = Field(ge=0, le=100)
    domain_fit: int = Field(ge=0, le=100)
    requirements_fit: int = Field(ge=0, le=100)
    language_fit: int = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    summary: str = ""


Recommendation = Literal["apply", "apply_with_notes", "stretch", "skip"]


class ScoreReport(BaseModel):
    overall: int
    keyword_score: int
    llm_score: int
    breakdown: dict[str, int]
    matched_keywords: list[str]
    missing_keywords: list[str]
    unconfirmed_matches: list[str] = Field(
        default_factory=list,
        description="Job keywords the candidate may have but has not confirmed in the SoT",
    )
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendation: Recommendation
    summary: str = ""


# ---------------------------------------------------------------- tailored CV


class CVBullet(BaseModel):
    text: str
    source_ids: list[str] = Field(description="Profile bullet ids this bullet is based on")


class CVExperienceDraft(BaseModel):
    experience_id: str = Field(description="Profile experience id")
    title: str = Field(description="Job title, may be translated to the CV language")
    bullets: list[CVBullet] = Field(default_factory=list)


class CVProjectDraft(BaseModel):
    name: str
    bullets: list[CVBullet] = Field(default_factory=list)


class SkillGroup(BaseModel):
    category: str
    items: list[str]


class CVEducation(BaseModel):
    degree: str
    institution: str
    start: str = ""
    end: str = ""
    notes: str = ""


class SectionTitles(BaseModel):
    summary: str
    experience: str
    projects: str
    skills: str
    education: str
    certifications: str
    languages: str


class TailoredDraft(BaseModel):
    """What the LLM returns when tailoring. Contact data and dates are filled in by code."""

    headline: str = Field(description="Target role title shown under the name")
    summary: str
    experience: list[CVExperienceDraft]
    projects: list[CVProjectDraft] = Field(default_factory=list)
    skills: list[SkillGroup]
    education: list[CVEducation] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list, description="e.g. 'English — C1'")
    section_titles: SectionTitles
    target_keywords: list[str] = Field(default_factory=list, description="Job keywords used verbatim in this CV")


class CVExperience(BaseModel):
    title: str
    company: str
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[CVBullet] = Field(default_factory=list)


class TailoredCV(BaseModel):
    language: str
    style: str
    contact: Contact
    headline: str
    summary: str
    experience: list[CVExperience]
    projects: list[CVProjectDraft] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    education: list[CVEducation] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    section_titles: SectionTitles
    target_keywords: list[str] = Field(default_factory=list)
    gdpr_clause: str = ""


# ---------------------------------------------------------------- checks


CheckStatus = Literal["pass", "warn", "fail"]


class CheckItem(BaseModel):
    rule: str
    status: CheckStatus
    detail: str = ""


class CheckReport(BaseModel):
    file: str
    items: list[CheckItem] = Field(default_factory=list)
    pages: int = 0
    previews: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def status(self) -> CheckStatus:
        states = {i.status for i in self.items}
        return "fail" if "fail" in states else "warn" if "warn" in states else "pass"

    def add(self, rule: str, status: CheckStatus, detail: str = "") -> None:
        self.items.append(CheckItem(rule=rule, status=status, detail=detail))


class VisualReview(BaseModel):
    issues: list[str] = Field(default_factory=list)
    verdict: Literal["ok", "minor_issues", "major_issues"]


# ---------------------------------------------------------------- insights


class RequirementFit(BaseModel):
    requirement: str
    candidate_has: bool
    note: str = ""


class InterviewTopic(BaseModel):
    topic: str
    story: str = Field("", description="Which candidate story/experience to use")


class InsightsReport(BaseModel):
    related_titles: list[str]
    typical_requirements: list[RequirementFit]
    upskilling: list[str]
    interview_topics: list[InterviewTopic]
    market_notes: list[str] = Field(default_factory=list)
