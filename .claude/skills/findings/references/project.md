# The project folder and who writes what

A project is the folder that holds `project_plan.md`. Every skill finds it by walking up from where it is working.

## The plan

The plan belongs to the user (or to whatever skill they plan with). This skill needs one thing from it: each goal or question has an id at the start of its row, bullet or heading.

```markdown
| ID | Goal | Success |
| --- | --- | --- |
| G1 | Explain why paid claims rose in May | Finance can say whether to change the reserve |
| G2 | Confirm the two claim sources agree | A list of what to fix before month-end close |
```

- Ids: `G1`, `G2` ... or `Q1`, `Q2` ...
- No ids: `findings.py init` stops. Ask the user to add them.

## Where each skill works

| Skill | Its folder in the project | Reads | Writes to findings |
| --- | --- | --- | --- |
| analysis | `analyses/<yyyy-mm-name>/` | `findings.md` before the brief | At gate 2, the claims the answer rests on; after a rerun, `check` |
| dashboard | `dashboard/` | `findings.md` when planning sections | When a section answers a plan question; after each refresh, `check` |
| commentary | Inside the deliverable (`analyses/<name>/commentary/`, beside a deck or dashboard) | Nothing | Nothing itself. Its ids (`C3`) are cited by findings |
| presentation | `presentations/<yyyy-mm-name>/` | `findings.md` first, in step 1 | Nothing. A deck reads; it does not discover |
| any other session | Its scripts under the project | `findings.md` | When it settles a plan question, citing its script |

## Shared data

- Source files every deliverable uses live once, in `<project>/data/`. Deliverables read them in place by a path from their own folder (`../../data/claims.csv`), never a copy and never a full path.
- Refreshing the project means replacing files in `data/`, then rerunning each deliverable, then `findings.py check`.
- A file only one deliverable uses stays in that deliverable (`inputs/`).

## Citing

| Source | `--evidence` |
| --- | --- |
| Analysis section | `script=analyses/<name>/sections/s2_x.py;section=s2;table=analyses/<name>/data/sections/s2_summary.parquet;figures=May row, column paid;commentary=C3` |
| Dashboard section | `script=dashboard/Analysis/<tab>.py;section=s3_paid_by_region;table=dashboard/Data/Current/<table>.parquet;figures=metric total_paid` |
| A one-off script | `script=<path>;table=<its output file>;figures=...` |
| A person or document, no data | `--stated-by "Finance lead, 12 Nov meeting"`. Shown as not checked against data |

- `script` is required for evidence: the code that computed it.
- `commentary`: an analysis section has a heading id and a body id. Cite the body's.
- `findings.md` adds the links a reader needs by itself: the deliverable's newest report, and its README (what was tested and ruled out).
- `table` is fingerprinted. That is how a refresh marks a refreshing finding stale.
- Several pieces of evidence: repeat `--evidence`.

## After a refresh

1. Replace the files in `data/`. Rerun each deliverable (analysis: `python run.py report --refresh`, then `python run.py commentary`).
2. Look at what period the new data covers. Different from the plan's stated period, or ending in a part month: say so to the user (auto: record it as an assumption), and keep period labels in `PARAMS`, not typed into sections.
3. `findings.py check`.
4. Each stale refreshing finding: read its section's new summary table or commentary. Still true with new figures: `confirm F2 --statement "..." --as-of <period>`; if the rows or tables it cites moved, also `--evidence`; if what it assumes or leaves open changed, also `--assumes` / `--open`. No longer true: `drop F2 --reason "..."`, and tell the user, since a goal's answer may have moved.
5. Each durable "recheck": does the conclusion still hold? `confirm F4`, or `drop`.
6. Rewrite the answer line of every goal whose findings changed.
7. Decks and reports built from a finding that changed or was dropped: list them for the user. `findings.md`, "Changed on", is the list of what moved.
