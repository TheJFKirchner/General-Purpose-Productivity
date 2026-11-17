---
name: commentary
description: Free-form AI commentary for dashboards, decks (.pptx), reports (.html/.md) and analysis folders, written from small summary tables by a separate writer with every number checked against the data, saved as one JSON file of id (C1, C2 ...), commentary and source. Use to plan commentary for a new deliverable, see what exists, generate or regenerate it, hand-edit it, or fill {{commentary:C1}} placeholders. Not for templated sentences like "the trend for this period is {trend}"; those belong in code.
---

# Commentary

## Is this the right tool?

Only for **free-form** commentary: judgement picks the drivers and the wording changes each time.

| Build it in code instead | Use this skill |
| --- | --- |
| "PMPM was ${pmpm}, {up/down} {pct}% vs last month" | "Which categories drove this month's change, and is it price or volume?" |
| KPI tile: "Allowed cost $45.8M (+4.2%)" | "Why did Medicare PMPM jump, and does it look one-off?" |

A sentence with a few blanks would be right every time: not this skill.

## How it works (every use)

| Principle | Meaning |
| --- | --- |
| Split into units | One unit per slide, section or panel: one question, its own tables, a length |
| Separate writer | Written in a separate headless session, never in the conversation doing the analysis or build |
| Summary tables only | The writer gets each unit's question, small aggregated tables (at most 50 rows × 15 columns), optional notes. Never raw data |
| Numbers from data | Every number is checked against the tables. Unchecked numbers are flagged, never called verified |
| Every unit says its source | Two to three sentences: which tables, which rows and columns, any filter or adjustment |
| Summary last | Executive summary: written last, only from the other units' checked commentary |
| Frozen once saved | Saved commentary is reused until regenerated on purpose |

## The output

One file beside the shell, rewritten every run: `commentary.json` (dashboards: `commentary_<snapshot>.json`). One item per piece of commentary, three fields:

```json
[
 {"id": "C1",
  "commentary": ["May paid $6.2M against $1.6M in a normal month."],
  "source": "From s2_summary, the May row and the normal-month row, column paid. Only claims paid at 10,000 or more are counted as large, as the notes state."}
]
```

| Field | What it is |
| --- | --- |
| `id` | `C1`, `C2`, `C3` ... Places the commentary: `{{commentary:C1}}` |
| `commentary` | The text, one string per bullet (a paragraph is one string) |
| `source` | Two to three sentences: the tables the figures come from, the rows and columns used, any adjustment (a filter, a computed difference or share). Written by the writer, for a reviewer |

- Dashboard unit with filters: one item per filter combination, plus a fourth field, `filters`.
- Failed its checks: `commentary` empty, `source` says so. Unchecked figures are counted in `source`.
- `commentary_outputs/`: the dated history behind this file. To place commentary, read `commentary.json`, not the history.

## Pick the path

| Deliverable | Start with | Then |
| --- | --- | --- |
| Analysis folder (`run.py`, `sections/`) | `references/analysis.md` | Nothing else: no interview, no plan, the shell is generated |
| Dashboard | `references/planning.md` | `references/shell.md`, `references/dashboard.md`, `references/running.md` |
| Deck | `references/planning.md` | `references/shell.md`, `references/deck.md`, `references/running.md` |
| Report (`.html`, `.md`) | `references/planning.md` | `references/shell.md`, `references/report.md`, `references/running.md` |

## Files in a project

| File | What it is |
| --- | --- |
| `commentary_plan.md` | How this deliverable handles commentary. Not used for analysis folders |
| `commentary_shell.json` | Every unit: where it sits, its question, tables, length. Never holds commentary |
| `commentary.json` | The output: id, commentary, source (above) |
| `commentary_outputs/commentary_<time>.json` | History: one per run that changes something |
| `commentary_run.md` | Report of the last run: written, failed, unverified |
| `run_commentary.py` | Dashboards only: the command to run after each refresh |

## Rules

- Existing project: read its plan (or the analysis `README.md`) and shell first.
- Never read data files or paste tables into the conversation. The scripts do that.
- Never launch the writer yourself; `generate.py` calls it.
- Missing filters, tables, snapshot column or questions: ask, never assume.
- Regenerate saved commentary only on purpose.
- After every run: report counts (generated, reused, failed, unverified, stale); show unverified bullets; ask keep, edit or drop.
- In a project (a folder with `project_plan.md` above the deliverable): commentary stays inside its deliverable; this skill never writes findings. After a run on refreshed data, run the `findings` skill's `findings.py check`: findings that cite this commentary's tables go stale and are reworded from the new commentary.
