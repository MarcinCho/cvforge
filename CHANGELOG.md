# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-30

First public release.

### Added

- Pipeline: analyse a job offer → job-fit score (keywords + LLM rubric) → tailored CV per writing style → PDF/DOCX rendering → ATS and visual checks → insights about similar positions.
- LLM providers: any CLI (`command`), any OpenAI-compatible HTTP API (`openai`), and copy-and-paste (`manual`).
- Grounding guard: rejects CVs with invented numbers, uncited bullets, unknown skills or forbidden/unconfirmed terms, and retries with feedback.
- Source-of-truth rules: private HTML comments, forbidden terms (masked before the LLM), unconfirmed skills.
- Four writing styles (`impact`, `concise`, `narrative`, `technical`) and nine templates (`ats-classic`, `ats-modern`, `compact`, `corporate`, `executive`, `tech`, `timeline`, `elegant`, `sidebar`) with bundled OFL fonts.
- One-page mode with condensed tailoring and one-item-at-a-time trimming.
- Web UI with a setup wizard, HTTP API (OpenAPI at `/docs`) with optional bearer token, n8n example workflow, Dockerfile.
- One-click launchers for Linux, macOS and Windows.

[Unreleased]: https://github.com/MarcinCho/cvforge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MarcinCho/cvforge/releases/tag/v0.1.0
