"""Setup endpoints for the web UI: pick/test the LLM, create candidates, edit the source of truth.

These can change which command the server runs, so they only answer requests from this computer —
unless an API token is configured, in which case the normal token check applies.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from .config import PACKAGE_DIR, LLMConfig, load_config, save_config
from .core.render import list_templates
from .core.styles import list_styles
from .core.workspace import SOURCE_NAMES, list_candidates
from .llm import LLMError, make_provider

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
SOT_TEMPLATE = PACKAGE_DIR / "builtin" / "source_of_truth_template.md"

PRESETS = [
    {
        "id": "claude",
        "label": "Claude Code",
        "kind": "command",
        "command": "claude -p",
        "binary": "claude",
        "hint": "Uses your Claude subscription. Install Claude Code and run `claude` once to log in.",
    },
    {
        "id": "antigravity",
        "label": "Google Antigravity",
        "kind": "command",
        "command": "agy -p {prompt}",
        "binary": "agy",
        "hint": "Uses your Google account. Install Antigravity and run `agy` once to log in.",
    },
    {
        "id": "gemini",
        "label": "Gemini CLI",
        "kind": "command",
        "command": "gemini",
        "binary": "gemini",
        "hint": "Install @google/gemini-cli and log in once. If it complains about a trusted folder, "
        "set GEMINI_CLI_TRUST_WORKSPACE=true.",
    },
    {
        "id": "codex",
        "label": "OpenAI Codex CLI",
        "kind": "command",
        "command": "codex exec --skip-git-repo-check -",
        "binary": "codex",
        "hint": "Uses your ChatGPT/OpenAI account. Run `codex` once to log in.",
    },
    {
        "id": "ollama",
        "label": "Ollama (local, free)",
        "kind": "openai",
        "base_url": "http://localhost:11434/v1",
        "binary": "ollama",
        "hint": "Runs on your computer. Pick a model you have pulled (bigger = better CVs).",
    },
    {
        "id": "openai",
        "label": "API key (OpenAI, OpenRouter…)",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "hint": "Any OpenAI-compatible API. OpenRouter: https://openrouter.ai/api/v1 · LM Studio: http://localhost:1234/v1",
    },
    {
        "id": "manual",
        "label": "Copy & paste (any chat)",
        "kind": "manual",
        "hint": "No install: cvforge writes each prompt to a file, you paste it into ChatGPT/Claude/Gemini and save "
        "the answer next to it. Slow, but works for everyone.",
    },
    {
        "id": "custom",
        "label": "Other CLI",
        "kind": "command",
        "command": "",
        "hint": "Any command that reads the prompt on stdin and prints the answer. Use {prompt_file} or {prompt} "
        "if it needs the prompt as a file or argument.",
    },
]


class LLMIn(BaseModel):
    provider: str
    command: str = ""
    base_url: str = ""
    model: str = ""
    api_key: str | None = None  # None = keep the stored key
    manual_dir: str | None = None
    timeout_s: int | None = None


class CandidateIn(BaseModel):
    name: str
    source: str | None = None  # None → start from the template


class SourceIn(BaseModel):
    text: str


class DefaultsIn(BaseModel):
    default_candidate: str | None = None
    default_template: str | None = None
    default_style: str | None = None


def _ollama_models(base_url: str = "http://localhost:11434") -> list[str] | None:
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=1.5)
        return sorted(m["name"] for m in r.json().get("models", []))
    except Exception:
        return None


def _hint(error: str, cfg: LLMConfig) -> str:
    e = error.lower()
    tool = cfg.command.split()[0] if cfg.provider == "command" and cfg.command else ""
    if any(w in e for w in ("authenticat", "oauth", "log in", "login", "unauthorized", "401", "api key")):
        return f"\n→ Log in first: open a terminal and run `{tool}` once." if tool else "\n→ Check the API key."
    if any(w in e for w in ("credit", "quota", "billing", "rate limit", "429", "insufficient")):
        return "\n→ Your account is out of credits/quota. Top it up or pick another model."
    if "not found" in e and tool:
        return f"\n→ `{tool}` is not installed or not on PATH."
    if any(w in e for w in ("connection refused", "connecterror", "failed to establish")):
        return "\n→ Nothing is listening at that address. Is the server (e.g. Ollama) running?"
    if "timed out" in e:
        return "\n→ The model is too slow or waiting for input. Try again or pick a smaller model."
    return ""


def register_setup(app: FastAPI, S, api_dep) -> None:
    def local_only(request: Request) -> None:
        if os.environ.get(S.cfg.api.token_env):
            return  # the token dependency already authenticated the caller
        host = request.client.host if request.client else ""
        if host not in LOCAL_HOSTS:
            raise HTTPException(
                403,
                "Setup is only available on the computer running cvforge "
                f"(or set {S.cfg.api.token_env} to allow remote setup).",
            )

    guard = [api_dep, Depends(local_only)]

    def llm_config(body: LLMIn) -> LLMConfig:
        cur = S.cfg.llm.model_copy()
        cur.provider = body.provider
        if body.provider == "command":
            if not body.command.strip():
                raise HTTPException(400, "enter the command that runs your LLM CLI")
            cur.command = body.command.strip()
        elif body.provider == "openai":
            if not body.base_url.strip() or not body.model.strip():
                raise HTTPException(400, "base URL and model are required")
            cur.base_url, cur.model = body.base_url.strip(), body.model.strip()
            if body.api_key is not None:
                cur.api_key = body.api_key.strip()
        elif body.provider == "manual":
            if body.manual_dir:
                cur.manual_dir = str(S.cfg.resolve(Path(body.manual_dir)))
        else:
            raise HTTPException(400, f"unknown provider {body.provider!r}")
        if body.timeout_s:
            cur.timeout_s = body.timeout_s
        return cur

    def save(mutator) -> dict:
        cfg = S.cfg.model_copy(deep=True)
        mutator(cfg)
        path = save_config(cfg)
        S.reload(load_config(path))
        return status()

    @app.get("/api/setup/status", dependencies=guard)
    def status():
        cfg = S.cfg
        presets = []
        for p in PRESETS:
            p = dict(p)
            p["detected"] = bool(p.get("binary") and shutil.which(p["binary"]))
            if p["id"] == "ollama":
                models = _ollama_models()
                p["models"] = models or []
                p["detected"] = p["detected"] or models is not None
                p["running"] = models is not None
            presets.append(p)
        llm = cfg.llm.model_dump(exclude={"api_key"})
        llm["api_key_set"] = bool(cfg.llm.api_key or os.environ.get(cfg.llm.api_key_env))
        return {
            "config_path": str(cfg.path) if cfg.path else None,
            "has_config": bool(cfg.path and cfg.path.exists()),
            "candidates_dir": str(cfg.candidates_path),
            "candidates": list_candidates(cfg),
            "default_candidate": cfg.default_candidate,
            "default_template": cfg.default_template,
            "default_style": cfg.default_style,
            "templates": list(list_templates(cfg.template_dirs)),
            "styles": list(list_styles(cfg.style_dirs)),
            "llm": llm,
            "presets": presets,
        }

    @app.post("/api/setup/llm/test", dependencies=guard)
    def test_llm(body: LLMIn):
        cfg = llm_config(body)
        if cfg.provider == "manual":
            return {
                "ok": True,
                "answer": "",
                "seconds": 0,
                "note": f"Manual mode: prompts will appear in {cfg.manual_dir}. Nothing to test.",
            }
        cfg.timeout_s = min(cfg.timeout_s, 120)
        t0 = time.monotonic()
        try:
            answer = make_provider(cfg).complete("Reply with exactly the word: OK")
        except LLMError as e:
            return {"ok": False, "error": str(e) + _hint(str(e), cfg), "seconds": round(time.monotonic() - t0, 1)}
        ok = "ok" in answer.lower()[:200]
        return {
            "ok": ok,
            "answer": answer[:300],
            "seconds": round(time.monotonic() - t0, 1),
            "error": "" if ok else "The model answered, but not as expected — it may still work.",
        }

    @app.post("/api/setup/llm", dependencies=guard)
    def save_llm(body: LLMIn):
        new = llm_config(body)
        return save(lambda cfg: setattr(cfg, "llm", new))

    @app.post("/api/setup/defaults", dependencies=guard)
    def save_defaults(body: DefaultsIn):
        def apply(cfg):
            if body.default_candidate is not None:
                cfg.default_candidate = body.default_candidate
            if body.default_template:
                if body.default_template not in list_templates(cfg.template_dirs):
                    raise HTTPException(400, "unknown template")
                cfg.default_template = body.default_template
            if body.default_style:
                if body.default_style not in list_styles(cfg.style_dirs):
                    raise HTTPException(400, "unknown style")
                cfg.default_style = body.default_style

        return save(apply)

    @app.get("/api/setup/sot-template", dependencies=guard)
    def sot_template():
        return {"text": SOT_TEMPLATE.read_text(encoding="utf-8")}

    def source_path(name: str):
        if not NAME_RE.match(name):
            raise HTTPException(400, "candidate name: lowercase letters, digits, - and _ (max 40)")
        d = S.cfg.candidates_path / name
        for n in SOURCE_NAMES:
            if (d / n).exists():
                return d / n
        return d / SOURCE_NAMES[0]

    @app.post("/api/candidates", dependencies=guard)
    def create_candidate(body: CandidateIn):
        path = source_path(body.name)
        if path.exists():
            raise HTTPException(409, f"candidate {body.name!r} already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body.source if body.source else SOT_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        if not S.cfg.default_candidate or not S.cfg.path:
            return save(lambda cfg: setattr(cfg, "default_candidate", body.name))
        return status()

    @app.get("/api/candidates/{name}/source", dependencies=guard)
    def get_source(name: str):
        path = source_path(name)
        if not path.exists():
            raise HTTPException(404, "no source of truth yet")
        return {"name": name, "path": str(path.resolve()), "text": path.read_text(encoding="utf-8")}

    @app.put("/api/candidates/{name}/source", dependencies=guard)
    def put_source(name: str, body: SourceIn):
        path = source_path(name)
        if not path.parent.is_dir():
            raise HTTPException(404, f"candidate {name!r} not found")
        path.write_text(body.text, encoding="utf-8")  # writes through a symlink to the original file
        return {"saved": True, "path": str(path.resolve()), "chars": len(body.text)}
