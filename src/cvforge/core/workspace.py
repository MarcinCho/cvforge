"""Where a candidate's files live: candidates/<name>/{source_of_truth.md,.cache,applications}."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

from ..config import Config

SOURCE_NAMES = ("source_of_truth.md", "source-of-truth.md", "sot.md")


def slug(s: str, maxlen: int = 40) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ł", "l").replace("Ł", "L"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:maxlen].strip("-") or "x"


class Workspace:
    def __init__(self, cfg: Config, candidate: str | None = None):
        candidate = candidate or cfg.default_candidate
        if not candidate:
            found = list_candidates(cfg)
            if len(found) != 1:
                raise ValueError(
                    "choose a candidate with --candidate (or set default_candidate in cvforge.toml); "
                    f"found: {found or 'none'}"
                )
            candidate = found[0]
        self.cfg = cfg
        self.name = candidate
        self.dir = cfg.candidates_path / candidate
        if not self.dir.is_dir():
            raise FileNotFoundError(
                f"candidate folder not found: {self.dir} (create it with `cvforge init --candidate {candidate}`)"
            )

    @property
    def source_path(self) -> Path:
        for n in SOURCE_NAMES:
            if (self.dir / n).exists():
                return self.dir / n
        raise FileNotFoundError(f"no source_of_truth.md in {self.dir}")

    @property
    def profile_cache(self) -> Path:
        return self.dir / ".cache" / "profile.json"

    @property
    def applications_dir(self) -> Path:
        return self.dir / "applications"

    def new_application(self, company: str, title: str) -> Path:
        base = f"{date.today():%Y-%m-%d}_{slug(company or 'company', 24)}_{slug(title, 32)}"
        d, n = self.applications_dir / base, 2
        while d.exists():
            d, n = self.applications_dir / f"{base}-{n}", n + 1
        d.mkdir(parents=True)
        return d

    def application(self, app_id: str) -> Path:
        d = (self.applications_dir / app_id).resolve()
        if self.applications_dir.resolve() not in d.parents or not d.is_dir():
            raise FileNotFoundError(f"application {app_id!r} not found")
        return d

    def list_applications(self) -> list[str]:
        if not self.applications_dir.is_dir():
            return []
        return sorted((p.name for p in self.applications_dir.iterdir() if p.is_dir()), reverse=True)


def list_candidates(cfg: Config) -> list[str]:
    root = cfg.candidates_path
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and any((p / n).exists() for n in SOURCE_NAMES))
