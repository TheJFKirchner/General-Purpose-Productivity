# Move existing work into a dashboard

For notebooks, scripts, SQL, spreadsheets, a Dash or Streamlit app, a finished report (analysis skill) or an older
dashboard of this kind. The old files are only read, never changed or moved.

What this does
1. An inventory helper (a small read-only agent) runs `tools/peek.py` on the old folder, which lists the data files
   and sorts the code into "Code to read" and "Code not needed", and writes `PLAN.md` in the new dashboard folder.
2. You agree `PLAN.md` with the user, filter by filter.
3. You load the data, then add one section per old visual, each from a library item fed the same numbers.

Step 1: make the empty dashboard
  Follow `make-a-dashboard.md` steps 2 and 3 (folder rule: never inside OneDrive or another synced folder).

Step 2: the inventory helper
  One per folder of old work. Send only this text, with the `<...>` filled in (`<skill>`: the folder holding this
  skill's `SKILL.md`):
  > Take stock of the existing work in `<old folder>` and write the plan for moving it into a dashboard. Read only:
  > change, move, copy, install or run nothing, except the script below and writing one file.
  > 1. Run `python "<skill>/tools/peek.py" "<old folder>"`.
  > 2. If there is a readme or index describing the data, read it first.
  > 3. Open only the files under "Code to read", around the lines it lists.
  > 4. Find every filter and input: dropdowns, request parameters, run arguments, values passed into queries, loops
  >    that write one output per segment, dates typed in at the top. For each: its column, where it is, which
  >    visuals change with it, and whether its value goes into the query.
  > 5. Write `<dashboard>/PLAN.md` as below: one row per table, per section (a visual group) and per filter; tabs
  >    follow the old pages or files; "Copy from" names the file and function or notebook cell; guess Level and
  >    Fast/slow and mark each guess with `?`; a loop making one output per value is one section plus a filter;
  >    under "Rules to keep" list every threshold or fixed value the old code applies.
  > 6. Report in a few lines: what you found, the filters, anything unclear. Describe; design nothing new.
  The shape of `PLAN.md`:
  ```
  # Plan: <title>
  ## Data
  | Table | From (file, query, script, or a report's source) | One row is | Columns |
  ## Tabs and sections
  | Tab | Section | Answers | Shows (library item) | Reads | Copy from |
  ## Filters
  | Filter | Column | Applies to | Level (dashboard, tab, section) | Fast / slow | Why |
  ## Rules to keep
  ```

Step 3: agree the plan
  Go through each filter with the user: keep it or not; its level (all sections, one tab, one section); fast (a
  column already in the loaded rows) or slow (its value goes into a query or picks a file). peek can miss a file:
  if a visual they care about is missing, ask where it lives.

Step 4: carry each old thing over
  | In the old work | In the dashboard |
  | --- | --- |
  | Loading and cleaning data | a line in `Pipeline/sources.py`, or a `Pipeline/<table>.py` script (`add-data-and-filters.md`) |
  | Prep code that lives elsewhere in the project | in a pipeline script: `df = outside("../analytics/prep.py", "claims_monthly")`, then `write_dataset(...)` |
  | A chart, table or tile row | one section from a library item (`add-a-section.md`); an image chart is redrawn the same way |
  | A query or function that makes a chart's numbers | the section's function in `Analysis/<tab>.py` (add the section without `--slot`; the stub is made) |
  | A page, notebook or output file | a tab |
  | Dropdowns or inputs | filters at the level they applied |
  | A loop writing one file per region | a filter, plus one offline report (`export-an-offline-report.md`) |
  | Styled tables, coloured cells | a library table; the colour rule stays in Python as a status column |
  | An older dashboard of this kind | copy its `Src/Sections/*.jsx`, `Analysis/<tab>.py`, `Pipeline/`, `Reports/`, `dashboard.config.json`; see `older-dashboards.md` |

A finished report's analytics, live (one function serves the report and the dashboard)
  1. Load the report's sources under the same names, in `Pipeline/sources.py`:
     write_source("claims", report="../reports/claims-review", as_of_from="service_month")
  2. Add the section without `--slot`; in its stub in `Analysis/<tab>.py`:
     ```python
     from Shared.reuse import from_report
     @section("s4_paid_by_region", tables=["claims"])
     def paid_by_region(t):
         r = from_report("../reports/claims-review", "s2_paid_by_region", t)
         return {"data": {"rows": r["tables"]["by_region"]}, "metrics": r["metrics"]}
     ```
  Filters act on it; unfiltered figures equal the report's. Thresholds come from the report's
  `sections/_shared.py` DEFAULTS; override one for the dashboard with `"analyticsDefaults": {"material": 0.3}` in
  `dashboard.config.json`. Never cache a report's finished tables: they have lost the filter columns.

Many sections at once (about eight or more): up to two helpers
  Data first, then every section made with `new-section`, then one helper per tab (never two on one file). Give
  each only: its tab's rows of `PLAN.md`, the old code to copy, the section files, this skill's
  `references/change-a-section.md`, and the rule "copy the old logic and look; do not redesign; leave a part on
  sample data and say why rather than invent numbers; run `npm run check` once at the end". They never touch
  `Src/Sections/index.js`, `dashboard.config.json`, `Pipeline/`, `Data/`, `Src/Lib/` or `Src/Components/`.

If something is missing
  - A visual whose numbers the old code cannot give: leave it out of the plan and tell the user.
  - A part the add command could not fill: its MANUAL line says what to do.

Step 5: check and look
  npm run check, then npm run shot -- <tab> for each tab; compare with the old work's output, figure by figure,
  with no filter and with one filter value. Add the `dashboard/` row to the project's map.
