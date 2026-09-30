# Templates and styles

A **template** decides how the CV looks (PDF and DOCX). A **writing style** decides how the LLM writes it. Every run can combine several of each: `-s impact -s concise -t ats-classic -t ats-modern` produces four files.

## Built-in templates

| Template | Look | ATS | Pages |
|---|---|---|---|
| `ats-classic` | Plain single column, black headings, thin rules. The safest choice. | ✅ | ≤2 |
| `ats-modern` | Navy accent, Lato, skills near the top. | ✅ | ≤2 |
| `compact` | Dense one-pager. | ✅ | 1 |
| `corporate` | Calibri-style (Carlito), light header band, blue accent bars. PDF and Word look the same. | ✅ | ≤2 |
| `executive` | Serif (Cambria-style Caladea), centred header, burgundy accents. For senior and management roles. | ✅ | ≤2 |
| `tech` | Monospace headings and dates, skills as tags first. For engineering roles. | ✅ | ≤2 |
| `timeline` | Experience and education on a vertical timeline with teal markers. | ✅ | ≤2 |
| `elegant` | Airy, serif name and headings, hairline rules. | ✅ | ≤2 |
| `sidebar` | Two columns with a tinted sidebar. For sending straight to a person, not for ATS uploads (its DOCX stays single-column). | ⚠️ design | ≤2 |

See them: `cvforge templates preview` renders a sample CV with every template into `template-previews/` (add `--cv my.cv.json` to use your own). The web UI template picker shows thumbnails.

An auto-fit step tightens spacing when a CV spills onto a nearly empty last page.

## Built-in writing styles

| Style | What it does |
|---|---|
| `impact` | Results first: bullets lead with a measurable outcome, confident active voice. |
| `concise` | Short, scannable bullets. |
| `narrative` | Flowing, story-like summary and bullets. |
| `technical` | Tools, systems and technical depth up front. |

`cvforge styles list` shows the full descriptions.

## One-page CVs

Use `--one-page` / `-1` (CLI), `"one_page": true` (API), or tick **One page** in the web UI. It works with any template:

1. The LLM is asked for a strict one-page version: a 2-sentence summary, 4–5 bullets for the latest role, only relevant skills.
2. The layout tightens spacing slightly.
3. If it still doesn't fit, cvforge removes the least important items **one at a time** until it does: projects, then bullets of older roles, lower-ranked bullets, extra skills, education notes and certificates. Nothing is rewritten or invented.

The check report lists exactly what was removed (`one_page_fit`), and one-page files get a `_1p` suffix.

## Making your own template

```bash
cvforge templates new my-template --from ats-modern
```

This creates `templates/my-template/` (next to your `cvforge.toml`) with:

- **`style.css`**: the look. Fonts, colours and spacing live in `:root` variables (`--font`, `--size`, `--accent`…).
- **`template.toml`**:

  ```toml
  name = "my-template"
  description = "One line shown in the picker."
  ats_safe = true
  max_pages = 2
  sections = ["summary", "skills", "experience", "projects", "education", "certifications", "languages"]
  skill_tags = false          # true renders skills as tags
  fonts = ["Lato"]            # bundled: NotoSans, NotoSerif, NotoSansMono, Lato, Carlito, Caladea

  [docx]                      # the Word version
  font = "Calibri"
  body_size = 10.5
  name_size = 22
  heading_size = 12
  accent = "1F4E79"
  muted = "555555"
  margins_cm = 1.7
  heading_rule = true
  ```

  Any extra keys are available in the HTML as `template.<key>` (the sidebar template uses `sidebar` and `main` this way).
- **`cv.html.j2`** (optional): the HTML structure, a Jinja2 template. Delete it to use the shared one in `src/cvforge/builtin/templates/_shared/`.

### Bringing your own font

```toml
[[font]]
family = "Inter"
file = "fonts/Inter-Regular.ttf"   # relative to the template folder
[[font]]
family = "Inter"
weight = 700
file = "fonts/Inter-Bold.ttf"
```

Make sure the font's license allows embedding in PDFs.

### Rules for ATS-safe templates

Keep ATS templates single-column, with real text, no tables or text boxes, and letter-spacing ≤ 0.05em. The checks flag each of these problems, so test with:

```bash
cvforge templates preview my-template
```

## Making your own writing style

Add `styles/my-style.yaml` next to your `cvforge.toml`:

```yaml
name: my-style
description: One line shown in the picker.
instructions: |
  - Bullet-point rules for the LLM.
  - They are appended to the tailoring prompt.
```

## What the checks look at

Each rendered file gets a `*.check.json` report. Checks include:

- text extraction round trip and encoding (`text_encoding`), including letter-by-letter text
- diacritics survive (`diacritics`)
- the e-mail can be parsed and contact details are in the body, not a header (`contact_email_parse`, `docx_contact_in_body`)
- standard section headings are found (`section_headings`)
- target keywords survive extraction (`keywords_extractable`)
- page count, overflow and minimum font size (`page_count`, `overflow`, `min_font_size`)
- fonts are embedded (`fonts_embedded`)
- no tables or text boxes in the DOCX (`docx_tables`, `docx_textboxes`)
- the template is ATS-safe (`template_ats_safe`)
- grounding: no forbidden or unconfirmed terms (`grounding`)
- optional: an LLM looks at the page images (`visual_review`, needs a vision model)

## Contributing a template or style

Built-in templates live in `src/cvforge/builtin/templates/<name>/` and styles in `src/cvforge/builtin/styles/`. To propose one, add it there, run `cvforge templates preview <name>`, attach the page-1 PNG to your pull request, and add it to the tables on this page. See [CONTRIBUTING.md](../CONTRIBUTING.md).
