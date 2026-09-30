"""HTTP API (for n8n and other automations) + the local web UI."""

from __future__ import annotations

import os
import secrets
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .config import PACKAGE_DIR, Config, load_config
from .core.pipeline import Engine, RunResult, Variant
from .core.render import get_template, list_templates, template_preview
from .core.styles import list_styles
from .core.workspace import list_candidates
from .llm import LLMError
from .models import InsightsReport, JobOffer, ScoreReport, TailoredCV


class AppState:
    """Config + engine, swappable at runtime when the setup page saves new settings."""

    def __init__(self, cfg: Config, engine: Engine | None = None):
        self.cfg = cfg
        self.engine = engine or Engine(cfg)

    def reload(self, cfg: Config) -> None:
        self.cfg = cfg
        self.engine = Engine(cfg)


class OfferIn(BaseModel):
    candidate: str | None = None
    offer: str | None = Field(None, description="Offer text or URL")
    job: JobOffer | None = Field(None, description="Already-parsed job (skips the analysis LLM call)")
    lang: str | None = Field(None, description="Output language; default = offer language")


class RunIn(OfferIn):
    styles: list[str] | None = None
    templates: list[str] | None = None
    insights: bool = True
    visual_review: bool = False
    min_score: int | None = None
    one_page: bool = False


class VariantIn(BaseModel):
    styles: list[str] | None = None
    templates: list[str] | None = None
    lang: str | None = None
    visual_review: bool = False
    one_page: bool = False


class RenderIn(BaseModel):
    candidate: str | None = None
    cv: TailoredCV
    templates: list[str] | None = None
    application: str | None = Field(None, description="Existing application folder to put the files in")
    visual_review: bool = False
    one_page: bool = False


class IngestIn(BaseModel):
    candidate: str | None = None
    force: bool = False


def _file_urls(r: RunResult, request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    prefix = f"{base}/files/{r.candidate}/{r.application}"
    return {
        "variants": [
            {
                "style": v.style,
                "template": v.template,
                "status": v.status,
                "pdf": f"{prefix}/{v.pdf}",
                "docx": f"{prefix}/{v.docx}",
                "previews": [f"{prefix}/previews/{p}" for p in v.previews],
            }
            for v in r.variants
        ],
        "insights_md": f"{prefix}/insights.md" if r.insights else None,
    }


def create_app(cfg: Config | None = None, engine: Engine | None = None) -> FastAPI:
    S = AppState(cfg or load_config(), engine)

    @asynccontextmanager
    async def lifespan(_app):
        # render template thumbnails in the background so the UI shows them instantly
        def work():
            for tpl in list_templates(S.cfg.template_dirs).values():
                try:
                    template_preview(tpl, S.cfg.root / ".cvforge-cache" / "previews")
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()
        yield

    app = FastAPI(
        title="cvforge",
        version="0.1.0",
        lifespan=lifespan,
        description="ATS-optimised, job-tailored CVs from a candidate's source of truth.",
    )

    def auth(request: Request) -> None:
        token = os.environ.get(S.cfg.api.token_env)
        if not token:
            return
        got = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.query_params.get(
            "token", ""
        )
        if not secrets.compare_digest(got, token):
            raise HTTPException(401, "missing or invalid bearer token")

    def guarded(fn):
        try:
            return fn()
        except (FileNotFoundError, KeyError) as e:
            raise HTTPException(404, str(e).strip("'\"")) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except LLMError as e:
            raise HTTPException(502, str(e)) from e

    api = Depends(auth)

    @app.get("/api/health")
    def health():
        return {"ok": True, "instance": S.cfg.instance_id}

    @app.get("/api/meta", dependencies=[api])
    def meta():
        return {
            "candidates": list_candidates(S.cfg),
            "default_candidate": S.cfg.default_candidate,
            "templates": [
                {"name": t.name, "description": t.description, "max_pages": t.max_pages, "ats_safe": t.ats_safe}
                for t in list_templates(S.cfg.template_dirs).values()
            ],
            "styles": [{"name": s.name, "description": s.description} for s in list_styles(S.cfg.style_dirs).values()],
            "default_template": S.cfg.default_template,
            "default_style": S.cfg.default_style,
            "vision": S.cfg.llm.provider == "openai" and S.cfg.llm.vision,
        }

    @app.get("/api/templates/{name}/preview.png", dependencies=[api])
    def preview(name: str):
        tpl = guarded(lambda: get_template(name, S.cfg.template_dirs))
        return FileResponse(template_preview(tpl, S.cfg.root / ".cvforge-cache" / "previews"), media_type="image/png")

    @app.post("/api/ingest", dependencies=[api])
    def ingest(body: IngestIn):
        p = guarded(lambda: S.engine.profile(S.engine.workspace(body.candidate), force=body.force))
        return {
            "roles": len(p.experience),
            "projects": len(p.projects),
            "skills": len(p.skills),
            "redactions": p.redactions,
            "unconfirmed_keywords": p.unconfirmed_keywords,
        }

    @app.post("/api/job", dependencies=[api], response_model=JobOffer)
    def job(body: OfferIn):
        if not body.offer:
            raise HTTPException(400, "offer is required")
        return guarded(lambda: S.engine.job(body.offer))

    @app.post("/api/score", dependencies=[api], response_model=ScoreReport)
    def score(body: OfferIn):
        def go():
            ws = S.engine.workspace(body.candidate)
            j = body.job or S.engine.job(body.offer or "")
            return S.engine.score(ws, j, body.lang)

        return guarded(go)

    @app.post("/api/insights", dependencies=[api], response_model=InsightsReport)
    def insights(body: OfferIn):
        def go():
            ws = S.engine.workspace(body.candidate)
            j = body.job or S.engine.job(body.offer or "")
            return S.engine.insights(ws, j, body.lang)

        return guarded(go)

    @app.post("/api/run", dependencies=[api])
    def run(body: RunIn, request: Request):
        """One-shot pipeline — the endpoint to call from n8n."""
        r = guarded(
            lambda: S.engine.run(
                S.engine.workspace(body.candidate),
                body.offer,
                job=body.job,
                styles=body.styles,
                templates=body.templates,
                lang=body.lang,
                with_insights=body.insights,
                visual=body.visual_review,
                min_score=body.min_score,
                one_page=body.one_page,
            )
        )
        return {**r.model_dump(mode="json"), "files": _file_urls(r, request)}

    @app.post("/api/render", dependencies=[api])
    def render(body: RenderIn):
        """Render a CV JSON written elsewhere (e.g. by an n8n AI agent). No LLM call."""

        def go() -> list[Variant]:
            ws = S.engine.workspace(body.candidate)
            return S.engine.render_external(
                ws, body.cv, body.templates, body.application, body.visual_review, body.one_page
            )

        variants = guarded(go)
        return {"variants": [v.model_dump(mode="json") for v in variants]}

    # ---- application-centric endpoints (used by the web UI, handy for step-by-step automations)

    @app.get("/api/applications/{candidate}", dependencies=[api])
    def applications(candidate: str):
        ws = guarded(lambda: S.engine.workspace(candidate))
        out = []
        for a in ws.list_applications():
            try:
                r = S.engine.load_application(ws, a)
                out.append(
                    {
                        "id": a,
                        "title": r.job.title,
                        "company": r.job.company,
                        "score": r.score.overall if r.score else None,
                        "variants": len(r.variants),
                    }
                )
            except Exception:
                continue
        return out

    @app.post("/api/applications", dependencies=[api])
    def create_application(body: OfferIn, request: Request):
        r = guarded(
            lambda: S.engine.create_application(S.engine.workspace(body.candidate), body.offer, body.job, body.lang)
        )
        return {**r.model_dump(mode="json"), "files": _file_urls(r, request)}

    @app.get("/api/applications/{candidate}/{app_id}", dependencies=[api])
    def get_application(candidate: str, app_id: str, request: Request):
        r = guarded(lambda: S.engine.load_application(S.engine.workspace(candidate), app_id))
        return {**r.model_dump(mode="json"), "files": _file_urls(r, request)}

    @app.post("/api/applications/{candidate}/{app_id}/variants", dependencies=[api])
    def add_variants(candidate: str, app_id: str, body: VariantIn, request: Request):
        r = guarded(
            lambda: S.engine.add_variants(
                S.engine.workspace(candidate),
                app_id,
                body.styles,
                body.templates,
                body.lang,
                body.visual_review,
                body.one_page,
            )
        )
        return {**r.model_dump(mode="json"), "files": _file_urls(r, request)}

    @app.post("/api/applications/{candidate}/{app_id}/insights", dependencies=[api])
    def add_insights(candidate: str, app_id: str, request: Request, body: VariantIn | None = None):
        r = guarded(lambda: S.engine.add_insights(S.engine.workspace(candidate), app_id, body.lang if body else None))
        return {**r.model_dump(mode="json"), "files": _file_urls(r, request)}

    @app.get("/files/{candidate}/{app_id}/{path:path}", dependencies=[api])
    def files(candidate: str, app_id: str, path: str):
        base = guarded(lambda: S.engine.workspace(candidate).application(app_id))
        f = (base / path).resolve()
        if base not in f.parents or not f.is_file():
            raise HTTPException(404, "file not found")
        return FileResponse(f, filename=f.name if f.suffix in (".pdf", ".docx", ".md") else None)

    from .setup_api import register_setup

    register_setup(app, S, api)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def ui():
        return (PACKAGE_DIR / "web" / "templates" / "index.html").read_text(encoding="utf-8")

    return app
