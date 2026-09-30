import json
from pathlib import Path

import pytest

from cvforge.config import Config
from cvforge.models import JobOffer, Profile

FIX = Path(__file__).parent / "fixtures"

SOT = """# Jan Kowalski — Source of Truth

## cvforge rules

- forbidden: Acme Secret Client

## 1. Contact
- Name: Jan Kowalski
- E-mail: jan@example.com

## 3. Experience

### IT Project Lead — RetailTech | 01/2025 – present

- Support for a key client — retail chain <!-- name (Globex) internal only — NIE umieszczać w CV -->
- Reached 80% MFA adoption in key tools (NIS2)
- Migrated 75 servers to Windows Server 2022 in 2 months

## 9. Keywords

### Security — do potwierdzenia (NIE używać w CV bez potwierdzenia)

- EDR/XDR, ISO 27001, incident response
"""


def profile_dict():
    return {
        "contact": {
            "name": "Jan Kowalski",
            "email": "jan@example.com",
            "phone": "+48 600 000 000",
            "location": "Kraków",
            "links": [],
        },
        "experience": [
            {
                "id": "exp1",
                "title": "IT Project Lead",
                "company": "RetailTech",
                "start": "01/2025",
                "end": "present",
                "stack": ["Okta", "PowerShell"],
                "bullets": [
                    {"id": "exp1.b1", "text": "Reached 80% MFA adoption in key tools (NIS2)"},
                    {"id": "exp1.b2", "text": "Migrated 75 servers to Windows Server 2022 in 2 months"},
                ],
            }
        ],
        "projects": [
            {
                "id": "proj1",
                "name": "Graylog SIEM",
                "bullets": [{"id": "proj1.b1", "text": "Deployed Graylog with dashboards"}],
            }
        ],
        "skills": [{"name": "Active Directory"}, {"name": "Okta"}, {"name": "PowerShell"}, {"name": "Python"}],
        "keywords": ["MFA", "NIS2", "IAM", "access management", "Windows Server"],
        "languages": [{"name": "English", "level": "C1"}],
        "redactions": [],
        "unconfirmed_keywords": [],
    }


def job_dict(**kw):
    d = {
        "title": "IT Security Specialist",
        "company": "Example SA",
        "location": "Kraków, Poland",
        "seniority": "mid",
        "language": "en",
        "must_have_keywords": ["Active Directory", "MFA", "PowerShell", "SIEM"],
        "nice_to_have_keywords": ["ISO 27001", "Terraform"],
        "requirements": ["3+ years in IT security"],
        "responsibilities": ["Manage IAM"],
    }
    d.update(kw)
    return d


def draft_dict(**kw):
    d = {
        "headline": "IT Security Specialist",
        "summary": "IT specialist who reached 80% MFA adoption and migrated 75 servers.",
        "experience": [
            {
                "experience_id": "exp1",
                "title": "IT Project Lead",
                "bullets": [
                    {"text": "Drove MFA adoption to 80% across key tools, supporting NIS2", "source_ids": ["exp1.b1"]},
                    {"text": "Migrated 75 servers to Windows Server 2022 within 2 months", "source_ids": ["exp1.b2"]},
                ],
            }
        ],
        "projects": [
            {
                "name": "Graylog SIEM",
                "bullets": [{"text": "Deployed Graylog SIEM dashboards", "source_ids": ["proj1.b1"]}],
            }
        ],
        "skills": [
            {"category": "Security", "items": ["Active Directory", "Okta", "MFA"]},
            {"category": "Automation", "items": ["PowerShell", "Python"]},
        ],
        "education": [],
        "certifications": [],
        "languages": ["English — C1"],
        "section_titles": {
            "summary": "Summary",
            "experience": "Experience",
            "projects": "Projects",
            "skills": "Skills",
            "education": "Education",
            "certifications": "Certifications",
            "languages": "Languages",
        },
        "target_keywords": ["MFA", "Active Directory", "PowerShell", "SIEM"],
    }
    d.update(kw)
    return d


@pytest.fixture
def profile() -> Profile:
    p = Profile(**profile_dict(), source_text=SOT)
    p.redactions = ["Globex", "Acme Secret Client"]
    p.unconfirmed_keywords = ["EDR", "XDR", "ISO 27001", "incident response"]
    return p


@pytest.fixture
def job() -> JobOffer:
    return JobOffer(**job_dict(), raw_text="offer text " * 20)


@pytest.fixture
def workspace_cfg(tmp_path) -> Config:
    cand = tmp_path / "candidates" / "jan"
    cand.mkdir(parents=True)
    (cand / "source_of_truth.md").write_text(SOT, encoding="utf-8")
    return Config(root=tmp_path, default_candidate="jan")


def as_json(d) -> str:
    return json.dumps(d)
