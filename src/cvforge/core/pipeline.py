"""The Engine: one entry point used by the CLI, the HTTP API and the web UI."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel, Field

from ..config import Config
from ..llm import LLMProvider, make_provider
from ..models import CheckReport, InsightsReport, JobOffer, Profile, ScoreReport, TailoredCV
from . import check as checks
from .guard import check_cv
from .ingest import ingest
from .insights import insights, insights_markdown
from .job import parse_job, read_offer
from .render import Template, fit_to_pages, get_template, render_docx, render_pdf
from .score import score
from .styles import get_style
from .tailor import tailor
from .workspace import Workspace, slug


class Variant(BaseModel):
    style: str
    template: str
    cv_json: str
    pdf: str
    docx: str
    status: str
    checks: dict[str, CheckReport]
    previews: list[str] = Field(default_factory=list)
    one_page: bool = False
    removed: list[str] = Field(default_factory=list, description="Content dropped to fit the page target")


class RunResult(BaseModel):
    candidate: str
    application: str
    dir: str
    job: JobOffer
    score: ScoreReport | None = None
    variants: list[Variant] = Field(default_factory=list)
    insights: InsightsReport | None = None
    skipped_reason: str = ""
    errors: list[str] = Field(default_factory=list)


def _write(path: Path, model: BaseModel) -> None:
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


class Engine:
    def __init__(self, cfg: Config, provider: LLMProvider | None = None):
        self.cfg = cfg
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = make_provider(self.cfg.llm)
        return self._provider

    @property
    def retries(self) -> int:
        return self.cfg.llm.max_retries

    # ------------------------------------------------------------ single steps

    def workspace(self, candidate: str | None = None) -> Workspace:
        return Workspace(self.cfg, candidate)

    def profile(self, ws: Workspace, force: bool = False) -> Profile:
        return ingest(ws.source_path, self.provider, ws.profile_cache, force=force, max_retries=self.retries)

    def job(self, offer: str) -> JobOffer:
        return parse_job(read_offer(offer), self.provider, self.retries)

    def score(self, ws: Workspace, job: JobOffer, lang: str | None = None) -> ScoreReport:
        return score(job, self.profile(ws), self.provider, lang or job.language, self.retries)

    def template(self, name: str | None = None) -> Template:
        return get_template(name or self.cfg.default_template, self.cfg.template_dirs)

    def insights(self, ws: Workspace, job: JobOffer, lang: str | None = None) -> InsightsReport:
        return insights(job, self.profile(ws), self.provider, lang or job.language, self.retries)

    def render(
        self,
        cv: TailoredCV,
        template: str | None,
        out_dir: Path,
        basename: str,
        visual: bool = False,
        profile: Profile | None = None,
        one_page: bool = False,
    ) -> Variant:
        tpl = self.template(template)
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf, docx = out_dir / f"{basename}.pdf", out_dir / f"{basename}.docx"
        cv_json = out_dir / f"{basename}.json"
        removed: list[str] = []
        if one_page:
            tpl = tpl.model_copy(update={"max_pages": 1})
            cv, layout, removed = fit_to_pages(cv, tpl, pdf)
        else:
            layout = render_pdf(cv, tpl, pdf)
        _write(cv_json, cv)  # exactly what was rendered (after any one-page trimming)
        render_docx(cv, tpl, docx)
        pdf_report = checks.check_pdf(pdf, cv, tpl, layout, previews_dir=out_dir / "previews")
        docx_report = checks.check_docx(docx, cv)
        if one_page:
            pdf_report.add(
                "one_page_fit",
                "pass" if not removed else "warn",
                "fits on one page without cuts" if not removed else "to fit one page, removed: " + "; ".join(removed),
            )
        if profile is not None:  # safety net for CVs that did not come from our tailor step
            for problem in check_cv(cv, profile):
                pdf_report.add("grounding", "fail", problem)
        if visual:
            previews = [out_dir / "previews" / p for p in pdf_report.previews]
            checks.merge_visual(pdf_report, checks.visual_review(previews, self.provider))
        _write(
            out_dir / f"{basename}.check.json",
            CheckReport(
                file=basename,
                items=pdf_report.items + docx_report.items,
                pages=pdf_report.pages,
                previews=pdf_report.previews,
            ),
        )
        worst = {"pass": 0, "warn": 1, "fail": 2}
        status = max(pdf_report.status, docx_report.status, key=worst.get)
        return Variant(
            style=cv.style,
            template=tpl.name,
            cv_json=cv_json.name,
            pdf=pdf.name,
            docx=docx.name,
            status=status,
            checks={"pdf": pdf_report, "docx": docx_report},
            previews=pdf_report.previews,
            one_page=one_page,
            removed=removed,
        )

    # ------------------------------------------------------------ applications (step by step)

    def create_application(
        self, ws: Workspace, offer: str | None = None, job: JobOffer | None = None, lang: str | None = None
    ) -> RunResult:
        """Parse the offer, score it and create the application folder."""
        profile = self.profile(ws)
        if job is None:
            if not offer:
                raise ValueError("pass an offer or a parsed job")
            job = parse_job(read_offer(offer), self.provider, self.retries)
        app_dir = ws.new_application(job.company, job.title)
        (app_dir / "offer.txt").write_text(job.raw_text, encoding="utf-8")
        _write(app_dir / "job.json", job)
        result = RunResult(candidate=ws.name, application=app_dir.name, dir=str(app_dir), job=job)
        result.score = score(job, profile, self.provider, lang or job.language, self.retries)
        _write(app_dir / "score.json", result.score)
        _write(app_dir / "result.json", result)
        return result

    def load_application(self, ws: Workspace, app_id: str) -> RunResult:
        return load_json(ws.application(app_id) / "result.json", RunResult)

    def add_variants(
        self,
        ws: Workspace,
        app_id: str,
        styles: list[str] | None = None,
        templates: list[str] | None = None,
        lang: str | None = None,
        visual: bool = False,
        one_page: bool = False,
    ) -> RunResult:
        """Tailor (or reuse an already tailored CV for the same style+language+length) and render."""
        result = self.load_application(ws, app_id)
        app_dir = Path(result.dir)
        profile = self.profile(ws)
        job = result.job
        styles = styles or [self.cfg.default_style]
        templates = templates or [self.cfg.default_template]
        language = (lang or job.language).lower()
        tpl_pages = 1 if one_page else min(self.template(t).max_pages for t in templates)
        base = f"{slug(profile.contact.name, 30)}_CV_{slug(job.company or job.title, 24)}"
        suffix = "_1p" if one_page else ""

        def make(style: str) -> TailoredCV:
            cached = app_dir / f"{base}_{style}_{language}{suffix}.cv.json"
            if cached.exists():
                return load_json(cached, TailoredCV)
            st = get_style(style, self.cfg.style_dirs)
            cv = tailor(profile, job, st, self.provider, language, max_pages=tpl_pages, max_retries=self.retries)
            _write(cached, cv)
            return cv

        with ThreadPoolExecutor(max_workers=min(4, len(styles))) as pool:
            futures = {s: pool.submit(make, s) for s in styles}
        for style, fut in futures.items():
            try:
                cv = fut.result()
            except Exception as e:
                result.errors.append(f"tailor[{style}]: {e}")
                continue
            for t in templates:
                v = self.render(
                    cv, t, app_dir, f"{base}_{style}_{language}{suffix}_{t}", visual=visual, one_page=one_page
                )
                result.variants = [x for x in result.variants if x.pdf != v.pdf] + [v]
        _write(app_dir / "result.json", result)
        return result

    def add_insights(self, ws: Workspace, app_id: str, lang: str | None = None) -> RunResult:
        result = self.load_application(ws, app_id)
        app_dir = Path(result.dir)
        result.insights = insights(
            result.job, self.profile(ws), self.provider, lang or result.job.language, self.retries
        )
        _write(app_dir / "insights.json", result.insights)
        (app_dir / "insights.md").write_text(insights_markdown(result.insights, result.job), encoding="utf-8")
        _write(app_dir / "result.json", result)
        return result

    def render_external(
        self,
        ws: Workspace,
        cv: TailoredCV,
        templates: list[str] | None = None,
        app_id: str | None = None,
        visual: bool = False,
        one_page: bool = False,
    ) -> list[Variant]:
        """Render a CV JSON produced elsewhere (e.g. an n8n agent), with the grounding term check."""
        profile = self.profile(ws)
        if app_id:
            out = ws.application(app_id)
        else:
            out = ws.new_application("external", cv.headline)
        base = f"{slug(cv.contact.name, 30)}_CV_{slug(cv.headline, 24)}_{cv.style}_{cv.language}"
        base += "_1p" if one_page else ""
        return [
            self.render(cv, t, out, f"{base}_{t}", visual=visual, profile=profile, one_page=one_page)
            for t in templates or [self.cfg.default_template]
        ]

    # ------------------------------------------------------------ full pipeline

    def run(
        self,
        ws: Workspace,
        offer: str | None = None,
        *,
        job: JobOffer | None = None,
        styles: list[str] | None = None,
        templates: list[str] | None = None,
        lang: str | None = None,
        with_insights: bool = True,
        visual: bool = False,
        min_score: int | None = None,
        one_page: bool = False,
    ) -> RunResult:
        result = self.create_application(ws, offer, job, lang)
        app = result.application
        assert result.score is not None
        if min_score is not None and result.score.overall < min_score:
            result.skipped_reason = f"score {result.score.overall} < min_score {min_score}; CV not generated"
            _write(Path(result.dir) / "result.json", result)
            return result
        result = self.add_variants(ws, app, styles, templates, lang, visual, one_page)
        if with_insights:
            try:
                result = self.add_insights(ws, app, lang)
            except Exception as e:  # insights are a bonus; never lose the CV because of them
                result.errors.append(f"insights: {e}")
                _write(Path(result.dir) / "result.json", result)
        return result


def load_json(path: Path, model):
    return model.model_validate_json(Path(path).read_text(encoding="utf-8"))


def dump(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2)
