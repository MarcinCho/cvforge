"""Hybrid job-fit score: deterministic keyword coverage + calibrated LLM rubric."""

from __future__ import annotations

import json
import re

from rapidfuzz import fuzz

from ..llm import LLMProvider, ask_json
from ..models import JobOffer, LLMAssessment, Profile, ScoreReport
from ..prompts import render_prompt
from .ingest import redact_for_prompt
from .job import language_name
from .text import contains_term, fold

KEYWORD_WEIGHT = 0.4  # rest is the LLM rubric
MUST_WEIGHT = 0.7

# Equivalent names (folded forms): any member proves any other member.
SYNONYMS: list[set[str]] = [
    {"active directory", "ad", "ms active directory"},
    {"azure ad", "entra id", "microsoft entra id", "microsoft entra", "azure active directory"},
    {
        "iam",
        "identity and access management",
        "access management",
        "zarzadzanie dostepami",
        "zarzadzanie tozsamoscia",
        "zarzadzanie uprawnieniami",
        "zarzadzanie tozsamoscia i dostepami",
    },
    {"mfa", "multi-factor authentication", "2fa", "uwierzytelnianie wieloskladnikowe"},
    {"itsm", "it service management"},
    {"windows server", "ms windows server"},
    {"project management", "zarzadzanie projektami"},
    {"english", "angielski", "jezyk angielski"},
    {"polish", "polski", "jezyk polski"},
    {"norwegian", "norweski", "jezyk norweski"},
    {"german", "niemiecki", "jezyk niemiecki"},
    {"automation", "automatyzacja", "automatyzacja procesow", "process automation"},
    {"virtualization", "wirtualizacja"},
    {"containerization", "konteneryzacja", "containers", "kontenery"},
    {"rollout", "wdrozenia", "wdrozenie", "deployment", "implementation"},
    {"backup", "kopie zapasowe", "backupy"},
    {"disaster recovery", "odtwarzanie po awarii", "dr"},
    {"nis2", "nis 2", "dyrektywa nis2"},
]
# Generic concept -> specific evidence. A specific tool proves the concept, never the other way round
# (Graylog proves "SIEM", but "SIEM" does not prove "Splunk").
EVIDENCE: dict[str, set[str]] = {
    "siem": {"graylog", "splunk", "sentinel", "microsoft sentinel", "wazuh", "qradar", "elastic siem"},
    "sso": {"okta", "entra id", "azure ad", "saml", "oauth"},
    "itsm": {"servicenow", "easyredmine", "jira service management", "service desk", "ticketing"},
    "virtualization": {"proxmox", "vmware", "hyper-v", "esxi"},
    "wirtualizacja": {"proxmox", "vmware", "hyper-v", "esxi"},
    "containerization": {"docker", "kubernetes", "podman"},
    "konteneryzacja": {"docker", "kubernetes", "podman"},
    "firewall": {"fortigate", "palo alto", "checkpoint", "pfsense"},
    "scripting": {"powershell", "python", "bash"},
    "linux": {"ubuntu", "debian", "rhel", "centos"},
    "cloud": {"aws", "azure", "gcp", "cloudflare"},
    "chmura": {"aws", "azure", "gcp", "cloudflare"},
}
CEFR = re.compile(r"\b(?:[abc][12]|native|ojczysty)\b|\(.*?\)|\bmin\.?\s*|\bna poziomie\b|\bpoziom\b", re.I)
# lines about plans/wishes are not evidence of a skill
NOT_EVIDENCE = re.compile(
    r"planowan|planned|w planach|plan to|chc[eę] si[eę] nauczy|do potwierdzenia|to confirm|"
    r"nie używać|not confirmed|unconfirmed",
    re.I,
)


def _expand(term: str) -> set[str]:
    t = fold(term)
    stripped = re.sub(r"\s+", " ", CEFR.sub(" ", t)).strip()
    out = {t, stripped} - {""}
    for group in SYNONYMS:
        if out & group:
            out |= group
    for concept, evidence in EVIDENCE.items():
        if concept in out:
            out |= evidence
    return out


def keyword_match(term: str, corpus: str, entries: list[str]) -> bool:
    for variant in _expand(term):
        if contains_term(corpus, variant):
            return True
        if len(variant) >= 5 and any(fuzz.token_set_ratio(variant, fold(e)) >= 90 for e in entries):
            return True
    return False


def evidence_text(profile: Profile) -> str:
    lines = [ln for ln in profile.source_text.splitlines() if not NOT_EVIDENCE.search(ln)]
    return "\n".join(lines)


def keyword_coverage(job: JobOffer, profile: Profile) -> tuple[float, list[str], list[str], list[str]]:
    entries = [s.name for s in profile.skills] + profile.keywords
    for exp in profile.experience:
        entries += exp.stack
    entries += [p.name for p in profile.projects]
    corpus = " \n ".join(entries + list(profile.bullet_map().values())) + "\n" + evidence_text(profile)
    for term in profile.redactions:
        corpus = corpus.replace(term, " ")

    def is_unconfirmed(t: str) -> bool:
        return any(keyword_match(t, u, [u]) for u in profile.unconfirmed_keywords)

    def cover(terms: list[str]) -> tuple[float, list[str], list[str]]:
        # unconfirmed skills never count as matches, even if the source mentions them
        hit = [t for t in terms if not is_unconfirmed(t) and keyword_match(t, corpus, entries)]
        miss = [t for t in terms if t not in hit]
        return (len(hit) / len(terms) if terms else 1.0), hit, miss

    must_ratio, must_hit, must_miss = cover(job.must_have_keywords)
    nice_ratio, nice_hit, nice_miss = cover(job.nice_to_have_keywords)
    weight = MUST_WEIGHT if job.nice_to_have_keywords else 1.0
    ratio = weight * must_ratio + (1 - weight) * nice_ratio
    missing = must_miss + nice_miss
    unconfirmed = [t for t in missing if is_unconfirmed(t)]
    return ratio, must_hit + nice_hit, missing, unconfirmed


def recommend(overall: int) -> str:
    if overall >= 75:
        return "apply"
    if overall >= 60:
        return "apply_with_notes"
    if overall >= 45:
        return "stretch"
    return "skip"


def score(
    job: JobOffer, profile: Profile, provider: LLMProvider, out_language: str = "en", max_retries: int = 2
) -> ScoreReport:
    ratio, matched, missing, unconfirmed = keyword_coverage(job, profile)
    kw = round(ratio * 100)
    prompt = render_prompt(
        "score",
        profile=profile,
        profile_json=redact_for_prompt(profile),
        job_json=json.dumps(job.model_dump(exclude={"raw_text"}), ensure_ascii=False, indent=1),
        out_language=language_name(out_language),
    )
    a = ask_json(provider, prompt, LLMAssessment, max_retries)
    breakdown = {
        "keywords": kw,
        "seniority": a.seniority_fit,
        "domain": a.domain_fit,
        "requirements": a.requirements_fit,
        "language": a.language_fit,
    }
    llm = round(0.25 * a.seniority_fit + 0.25 * a.domain_fit + 0.4 * a.requirements_fit + 0.1 * a.language_fit)
    overall = round(KEYWORD_WEIGHT * kw + (1 - KEYWORD_WEIGHT) * llm)
    return ScoreReport(
        overall=overall,
        keyword_score=kw,
        llm_score=llm,
        breakdown=breakdown,
        matched_keywords=matched,
        missing_keywords=missing,
        unconfirmed_matches=unconfirmed,
        strengths=a.strengths,
        gaps=a.gaps,
        recommendation=recommend(overall),
        summary=a.summary,
    )
