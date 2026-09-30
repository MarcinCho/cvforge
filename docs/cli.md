# Command line reference

Run `cvforge --help` or `cvforge <command> --help` for the same information in your terminal.

Many commands take an **offer**: a file path, a URL, `-` to read from stdin, or the offer text itself. Most take `--candidate/-c` (the folder name under `candidates/`; defaults to `default_candidate`, or the only candidate if there is one).

## Getting started

| Command | Description |
|---|---|
| `cvforge start [--port 8765]` | Start cvforge (or reopen the running instance for this folder) and open it in the browser. This is what the launcher files run. |
| `cvforge setup [--port 8765]` | Open the web setup page: pick your AI, paste your career data, choose defaults. |
| `cvforge init -c NAME [--source FILE] [--link]` | Create `cvforge.toml` (if missing) and `candidates/NAME/` with a source-of-truth template, or a copy of `FILE` (`--link` symlinks it instead). |
| `cvforge doctor` | Check the config, the LLM connection and PDF rendering. |

## The pipeline

| Command | Description |
|---|---|
| `cvforge run OFFER` | Full pipeline: analyse offer → score → tailored CV(s) → render → check → insights. |
| `cvforge tailor OFFER` | Same as `run` without insights. |
| `cvforge score OFFER` | Job-fit score only (0–100). |
| `cvforge insights OFFER` | Similar titles to search for, typical requirements, what to learn, likely interview topics. |
| `cvforge job OFFER [-o FILE]` | Analyse the offer only (keywords, requirements, language); `-o` writes the JobOffer JSON. |
| `cvforge ingest [--force] [--show]` | Build the structured profile from the source of truth (cached until the file changes). |

Options for `run` and `tailor`:

| Option | Description |
|---|---|
| `-s, --style STYLE` | Writing style; repeat for several variants (`-s impact -s concise`) |
| `-t, --template NAME` | Template; repeat for several |
| `-l, --lang CODE` | CV language (default: the offer's language) |
| `-1, --one-page` | Force a one-page CV (condensed writing + auto-trim) |
| `--visual-review` | Let a vision-capable LLM look at the rendered pages |
| `--min-score N` | (`run` only) skip CV generation below this score |
| `--no-insights` | (`run` only) skip insights |
| `--json` | Machine-readable output (also on `score` and `insights`) |

## Rendering and checks (no LLM needed)

| Command | Description |
|---|---|
| `cvforge render CV.json [-t NAME ...] [-o DIR] [-1] [--visual-review]` | Render a tailored CV JSON (from `tailor`/`run`, or written by hand or by another tool) and check the result. Output goes next to the JSON unless `-o` is given. |
| `cvforge check CV.pdf --cv CV.json [-t NAME] [--visual-review]` | Re-run the ATS and visual checks on a rendered PDF and the `.docx` next to it. |

## Templates, styles, applications

| Command | Description |
|---|---|
| `cvforge templates list` | List templates (built-in and your own). |
| `cvforge templates preview [NAME ...] [--cv CV.json] [-o DIR]` | Render the sample CV (or yours) with each template: PDF, DOCX and a page-1 PNG, into `template-previews/` by default. |
| `cvforge templates new NAME [--from ats-classic]` | Copy a template into your `templates/` folder to customise it. |
| `cvforge styles list` | List writing styles. |
| `cvforge apps` | List generated applications for a candidate. |

## Server

| Command | Description |
|---|---|
| `cvforge serve [--host 127.0.0.1] [--port 8765] [--open]` | Start the web UI and HTTP API. API docs at `/docs`. See [HTTP API](http-api.md). |

## Examples

```bash
cvforge run https://example.com/job/123 -s impact -s concise -t ats-classic -t ats-modern
cvforge run offer.txt --one-page --min-score 60
pbpaste | cvforge score - --json
cvforge render candidates/anna/applications/<application>/<name>_CV_<company>_impact_en.cv.json -t executive
```
