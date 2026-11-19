# Analysis toolbox

Status: built
Date: 2026-11-18

Note, 2026-11-19: the design library now lives only in `Toolkit Update/design-library/`. Paths below that name a top-level `design-library/` folder refer to its old location.

Seven separate skills that work as one toolbox for analysis work: `toolbox`, `analysis`, `findings`, `commentary`, `dashboard-new`, `dashboard-work`, `presentation`, plus a top-level `design-library/`. They share one vocabulary, one way of finding things (the map in the project's `CLAUDE.md`) and one look. They are optional tools, not a path: people explore however they like, and structure applies only when something goes into a deliverable. The goal of every skill is simple, easy to follow and not wordy.

## Assumptions

1. Everything lives in this repo. `Integrated Dash` (the old dashboard home, outside this repo) is left untouched; the dashboard starter is copied in from its `dashboard-new` and `dashboard-work` folders.
2. The old `analysis`, `commentary`, `findings` and `presentation` skills are replaced in place; git history keeps the old versions.
3. ECharts everywhere. One shared look (see "Look").
4. No environment variables anywhere. Settings go in a config file.
5. Skills are bullets and tables. Target under 80 lines per `SKILL.md`. A reference file is opened only when a step names it.
6. Test projects live outside the repo and are never committed.
7. The dashboard keeps its own fixed internal folder structure, because the app needs it. Folder freedom applies to the project around it.
8. One analytic shape wherever an analytic feeds a deliverable: a Python function that returns tables and metrics, with its question and notes.
9. Skills read the project's `CLAUDE.md` map before touching anything, and add a line when they create a folder.

## Vocabulary (same meaning in every skill)

| Word | Means | Has a look? |
| --- | --- | --- |
| Pipeline | Fetch and prep data into tables. Answers nothing | No |
| Analytic | One Python function, one question, returns tables and metrics, plus its question and notes | No |
| Section | One visual block in an output (report, dashboard, deck) that shows an analytic | Yes |
| Deliverable | Something handed to a reader: report, dashboard, deck, Excel file, data asset | |
| Finding | A result against the project plan, with its source | No |
| Commentary | Generated text for a deliverable that needs it across many scenarios (dashboards) | |

## Decisions

- **Separate skills, not one router skill.** Easier to maintain, each loads only its own instructions, each can be tested alone. Rejected: one `analysis-toolbox` skill with sub-pages.
- **No fixed project shape.** The user decides the folders at the start of each project. The skills fix names, not shapes. No folder is created until there is a file for it. Folder bloat was the core complaint. Rejected: one common tree for every project; two fixed shapes (one-time and recurring).
- **The map lives in the project's `CLAUDE.md`.** New folder = new line. Format:

  ```markdown
  ## Map
  - Project plan: [plan file](path)
  - Findings: [findings.md](path)
  - Design library: <path>            (optional)

  | Folder or file | Holds |
  | --- | --- |
  | `analytics/` | ... |
  ```

  Preferred names when a folder of that kind is wanted: `pipeline/`, `data/`, `analytics/`, `outputs/`, `dashboard/`, `deck/`, `inputs/`, `exports/`.
- **`toolbox` skill: new projects and full rescopes only.** It asks what is being made (analysis, data asset, Excel file, dashboard, deck, a mix), proposes the fewest folders that fit, the user edits, it writes the map and a project plan. The plan comes from a project-type table that ships blank. No matching type: interview on audience, goals, success; "exploration" is a valid answer. Other skills read the plan and never shape it. The user has a separate new-project skill at work; toolbox must be small enough to earn its place.
- **Only two fixed rules across the toolbox.** (1) A new project starts with a short talk and a map in `CLAUDE.md`. (2) Every number in a deliverable traces to code or a named source. Gates such as "agree the answer before building the report" live inside the deliverable they belong to. Rejected: mandatory commentary step, mandatory cold read, scripted number checks on commentary ("no convoluted checks yet").
- **Do not save every query result.** The analysis report engine keeps tables in memory and saves one only when asked. CSV imports and exports are fine.
- **Scripts do mechanical jobs only.** Engine and run scripts are fine. A script never decides the next step and never calls an AI. AI steps are subagents.
- **`analysis` has two modes, short.** Explore: no required file format, no folders created, results in the conversation. Report: only when asked; the quick template, analytics wrapped as functions, bullets written by the author from the results and findings. Cold read is an optional suggestion. A quick analysis must never need a dashboard.
- **Findings are the commentary for reports and decks.** The author writes bullets directly from findings and results: no commentary skill, no subagent.
- **`commentary` is for dashboards** that need text across many filter scenarios or on each refresh, or when the user asks. It is a `commentary-generator` subagent that gets a question and small tables and writes one `commentary.json`: a list of items with `id` (C1, C2 ...), `commentary` (list of strings), `source` (two to three sentences) and optional `filters`. All the old commentary scripts are removed, and with them the `claude` command-line dependency.
- **Dashboard without the design agent.** The chat panel, its loader stubs and its raw-SDK code are removed. All settings move to `dashboard.config.json`. Looks-only changes go through `custom.css` and the theme.
- **Dashboard runs from its own folder.** The framework is copied from the skill into the project and nothing runs from the skill folder afterwards. The dashboard may run an outside analysis script and cache its result in its own data folder.
- **Dashboard reports are a sub-workflow.** One Python script per report plus a JSON file saying how to run it and what it needs, documented in one reference file. (This mirrors changes the user made on another machine that could not be seen from here; expect small differences to reconcile.)
- **`dashboard-new` and `dashboard-work` stay two skills**, new versus working.
- **Decks stay on reveal.js**, no build step. Vite is the dashboard only.
- **`presentation` has two modes.** Quick (default for decks under about eight slides): one confirmed brief, one confirmed slide list, built in the main conversation. Full: the interviews, reviewer and builder, for a real readout or when asked.
- **Design library is a top-level `design-library/` folder**, not inside a skill. Seeded from the presentation slide library. One index by type (slides, charts, dashboard sections, report blocks, themes), descriptions only; design subagents open the items. Found through the "Design library" line in a `CLAUDE.md`. Skills work without it using the plain default look.

## Look

Light, professional readout level, blue-led. No company named in any file, no logos.

| Token | Value | Use |
| --- | --- | --- |
| `--blue` | `#0170BC` | Primary, first series |
| `--navy` | `#002D72` | Headings, emphasis |
| `--green` | `#56A944` | Accent, second series, positive |
| `--teal` | `#00A9A5` | Third series |
| `--orange` | `#F68621` | Highlight, used sparingly |
| `--ink` | `#1F2A37` | Body text |
| `--muted` | `#5B6770` | Notes, axes |
| `--rule` | `#D9E2EA` | Lines, borders |
| `--wash` | `#F4F8FB` | Panels, alternating rows |
| `--paper` | `#FFFFFF` | Page |

Series order: blue, green, navy, teal, orange, muted. The canonical copy is `design-library/themes/`; each template carries the same tokens.

## Test budgets

A test passes only if the output is right and it stays inside the budget. A blown budget is fixed by cutting the skill.

| Task | Skills loaded | Subagents | Reference files read |
| --- | --- | --- | --- |
| Report: one chart, three bullets | 1 | 0 | 2 or fewer |
| Add a finding | 1 | 0 | 0 |
| Add or edit a dashboard section | 1 | 0 | 2 or fewer |
| New dashboard, about five sections | 1 | 2 or fewer | 3 or fewer |
| Quick deck, about five slides | 1 | 0 | 3 or fewer |
| Dashboard commentary, ten scenarios | 1 | 1 | 1 |
| New project with toolbox | 1 | 0 | 1 |

## What changed during the build and testing

Decisions made after the plan, from two rounds of testing:

- **Reuse between a report and a dashboard.** Caching a report's finished table in a dashboard is not reuse: the table has no filter columns. A dashboard section instead calls the report's analytic live on the filtered rows (`from_report`). Analytics must cope with empty or tiny inputs and must not assume they are given the full file.
- **Shared definitions.** Thresholds, periods and cut-offs live once, as a `DEFAULTS` dict in the analytics file. A report's `PARAMS` hold only what differs for that report. Rejected: a separate `params.json`.
- **The map.** One "Project plan" link line, then a two-column table. It lists only what exists; each skill adds its own row when it creates something. A row for anything run again ends with `Refresh: <command or step>`. The findings skill adds its own "Findings" line. The "Design library" line is optional: the presentation skill uses the library in this repo by default.
- **Basis of an answer.** The toolbox asks the date basis, comparison periods and thresholds for each goal at setup. A report's answer needs a `basis` line. A comparison word (normal, flat, in line) needs both sides as figures on one basis.
- **Findings.** A source is the folder, the command and the metric. A person's statement is recorded as "not checked against data" until a "Checks finding N" row tests it. Old rows are never edited except to add "See M.".
- **Commentary.** Matching is exact: an item shows only for the filter combination it was written for. Tables come from one dashboard command, `npm run tables`. The generator writes only what its own scenario's table supports and does not restate figures already on the page.
- **Getting numbers between skills.** `python run.py data NAME [TABLE]` in a report folder; `npm run tables` in a dashboard. No throwaway scripts.
- **Looking at the result.** `python run.py shot` and `npm run shot` find the browser themselves. Decks use one contact-sheet image and one fix pass.
- **Rescopes.** The plan keeps a dated history, goal numbers are never reused, and dropped folders are marked "Old since <date>".
- **Small requests.** A report's bullets and key figures are optional; a stated size gets exactly that size.
- **Look, deviations from the table below.** In reports the second chart series is light blue (`#7FB8E0`), not green. In dashboards orange is not a series colour; it marks "needs attention" only. `design-library/themes/` still carries the series order as first agreed. This is open for the owner to settle.
- **Removed.** The toolbox's reference file (one file now), the analysis `_engine/` folder (the engine is `run.py`), Plotly and the neon theme in the dashboard starter, the presentation `advanced-features.md`.

### Round 3: how much is read on a normal edit (2026-11-19)

The owner's rule: what matters is how much gets read on a normal edit, not how many files a skill holds. On existing work, "add a bar chart of X by month and 2 bullet points" may read only the skill, at most one short reference page, and an inventory printed by a command. Copied framework files are created and never read.

- **Registry.** Each of the three has one inventory command that lists every item with its file, kind and an 8 to 10 word description: `python run.py list` (report sections, plus each section's tables, columns and metrics, and the sources with columns and date ranges), `npm run status` (dashboard sections and tables), and `slides.js <deck or project folder>` (slides; this script lives in the skill). The report and dashboard commands run from the copy inside the project, because those run only from their own folder.
- **Section definitions.** A report section is one file, `sections/sN_<name>.py`: description, analytic, title, chart and bullets. `sections/_shared.py` holds `DEFAULTS` and helpers; `report.py` keeps the brief, answer, sources and the order. A dashboard section is one `.jsx` file: for simple shapes its `meta` declares the numbers (x, y, aggregation, split) and a shared Python function computes them on the filtered table, so nothing is computed in the browser and no Python is written unless the calculation is unusual. A slide carries its own description. Accepted cost: a report folder is four files plus one per section.
- **Add commands.** `python run.py add-section`, `npm run new-section` and `add-slide.js` each write a WORKING item (bar, line, table, plus tiles or figures) and print what is left to word. They cover a few shapes only and say so; anything unusual is a hand edit from a short page. They name an existing item that the request would repeat. `add-slide.js --from` pulls a chart's series from a report itself.
- **Short everyday pages.** Each skill has a simple-add part of about 30 to 47 lines; rare material sits below a "stop here" line.
- **Never read.** A report's `run.py` and `page.html`; a dashboard's app, shared code, server, tools and theme; a deck's engine below the slides marker, its stylesheet below `:root`, the scripts and library slide files.
- **Consequence to know.** A report or dashboard keeps the copy of the framework it was created with. Older ones do not get new commands until the framework is copied in again. No update command exists yet.

Round 3 results (fresh subagents, strict log of every file opened): the add case passed on all three in 11 to 19 tool calls with no framework file opened, and creating a new report, dashboard and deck passed with no copied framework file read.

### Design library and its subagent (2026-11-19)

- **Saving is done by a subagent, `design-librarian`** (`.claude/agents/design-librarian.md`), on Haiku because it is a copy job. When the user likes a visual, the analysis, dashboard-work or presentation skill launches it with the files. A script (`design-library/save-item.js`) does the copying; the agent writes the one-sentence purpose and runs the check. It never edits the project it copies from.
- **One item, one file.** Every item is one HTML file that renders by itself (ECharts from its CDN is the only outside file), with a header: `id`, `type`, `name`, a one-sentence `purpose`, and the skill it came from. Sample data is inline, 4 to 6 made-up round values.
- **Ids.** Two capitals, a hyphen, two digits; never changed and never reused. Slides keep their group codes; `CT` chart, `RS` report section, `DS` dashboard section, `TH` theme.
- **A saved section is a pattern, not the project's analysis.** A report or dashboard section is saved as a generic definition of its shape with `DATA`, `GROUP` and `VALUE` placeholders, starting with the add command that recreates it. The project's own calculation is not copied. Rejected: copying the section file as it is, which carried project dates, categories and thresholds into the library.
- **Checks.** `build-index.js` fails on a bad or duplicate id, a missing purpose, an outside file, a hard-coded colour or font, a date literal, more than six sample points, or a project word (the source's table, column and category names, stored as hashes). The original hand-made samples are exempt from the date, size and project-word checks.
- **Themes and the index.** A theme is an item holding the CSS tokens and the chart series order. Items use token names only, so `index.html` can show every item in any theme: a side bar of themes, a main grid of items, a filter by type. Three themes ship: the default light blue-led look, and a dark and a greyscale one marked as examples. This restyles the library and its index only; reports, dashboards and decks keep their own look.
- **`design-library/CLAUDE.md`** holds the rules, how to use and how to save, in 24 lines. It replaces the library's README and its new-component guide.

Tested cold on Haiku: four visuals (two report sections, a dashboard section, a slide) saved in 21 tool calls with no project value surviving, after one fix round.

Tested: 32 runs over two rounds (build, together, pick-up), each by a fresh subagent, with manager reviews after each round. All seven skills were judged "roll out after must-fixes" in round 2. Those must-fixes were applied and checked by the builders, not by a further cold run.

Not tested: interviews and approval gates with a real person, presentation full mode, porting existing work into a dashboard, hosting, real data volumes, and any engine other than Claude.

## Test plan

Two rounds, each with three kinds of test, every run by a fresh subagent that knows only the skill:

| Kind | What it proves |
| --- | --- |
| Build | Each skill, used alone, produces its deliverable from nothing |
| Together | The skills pass work to each other: new project, analysis, findings, report, dashboard, commentary, deck, all through the one map |
| Pick up | A fresh subagent is dropped onto work that already exists, with no history, and continues or changes it (rerun, add a section, edit a slide, add a finding) |

- Each runner reports its tool calls, files read, skills loaded, subagents used, and where it got stuck.
- A manager subagent reviews each piece of work: did it do the job, is it auditable, can a section be rebuilt or changed easily; plus visual feedback.
- Token cost, tool calls and time are logged for every subagent. The report names where the cost bleeds and which step of the process causes it.
- Feedback goes to the builder that owns the skill, once; then round 2 reruns everything.

## Tasks

| # | Slice | Owns |
| --- | --- | --- |
| 1 | `toolbox` (new) and `findings` (light edit) | `.claude/skills/toolbox/`, `.claude/skills/findings/` |
| 2 | `analysis` reshaped: explore and report modes, no saved query results, sharper template | `.claude/skills/analysis/` |
| 3 | `commentary` cut down, `commentary-generator` subagent | `.claude/skills/commentary/`, `.claude/agents/commentary-generator.md` |
| 4 | `dashboard-new` and `dashboard-work`: copied in, agent removed, config only, reports sub-workflow | `.claude/skills/dashboard-new/`, `.claude/skills/dashboard-work/` |
| 5 | `presentation` quick and full modes; `design-library/` | `.claude/skills/presentation/`, `design-library/` |

All five run in parallel; no file overlap. Then: round 1 tests (each skill run cold by a fresh subagent), a manager review and a visual review of each piece of work, one fix pass per skill, round 2 rerun, and a full report. Test output is saved outside the repo in round 1, feedback and round 2 folders.
