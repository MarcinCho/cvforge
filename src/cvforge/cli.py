"""cvforge command line interface."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer

from .config import DEFAULT_CONFIG, PACKAGE_DIR, find_config_file, load_config
from .core import check as checks
from .core.insights import insights_markdown
from .core.pipeline import Engine, RunResult, dump, load_json
from .core.render import SAMPLE_CV, get_template, list_templates, new_template
from .core.styles import list_styles
from .core.workspace import Workspace, list_candidates
from .llm import LLMError
from .models import JobOffer, ScoreReport, TailoredCV

app = typer.Typer(
    help="ATS-optimised, job-tailored CVs from your source of truth, with any LLM.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
templates_app = typer.Typer(help="List or create CV templates.", no_args_is_help=True)
styles_app = typer.Typer(help="List writing styles.", no_args_is_help=True)
app.add_typer(templates_app, name="templates")
app.add_typer(styles_app, name="styles")

CandidateOpt = typer.Option(None, "--candidate", "-c", help="Candidate folder name (default from config)")
LangOpt = typer.Option(None, "--lang", "-l", help="CV language code (default: the offer's language)")
JsonOpt = typer.Option(False, "--json", help="Print machine-readable JSON")
OnePageOpt = typer.Option(False, "--one-page", "-1", help="Force a one-page CV (condensed writing + auto-trim)")
OfferArg = typer.Argument(..., help="Job offer: file path, URL, '-' for stdin, or the text itself")


def _engine() -> Engine:
    return Engine(load_config())


def _fail(msg: str) -> None:
    typer.secho(f"error: {msg}", fg="red", err=True)
    raise typer.Exit(1)


def _job(engine: Engine, offer: str) -> JobOffer:
    p = Path(offer)
    if len(offer) < 400 and p.suffix == ".json" and p.exists():
        return load_json(p, JobOffer)
    typer.secho("• analysing job offer…", fg="cyan", err=True)
    return engine.job(offer)


def print_score(s: ScoreReport) -> None:
    color = "green" if s.overall >= 75 else "yellow" if s.overall >= 55 else "red"
    typer.secho(f"\nJOB FIT: {s.overall}/100  →  {s.recommendation.replace('_', ' ')}", fg=color, bold=True)
    typer.echo("  " + "  ".join(f"{k}: {v}" for k, v in s.breakdown.items()))
    if s.summary:
        typer.echo(f"\n{s.summary}")
    if s.strengths:
        typer.echo("\nStrengths:\n" + "\n".join(f"  + {x}" for x in s.strengths))
    if s.gaps:
        typer.echo("Gaps:\n" + "\n".join(f"  - {x}" for x in s.gaps))
    typer.echo(f"\nKeywords matched ({len(s.matched_keywords)}): {', '.join(s.matched_keywords) or '-'}")
    typer.echo(f"Keywords missing ({len(s.missing_keywords)}): {', '.join(s.missing_keywords) or '-'}")
    if s.unconfirmed_matches:
        typer.secho(
            "Unconfirmed in your source of truth (confirm to use them): " + ", ".join(s.unconfirmed_matches),
            fg="yellow",
        )


def print_run(r: RunResult) -> None:
    if r.score:
        print_score(r.score)
    if r.skipped_reason:
        typer.secho(f"\nskipped: {r.skipped_reason}", fg="yellow")
    for v in r.variants:
        color = {"pass": "green", "warn": "yellow", "fail": "red"}[v.status]
        typer.secho(
            f"\n[{v.status.upper()}] style={v.style} template={v.template}" + (" one-page" if v.one_page else ""),
            fg=color,
            bold=True,
        )
        typer.echo(f"  {Path(r.dir) / v.pdf}\n  {Path(r.dir) / v.docx}")
        for rep in v.checks.values():
            for item in rep.items:
                if item.status != "pass":
                    typer.echo(f"  {item.status}: {rep.file} {item.rule}: {item.detail}")
    for e in r.errors:
        typer.secho(f"error: {e}", fg="red")
    if r.insights:
        typer.echo(f"\nInsights: {Path(r.dir) / 'insights.md'}")
    typer.echo(f"\nApplication folder: {r.dir}")


# ---------------------------------------------------------------- setup


@app.command()
def init(
    candidate: str = typer.Option(..., "--candidate", "-c", help="Folder name for the candidate, e.g. 'anna'"),
    source: Path | None = typer.Option(None, "--source", "-s", help="Existing source-of-truth markdown"),
    link: bool = typer.Option(False, "--link", help="Symlink the source instead of copying it"),
) -> None:
    """Create cvforge.toml (if missing) and a candidate folder with a source of truth."""
    cfg_path = find_config_file()
    if cfg_path is None:
        cfg_path = Path.cwd() / "cvforge.toml"
        cfg_path.write_text(
            DEFAULT_CONFIG.replace('default_candidate = ""', f'default_candidate = "{candidate}"'), encoding="utf-8"
        )
        typer.echo(f"created {cfg_path}")
    cfg = load_config(cfg_path)
    cdir = cfg.candidates_path / candidate
    cdir.mkdir(parents=True, exist_ok=True)
    dest = cdir / "source_of_truth.md"
    if dest.exists() or dest.is_symlink():
        typer.echo(f"{dest} already exists — leaving it")
    elif source:
        if link:
            dest.symlink_to(source.resolve())
        else:
            shutil.copy(source, dest)
        typer.echo(f"{'linked' if link else 'copied'} {source} → {dest}")
    else:
        shutil.copy(PACKAGE_DIR / "builtin" / "source_of_truth_template.md", dest)
        typer.echo(f"created {dest} from the template — fill it in, then run `cvforge ingest`")


@app.command()
def doctor() -> None:
    """Check config, LLM connection and rendering."""
    cfg = load_config()
    typer.echo(f"config: {find_config_file() or '(defaults)'}")
    typer.echo(f"candidates: {cfg.candidates_path} → {list_candidates(cfg) or 'none'}")
    typer.echo(f"templates: {', '.join(list_templates(cfg.template_dirs))}")
    typer.echo(f"styles: {', '.join(list_styles(cfg.style_dirs))}")
    engine = Engine(cfg)
    typer.echo(f"llm: {engine.provider.name} (images: {engine.provider.supports_images})")
    try:
        out = engine.provider.complete("Reply with exactly: OK")
        typer.secho(f"llm answered: {out[:80]!r}", fg="green")
    except LLMError as e:
        _fail(str(e))


# ---------------------------------------------------------------- steps


@app.command()
def ingest(
    candidate: str | None = CandidateOpt,
    force: bool = typer.Option(False, "--force", help="Re-extract even if the source is unchanged"),
    show: bool = typer.Option(False, "--show", help="Print the extracted profile JSON"),
) -> None:
    """Parse the source of truth into a structured profile (cached until the source changes)."""
    engine = _engine()
    ws = engine.workspace(candidate)
    typer.secho("• reading source of truth…", fg="cyan", err=True)
    p = engine.profile(ws, force=force)
    if show:
        typer.echo(p.model_dump_json(indent=2, exclude={"source_text"}))
    typer.echo(
        f"profile: {len(p.experience)} roles, {len(p.projects)} projects, {len(p.skills)} skills, "
        f"{len(p.keywords)} keywords → {ws.profile_cache}"
    )
    typer.echo(f"never in a CV: {p.redactions or '-'}")
    typer.echo(f"unconfirmed (not used): {p.unconfirmed_keywords or '-'}")


@app.command()
def job(offer: str = OfferArg, out: Path | None = typer.Option(None, "-o", help="Write JobOffer JSON here")) -> None:
    """Analyse a job offer (keywords, requirements, language)."""
    j = _engine().job(offer)
    text = dump(j)
    if out:
        out.write_text(text, encoding="utf-8")
    typer.echo(text)


@app.command()
def score(
    offer: str = OfferArg, candidate: str | None = CandidateOpt, lang: str | None = LangOpt, as_json: bool = JsonOpt
) -> None:
    """Score how well the candidate fits a job offer (0-100)."""
    engine = _engine()
    ws = engine.workspace(candidate)
    j = _job(engine, offer)
    typer.secho("• scoring…", fg="cyan", err=True)
    s = engine.score(ws, j, lang)
    typer.echo(dump(s)) if as_json else print_score(s)


@app.command()
def tailor(
    offer: str = OfferArg,
    candidate: str | None = CandidateOpt,
    style: list[str] = typer.Option(None, "--style", "-s", help="Writing style (repeat for variants)"),
    template: list[str] = typer.Option(None, "--template", "-t", help="Template (repeat for several)"),
    lang: str | None = LangOpt,
    visual_review: bool = typer.Option(False, "--visual-review", help="LLM looks at rendered pages"),
    one_page: bool = OnePageOpt,
    as_json: bool = JsonOpt,
) -> None:
    """Score + generate tailored CV(s), skipping insights."""
    engine = _engine()
    ws = engine.workspace(candidate)
    j = _job(engine, offer)
    typer.secho("• tailoring…", fg="cyan", err=True)
    r = engine.run(
        ws,
        job=j,
        styles=style or None,
        templates=template or None,
        lang=lang,
        with_insights=False,
        visual=visual_review,
        one_page=one_page,
    )
    typer.echo(dump(r)) if as_json else print_run(r)


@app.command()
def run(
    offer: str = OfferArg,
    candidate: str | None = CandidateOpt,
    style: list[str] = typer.Option(None, "--style", "-s", help="Writing style (repeat for variants)"),
    template: list[str] = typer.Option(None, "--template", "-t", help="Template (repeat for several)"),
    lang: str | None = LangOpt,
    no_insights: bool = typer.Option(False, "--no-insights"),
    visual_review: bool = typer.Option(False, "--visual-review", help="LLM looks at rendered pages"),
    min_score: int | None = typer.Option(None, "--min-score", help="Skip CV generation below this score"),
    one_page: bool = OnePageOpt,
    as_json: bool = JsonOpt,
) -> None:
    """Full pipeline: analyse offer → score → tailored CV(s) → render → check → insights."""
    engine = _engine()
    ws = engine.workspace(candidate)
    typer.secho("• reading profile…", fg="cyan", err=True)
    engine.profile(ws)
    j = _job(engine, offer)
    typer.secho(
        f"• {j.title} @ {j.company or '?'} [{j.language}] — scoring, tailoring, rendering…", fg="cyan", err=True
    )
    r = engine.run(
        ws,
        job=j,
        styles=style or None,
        templates=template or None,
        lang=lang,
        with_insights=not no_insights,
        visual=visual_review,
        min_score=min_score,
        one_page=one_page,
    )
    typer.echo(dump(r)) if as_json else print_run(r)
    if not r.variants and not r.skipped_reason:
        raise typer.Exit(1)


@app.command()
def render(
    cv_json: Path = typer.Argument(..., help="Tailored CV JSON (from tailor/run, or written by hand/n8n)"),
    template: list[str] = typer.Option(None, "--template", "-t"),
    out: Path | None = typer.Option(None, "-o", help="Output folder (default: next to the JSON)"),
    candidate: str | None = CandidateOpt,
    visual_review: bool = typer.Option(False, "--visual-review"),
    one_page: bool = OnePageOpt,
) -> None:
    """Render a CV JSON with one or more templates (no LLM needed) and check the result."""
    engine = _engine()
    cv = load_json(cv_json, TailoredCV)
    # with --candidate, also check forbidden/unconfirmed terms from that person's source of truth
    profile = engine.profile(engine.workspace(candidate)) if candidate else None
    out = out or cv_json.parent
    stem = cv_json.name.removesuffix(".json").removesuffix(".cv")
    for known in list_templates(engine.cfg.template_dirs):  # re-rendering a rendered CV: drop old template name
        stem = stem.removesuffix(f"_{known}")
    for t in template or [engine.cfg.default_template]:
        v = engine.render(
            cv,
            t,
            out,
            f"{stem}{'_1p' if one_page else ''}_{t}",
            visual=visual_review,
            profile=profile,
            one_page=one_page,
        )
        typer.echo(checks.summarize(v.checks["pdf"]))
        typer.echo(checks.summarize(v.checks["docx"]))
        typer.echo(f"→ {out / v.pdf}\n→ {out / v.docx}")


@app.command()
def check(
    pdf: Path = typer.Argument(..., help="Rendered CV PDF"),
    cv_json: Path = typer.Option(..., "--cv", help="The CV JSON it was rendered from"),
    template: str | None = typer.Option(None, "--template", "-t"),
    visual_review: bool = typer.Option(False, "--visual-review"),
) -> None:
    """Re-run ATS/visual checks on a rendered PDF (+ the .docx next to it)."""
    engine = _engine()
    cv = load_json(cv_json, TailoredCV)
    tpl = engine.template(template)
    rep = checks.check_pdf(pdf, cv, tpl, previews_dir=pdf.parent / "previews")
    if visual_review:
        checks.merge_visual(
            rep, checks.visual_review([pdf.parent / "previews" / p for p in rep.previews], engine.provider)
        )
    typer.echo(checks.summarize(rep))
    if pdf.with_suffix(".docx").exists():
        typer.echo(checks.summarize(checks.check_docx(pdf.with_suffix(".docx"), cv)))
    if rep.status == "fail":
        raise typer.Exit(2)


@app.command()
def insights(
    offer: str = OfferArg, candidate: str | None = CandidateOpt, lang: str | None = LangOpt, as_json: bool = JsonOpt
) -> None:
    """Tips about similar positions: titles to search, typical requirements, what to learn, interview topics."""
    engine = _engine()
    ws = engine.workspace(candidate)
    j = _job(engine, offer)
    typer.secho("• generating insights…", fg="cyan", err=True)
    rep = engine.insights(ws, j, lang)
    typer.echo(dump(rep) if as_json else insights_markdown(rep, j))


@app.command("apps")
def apps(candidate: str | None = CandidateOpt) -> None:
    """List generated applications for a candidate."""
    ws = Workspace(load_config(), candidate)
    for a in ws.list_applications():
        s = ws.applications_dir / a / "score.json"
        sc = load_json(s, ScoreReport).overall if s.exists() else "-"
        typer.echo(f"{a}  score={sc}")


def _serve(host: str, port: int, open_path: str | None) -> None:
    import threading
    import webbrowser

    import uvicorn

    from .api import create_app

    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    typer.echo(f"cvforge UI: {url}   API docs: {url}docs   (Ctrl+C to stop)")
    if open_path is not None:
        threading.Timer(1.2, lambda: webbrowser.open(url + open_path)).start()
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    open_browser: bool = typer.Option(False, "--open", help="Open the web UI in your browser"),
) -> None:
    """Start the HTTP API (for n8n) and the web UI."""
    _serve(host, port, "" if open_browser else None)


@app.command()
def start(port: int = typer.Option(8765, "--port")) -> None:
    """One command for everyone: start cvforge and open it in the browser (setup appears on first run)."""
    import socket
    import webbrowser

    import httpx

    me = load_config().instance_id
    for p in range(port, port + 20):
        try:  # this installation already running? just open it
            if httpx.get(f"http://127.0.0.1:{p}/api/health", timeout=1).json().get("instance") == me:
                typer.echo(f"cvforge is already running — opening http://127.0.0.1:{p}/")
                webbrowser.open(f"http://127.0.0.1:{p}/")
                return
        except Exception:
            pass
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", p)) != 0:  # port is free
                break
    else:
        _fail(f"no free port between {port} and {port + 19}")
    typer.secho("\n  cvforge is running. Your browser will open in a moment.", fg="green", bold=True)
    typer.echo("  Keep this window open while you use it. Close it (or press Ctrl+C) to stop.\n")
    _serve("127.0.0.1", p, "")


@app.command()
def setup(port: int = typer.Option(8765, "--port")) -> None:
    """Easiest start: opens the web setup (pick your AI, paste your career data) in the browser."""
    _serve("127.0.0.1", port, "#setup")


# ---------------------------------------------------------------- templates & styles


@templates_app.command("list")
def templates_list() -> None:
    cfg = load_config()
    for t in list_templates(cfg.template_dirs).values():
        typer.echo(
            f"{t.name:<14} pages≤{t.max_pages} {'ATS-safe' if t.ats_safe else 'not ATS-safe'}  "
            f"{t.description}\n{'':14} {t.path}"
        )


@templates_app.command("new")
def templates_new(name: str, base: str = typer.Option("ats-classic", "--from")) -> None:
    """Scaffold a new template in your templates folder by copying an existing one."""
    cfg = load_config()
    target = cfg.resolve(cfg.templates_dir)
    target.mkdir(parents=True, exist_ok=True)
    dest = new_template(name, get_template(base, cfg.template_dirs), target)
    typer.echo(
        f"created {dest}\n  edit style.css (look), template.toml (sections order, page target, DOCX look),\n"
        f"  cv.html.j2 (structure). Test: cvforge render <cv.json> -t {name}"
    )


@templates_app.command("preview")
def templates_preview(
    names: list[str] = typer.Argument(None, help="Templates (default: all)"),
    out: Path = typer.Option(Path("template-previews"), "-o", help="Output folder"),
    cv_json: Path | None = typer.Option(None, "--cv", help="Use this CV JSON instead of the sample"),
) -> None:
    """Render the sample CV (or your own CV JSON) with each template: PDF + DOCX + page-1 PNG."""
    cfg = load_config()
    engine = Engine(cfg)
    cv = load_json(cv_json, TailoredCV) if cv_json else load_json(SAMPLE_CV, TailoredCV)
    templates = list_templates(cfg.template_dirs)
    for name in names or list(templates):
        v = engine.render(cv, name, out, name)
        typer.echo(f"{name:<12} [{v.status}] {out / v.pdf}  preview: {out / 'previews' / v.previews[0]}")


@styles_app.command("list")
def styles_list() -> None:
    cfg = load_config()
    for s in list_styles(cfg.style_dirs).values():
        typer.echo(f"{s.name:<11} {s.description}")
    typer.echo(f"\nadd your own: drop a YAML file (name, description, instructions) into {cfg.resolve(cfg.styles_dir)}")


def main() -> None:  # pragma: no cover
    try:
        app()
    except (LLMError, FileNotFoundError, KeyError, ValueError) as e:
        typer.secho(f"error: {e}", fg="red", err=True)
        sys.exit(1)
