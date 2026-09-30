import json

import pytest

from cvforge.core.guard import check_draft
from cvforge.core.score import keyword_coverage, score
from cvforge.core.styles import Style
from cvforge.core.tailor import GroundingError, tailor
from cvforge.llm.fake import FakeProvider
from cvforge.models import TailoredDraft

from .conftest import draft_dict

STYLE = Style(name="impact", instructions="results first")


def test_valid_draft_passes(profile):
    assert check_draft(TailoredDraft(**draft_dict()), profile) == []


def test_guard_rejects_invented_number(profile):
    d = draft_dict()
    d["experience"][0]["bullets"][0]["text"] = "Drove MFA adoption to 95% across 40 tools"
    problems = check_draft(TailoredDraft(**d), profile)
    assert any("95" in p for p in problems)


def test_guard_rejects_redacted_and_unconfirmed_terms(profile):
    d = draft_dict(summary="Supported Globex stores; ISO 27001 expert.")
    problems = " ".join(check_draft(TailoredDraft(**d), profile))
    assert "Globex" in problems and "ISO 27001" in problems


def test_guard_rejects_unknown_ids_and_skills(profile):
    d = draft_dict()
    d["experience"][0]["bullets"][0]["source_ids"] = ["exp9.b1"]
    d["skills"][0]["items"].append("Kubernetes")
    problems = " ".join(check_draft(TailoredDraft(**d), profile))
    assert "exp9.b1" in problems and "Kubernetes" in problems


def test_tailor_retries_with_feedback_then_succeeds(profile, job):
    bad = draft_dict(summary="Led 500 engineers at Globex.")
    fake = FakeProvider([json.dumps(bad), json.dumps(draft_dict())])
    cv = tailor(profile, job, STYLE, fake, max_retries=2)
    assert "Fix these problems" in fake.prompts[1] and "Globex" in fake.prompts[1]
    assert cv.experience[0].company == "RetailTech" and cv.experience[0].start == "01/2025"
    assert "Example SA" in cv.gdpr_clause  # job in Poland → consent clause


def test_tailor_gives_up_with_report(profile, job):
    bad = json.dumps(draft_dict(summary="Led 500 engineers."))
    with pytest.raises(GroundingError) as e:
        tailor(profile, job, STYLE, FakeProvider([bad] * 3), max_retries=2)
    assert any("500" in p for p in e.value.problems)


def test_keyword_coverage(profile, job):
    ratio, matched, missing, unconfirmed = keyword_coverage(job, profile)
    assert {"Active Directory", "MFA", "PowerShell", "SIEM"} <= set(matched)  # SIEM via Graylog synonym
    assert "Terraform" in missing and "ISO 27001" in unconfirmed
    assert ratio == pytest.approx(0.7 * 1.0 + 0.3 * 0.0)


def test_score_combines_keywords_and_llm(profile, job):
    fake = FakeProvider(
        [
            json.dumps(
                {
                    "seniority_fit": 70,
                    "domain_fit": 80,
                    "requirements_fit": 60,
                    "language_fit": 100,
                    "strengths": ["MFA"],
                    "gaps": ["SOC"],
                    "summary": "ok",
                }
            )
        ]
    )
    s = score(job, profile, fake)
    assert s.keyword_score == 70
    assert s.llm_score == round(0.25 * 70 + 0.25 * 80 + 0.4 * 60 + 0.1 * 100)
    assert s.overall == round(0.4 * 70 + 0.6 * s.llm_score)
    assert "Globex" not in fake.prompts[0]


def test_keyword_matching_is_directional_and_ignores_plans(profile, job):
    profile.source_text += "\n- Planowany certyfikat po studiach: CompTIA Security+\n- Angielski — C1\n"
    job.must_have_keywords = ["SIEM", "zarządzanie uprawnieniami", "angielski B2", "SSO"]
    job.nice_to_have_keywords = ["Splunk", "CompTIA Security+"]
    _, matched, missing, _ = keyword_coverage(job, profile)
    assert {"SIEM", "zarządzanie uprawnieniami", "angielski B2", "SSO"} <= set(matched)
    assert {"Splunk", "CompTIA Security+"} <= set(missing)
