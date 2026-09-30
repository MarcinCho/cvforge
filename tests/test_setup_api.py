from fastapi.testclient import TestClient

from cvforge.api import create_app
from cvforge.config import Config, load_config


def client_for(tmp_path, **kw):
    cfg = Config(root=tmp_path)
    return TestClient(create_app(cfg), **kw), tmp_path


def test_first_run_setup_flow(tmp_path):
    c, root = client_for(tmp_path)
    st = c.get("/api/setup/status").json()
    assert st["has_config"] is False and st["candidates"] == []
    assert {p["id"] for p in st["presets"]} >= {"claude", "gemini", "codex", "ollama", "openai", "manual", "custom"}

    # test + save an LLM command (`cat` echoes the prompt, which contains "OK")
    r = c.post("/api/setup/llm/test", json={"provider": "command", "command": "cat"}).json()
    assert r["ok"] is True
    bad = c.post("/api/setup/llm/test", json={"provider": "command", "command": "no-such-llm-cli"}).json()
    assert bad["ok"] is False and "not found" in bad["error"]
    st = c.post("/api/setup/llm", json={"provider": "command", "command": "cat"}).json()
    assert st["has_config"] and (root / "cvforge.toml").exists()
    assert load_config(root / "cvforge.toml").llm.command == "cat"

    # candidate from template, edit source, defaults
    st = c.post("/api/candidates", json={"name": "anna"}).json()
    assert st["candidates"] == ["anna"] and st["default_candidate"] == "anna"
    src = c.get("/api/candidates/anna/source").json()["text"]
    assert "Source of Truth" in src
    assert c.put("/api/candidates/anna/source", json={"text": "# Anna\n"}).json()["saved"]
    assert (root / "candidates" / "anna" / "source_of_truth.md").read_text() == "# Anna\n"
    st = c.post("/api/setup/defaults", json={"default_template": "tech", "default_style": "concise"}).json()
    assert st["default_template"] == "tech"
    assert load_config(root / "cvforge.toml").default_style == "concise"
    assert c.get("/api/meta").json()["default_template"] == "tech"  # engine/config reloaded


def test_openai_key_is_stored_but_never_returned(tmp_path):
    c, root = client_for(tmp_path)
    st = c.post(
        "/api/setup/llm", json={"provider": "openai", "base_url": "http://x/v1", "model": "m", "api_key": "sk-secret"}
    ).json()
    assert st["llm"]["api_key_set"] and "sk-secret" not in str(st)
    # saving again without a key keeps it
    c.post("/api/setup/llm", json={"provider": "openai", "base_url": "http://x/v1", "model": "m2", "api_key": None})
    assert load_config(root / "cvforge.toml").llm.api_key == "sk-secret"


def test_validation_and_remote_block(tmp_path):
    c, _ = client_for(tmp_path)
    assert c.post("/api/candidates", json={"name": "Bad Name!"}).status_code == 400
    assert c.post("/api/setup/llm", json={"provider": "command", "command": " "}).status_code == 400
    remote = TestClient(create_app(Config(root=tmp_path)), client=("203.0.113.9", 5000))
    r = remote.post("/api/setup/llm", json={"provider": "command", "command": "rm -rf /"})
    assert r.status_code == 403


def test_config_file_is_owner_only(tmp_path):
    import stat

    c, root = client_for(tmp_path)
    (root / "cvforge.toml").write_text("# old\n")
    (root / "cvforge.toml").chmod(0o644)
    c.post("/api/setup/llm", json={"provider": "openai", "base_url": "http://x/v1", "model": "m", "api_key": "sk-1"})
    assert stat.S_IMODE((root / "cvforge.toml").stat().st_mode) == 0o600
