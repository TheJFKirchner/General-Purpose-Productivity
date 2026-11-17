# Convert an existing process

For an analysis that exists in another form (SQL scripts, notebooks, a workbook, a hand-built report) and should become an analysis folder giving the same answer.

## Who does what

The main conversation does not read the old process or write the new files.

| Main conversation | Subagents |
| --- | --- |
| Talks to the user, holds the gates | Explore the old process (read-only) |
| Writes the brief, conversion map and storyline in `README.md` | Write `config.py`, `sql/`, `sections/` |
| Briefs each subagent, reads its short return | Reconcile new figures against the old output |
| Decides what is kept and dropped | |

No subagent tool: stop and tell the user. Do the reading and rewriting in the main conversation only if they say to.

## Steps

| # | Step | Who | Gate |
| --- | --- | --- | --- |
| 1 | Scope | Main | |
| 2 | Explore | Subagents, in parallel | |
| 3 | Brief and conversion map | Main | **Gate 1:** user approves both |
| 4 | Rewrite | Subagents | |
| 5 | Reconcile | Subagent | **Gate 2:** figures match, or each difference is explained and the user agrees |
| 6 | Report, commentary, cold read, hand-over | As `SKILL.md` steps 5 to 8 | Gate 3 |

Auto mode (`auto.md`) applies as usual: every keep-or-drop decision and every unexplained difference is an assumption in the note.

### 1. Scope

Ask once:

- Where the process lives (folders, files, queries, the workbook).
- What it produces, for whom, how often.
- The most recent output known to be right. New figures are checked against it.
- What must not change (a definition, a figure, a layout the reader relies on).

### 2. Explore

One read-only subagent per part, run together. Split by part, not by file count.

| Part | Finds |
| --- | --- |
| Data in | Every source: the query or file, what one row is, the filters and dates applied |
| Calculations | Each step from source to final figures, in order, the rule in plain words |
| Output | Every table, chart and written statement in the old output, and which calculation feeds it |

Explorer brief:

```
Read-only. Do not change or run anything that writes.
Process: <paths>. Your part: <data in | calculations | output>.
Return at most 40 lines, in this form:
- Items: one line each: name, where it is (file and line or sheet and range), what it does in plain words
- Parameters: dates, thresholds and hard-coded values, with where they are set
- Manual steps: anything a person does by hand
- Oddities: anything that looks wrong, duplicated or unused
- Not read: what you could not open or follow
```

### 3. Brief and conversion map

- Brief (`request.md`): the Question is what the old output answers. Nobody can say what it answers: settle that with the user first.
- Map: `README.md`, "Storyline". One row per old output item:

```markdown
| Old item | Becomes | Why |
| --- | --- | --- |
| Query `paid_by_month.sql` | Source `claims`, `sql/claims.sql` | |
| Tab "Provider pivot" | s2 | Proves the provider claim |
| Tab "All fields summary" | Dropped | Answers no part of the question |
| Manual copy of totals into the email | Commentary | Written by the commentary step |
```

- Every old item: kept, merged or dropped. Dropped items get a reason.
- The limits in `storyline.md` hold. A converted report is not a copy of every old tab.
- Manual steps become parameters in `config.py` or code in a section. None stay manual.

### 4. Rewrite

Create the folder (`sources.md`), then one writer subagent per file:

| Order | Subagent | Writes |
| --- | --- | --- |
| First | Sources | `config.py` (`SOURCES`, `PARAMS`, `run_query`), `sql/`, and `sections/shared.py` if several sections need the same step |
| Then, in parallel | One per section | Its own `sections/sN_<name>.py`, without `charts()` |

Writer brief:

```
Read <skill>/references/sections.md (and sources.md for the sources writer). Follow them.
Analysis folder: <path>. Write only: <the file or files>.
From the conversion map: <its row or rows>.
Explorer notes for this part: <the relevant lines>.
Reproduce the old logic exactly; do not improve it. Where the old logic looks wrong, keep it and report it.
Run `python run.py <sN>` and return: the file written, the summary table as printed, anything you could not reproduce.
```

### 5. Reconcile

One subagent compares the new section figures with the old known-good output, same period and parameters.

```
Read-only except for running `python run.py`.
Old output: <path>. New analysis: <path>.
Return a table: figure | old | new | difference | reason.
Reason is one of: match, rounding, or the specific cause you found. "Unknown" if you cannot find it.
```

| Result | Do |
| --- | --- |
| All match or rounding | Record the table in `README.md`, "Hand-over notes". Go on |
| A difference with a found cause | Show the user. Their choice: reproduce the old figure, or keep the new one and say so in the report |
| Unknown | Stop. Do not build the report |

A flaw found in the old logic: report it to the user. Never fix it silently.

## Rules

- Never edit or delete the old process.
- No HTML until the figures reconcile.
- Subagent returns are reports, not proof. The reconcile step is the check.
