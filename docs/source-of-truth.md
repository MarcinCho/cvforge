# Writing your source of truth

The source of truth is one Markdown file with **everything** about your career. cvforge never invents facts: every CV it produces is built from, and checked against, this file. The richer it is, the better your CVs.

It lives at `candidates/<name>/source_of_truth.md` (`source-of-truth.md` and `sot.md` also work). `cvforge init --candidate <name>` creates it from a [template](../src/cvforge/builtin/source_of_truth_template.md), and the web setup page has an editor for it.

## What to put in it

- Contact details, links, and any consent clause employers in your country expect.
- Several positioning paragraphs for the kinds of roles you target.
- Every job: employer, dates, title, and **many** concrete bullets. Numbers matter (users, devices, %, time saved, budget, team size): the guard only lets a number into a CV if it appears in the cited source bullet.
- Projects, education, certificates (mark planned ones as planned), languages with levels, skills.
- Any language works. CVs are written in the job offer's language unless you pass `--lang`.

## Private notes

Anything inside an HTML comment is stripped **before** the text reaches the LLM:

```markdown
- Rolled out a new POS system to 120 stores <!-- the client was Globex; internal only -->
```

## Forbidden terms

Names that must never appear in a CV (a confidential client, a former employer's internal project...). Declare them in any of these ways:

```markdown
## cvforge rules

- forbidden: Globex, Project Nightingale
```

```markdown
<!-- (Globex) — do not include in CV -->
```

The Polish phrase `NIE umieszczać w CV` in a comment works the same way.

Forbidden terms are masked as `[REDACTED]` before the LLM sees the source, and any CV that contains them is rejected, including CVs you send to `POST /api/render` yourself.

## Unconfirmed skills

Skills you might have but can't back up yet:

```markdown
## cvforge rules

- unconfirmed: ISO 27001, Intune
```

or a list under a heading that contains "unconfirmed" (or the Polish "do potwierdzenia").

They are **never** used in a CV. When an offer asks for one, the score report lists it as "confirm to use", so you know what to add to your source of truth.

## The extracted profile

On first use the LLM turns the file into a structured profile, cached at `candidates/<name>/.cache/profile.json`. It is rebuilt automatically when the file changes (or with `cvforge ingest --force`). Check what cvforge understood with:

```bash
cvforge ingest --show
```

## Truthfulness guarantees

The grounding guard (`core/guard.py`) rejects a generated CV and asks the LLM to try again, with the list of problems, when:

- a bullet doesn't cite a real source bullet
- a number or percentage doesn't appear in the cited source
- a skill isn't in your profile
- a forbidden or unconfirmed term appears
