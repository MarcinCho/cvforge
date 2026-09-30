# How scoring works

`cvforge score` (and the first step of `run`) gives an **overall score from 0 to 100** plus strengths, gaps, and matched and missing keywords. It combines a deterministic keyword check with an LLM rubric.

```
overall = 0.4 × keyword score + 0.6 × LLM rubric score
```

## Keyword score (40%)

The job analysis splits the offer's keywords into **must-have** and **nice-to-have**. The keyword score is the share of them found in your profile:

- must-have coverage counts 70%, nice-to-have 30% (must-have counts 100% if the offer lists no nice-to-haves)
- matching is fuzzy and uses a synonym table, so "AD" matches "Active Directory"
- an **evidence** table lets specific skills prove general ones, but not the other way round: Graylog proves "SIEM", while "SIEM" does not prove "Splunk"
- planned certificates and [unconfirmed skills](source-of-truth.md#unconfirmed-skills) never count; when an offer asks for one, it is listed under `unconfirmed_matches` ("confirm to use")

The synonym and evidence tables are `SYNONYMS` and `EVIDENCE` in [`src/cvforge/core/score.py`](../src/cvforge/core/score.py). Additions for other fields are welcome contributions.

## LLM rubric (60%)

A calibrated prompt ([`prompts/score.md.j2`](../src/cvforge/prompts/score.md.j2)) asks the LLM to rate four aspects from 0 to 100:

| Aspect | Weight |
|---|---|
| Hard requirements met | 40% |
| Seniority fit | 25% |
| Domain fit | 25% |
| Language requirements | 10% |

## Recommendation

| Overall | Recommendation |
|---|---|
| ≥ 75 | `apply` |
| ≥ 60 | `apply_with_notes` |
| ≥ 45 | `stretch` |
| < 45 | `skip` |

Use `--min-score N` on `run` (or `"min_score"` in the API) to skip CV generation for offers below a threshold.
