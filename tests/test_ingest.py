import json

from cvforge.core.ingest import ingest, parse_private
from cvforge.llm.fake import FakeProvider

from .conftest import SOT, profile_dict


def test_parse_private_extracts_rules_and_strips_comments():
    clean, redactions, unconfirmed = parse_private(SOT)
    assert "<!--" not in clean and "Globex" not in clean
    assert "Globex" in redactions and "Acme Secret Client" in redactions
    assert {"EDR", "XDR", "ISO 27001", "incident response"} <= set(unconfirmed)


def test_ingest_merges_deterministic_rules_and_caches(tmp_path):
    src = tmp_path / "sot.md"
    src.write_text(SOT, encoding="utf-8")
    fake = FakeProvider([json.dumps(profile_dict())])
    cache = tmp_path / "profile.json"
    p = ingest(src, fake, cache)
    assert "Globex" in p.redactions and "ISO 27001" in p.unconfirmed_keywords
    assert "Globex" not in fake.prompts[0].split("<source_of_truth>")[1]  # private comment never sent
    # cached: no second LLM call
    assert ingest(src, FakeProvider([]), cache).source_hash == p.source_hash


def test_redacted_terms_masked_before_llm(tmp_path):
    src = tmp_path / "sot.md"
    src.write_text(SOT + "\nClients include Globex and others.\n", encoding="utf-8")
    fake = FakeProvider([json.dumps(profile_dict())])
    p = ingest(src, fake, None)
    body = fake.prompts[0].split("<source_of_truth>")[1]
    assert "Globex" not in body and "[REDACTED]" in body
    assert "Globex" not in p.source_text
