---
name: analysis
description: One-off or occasional data analysis that answers one question (compare two sources, test a relationship, explain a change, find outliers), delivered as one HTML report. Two phases. Analysis: define the request, test, save findings as small Python section files; no HTML. Report: only once the answer is agreed, build the HTML from the sections that prove it, add number-checked commentary, and have a cold reader confirm it answers the request. Use for "can you tell me if / where / why ..." requests on data, or to rerun or change an existing analysis folder. Not for standing weekly or monthly reporting; that is a dashboard.
---

# Analysis

One question in, one HTML report out. One self-contained, rerunnable folder per analysis.

| Analysis (this skill) | Dashboard (not this skill) |
| --- | --- |
| Asked once, or a few times a year | Weekly or monthly monitoring |
| Answers one question | Standing view with filters and history |

## Mode

| Mode | Gates 1 and 2 | Ends with |
| --- | --- | --- |
| Guided (default) | User answers and approves | The report |
| Auto | You answer; each answer logged as an assumption | The report + a note: what was done, assumptions, "do these sound right?" (`references/auto.md`) |

- Mode not stated: ask in one line before step 1.
- "Just run it", "don't ask me", "auto": auto.

## The folder

```
<yyyy-mm-name>/
  README.md     brief, storyline, cold-read result            you write
  config.py     title, question, sources, parameters, REPORT  you write
  sections/     s1_<name>.py, s2_... (+ shared.py)            you write, one per piece of analysis
  sql/          one .sql per query (if needed)                you write
  inputs/       files handed over (if any)                    you add
  page.html     report look: fonts, colours, layout           copied; edit only to restyle
  run.py        the one command                               copied, never edit
  _engine/      build code                                    copied, never edit, never read
  data/         sources/ (saved query results), sections/ (each section's tables)   generated
  commentary/   commentary files                              generated
  output/       <folder>_<date>.html, exported CSVs           generated
```

## In a project

A project is a folder with `project_plan.md` (here or above). Then the `findings` skill applies; read its `SKILL.md`.

| When | Do |
| --- | --- |
| Step 1 | `findings.py list` first: what is already known. The brief's "Where it fits" names the plan goal ids this analysis serves |
| Step 2 | The folder goes in `<project>/analyses/`. Sources in the project's `data/` are read in place, never copied (`references/sources.md`) |
| Gate 2 | With the storyline, fill the README table "Findings for the project": only storyline claims that pass the findings skill's four tests. Usually fewer than the claims. Check each against the sections left out of the report: one that argues against a candidate goes into the finding. The user approves them with the answer |
| Step 8 | Add the approved findings, each citing its section file, summary table and the section's body commentary id. Set the goal's answer line. Hand-over notes list the finding ids |
| Rerun | After `python run.py commentary`: `findings.py check` |

No project plan: skip this section. Do not create one.

## Steps

In order. Gate = stop until it passes.

**Phase 1: analysis. No HTML.**

| # | Step | Gate | Read |
| --- | --- | --- | --- |
| 1 | Define the request | **Gate 1:** user approves the brief | `references/request.md` |
| 2 | Create the folder, connect sources | | `references/sources.md` |
| 3 | Analyse only what the brief asks or lists to test. Keep-worthy pieces: section files. `python run.py s2` prints results | | `references/sections.md` |
| 4 | State the answer and the sections that prove it | **Gate 2:** user agrees it is the answer | `references/storyline.md` |

**Phase 2: report. Only after gate 2.**

| # | Step | Gate | Read |
| --- | --- | --- | --- |
| 5 | Chosen sections into `config.py` `REPORT`, add charts, `python run.py report` | | `references/charts.md` |
| 6 | `python run.py commentary` | | `references/commentary.md` |
| 7 | Cold read | **Gate 3:** a fresh reader's conclusion matches the brief | `references/cold-read.md` |
| 8 | Hand over: report path, answer, what is assumed or unverified. Record in `README.md`, "Hand-over notes". Auto: the note in `references/auto.md` | | |

Other starting points:

| Situation | Read |
| --- | --- |
| Existing folder | Its `README.md` first |
| Rerun or change | `references/rerun.md` |
| Convert an existing process (scripts, workbook, hand-built report) | `references/convert.md`. Subagents explore and rewrite; main conversation only holds the gates |

## Do not read

| File | Read only when |
| --- | --- |
| `_engine/engine.py` (large) | Both: (1) a `python run.py` command ended in a Python traceback, not a `STOP:` message; (2) the traceback's last lines are in `_engine/engine.py`, not `config.py` or a section file. Then only the function it names |
| `page.html` | User asks for a different look. Then only its `:root` block |

Commands: `python run.py --help`. A `STOP:` message says what to do.

## Delegating

Give the subagent the reference's path; tell it to read and follow it. Do not read it yourself.

| Step handed over | Give the subagent | You read |
| --- | --- | --- |
| Connect sources, write SQL | `references/sources.md` | Nothing |
| Write or change a section's figures | `references/sections.md` | Nothing |
| Add charts to a section | `references/charts.md` | Nothing |
| Run commentary, fix failures | `references/commentary.md` | Nothing |
| Rerun with new dates or files | `references/rerun.md` | Nothing |
| Cold read | The brief in `references/cold-read.md` | `references/cold-read.md` |

- Always yours (you hold the gates): `references/request.md`, `references/storyline.md`.
- Every brief also gives: the analysis folder, the files it may write, what to return (files written, summary table as printed).

## Rules

- Before gate 1: look only. Read the named files or tables, quick counts and totals in the session. Save nothing, create nothing.
- No HTML before gate 2. `REPORT` stays empty until the user agrees the answer (auto: until the answer meets the brief's Success line). Report commands refuse to run while it is empty.
- Auto skips the asking, never the steps. Brief, test list and storyline are still written down.
- A section file is analysis, not a place in the report. Dead ends stay in `sections/`, out of `REPORT`, one line each under "Not included".
- Open question ("why is X high?"): a list of things to test, agreed in the brief. Test only what is on it. Never check fields at random.
- The report answers the question, nothing else. Every `REPORT` section proves one claim the answer needs. None "for context" or "for completeness".
- A visual exists only to prove its section's claim. Claim reads the same without it: cut it.
- Reader does not know the data: plain words; no column names, codes or unexplained abbreviations in titles, labels or notes. One plain name per source, used everywhere.
- Sections ask for sources by name. No SQL, no file paths in section files.
- No hand-written commentary or findings in the page. Numbers come from code; prose from the commentary step.
- Never edit `_engine/`, `run.py`, or anything under `data/`, `commentary/`, `output/`. Old dated reports in `output/` may be deleted.
- Different look (fonts, colours, logo, layout): that analysis's own `page.html`, only when the user asks. Never change the skill's `template/` for one analysis. `references/charts.md`, "Restyling".
- Create no files beyond those listed above.
