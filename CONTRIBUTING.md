# Contributing to cvforge

Thanks for your interest in improving cvforge! Bug reports, docs fixes, new templates, writing styles and code are all welcome. This guide gets you from zero to an open pull request.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** or **suggest a feature**: open an [issue](https://github.com/MarcinCho/cvforge/issues/new/choose) using one of the forms. Search existing issues first.
- **Improve the docs**: everything in [`docs/`](docs/) and this README is plain Markdown. Small fixes can go straight to a pull request.
- **Add a template or writing style**: no Python needed. See [Templates and styles](docs/templates-and-styles.md).
- **Write code**: look for issues labelled [`good first issue`](https://github.com/MarcinCho/cvforge/labels/good%20first%20issue) or [`help wanted`](https://github.com/MarcinCho/cvforge/labels/help%20wanted). For bigger changes, open an issue first so we can agree on the approach before you spend time on it.

Security problems: please follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Development setup

You need Python 3.11+ and the system libraries WeasyPrint uses for PDF rendering, plus `pdftotext` for the checks.

```bash
# Debian / Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 poppler-utils
```

```bash
# macOS
brew install pango poppler
```

On Windows, follow the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows) (MSYS2) and install Poppler.

Then fork the repository, clone your fork and install cvforge in editable mode with the dev tools:

```bash
git clone https://github.com/<you>/cvforge.git
cd cvforge
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

`pre-commit install` makes lint and formatting run automatically on every commit.

## Running the checks

```bash
pytest                 # the test suite
ruff check .           # lint
ruff format .          # format (CI runs `ruff format --check`)
```

The tests use a scripted `FakeProvider` (`src/cvforge/llm/fake.py`), so **no LLM, API key or network is needed**. Any new feature that talks to the LLM should be tested the same way: script the answers you expect and assert on the prompts and the result. Shared fixtures (a sample source of truth, profile and CV) are in `tests/conftest.py`.

To try the app by hand, create a throwaway workspace outside the repo and use the `manual` provider if you don't have an LLM CLI:

```bash
mkdir -p ~/cvforge-play && cd ~/cvforge-play
cvforge init --candidate test
CVFORGE_LLM_PROVIDER=manual cvforge serve --open
```

## Project layout

```
src/cvforge/
  cli.py            Typer CLI (all `cvforge ...` commands)
  api.py            FastAPI app: HTTP API + web UI
  setup_api.py      setup wizard endpoints (local-only)
  config.py         cvforge.toml loading/saving
  models.py         Pydantic models shared by every layer
  core/             the pipeline: ingest, job, score, tailor, guard, render, check, insights
  llm/              LLM providers (command, openai, manual, fake) and JSON extraction
  prompts/          Jinja2 prompt templates sent to the LLM
  builtin/          templates, styles, fonts, sample data shipped with the package
  web/              single-page web UI
tests/              pytest suite
examples/n8n/       importable n8n workflow
docs/               user and developer documentation
```

[docs/architecture.md](docs/architecture.md) explains how the pieces fit together and how to add an LLM provider.

## Making a change

1. Create a branch from `main`: `git checkout -b fix/short-description` (or `feat/`, `docs/`).
2. Make your change. Keep it focused: one bug or feature per pull request.
3. Add or update tests for behaviour changes.
4. Update the docs in `docs/` (and the README if it's user-facing) when you change commands, config keys, API endpoints or templates.
5. Add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) for anything a user would notice.
6. Make sure `pytest`, `ruff check .` and `ruff format --check .` pass.
7. Push and open a pull request. Fill in the template; link the issue it closes (`Closes #123`).

### Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(templates): add a "minimal" template
fix(check): count diacritics correctly in DOCX text
docs: explain the manual provider
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

### Code style

- Formatting and import order are handled by `ruff format` and `ruff check --fix`. Line length is 120.
- Type hints on public functions; `from __future__ import annotations` at the top of modules, like the existing code.
- Data that crosses layers goes through the Pydantic models in `models.py`.
- Keep the truthfulness guarantees intact: anything that changes tailoring must still pass through `core/guard.py`.

## Privacy rule: never commit real CV data

cvforge works with personal data. **Do not commit real names, career histories, job offers you applied to, or API keys**, not even in tests or screenshots. Use made-up people (the sample CV uses "Alex Morgan") and `example.com` addresses. `cvforge.toml`, `candidates/`, `llm-exchange/` and `.cvforge-cache/` are git-ignored for this reason; don't force-add them.

## Reviews and releases

A maintainer reviews every pull request; expect a first response within a week. CI must be green before merging. Pull requests are squash-merged, so the PR title becomes the commit message and should follow Conventional Commits.

Releases follow [Semantic Versioning](https://semver.org/). The maintainer moves the `Unreleased` changelog entries under a new version, bumps `version` in `pyproject.toml`, and tags `vX.Y.Z`.
