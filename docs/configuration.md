# Configuration

cvforge reads `cvforge.toml`. `cvforge init` and the web setup page create one for you; you can edit it by hand at any time.

## Where the file is found

In this order:

1. the path in the `CVFORGE_CONFIG` environment variable
2. `cvforge.toml` in the current directory or any parent directory
3. `~/.config/cvforge/cvforge.toml`

Relative paths in the file are resolved from the folder that contains it. With no file at all, the defaults below apply.

## Full reference

```toml
candidates_dir    = "./candidates"   # one sub-folder per person
default_candidate = ""               # used when --candidate is omitted (optional if there's only one)
default_template  = "ats-classic"
default_style     = "impact"
templates_dir     = "./templates"    # your own templates, added to the built-in ones
styles_dir        = "./styles"       # your own writing styles, added to the built-in ones

[llm]
provider    = "command"              # "command", "openai" or "manual" (see below)
command     = "claude -p"            # provider = "command"
timeout_s   = 600                    # per LLM call
base_url    = "http://localhost:11434/v1"   # provider = "openai"
model       = ""                     # provider = "openai"
api_key_env = "OPENAI_API_KEY"       # environment variable holding the API key
api_key     = ""                     # key stored in the file; api_key_env wins when that variable is set
vision      = false                  # the HTTP model accepts images → enables --visual-review
manual_dir  = "./llm-exchange"       # provider = "manual"
max_retries = 2                      # retries when an answer is not valid JSON or fails the grounding guard

[api]
token_env = "CVFORGE_TOKEN"          # if this env var is set, the API requires "Authorization: Bearer <value>"
```

When the setup page writes the file it uses owner-only permissions (`0600`), because it may contain an API key.

## LLM providers

### `command`: any CLI

The prompt is sent on stdin and the answer read from stdout.

```toml
[llm]
provider = "command"
command  = "claude -p"          # Claude Code
# command = "agy -p {prompt}"   # Google Antigravity (prompt as an argument)
# command = "gemini"            # Gemini CLI
# command = "codex exec -"      # OpenAI Codex CLI
# command = "ollama run qwen3"  # local model
# command = "mytool --in {prompt_file}"   # CLI that wants a file
```

Placeholders: `{prompt}` passes the prompt as an argument, `{prompt_file}` passes the path of a temporary file containing it. Without a placeholder the prompt goes to stdin.

### `openai`: any OpenAI-compatible HTTP API

Works with OpenAI, OpenRouter, Ollama, LM Studio, vLLM and similar.

```toml
[llm]
provider    = "openai"
base_url    = "http://localhost:11434/v1"
model       = "qwen3"
api_key_env = "OPENAI_API_KEY"
vision      = false
```

This is the provider to use in Docker.

### `manual`: copy and paste

No CLI or API key needed. Each prompt is written to `llm-exchange/prompt-N.md`; paste it into any chat window and save the reply as `llm-exchange/answer-N.md`. cvforge waits (up to `timeout_s`) for the answer file.

```toml
[llm]
provider   = "manual"
manual_dir = "./llm-exchange"
```

## Environment variables

| Variable | Effect |
|---|---|
| `CVFORGE_CONFIG` | Path of the config file to use |
| `CVFORGE_LLM_COMMAND` | Use the `command` provider with this command, e.g. `CVFORGE_LLM_COMMAND="ollama run qwen3" cvforge run offer.txt` |
| `CVFORGE_LLM_PROVIDER` | Override `llm.provider` (e.g. `manual`) |
| `CVFORGE_TOKEN` (or the name in `api.token_env`) | Bearer token required by the HTTP API; also allows remote access to the setup page |
| `OPENAI_API_KEY` (or the name in `llm.api_key_env`) | API key for the `openai` provider |

Check your setup with `cvforge doctor`.
