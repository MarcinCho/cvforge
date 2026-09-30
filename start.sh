#!/usr/bin/env bash
# cvforge launcher for Linux/macOS: installs on first run, then opens cvforge in your browser.
set -e
cd "$(dirname "$0")"

say() { printf '\n  %s\n' "$*"; }

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  say "cvforge needs Python 3.11 or newer."
  if [ "$(uname)" = "Darwin" ]; then say "Install it from https://www.python.org/downloads/ and run this again."
  else say "Install it with:  sudo apt install python3 python3-venv   (then run this again)"; fi
  read -r -p "  Press Enter to close…" _ || true; exit 1
fi

# (re)install when first run or when the app was updated
STAMP=".venv/.installed-$(cksum pyproject.toml | cut -d' ' -f1)"
if [ ! -f "$STAMP" ]; then
  say "Setting up cvforge (first start takes 1–2 minutes)…"
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -e .
  rm -f .venv/.installed-*; touch "$STAMP"
fi

# the PDF engine needs the Pango text library from the system
if ! .venv/bin/python -c "import weasyprint" >/dev/null 2>&1; then
  say "One more thing: cvforge needs the 'Pango' library to create PDFs."
  if [ "$(uname)" = "Darwin" ]; then
    say "Install Homebrew (https://brew.sh), then run:  brew install pango"
  else
    say "Run:  sudo apt install libpango-1.0-0 libpangoft2-1.0-0 poppler-utils"
  fi
  say "Then start cvforge again."
  read -r -p "  Press Enter to close…" _ || true; exit 1
fi

exec .venv/bin/cvforge start
