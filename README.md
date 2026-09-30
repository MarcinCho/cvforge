# cvforge

[![CI](https://github.com/MarcinCho/cvforge/actions/workflows/ci.yml/badge.svg)](https://github.com/MarcinCho/cvforge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

**ATS-optimised CVs tailored to each job offer, generated from your own career notes and whichever LLM you already use.**

cvforge takes one Markdown file with your whole career (your *source of truth*) and a job offer, and gives you a fit score, a tailored CV as PDF and Word, ATS checks on the result, and tips for similar roles. It works with an LLM CLI (`claude -p`, `gemini`, `codex`, `ollama`…), any OpenAI-compatible API, or plain copy and paste into a chat window.

## Features

- **Job-fit score (0–100)**: deterministic keyword coverage plus a calibrated LLM rubric, with strengths, gaps, and matched and missing keywords.
- **Tailored CVs** in the offer's language, in one or more writing styles (`impact`, `concise`, `narrative`, `technical`, or your own).
- **9 templates** for PDF and DOCX, from plain ATS-safe to designed, plus your own. One-page mode trims content without inventing anything.
- **ATS and visual checks** on every file: text extraction, diacritics, contact details, headings, keyword survival, page count, overflow, font sizes, embedded fonts, no tables or text boxes in the DOCX, page previews, and an optional LLM review of the rendered pages.
- **Insights**: titles to search for, typical requirements, what to learn next, likely interview topics mapped to your own stories.
- **Truthfulness guard**: a CV is rejected and regenerated when a bullet doesn't cite your source, a number isn't in the source, a skill isn't yours, or a forbidden or unconfirmed term appears. Confidential names are masked before the LLM ever sees them.
- **Three ways to use it**: a web UI with a setup wizard, a CLI, and an HTTP API (with an n8n example workflow and a Dockerfile).

## Quick start

### No technical knowledge needed

1. [Download cvforge](https://github.com/MarcinCho/cvforge/archive/refs/heads/main.zip) and unzip it.
2. Double-click the launcher: `start.command` (macOS), `start.bat` (Windows) or `start.sh` (Linux). The first start installs everything (1–2 minutes) and opens your browser.
3. Follow the **Setup** page: pick your AI → paste your career history → choose a style and template.
4. Paste a job offer → **Analyse & score** → **Generate CV** → download the PDF or Word file.

### With pip

cvforge needs Python 3.11+ and the libraries WeasyPrint uses for PDFs:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 poppler-utils   # macOS: brew install pango poppler
```

```bash
pipx install git+https://github.com/MarcinCho/cvforge.git
```

```bash
mkdir ~/my-cvs && cd ~/my-cvs
cvforge init --candidate anna        # creates cvforge.toml and a source-of-truth template to fill in
cvforge doctor                       # checks the LLM connection
cvforge run https://example.com/job/123 -s impact -t ats-modern
```

or `cvforge setup` to do it all in the browser. The full walkthrough, including Docker, is in [Getting started](docs/getting-started.md).

## Connect your LLM

Pick one in `cvforge.toml` (the setup page writes it for you):

```toml
[llm]
provider = "command"
command  = "claude -p"          # or "gemini", "codex exec -", "ollama run qwen3", ...
```

```toml
[llm]
provider = "openai"             # OpenAI, OpenRouter, Ollama, LM Studio, vLLM...
base_url = "http://localhost:11434/v1"
model    = "qwen3"
```

```toml
[llm]
provider = "manual"             # no CLI or key: copy prompts into any chat window
```

All options and environment variables: [Configuration](docs/configuration.md).

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started.md) | Install and make your first CV |
| [Configuration](docs/configuration.md) | `cvforge.toml`, LLM providers, environment variables |
| [Writing your source of truth](docs/source-of-truth.md) | Private notes, forbidden and unconfirmed terms |
| [Command line](docs/cli.md) | Every command and option |
| [Templates and styles](docs/templates-and-styles.md) | Built-in looks, one-page mode, making your own |
| [How scoring works](docs/scoring.md) | The formula and thresholds |
| [HTTP API and n8n](docs/http-api.md) | Endpoints, auth, automation |
| [Architecture](docs/architecture.md) | For contributors: how it fits together |

## Contributing

Contributions are welcome: bug reports, docs, templates, writing styles and code. Read [CONTRIBUTING.md](CONTRIBUTING.md) to get set up (the test suite needs no LLM), and please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately as described in [SECURITY.md](SECURITY.md).

## License

cvforge is released under the [MIT License](LICENSE).

The bundled fonts (Noto Sans/Serif/Sans Mono, Lato, Carlito, Caladea) are under the SIL Open Font License 1.1; see [`src/cvforge/builtin/fonts/README.md`](src/cvforge/builtin/fonts/README.md).
