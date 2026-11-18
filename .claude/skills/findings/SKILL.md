---
name: findings
description: Use when work on a project that has a plan produces a result or answer worth quoting later, when the user says "note that" or "add to the findings", or before writing a deck, report or summary. Keeps findings.md, a list of cited findings, each tied to the plan item it bears on. No project plan, no findings.
---

# Findings

One file, `findings.md`: what the work has established against the project plan, and where each came from. A list, not a report. Nothing is ranked or judged here; the user decides later what gets used.

## Finding or fact

| | Finding: a result against the plan | Fact: reference knowledge |
| --- | --- | --- |
| Test | Did the work establish it (computed, checked or settled), and does it answer, confirm, rule out, block or change an item in the plan? | Would someone starting other work here want to know it beforehand? |
| Typical | The answer to a plan question, with its figure; a check that passed or failed; a negative result the plan asked about; something that blocks or changes a plan item | How data and systems behave, gotchas, methodology, metric definitions, reference numbers (headline metrics, agreed assumptions, contract terms), standing requirements |
| Goes in | `findings.md` (this skill) | The session facts file, then the wiki (`brain-intake`, `add-to-main-agent.md`) |

| Case | Rule |
| --- | --- |
| No project plan | No findings. Facts are still recorded as facts |
| Given, not established by the work (a contract term, another team's assumption) | A fact, not a finding, even when the plan depends on it |
| A decision made for this project | Not a finding; it belongs in the plan |
| A result that bears on no plan item | Not a finding. Tell the user in one line |
| It is both | Record it in both places. The finding carries this project's result; the fact carries the general lesson |
| Unsure it is a finding | Leave it out and tell the user in one line |

## The file

```markdown
# Findings

| # | Finding | Plan item | Source | As of | Added |
| --- | --- | --- | --- | --- | --- |
| 1 | May 2026 paid claims were $6.22M, 3.9 times a normal month. | Goal 1: explain the May rise | `analyses/may-rise/sections/s1_monthly.py`, table `s1_summary`, May row, columns paid and times_normal | Jan to Jun 2026 | 2026-11-16 |
| 2 | The rise is one batch of late-paid claims, not a change in volume. | Goal 1: explain the May rise | `analyses/may-rise/sections/s3_batch.py`, table `s3_by_batch` | Jan to Jun 2026 | 2026-11-16 |
```

- Where: beside the project plan. A `findings.md` already here or in a folder above: use that one.
- No file yet: create it with the heading and the header row.

## Adding a finding

| Part | Rule |
| --- | --- |
| Finding | One sentence, plain words, with its figure. One finding per row |
| Plan item | The goal, question or step in the plan it bears on, in the plan's own words or id. Bears on nothing in the plan: it is not a finding (tell the user in one line if it looks important) |
| Source | The file that produced it (script, section file, query) and where the figure sits (table, row, column). A document: its name and date. A person: who, and the date. Enough for someone to find it in a minute |
| As of | The data period or date the finding is true for. Blank when it does not depend on data |
| Added | Today |

- No source: do not add it. Nothing from memory.
- Add when the work produces something worth quoting later, or when the user says to. Do not rank or filter; do not ask for approval.
- Already in the list: skip.
- New data gives a new figure: add a new row with the new "As of". Never edit or delete old rows.
- Append only. Numbers continue from the last row.

## Using findings

- Before writing a deck, report or summary: read `findings.md`.
- Cite the row number where a finding is used (finding 12).
- Check "As of". Older than the current data: re-read the source, or say the date with the finding.
- Not in the list and no source: not used.
