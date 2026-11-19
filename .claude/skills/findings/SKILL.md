---
name: findings
description: Use when work on a project that has a plan produces a result or answer worth quoting later, when the user says "note that" or "add to the findings", or before writing a deck, report or summary. Keeps findings.md, a list of cited findings, each tied to the plan item it bears on. No project plan, no findings.
---

# Findings

One file, `findings.md`: what the work has established against the project plan, and where each came from. A list, not a report. Nothing is ranked or judged here; the user decides later what gets used.

## What counts

- A finding: a result the work established, or a plan item settled by a person, that bears on a plan item.
- No project plan (the "Project plan" line in the map in the project's CLAUDE.md): no findings.
- Working choices (basis, filter, threshold, assumption) go in the plan, not here.
- Reference knowledge that outlives the project (definitions, gotchas, contract terms) is not a finding. Tell the user in one line.
- Bears on no plan item, or unsure: leave it out and say so in one line.

## The file

```markdown
# Findings

| # | Finding | Plan item | Source | As of | Added |
| --- | --- | --- | --- | --- | --- |
| 1 | May 2026 paid claims were $6.22M, 3.9 times a normal month (months are when claims were paid). | Goal 1: explain the May rise | `outputs/may-rise/`: `python run.py monthly`, metrics `may`, `times_normal` | Claims paid to Jun 2026 | 2026-11-16 |
| 2 | The May rise is a one-off. | Goal 1: explain the May rise | Finance lead, relayed by the user, 2026-11-16 (chat); not checked against data. See 3. | | 2026-11-16 |
| 3 | Checks finding 2: 80% of the May rise is one batch of late-paid claims for March care. | Goal 1: explain the May rise | `outputs/may-rise/`: `python run.py by_batch`, table `by_batch`, top row, column `share` | Claims paid to Jun 2026 | 2026-11-17 |
| 4 | Rerun on the July extract: findings 1 to 3 unchanged. | Goal 1: explain the May rise | `outputs/may-rise/`: `python run.py` | Claims paid to Jul 2026 | 2026-11-20 |
```

- Where: the "Findings" line in the map in the project's CLAUDE.md. No line: put it beside the plan and add `- Findings: [findings.md](findings.md)` under the map's "Project plan" line.
- No file yet: create it with the heading and the header row.

## Adding a finding

| Part | Rule |
| --- | --- |
| Finding | One sentence, plain words. One claim per row, with the figures that support it, its basis and a caveat if any. The period it describes goes here |
| Plan item | The goal or question it bears on, in the plan's own words or id |
| Source | Computed: the folder to run in, the command, and the metric or table name (with row and column for a table). A document: its name and date. A person: who and their role, who relayed it if not said to you, the date, where (chat, email, meeting), and "not checked against data" until a later row checks it |
| As of | The data the figure was computed on: the extract window or cut-off (claims paid to Jul 2026). Blank when it does not depend on data |
| Added | Today |

- No source: do not add it. Nothing from memory. A report claim with no metric behind it is not a finding.
- Add when the work produces something worth quoting later, or when the user says to. Do not rank or filter; do not ask for approval.
- Already in the list: skip.
- When the work's data bears on an existing row (supports it, narrows it or contradicts it, including a person's statement), add a row that starts `Checks finding N:` with the figure, add `See M.` to row N's Source, and tell the user in one line. That pointer is the only edit an old row ever gets.
- Rerun on new data: one `Rerun on <data>:` row, with the new As of, listing only the figures that changed (old to new), or "findings N to M unchanged". Add `See M.` to every row it touches.
- Append only. Numbers continue from the last row. Never edit or delete old rows, except to add `See M.` when a later row checks or reruns them.

## Using findings

- For reports and decks, write the bullets from findings; the commentary skill is only for dashboard text across many filters.
- Cite the row number where a finding is used (finding 12).
- Check As of. Older than the current data: rerun the source, or say the date with the finding.
- Not in the list and no source: not used.
