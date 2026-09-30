# Getting started

## Option 1: one-click launcher (no technical knowledge needed)

1. **Get cvforge:** download the repository as a ZIP from GitHub (**Code → Download ZIP**) and unpack it, or `git clone` it.
2. **Start it:**
   - **macOS:** double-click `start.command`.
   - **Windows:** double-click `start.bat`.
   - **Linux:** double-click `start.sh` (or run `./start.sh`).

   The first start creates a private Python environment and installs everything (1–2 minutes). Then your browser opens cvforge. If Python or the PDF library is missing, the launcher tells you exactly what to install; you only do that once.
3. **Follow the Setup page** in the browser:
   1. **AI model:** click the AI you use (Claude, Antigravity, Gemini, ChatGPT/Codex, Ollama…) → **Test connection** → **Save**. Tools found on your computer are marked "found". No AI tool at all? Choose **Copy & paste**.
   2. **Career data:** type your name → **Add**, then paste your career history into the big box (or **Upload** a file) → **Save & analyse**. See [Writing your source of truth](source-of-truth.md).
   3. **Defaults:** pick a writing style and template → **Done**.
4. **Create CVs:** paste a job offer (text or link) → **Analyse & score** → pick style and template (tick **One page** if you want) → **Generate CV** → download the PDF or Word file.

Keep the small terminal window open while you use cvforge; closing it stops cvforge. Next time, double-click the start file again.

## Option 2: install with pip

### 1. System libraries

cvforge renders PDFs with [WeasyPrint](https://weasyprint.org/) and reads them back with `pdftotext`:

```bash
# Debian / Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 poppler-utils
```

```bash
# macOS
brew install pango poppler
```

Windows: follow the [WeasyPrint Windows guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows) and install Poppler, or use the launcher / Docker.

### 2. cvforge (Python 3.11+)

```bash
pipx install git+https://github.com/MarcinCho/cvforge.git
```

or, from a clone:

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

### 3. First run

Work in a folder of your own (your data lives there, not in the cvforge source):

```bash
mkdir ~/my-cvs && cd ~/my-cvs
cvforge setup            # web setup in the browser
```

or entirely on the command line:

```bash
cvforge init --candidate anna        # creates cvforge.toml and candidates/anna/source_of_truth.md (a template)
$EDITOR candidates/anna/source_of_truth.md
cvforge doctor                       # checks the LLM connection and PDF rendering
cvforge run offer.txt                # or a URL, or '-' to read the offer from stdin
```

Already have a career file? `cvforge init --candidate anna --source my_career.md --link` uses it in place.

## Option 3: Docker

The image runs the web UI and HTTP API. LLM CLIs on your host aren't available inside the container, so use the `openai` provider (OpenAI, OpenRouter, or Ollama/LM Studio on the host).

```bash
docker build -t cvforge .
docker run --rm -p 8765:8765 -v "$PWD:/data" -e CVFORGE_TOKEN=change-me -e OPENAI_API_KEY cvforge
```

Mount the folder that holds your `cvforge.toml` and `candidates/` at `/data`.

## What you get

Everything for one application goes into `candidates/<name>/applications/<date>_<company>_<role>/`:

- the offer text and `job.json` (the analysed offer)
- `score.json` (fit score, strengths, gaps, keywords)
- the tailored CV JSON for each style
- PDF and DOCX for each style × template, their `*.check.json` reports and `previews/` page images
- `insights.md` (similar titles, typical requirements, what to learn, likely interview topics)

List them with `cvforge apps`.

## Next steps

- Connect your LLM: [Configuration](configuration.md)
- Pick or design a look: [Templates and styles](templates-and-styles.md)
- Automate it: [HTTP API and n8n](http-api.md)
