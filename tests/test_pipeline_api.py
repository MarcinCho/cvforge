import json

from fastapi.testclient import TestClient

from cvforge.api import create_app
from cvforge.core.pipeline import Engine
from cvforge.llm.fake import FakeProvider

from .conftest import draft_dict, job_dict, profile_dict

ASSESS = {
    "seniority_fit": 70,
    "domain_fit": 80,
    "requirements_fit": 70,
    "language_fit": 100,
    "strengths": ["MFA rollout"],
    "gaps": ["No SOC experience"],
    "summary": "Solid fit.",
}
INSIGHTS = {
    "related_titles": ["IAM Specialist"],
    "typical_requirements": [{"requirement": "SIEM", "candidate_has": True}],
    "upskilling": ["Security+"],
    "interview_topics": [{"topic": "MFA rollout", "story": "NIS2"}],
    "market_notes": ["General knowledge"],
}


def router(prompt: str) -> str:
    if "career-data extractor" in prompt:
        return json.dumps(profile_dict())
    if "Analyse the job offer" in prompt:
        return json.dumps(job_dict())
    if "Assess honestly" in prompt:
        return json.dumps(ASSESS)
    if "CV writer" in prompt:
        return json.dumps(draft_dict())
    if "career advisor" in prompt:
        return json.dumps(INSIGHTS)
    raise AssertionError(prompt[:200])


def test_full_run(workspace_cfg):
    engine = Engine(workspace_cfg, FakeProvider(router))
    ws = engine.workspace()
    r = engine.run(
        ws,
        "We are looking for an IT Security Specialist in Kraków. " * 5,
        styles=["impact", "concise"],
        templates=["ats-classic", "compact"],
    )
    assert r.score and r.score.overall > 0
    assert len(r.variants) == 4 and all(v.status == "pass" for v in r.variants), [
        (v.style, v.template, [i for c in v.checks.values() for i in c.items if i.status != "pass"]) for v in r.variants
    ]
    d = ws.application(r.application)
    assert (d / "insights.md").exists() and (d / "result.json").exists()
    # re-render with another template re-uses the tailored text (no new "CV writer" prompt)
    calls = len(engine.provider.prompts)
    engine.add_variants(ws, r.application, ["impact"], ["ats-modern"])
    assert len(engine.provider.prompts) == calls


def test_min_score_skips_generation(workspace_cfg):
    engine = Engine(workspace_cfg, FakeProvider(router))
    r = engine.run(engine.workspace(), "Offer text long enough to be parsed as an offer. " * 3, min_score=99)
    assert r.skipped_reason and not r.variants


def test_api_run_and_files(workspace_cfg, monkeypatch):
    monkeypatch.setenv("CVFORGE_TOKEN", "s3cret")
    engine = Engine(workspace_cfg, FakeProvider(router))
    client = TestClient(create_app(workspace_cfg, engine))
    assert client.post("/api/run", json={"offer": "x"}).status_code == 401
    h = {"Authorization": "Bearer s3cret"}
    r = client.post(
        "/api/run",
        headers=h,
        json={"offer": "IT Security Specialist offer text. " * 5, "templates": ["ats-modern"], "insights": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    pdf_url = body["files"]["variants"][0]["pdf"]
    f = client.get(pdf_url.replace("http://testserver", ""), headers=h)
    assert f.status_code == 200 and f.content.startswith(b"%PDF")
    assert client.get(f"/files/jan/{body['application']}/../../source_of_truth.md", headers=h).status_code == 404
    assert client.get("/", headers=h).status_code == 200


def test_api_render_external_cv_flags_redacted_terms(workspace_cfg):
    engine = Engine(workspace_cfg, FakeProvider(router))
    client = TestClient(create_app(workspace_cfg, engine))
    cv = json.loads((__import__("pathlib").Path(__file__).parent / "fixtures" / "sample_cv.json").read_text())
    cv["summary"] += " Worked for Globex."
    r = client.post("/api/render", json={"cv": cv, "templates": ["ats-classic"]})
    assert r.status_code == 200, r.text
    v = r.json()["variants"][0]
    assert v["status"] == "fail" and any(i["rule"] == "grounding" for i in v["checks"]["pdf"]["items"])


def test_one_page_variant(workspace_cfg):
    engine = Engine(workspace_cfg, FakeProvider(router))
    ws = engine.workspace()
    r = engine.run(
        ws,
        "IT Security Specialist offer text, long enough. " * 4,
        templates=["ats-modern"],
        with_insights=False,
        one_page=True,
    )
    v = r.variants[0]
    assert v.one_page and v.checks["pdf"].pages == 1 and "_1p_" in v.pdf
    assert any("ONE-PAGE CV" in p for p in engine.provider.prompts)
    assert any(i.rule == "one_page_fit" for i in v.checks["pdf"].items)
