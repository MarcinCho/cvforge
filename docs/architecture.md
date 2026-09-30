# Architecture

This page is for contributors. It explains how a job offer becomes a checked PDF and where to make changes.

## Overview

```
                 ┌──────────── cli.py (Typer) ────────────┐
 user / n8n ───▶ │                                         │ ──▶ core.pipeline.Engine
                 └── api.py + setup_api.py (FastAPI, web) ─┘            │
                                                                        ▼
  source_of_truth.md ─▶ ingest ─▶ Profile (cached)                      │
  job offer ─────────▶ job ─────▶ JobOffer                              │
                          score(Profile, JobOffer) ─▶ ScoreReport       │
                          tailor(Profile, JobOffer, Style) ─▶ TailoredCV
                                   └─ guard (reject + retry with feedback)
                          render(TailoredCV, Template) ─▶ PDF + DOCX (+ fit to pages)
                          check(PDF, DOCX) ─▶ CheckReport (+ previews, optional visual review)
                          insights(Profile, JobOffer) ─▶ InsightsReport
```

The CLI, the HTTP API and the web UI are thin layers: they all call the same `Engine` in [`core/pipeline.py`](../src/cvforge/core/pipeline.py), so a feature added there is available everywhere.

## Modules

| Path | Responsibility |
|---|---|
| `cli.py` | All `cvforge` commands (Typer). Formatting of terminal output. |
| `api.py` | FastAPI app: JSON API, file downloads, the single-page web UI (`web/templates/index.html`), bearer-token auth. |
| `setup_api.py` | Setup-wizard endpoints: LLM presets and connection test, candidates, source editor, defaults. Local-only unless a token is set. |
| `config.py` | Finding, loading and saving `cvforge.toml`; environment overrides. |
| `models.py` | Pydantic models shared by every layer: `Profile`, `JobOffer`, `ScoreReport`, `TailoredCV`, `CheckReport`, `InsightsReport`… These are also the JSON schemas the LLM must fill. |
| `core/ingest.py` | Strips private comments, extracts forbidden/unconfirmed rules, masks forbidden terms, asks the LLM for a `Profile`, caches it by source hash. |
| `core/job.py` | Reads an offer (file, URL, stdin, text) and asks the LLM for a `JobOffer`. |
| `core/score.py` | Deterministic keyword coverage (synonyms, evidence map) + LLM rubric → `ScoreReport`. |
| `core/tailor.py` | Builds the tailoring prompt for a style and turns the LLM's draft into a `TailoredCV`. |
| `core/guard.py` | Truthfulness checks: cited source bullets, numbers present in the source, known skills, no forbidden/unconfirmed terms. |
| `core/styles.py` | Loads writing styles (YAML) from the built-in and user folders. |
| `core/render.py` | Templates: Jinja2 → HTML → WeasyPrint PDF; python-docx DOCX; fonts; auto-fit and one-page trimming; template previews. |
| `core/check.py` | ATS and visual checks on the rendered PDF/DOCX, page previews (pypdfium2), optional LLM visual review. |
| `core/insights.py` | Similar positions, requirements, learning plan and interview topics. |
| `core/workspace.py` | Candidate folders and application folders on disk. |
| `core/text.py` | Text helpers (folding diacritics, normalisation). |
| `llm/` | Providers and JSON extraction (see below). |
| `prompts/*.md.j2` | Every prompt sent to the LLM, as Jinja2 templates. |
| `builtin/` | Templates, styles, fonts, the source-of-truth template and the sample CV used for previews. |

## Data on disk

```
<folder with cvforge.toml>/
  cvforge.toml
  templates/  styles/                    # optional user additions
  llm-exchange/                          # manual provider only
  .cvforge-cache/previews/               # template thumbnails
  candidates/<name>/
    source_of_truth.md
    .cache/profile.json
    applications/<date>_<company>_<role>/
      offer.txt, job.json, score.json
      <name>_CV_<company>_<style>_<lang>[_1p].cv.json
      *.pdf, *.docx, *.check.json, previews/
      insights.md
```

## LLM layer

A provider is anything with this shape ([`llm/base.py`](../src/cvforge/llm/base.py)):

```python
class LLMProvider(Protocol):
    name: str
    supports_images: bool

    def complete(self, prompt: str, images: list[Path] | None = None) -> str: ...
```

Built-in providers:

| Provider | File | How it works |
|---|---|---|
| `command` | `llm/command.py` | Runs a CLI; prompt on stdin, `{prompt}` or `{prompt_file}` |
| `openai` | `llm/openai_compat.py` | `POST {base_url}/chat/completions` with httpx; images when `vision = true` |
| `manual` | `llm/manual.py` | Writes `prompt-N.md`, waits for `answer-N.md` |
| fake | `llm/fake.py` | Scripted answers for tests; records the prompts it received |

Structured output goes through `ask_json()` in [`llm/structured.py`](../src/cvforge/llm/structured.py): it appends the Pydantic model's JSON schema to the prompt, extracts JSON from the reply, validates it, and retries with the validation error up to `max_retries` times. Providers never need to know about JSON.

### Adding a provider

1. Create `src/cvforge/llm/myprovider.py` with a class that has `name`, `supports_images` and `complete()`. Raise `LLMError` (from `llm/base.py`) on failure, with a message a user can act on.
2. Add a branch for it in `make_provider()` in [`llm/__init__.py`](../src/cvforge/llm/__init__.py), and any new settings to `LLMConfig` in `config.py`.
3. If the setup page should offer it, add it to the provider handling in `setup_api.py` and the presets in the web UI.
4. Add tests in `tests/test_llm.py` (mock the transport; no real network calls).
5. Document it in [configuration.md](configuration.md).

## Changing prompts

Prompts are in `src/cvforge/prompts/`. When you change one, keep the output model in `models.py` in sync, and run the tests: they assert on key parts of the prompts (for example that redacted terms never reach the LLM).

## Testing approach

- Unit and integration tests use `FakeProvider` with scripted JSON answers; `tests/conftest.py` has a sample source of truth, profile and CV.
- Rendering tests use real WeasyPrint, so the system libraries must be installed.
- API tests use FastAPI's `TestClient` against `create_app()` with a temporary config.
