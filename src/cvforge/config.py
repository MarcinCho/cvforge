"""Configuration: cvforge.toml in the working directory (or $CVFORGE_CONFIG, or ~/.config/cvforge)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

PACKAGE_DIR = Path(__file__).parent
BUILTIN_TEMPLATES = PACKAGE_DIR / "builtin" / "templates"
BUILTIN_STYLES = PACKAGE_DIR / "builtin" / "styles"

DEFAULT_CONFIG = """\
# cvforge configuration
candidates_dir = "./candidates"
default_candidate = ""
default_template = "ats-classic"
default_style = "impact"
# extra template/style folders (added to the built-in ones)
templates_dir = "./templates"
styles_dir = "./styles"

[llm]
# "command": any CLI that reads a prompt on stdin and prints the answer, e.g.
#   "claude -p", "gemini", "codex exec -", "ollama run qwen3"
#   use {prompt_file} or {prompt} in the command if your CLI needs the prompt as a file/argument
# "openai": any OpenAI-compatible HTTP API (OpenAI, OpenRouter, Ollama, LM Studio, vLLM)
# "manual": prompts are written to manual_dir/prompt-N.md; paste them into any chat UI and save
#           the reply as manual_dir/answer-N.md (no CLI or API key needed)
provider = "command"
command = "claude -p"
timeout_s = 600
# base_url = "http://localhost:11434/v1"
# model = "qwen3"
# api_key_env = "OPENAI_API_KEY"
# manual_dir = "./llm-exchange"
# vision = false   # set true if the HTTP model accepts images (enables --visual-review)

[api]
# if this env var is set, the API requires "Authorization: Bearer <value>"
token_env = "CVFORGE_TOKEN"
"""


class LLMConfig(BaseModel):
    provider: str = "command"
    command: str = "claude -p"
    timeout_s: int = 600
    base_url: str = "http://localhost:11434/v1"
    model: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""  # stored in cvforge.toml; api_key_env wins when that variable is set
    vision: bool = False
    manual_dir: str = "./llm-exchange"
    max_retries: int = 2


class APIConfig(BaseModel):
    token_env: str = "CVFORGE_TOKEN"


class Config(BaseModel):
    root: Path = Field(default_factory=Path.cwd)
    path: Path | None = Field(None, exclude=True, description="The cvforge.toml this was loaded from")
    candidates_dir: Path = Path("./candidates")
    default_candidate: str = ""
    default_template: str = "ats-classic"
    default_style: str = "impact"
    templates_dir: Path = Path("./templates")
    styles_dir: Path = Path("./styles")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    def resolve(self, p: Path) -> Path:
        p = p.expanduser()
        return p if p.is_absolute() else (self.root / p).resolve()

    @property
    def instance_id(self) -> str:
        """Identifies one installation/data folder (so `cvforge start` only reuses its own server)."""
        import hashlib

        return hashlib.sha1(str(self.root.resolve()).encode()).hexdigest()[:12]

    @property
    def candidates_path(self) -> Path:
        return self.resolve(self.candidates_dir)

    @property
    def template_dirs(self) -> list[Path]:
        return [self.resolve(self.templates_dir), BUILTIN_TEMPLATES]

    @property
    def style_dirs(self) -> list[Path]:
        return [self.resolve(self.styles_dir), BUILTIN_STYLES]


def find_config_file(start: Path | None = None) -> Path | None:
    if env := os.environ.get("CVFORGE_CONFIG"):
        return Path(env)
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        if (d / "cvforge.toml").exists():
            return d / "cvforge.toml"
    user = Path.home() / ".config" / "cvforge" / "cvforge.toml"
    return user if user.exists() else None


def load_config(path: Path | None = None) -> Config:
    path = path or find_config_file()
    if path is None:
        cfg = Config()
    else:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        cfg = Config(root=path.parent.resolve(), path=path.resolve(), **data)
    if not Path(cfg.llm.manual_dir).expanduser().is_absolute():
        cfg.llm.manual_dir = str(cfg.resolve(Path(cfg.llm.manual_dir)))
    # env overrides, handy for n8n/docker and for friends trying another CLI quickly
    if cmd := os.environ.get("CVFORGE_LLM_COMMAND"):
        cfg.llm.provider, cfg.llm.command = "command", cmd
    if prov := os.environ.get("CVFORGE_LLM_PROVIDER"):
        cfg.llm.provider = prov
    return cfg


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def save_config(cfg: Config, path: Path | None = None) -> Path:
    """Write cfg as cvforge.toml (used by the web setup page). Paths are kept relative when possible."""
    path = path or cfg.path or (cfg.root / "cvforge.toml")

    def rel(p: Path) -> str:
        try:
            return "./" + str(Path(p).resolve().relative_to(cfg.root.resolve()))
        except ValueError:
            return str(p)

    llm = cfg.llm.model_dump()
    llm["manual_dir"] = rel(Path(llm["manual_dir"]))
    lines = [
        "# cvforge configuration (written by the setup page — safe to edit by hand)",
        f"candidates_dir = {_toml_value(rel(cfg.resolve(cfg.candidates_dir)))}",
        f"default_candidate = {_toml_value(cfg.default_candidate)}",
        f"default_template = {_toml_value(cfg.default_template)}",
        f"default_style = {_toml_value(cfg.default_style)}",
        f"templates_dir = {_toml_value(rel(cfg.resolve(cfg.templates_dir)))}",
        f"styles_dir = {_toml_value(rel(cfg.resolve(cfg.styles_dir)))}",
        "",
        "[llm]",
        *(f"{k} = {_toml_value(v)}" for k, v in llm.items() if not (k == "api_key" and not v)),
        "",
        "[api]",
        f"token_env = {_toml_value(cfg.api.token_env)}",
        "",
    ]
    # the file may hold an API key: owner-only permissions, also when it already existed
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    cfg.path = path
    return path
