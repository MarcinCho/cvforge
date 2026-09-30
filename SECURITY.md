# Security policy

## Supported versions

cvforge is pre-1.0. Security fixes go into the latest release only.

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1 | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report it privately through GitHub: go to the repository's **Security** tab → **Report a vulnerability** ([direct link](https://github.com/MarcinCho/cvforge/security/advisories/new)).

Please include:

- what the problem is and what an attacker could do with it
- steps to reproduce (a minimal `cvforge.toml`, command or HTTP request)
- the cvforge version (`pip show cvforge`), OS and Python version

You should get a first answer within 7 days. Once a fix is released, the advisory is published and you are credited unless you prefer not to be.

## What counts as a vulnerability

cvforge handles personal data (career histories, contact details) and may hold LLM API keys, so these are in scope:

- reading or writing files outside the configured `candidates/` folder (path traversal in `/files/...` or candidate/application names)
- bypassing the `CVFORGE_TOKEN` bearer token, or reaching the setup endpoints from a non-local address without the token
- leaking the API key stored in `cvforge.toml`, or a forbidden term (redaction) reaching the LLM or a generated CV
- command injection through the `command` LLM provider from data that isn't the user's own config

Out of scope: an LLM producing bad or untrue text that passes the checks (please open a normal issue for that), and problems that need an attacker who can already edit your `cvforge.toml`.

## Running cvforge safely

- `cvforge serve` listens on `127.0.0.1` by default. If you use `--host 0.0.0.0` (Docker, n8n on another machine), **set `CVFORGE_TOKEN`**; without it the API is open to anyone who can reach the port.
- `cvforge.toml` is written with owner-only permissions (`0600`) because it may contain an API key. Prefer `api_key_env` (an environment variable) over storing the key in the file.
- Never commit `cvforge.toml`, `candidates/` or `llm-exchange/`. They are in `.gitignore` for that reason.
