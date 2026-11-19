# Helpers (optional subagents)

Only for many sections or tables at once (about eight or more, or two big tabs). For a few, do it yourself.
At most two helpers per job. A small model is enough for copying; use a stronger one only for new analysis with
nothing to copy, or after the small one fails the same job twice.

## Rules
- Order: data first (`npm run pipeline` done, filters in the config), then every section shell made with
  `npm run new-section`, then the helpers. One tab per helper, so no two edit the same file.
- Give each helper its rows of `PLAN.md`, the old code to copy, and the rules to keep. Not the conversation.
- Files, not folders. One check each; no extra testing.

## Sections helper
Fill in the `<...>` parts and send only the quoted text. `<work>` is the dashboard-work skill folder.

> Fill in the sections on the `<tab>` tab of the dashboard at `<dashboard>`. Each section exists as a shell: an
> analytic in `Analysis/<tab>.py` and a file `Src/Sections/<id>.jsx`. Copy existing logic and visuals; don't
> redesign them.
>
> Read only: `<work>/references/sections.md`, `Analysis/<tab>.py`, your sections' `.jsx` files, and the old code
> named below. Open nothing else.
>
> The sections:
> - `<id>`: `<title>`. Shows `<the visuals>`. Reads `<tables>`. Copy from `<old file and function / cell>`.
>
> For each section:
> 1. **Analytic:** copy the old calculation into its function. Return `data` for the drawing and `metrics` for the
>    note. The tables arrive already filtered. A report analytic is called live with `from_report`, never retyped.
> 2. **Look:** draw the same visuals in its `.jsx`. Colors from the theme (`fx()`). Replace "Not built yet".
> 3. No filter dropdowns; filters come from the config.
>
> When all are done, run `npm run check` once and fix what it names.
> Don't touch: `Src/Sections/index.js`, other tabs' files, `dashboard.config.json`, `Pipeline/`, `Data/`,
> `Src/Components/`, `Src/Lib/`. If a section can't be built as described, leave it "Not built yet" and say why.
> Don't invent numbers. Report a few lines per section: done or not, and anything assumed.

## Pipeline helper (one per table, only when there are many)
> Build one table, `<table>`, for the dashboard at `<dashboard>`. Read only the old code named below and the "A
> pipeline script" part of `<work>/references/data.md`.
> Copy from: `<old file and function / query>`. The table: `<one row is ...; columns ...>`. Rules: `<...>`.
> 1. Write `Pipeline/<table>.py`: the old prep code as it is, paths built from `Path(__file__)`, ending with
>    `write_dataset("<table>", df, grain=..., source=..., as_of=...)` from `_dataset_io`. Prep code that lives in
>    the project outside the dashboard is called with `outside("<path from the dashboard>", "<function>")`, not copied.
> 2. Run `npm run pipeline -- --try <table>.py` until it runs. That is the only check.
> Don't touch the user's files, other Pipeline scripts, `Data/`, `Analysis/`, `Src/` or the config. Don't run
> `npm run pipeline`. Report: the script path, its columns and row count, anything odd.
