# How to build findings.md

Put this file wherever new projects are set up. It stands alone: everything needed to create and keep a project's `findings.md` is here.

## What it is

One file per project: what the work has established against the project plan, and where each result came from. A list, not a report. Nothing is ranked or judged in it.

- A project has findings only if it has a project plan. The plan is the one linked in the project's `CLAUDE.md`. No plan linked: no `findings.md`.
- Durable facts (methods, gotchas, definitions, reference numbers) are not findings. They go to the session facts file and on to the wiki.

## Where it goes

- In the same folder as the project plan, named `findings.md`.
- It is made the first time there is a finding to record. If it does not exist, create it.

## Starting content

Create the file with exactly this:

```markdown
# Findings

| # | Finding | Plan item | Source | As of | Added |
| --- | --- | --- | --- | --- | --- |
```

## Add to the project's CLAUDE.md

```markdown
- Project plan: [project_plan.md](project_plan.md)
- Findings: [findings.md](findings.md). Results against the plan go here as they are established; create the file if it does not exist.
```

## Is it a finding?

Both must be true:

1. The work established it: computed it, checked it, or got it settled by someone.
2. It answers, confirms, rules out, blocks or changes an item in the plan.

| Case | Rule |
| --- | --- |
| Given, not established by the work | Reference knowledge that outlives the project (a contract term, another team's assumption, last year's result): not a finding. Specific to this project and bearing on a plan item (the pilot's roster): a finding, with the document or person as its source |
| A working choice (a basis, filter, threshold or assumption), or an edit to the plan itself | Not a finding; it belongs in the plan |
| A plan item settled by the person who owns it ("the director decided to extend") | A finding. Source = who decided, and the date |
| An opinion or intention that settles nothing | Not a finding |
| A caveat on a finding | Put it in the finding's sentence. Learned later: add a new row naming the row it qualifies. A finding computed on data with a known problem says so |
| A result that bears on no plan item | Not a finding. Tell the user in one line |
| A negative result the plan asked about ("no seasonality found") | A finding |
| Something that blocks a plan item | A finding |
| Unsure | Leave it out and tell the user in one line |

## Adding a row

| Column | Rule |
| --- | --- |
| # | Continues from the last row |
| Finding | One sentence, plain words, with its figure. One finding per row |
| Plan item | The plan's own id or words for the goal, question or step it bears on |
| Source | The script, section file or query, and where the figure sits (table, row, column). A document: its name and date. A person: who, and the date. Enough for someone to find it in a minute |
| As of | The data period or date the finding is true for. Blank when it does not depend on data |
| Added | Today |

- No source: do not add it. Nothing from memory.
- Already in the list: skip.
- New data gives a new figure: add a new row with the new "As of". Never edit or delete old rows.
- Append only. One writer: the main conversation. Sub-agents report findings back; they do not write the file.

## Example

```markdown
# Findings

| # | Finding | Plan item | Source | As of | Added |
| --- | --- | --- | --- | --- | --- |
| 1 | May 2026 paid claims were $6.22M, 3.9 times a normal month. | Goal 1: explain the May rise | `analyses/may-rise/sections/s1_monthly.py`, table `s1_summary`, May row | Jan to Jun 2026 | 2026-11-16 |
| 2 | No seasonality was found in large claims over 36 months. | Goal 1: explain the May rise | `analyses/may-rise/sections/s5_monthly.py`, table `s5_monthly` | Jul 2023 to Jun 2026 | 2026-11-17 |
| 3 | Client C's data is not available until January, so Step 4 cannot be done this quarter. | Step 4: repeat for Client C | Data team, message of 18 Nov 2026 | | 2026-11-18 |
```

The figures are invented.

## Using it

- Before writing a deck, report or summary: read `findings.md`.
- Cite the row number where a finding is used (finding 12).
- Check "As of". Older than the current data: re-read the source, or say the date with the finding.
