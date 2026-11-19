# Porting existing work

Write `PLAN.md` in the shape in `plan.md`, filled in from the old work by one inventory helper.

## Inventory helper
One per folder of old work (a small model, read-only). Fill in the `<...>` parts and send only the quoted text.
`<skill>` is the dashboard-new folder.

> Take stock of the existing work in `<folder>` and write the plan for moving it into a dashboard. Read only:
> don't change, move, copy, install or run anything, except the script below and writing one file.
>
> 1. Run `python "<skill>/tools/peek.py" "<folder>"`. It lists data files and sorts code into **Code to read**
>    and **Code not needed**.
> 2. If there's a readme or index describing the data, read it first.
> 3. Open only the files under **Code to read**, and only around the lines it lists. Open a file under **Code not
>    needed** only to read one function a file you're reading calls.
> 4. Find every filter and input (peek lists them per file): dropdowns, request parameters, run arguments,
>    values passed into queries, loops that write one output per segment, dates typed in at the top. For each:
>    its column, where it is, which visuals change with it, and whether its value goes into the query.
> 5. Write `<dashboard>/PLAN.md` in exactly this shape: `<paste "Its shape" from plan.md>`.
>    - One row per table, per section (a visual group) and per filter. Tabs follow the old pages or files.
>    - "Copy from" names the file and function, or notebook cell.
>    - Guess Level and Fast / slow, and mark both guesses with `?`.
>    - A loop making one output per value is one section plus a filter, not one section per value.
>    - Under "Rules to keep", list every threshold or fixed value the old code applies.
> 6. Report in a few lines: what you found, the filters, anything you couldn't read or that was unclear.
>
> Describe what's there and where it goes. Don't design anything new.

Then go through `PLAN.md` with the user, filter by filter: keep it or not, its level, fast or slow. peek sorts by
pattern, so it can miss a file; if a visual they care about is missing, ask where it lives.

## What old things become
| In the old work | In the dashboard |
|---|---|
| Loading and cleaning data | A Pipeline script (one per table) |
| A finished report (analysis skill) | Its sources saved as they are (`write_source`); sections call its analytics live with `from_report` |
| A query or function that makes a chart's numbers | A section's analytic |
| A chart, table or KPI row (or a few shown together) | One section |
| A page, notebook or output file | A tab |
| Dropdowns or inputs | Filters at the level they applied |
| A loop writing one file per region | A filter, plus one offline report |
| Image charts (matplotlib, seaborn) | Redrawn with ECharts from the same numbers |
| Styled tables, colored cells | A table; the color rule stays in Python as a flag |
| An older dashboard of this kind | Copy `Src/Sections/*.jsx`, `Analysis/<tab>.py`, `Pipeline/`, `Reports/`, `dashboard.config.json`; rename `export const commentary` to `export const note` |
