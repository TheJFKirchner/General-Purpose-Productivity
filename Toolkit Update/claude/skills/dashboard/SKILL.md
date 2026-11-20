---
name: dashboard
description: Make a new dashboard (tabs, filters, charts on live data) or change one (a folder with dashboard.config.json). Sections are design library items copied by id, wired to a table, then edited. Also porting, new data, filters, offline reports, hosting.
---

# Dashboard

A section is one file, `Src/Sections/sN_name.jsx`. "The map" is the project's `CLAUDE.md` folder map.
Run commands in the dashboard folder (the map's `dashboard/` row).

## Before building
One message, one yes: who uses it, the questions it answers, tabs, sections (claim, item), filters.
Keep it in `PLAN.md` (`references/plan.md`). Told "just do it": list what you assumed.

## Make a new one
1. Folder: the map's `dashboard/` row; none, ask. Never in OneDrive: the workspace dashboards folder.
2. `python <skill>/tools/setup.py <folder> --title "..." --theme TH-01`, then add the `dashboard/` row to the map.
3. Per input file, in `Pipeline/sources.py`: `write_source("claims", "../inputs/claims.csv", as_of_from="date")`; `npm run pipeline`.
4. Filters: `dashboard.config.json` (`references/data.md`).

## Add from the library
1. Library: the map's `Design library:` line; else `design-library` beside `.claude`; else `Toolkit Update/design-library`.
2. Read the index files the request needs there (`index/charts.md`, `tables.md`, `hero-cards.md`); note each pick's `data:` line.
3. `npm run new-section -- NAME --use CT-34 --page overview --tables claims --slot label=region --slot value=paid,allowed`
4. Options: `--agg mean|count`, `--by COL` (a line per value), `--month` (groups the date in the text slot), `--top N`,
   `--share`, `--pareto COL`, `--size half`. `rows` counts rows. No text slot given: one row per measure (tiles).
5. Two periods or values: `--compare service_date=2026-04,2026-05`. Waterfall (CT-06): `--slot step=GROUP --slot total=AMOUNT`.
6. It prints what it did and the lines to reword. No `--slot`: a stub in `Analysis/<tab>.py` (`references/sections.md`).

## Change a section
- One file holds it all: `meta` (title, tab, size, `x`, `y`, `agg` ...), `slots`, `names`, `format`, `note`, `basis`, `chart` or `html`.
- Edit it by hand. A third line: its column in `meta.y` and `slots`, one more series in `chart`.
- A line per category: `by: 'col'` in `meta`, `'*'` in that slot. Axis names, ranges, colours, `format` the same way.
- Data lists refill at every draw and filter change; your edits stay.

## Make your own
`npm run new-section -- NAME --own chart --page overview --tables claims` (or `--own html`): a blank section. Then as above.

## Page-level changes
- Theme: `npm run theme -- TH-02` (ids: the library's `index/themes.md`). Order: the list in `Src/Sections/index.js`.
- Spacing, page width, chart height: the settings at the top of `Src/custom.css`.
- Width: two neighbouring sections with `size: 'half'` share a row at one height; any other section is full width.

## Run, check, look
- `npm run status`: tabs, sections, tables and columns, filters. Read it before adding.
- `npm run check`: fix every ERROR, and every WARN about sample words, sample ranges or column words.
- `npm run shot -- [tab or id] [lob=Medicare]`: a picture plus `check` lines (cut off, overlapping, hidden labels).

## Rules
- Titles say what is shown. Notes use `{metric|format}`, never typed numbers. No column names or company names shown.
- User likes a visual, or says save it: launch `design-librarian` with the files and the library folder.
- Never edit the user's files. Never open `Src/Lib`, `Src/Components`, `Tools`, `Analysis/Shared`.

## Elsewhere
- New data, slow filters, a report's analytics: `references/data.md`
- Section parts, hand-written analytics: `references/sections.md`
- Offline HTML reports: `references/exports.md`; live view: `npm run dev`, `npm run stop`
- Hosting: `references/hosting.md`; many sections at once: `references/helpers.md`
- Generated commentary: `npm run tables -- --sections <id,id> --by <col>`, then the commentary skill
- Porting notebooks, scripts, a report or an old dashboard: `references/port.md`
