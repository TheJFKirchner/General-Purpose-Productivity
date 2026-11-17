---
name: facts
description: Keeps facts.md, a plain running list of facts the work has established, each with where it came from (script, section, table, document). Use to note a fact while doing analysis, dashboard or other data work, when the user says "note that" or "add that to the facts", or to look up what is already known before writing a deck, report or summary. A collection only. It does not rank, judge or check facts, and a fact with no source is not added.
---

# Facts

One file, `facts.md`: things the work has established and where each came from. A list, not a report. Nothing is ranked or judged here; the user decides later what gets used.

## The file

```markdown
# Facts

| # | Fact | Source | As of | Added |
| --- | --- | --- | --- | --- |
| 1 | May 2026 paid claims were $6.22M, 3.9 times a normal month. | `analyses/may-rise/sections/s1_monthly.py`, table `s1_summary`, May row, columns paid and times_normal | Jan to Jun 2026 | 2026-11-16 |
| 2 | Month-end close excludes voided claims. | Controller, email of 12 Nov 2026 | | 2026-11-16 |
```

- Where: beside the project plan if there is one, otherwise the top folder of the work. A `facts.md` already here or in a folder above: use that one.
- No file yet: create it with the heading and the header row.

## Adding a fact

| Part | Rule |
| --- | --- |
| Fact | One sentence, plain words, with its figure. One fact per row |
| Source | The file that produced it (script, section file, query) and where the figure sits (table, row, column). A person or document: who or which, and the date. Enough for someone to find it in a minute |
| As of | The data period or date the fact is true for. Blank when it does not depend on data |
| Added | Today |

- No source: do not add it. Nothing from memory.
- Add when the work produces something worth quoting later, or when the user says to. Do not test, rank or filter; do not ask for approval.
- Already in the list: skip.
- New data gives a new figure: add a new row with the new "As of". Never edit or delete old rows.
- Append only. Numbers continue from the last row.

## Using facts

- Before writing a deck, report or summary: read `facts.md`.
- Cite the row number where a fact is used (fact 12).
- Check "As of". Older than the current data: re-read the source, or say the date with the fact.
- Not in the list and no source: not used.
