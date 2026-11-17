---
name: findings
description: The shared findings file of a project (a folder with project_plan.md). Records what the work has learned that bears on a goal in the plan, each finding citing the script, section and table it came from, so analysis, dashboard, commentary and presentation work can pass results to each other. Use when work in a project reaches a result (an analysis answer is agreed, a dashboard section answers a plan question, a session settles something), when a deliverable needs to read what is already known, after a data refresh, or to set up a project folder. Not a log of everything done, and not for work with no project plan.
---

# Findings

One file per project that every deliverable writes to and reads from. Small on purpose: the reader is the plan's owner with ten minutes.

## The project folder

```
<project>/
  project_plan.md     goals, each with an id (G1, G2 ...)        the user's; never edited by this skill
  findings.json       the findings                               written only by findings.py
  findings.md         the same, readable, grouped by goal        generated; never edit
  data/               source files shared by every deliverable   read in place, never copied
  analyses/<yyyy-mm-name>/        analysis skill folders
  dashboard/                      dashboard project
  presentations/<yyyy-mm-name>/   presentation skill folders
```

- Commentary files stay inside the deliverable they describe.
- Who writes what, how to cite, what to do after a refresh: `references/project.md`.

## What is a finding

Something learned that **answers, supports, contradicts or changes** a goal in the plan. All four:

| Test | Fails when |
| --- | --- |
| It names a goal id from the plan | It is interesting but bears on no goal |
| "What it means for the goal" is a consequence: what can now be decided, done or ruled out | It is a fact, or the meaning only repeats the finding |
| It cites the script (and section, table, figures) it came from | It cannot be traced |
| Nothing else in the same work argues against it, or the finding says what does | Another section shows a case the finding denies |

| Not a finding | Where it goes instead |
| --- | --- |
| A test that showed nothing, a dead end | The analysis README, "Not included". `findings.md` links to it |
| A method choice, filter, definition | The section's `NOTES`; the brief's Definitions |
| A data quirk that changes no goal's answer | The analysis README, hand-over notes |
| A step done, a status, a to-do | The project plan (the user's) |
| A number with no claim ("May paid $6.2M") | Commentary |
| Supporting detail of a finding already recorded | Nothing: the cited section holds it |
| The same argument seen a second way ("and without the batch, May is normal") | Part of the first finding |

Edge cases:

| Case | Rule |
| --- | --- |
| "Nothing stands out" | A finding only when the goal's Success accepts "none" as an answer. It states the line used (`--assumes`) and names the nearest cases, so the reader can disagree |
| Success asks for a list (what to fix, who to call) | Each item someone must act on is its own finding, largest first. Otherwise items are detail |
| Bears on no goal but looks important | Do not file it. Tell the user in one line; ask whether the plan should change |

## Two kinds

Test: load one more month of data. Would the sentence need new numbers?

| Kind | Is | When the data refreshes |
| --- | --- | --- |
| `durable` | No. A mechanism, cause or rule: "the warehouse keeps voided claims". Any figure in it names its period | Flagged **recheck** if its evidence changed. Not used until confirmed (same wording allowed) or dropped |
| `refreshing` | Yes. A size, level, count, ranking, a gap that someone can fix, or "none found", for the period in `--as-of` | Goes **stale**. Not used until confirmed with the new wording and period, or dropped |

- Mechanism and size in one sentence: file it as refreshing, or state the mechanism alone as durable.
- Something a team can fix at source (a missing load, a wrong amount) is refreshing: the next data may not have it.
- Refreshing findings follow the number-checked commentary: cite the id of the section's body commentary (`commentary=C3`) and reword from it after a refresh.

## What each finding carries

| Part | Flag | Rule |
| --- | --- | --- |
| Statement | `--statement` | One claim, one or two sentences, at most 300 characters, plain words, the figure that matters first. Every figure is in the cited table, computed the way the sentence says |
| Meaning | `--means` | The consequence for the goal |
| Chosen lines | `--assumes` (repeatable) | Every threshold or definition you chose that the claim depends on ("stands out = 3 points or more above the overall rate; chosen by the analyst") |
| Still to confirm | `--open` (repeatable) | What only the user or another team can settle, and who ("whether close already excludes voided claims: Controller") |
| Evidence | `--evidence` (repeatable) | The code and the table. `figures` names the rows and columns, never the values (values go out of date). No semicolon inside a value. `references/project.md`, "Citing" |

## The answer line

One line per goal, above its findings: does the work so far meet the goal's Success?

`findings.py answer G1 --status answered|conditional|open --text "..."`

| Status | When |
| --- | --- |
| `answered` | Success is met by the findings as they stand. No "assumes" or "to confirm" item under the goal could change it |
| `conditional` | Met only if an `--assumes` or `--open` item goes one way. Say which |
| `open` | Not met. Say what is missing |

- At most 300 characters. Names the findings it rests on (F1, F4). Every figure in it is in one of them.
- Rewrite it whenever that goal's findings change.

## Steps

| When | Do |
| --- | --- |
| New project, or no `findings.json` | `findings.py init`. Stops if the plan has no goal ids: ask the user to add them; never edit the plan |
| Before starting any deliverable | `findings.py list`. Read what is known. Do not redo it |
| A deliverable reaches its agreed result (analysis gate 2; a dashboard section built; a session settles a plan question) | List candidates against the four tests. Guided: show the user the candidates, add what they approve (`--approved "name, date"`). Auto: add; they are marked not yet confirmed. Then the goal's answer line |
| The user confirms findings later | `findings.py approve F1 F2 --by "name, date"` |
| After any data refresh or rerun | `findings.py check`. For each stale one: read the new figures, then `confirm` or `drop`. Then the answer line |
| Building a deck or report from the project | Read `findings.md`. Cite finding ids. Never use a stale finding. Unconfirmed ones: list them for the user at the first gate |

## Commands

`python <this skill>/scripts/findings.py <command>`, from anywhere inside the project. Paths in `--evidence` start at the project folder.

| Command | Does |
| --- | --- |
| `init` | Creates `findings.json`, lists the plan's goals |
| `goals` | Each goal and its number of findings |
| `add --goal G1 --kind durable\|refreshing --bearing answers\|supports\|contradicts\|changes-plan --statement "..." --means "..." --evidence "script=...;section=s2;table=...;figures=...;commentary=C3"` | Adds one. Refreshing also needs `--as-of`. Optional: `--assumes`, `--open`, `--by`, `--approved`, `--replaces F2`, `--stated-by "who"` (no data behind it) |
| `answer G1 --status ... --text "..."` | Sets the goal's answer line |
| `approve F1 F2 --by "name, date"` | Records the user's confirmation |
| `list [--goal G1] [--all]` | Prints them |
| `check` | Cited files exist; cited tables unchanged; goals with no findings or no answer line |
| `confirm F2 [--statement "..." --means "..." --as-of ... --why "..."] [--evidence] [--assumes] [--open]` | Marks a stale or recheck finding current. A stale one is confirmed whole: read every part against the new tables and restate statement, meaning, period and why it changed. `--evidence`, `--assumes`, `--open` replace what was there (`--open none` clears) |
| `drop F2 --reason "..."` | Retires one. Kept under "No longer used"; the reason says what happened ("fixed at source: the March week is now loaded") |

`findings.md` shows what the last refresh changed ("Changed on <date>": reworded, replaced, dropped, each with what it said before). A deck may cite a dropped finding as history, with its reason; never as a current result.

A `STOP:` line says what to fix. Fix the finding, not the check.

## Rules

- At most 5 live findings per goal. Full: `--replaces` the weaker one, or do not add. Only the user changes the limit.
- Fewer is better. Two findings that make one argument are one finding.
- Evidence is the code, not the output: `script` is the section file or script that computed it; `table` and `figures` say where the number sits.
- Before filing, open the cited table and read the figure off it. A figure computed on a slightly different set (all 221 large claims, not the provider's 220) is a wrong citation.
- Never edit `findings.json` or `findings.md` by hand. Never edit `project_plan.md`.
- Do not file a finding to record effort. Nothing bears on a goal: leave it empty and set its answer line to `open`.
