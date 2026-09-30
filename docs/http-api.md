# HTTP API and n8n

`cvforge serve` starts the web UI and a JSON API on `http://127.0.0.1:8765`. Interactive OpenAPI docs are at [`/docs`](http://127.0.0.1:8765/docs).

## Authentication

If the `CVFORGE_TOKEN` environment variable is set (the name is configurable with `api.token_env`), every `/api/*` and `/files/*` request needs:

```
Authorization: Bearer <token>
```

(`?token=<token>` in the URL also works, for download links.) Without the variable the API is open, which is fine on `127.0.0.1` but **not** when you bind to `0.0.0.0`. See [SECURITY.md](../SECURITY.md).

The setup endpoints (`/api/setup/*`, `/api/candidates/*`) only accept requests from the local machine unless a token is set.

Errors use standard status codes: `400` bad input, `401` bad token, `403` remote setup without a token, `404` unknown candidate/application/template, `502` the LLM failed.

## One-shot pipeline

`POST /api/run`

```json
{
  "offer": "<offer text or URL>",
  "candidate": "anna",
  "styles": ["impact"],
  "templates": ["ats-classic"],
  "min_score": 55,
  "insights": true,
  "one_page": false,
  "lang": null
}
```

Only `offer` (or an already-parsed `job`) is required; everything else falls back to `cvforge.toml`. The response contains the score, each variant with its check results, the insights, and download URLs under `files`.

## Single steps

| Method and path | Body | Returns |
|---|---|---|
| `POST /api/job` | `{"offer": ...}` | analysed JobOffer |
| `POST /api/score` | `{"offer": ..., "candidate": ...}` | ScoreReport |
| `POST /api/insights` | `{"offer": ..., "candidate": ...}` | InsightsReport |
| `POST /api/ingest` | `{"candidate": ..., "force": false}` | summary of the extracted profile (counts, forbidden and unconfirmed terms) |
| `POST /api/render` | `{"cv": <TailoredCV JSON>, "templates": [...], "one_page": false}` | rendered files and checks, **no LLM call** |

`/api/score` and `/api/insights` also accept `"job"` (a JobOffer from `/api/job`) instead of `"offer"` to skip re-analysing it.

`/api/render` is for CVs written by something else, such as your own n8n AI agent. Forbidden and unconfirmed terms are still flagged as `fail`.

## Step by step (used by the web UI)

| Method and path | Purpose |
|---|---|
| `POST /api/applications` | analyse + score an offer, create the application folder |
| `GET /api/applications/{candidate}` | list applications |
| `GET /api/applications/{candidate}/{id}` | load one application |
| `POST /api/applications/{candidate}/{id}/variants` | generate CVs: `{"styles": [...], "templates": [...], "one_page": false}` |
| `POST /api/applications/{candidate}/{id}/insights` | add insights |
| `GET /files/{candidate}/{id}/{file}` | download a PDF, DOCX, preview image or `insights.md` |

## Other endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/health` | liveness check (no auth) |
| `GET /api/meta` | candidates, templates, styles and defaults |
| `GET /api/templates/{name}/preview.png` | template thumbnail |
| `GET /api/setup/status`, `POST /api/setup/llm`, `POST /api/setup/llm/test`, `POST /api/setup/defaults`, `GET /api/setup/sot-template` | setup wizard |
| `POST /api/candidates`, `GET`/`PUT /api/candidates/{name}/source` | create a candidate, read/write the source of truth |

## n8n

[`examples/n8n/cvforge_workflow.json`](../examples/n8n/cvforge_workflow.json) is an importable workflow: a webhook receives an offer → `POST /api/run` → if a CV was generated, download the PDF and reply with the score, gaps and links. It reads `CVFORGE_URL` and `CVFORGE_TOKEN` from n8n's environment.

Run cvforge where n8n can reach it:

```bash
CVFORGE_TOKEN=change-me cvforge serve --host 0.0.0.0
```

or use the [Docker image](getting-started.md#option-3-docker) with the `openai` provider.

## Example with curl

```bash
curl -s http://127.0.0.1:8765/api/score \
  -H "Authorization: Bearer $CVFORGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"offer": "https://example.com/job/123"}' | jq .overall
```
