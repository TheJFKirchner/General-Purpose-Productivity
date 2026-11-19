---
name: dashboard-new
description: "Make a new dashboard (Python analytics, React and ECharts page), or port existing work into one: notebooks, scripts, SQL, spreadsheets, a Dash or Streamlit app, an older dashboard, a finished report. Four steps: copy the starter, plan, data, sections. Later changes use dashboard-work."
---

# Dashboard new

## Words
| Word | Means |
|---|---|
| Section | One visual block on the page (chart, table, KPI tiles, or a few together) |
| Analytic | The Python function behind a section: one question, returns `data` and `metrics` |
| Pipeline | Scripts that fetch and prep tables into `Data/Current/`. They answer nothing |
| Commentary | Optional `commentary.json` text, made by the commentary skill |

A dashboard has tabs; each tab has sections. Filters sit on the whole dashboard, one tab or one section.

## Steps
| Step | Done when |
|---|---|
| 1. Copy the starter | setup prints `check OK` |
| 2. Plan | the user has agreed `PLAN.md` |
| 3. Data | `npm run pipeline` finishes, or the files are in `Data/Current/` |
| 4. Sections | `npm run check` passes and the user has seen it |

One check per step. Build only what the plan lists. Edit files with the Edit tool; on Windows never `Set-Content`.

### 1. Copy the starter
1. Read the project's `CLAUDE.md` map. A `dashboard/` row: use that folder. None: propose `<project>/dashboard/` and ask.
   Avoid OneDrive folders (installed packages sync badly).
2. Run `python <this skill>/tools/setup.py <folder> --title "<title>"`. Missing Node, or Python 3.10+ with
   `fastapi uvicorn duckdb pyarrow pandas`: tell the user and stop.
3. After step 4, add or replace the map's `dashboard/` row: `` | `dashboard/` | The <what> dashboard for <whom>.
   Data: <files> in `<folder>/`, loaded by `Pipeline/sources.py`. Refresh: replace them (same names), `npm run pipeline`,
   `npm run check`. Change it with dashboard-work. | `` (the commentary skill adds which id sits on which section).

Setup copies the starter in and writes `dashboard.config.json`. After that nothing points back at this skill.

### 2. Plan
- **New:** ask what it should answer, where the data is, which filters readers need. Write `PLAN.md` in the shape
  in `references/plan.md`. Every goal in the project plan gets a section that shows it directly (a rate or a
  change, not an 18-month total). The user's own list of sections wins; note any gap with the goals. Agree it.
- **Port:** open `references/port.md`. It sends one inventory helper, then you settle the plan.
- For each filter settle its level (what it applies to) and fast or slow (does a change re-query?).

### 3. Data
- **Every input file:** one line in `Pipeline/sources.py`: `write_source("claims", "../inputs/claims.csv",
  as_of_from="service_month")` (the date column gives "Data as of"). Never copy files into `Data/Current`.
- **Needs prep:** `Pipeline/<table>.py` ending in `write_dataset("<table>", df, grain=..., source=..., as_of=...)`.
- **Reusing a report's analytics** (analysis skill): one function, both places. Load its sources in `sources.py`
  (`write_source("claims", report="../<report>")`); a section calls `from_report("../<report>", "s2_<name>", t)`.
  Filters act on it; unfiltered figures equal the report's. Never cache a report's finished tables.
- `npm run pipeline` once (`-- --try <script>` tries one).
- Fast filters go in `dashboard.config.json`: `"region": { "label": "Region", "column": "region" }`, plus `"tab"` or
  `"section"` for a lower level. Set `"dataSource"` (source and basis, e.g. "months are the month care was given").
  Slow filters, prep outside the folder: `dashboard-work` `references/data.md`.

### 4. Sections
1. Each simple section is one command (`dashboard-work` `references/sections.md`, "Simple add"):
   `npm run new-section -- <name> --page <tab> --tables <t> --chart bar|line|table|kpi --x <col> --y <col>`.
2. Reword each note; headline KPI tiles first. Unusual ones: the same page, below STOP HERE.
3. Many sections at once (about eight or more): up to 2 helpers, `dashboard-work` `references/helpers.md`.
4. `npm run check`; `npm run status` lists every section in `PLAN.md`.
5. Look: `npm run shot -- <tab> <out.png> [region=West]` (starts and stops its own server). `npm run dev` opens it live
   (`npm run stop` ends it).

Later changes, reports and commentary go through **dashboard-work**.

## Who does what
- **You:** talk to the user, settle the plan and filters, run setup, the pipeline, `new-section` and the check.
- **Helpers (optional):** copy old code into sections, one tab each. They copy, they don't redesign.
- Never edit or move the user's original files.

## What to open
| | Files |
|---|---|
| **Read** | This page; `references/plan.md` (new) or `references/port.md` (port) at step 2; the `dashboard-work` reference a step names |
| **Run, don't read** | `tools/setup.py`, `tools/peek.py` (`--help` lists options) |
| **Never open** | `starter/` and `themes/`. In the dashboard, open only the **Edit** files in `dashboard-work` |
