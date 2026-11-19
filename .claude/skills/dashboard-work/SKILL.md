---
name: dashboard-work
description: "Change an existing dashboard (a folder with dashboard.config.json, Analysis/ and Src/Sections/). Mostly adding or editing a section; also new data, filters, looks, commentary tables, offline HTML reports and hosting. For a new dashboard, or porting work into one, use dashboard-new."
---

# Dashboard work

## How a dashboard is built
- Find it from the project's `CLAUDE.md` map (the `dashboard/` row). Run every command inside it.
- Tabs hold **sections**. A section is one file, `Src/Sections/<id>.jsx`: meta (title, tables, description, and
  for simple ones the numbers: `x`, `y`, `agg`), note and chart. Numbers are worked out in Python: from the meta,
  or by its own **analytic** in `Analysis/<tab>.py` when the calculation is unusual.
- **Data:** `Data/Current/`, one file per table, filled by `Pipeline/` scripts or dropped in.
- **Settings:** all in `dashboard.config.json`. No environment variables. Edit files with the Edit tool; on
  Windows never `Set-Content`.
- **Filters** live in the config, each at one level:

| Level | In the config | Shown | Applies to |
|---|---|---|---|
| Dashboard | no `tab` or `section` | above the tabs | every section |
| Tab | `"tab": "<tab id>"` | under the tab names | that tab's sections |
| Section | `"section": "<section id>"` | in the section's header | that section |

  Fast (`filters`) narrow loaded data; slow (`parameters`) re-query the source. Sections draw no filter dropdowns.

## First: add or edit?
Run `npm run status`: every section (file, title, chart, tables, description), every table's columns, reports.
- "Show X", "add a chart of Y": **Add a section**. "Change", "fix", "move", "looks wrong": **Edit a section**.

## Add a section
Run commands in the map's `dashboard/` folder, not the project root. Read nothing else; options: `references/sections.md` "Simple add".
1. `npm run status`. Already there (same table, grouping, measure)? Tell the user which section; ask first.
2. `npm run new-section -- <name> --page <tab> --tables <t> --chart bar|line|table|kpi --x <col> --y <col> --note "a | b"`.
3. `npm run check`. 4. `npm run shot -- <id>` (own server; saved in `Data/.shots/`, not kept), look, show the user.

Several tables, an unusual calculation or a report's analytic: the same page, below STOP HERE. A new filter:
the config, at its level; `npm run status` then lists it on the section.

## Edit a section
First see what it does now: `python Analysis/check.py --show <id>`. Open only its `.jsx` (its Python function too,
when it has one and the numbers change). Then `npm run check`.

| The user wants | Change |
|---|---|
| Different numbers | `x`, `y`, `agg`, `by` in its meta, or its analytic in `Analysis/<tab>.py` |
| Another chart or table, title or note | Its `.jsx` (`references/sections.md`). Titles say what is shown |
| Looks only (colors, fonts, spacing) | `Src/custom.css` scoped to `#<id>`, or `Themes/default/tokens.json` |
| Another tab | `tab:` in its meta only; the analytic stays where it is |
| Different filters | The filter's level in the config, not the section |
| Its commentary | `commentary: 'C1'` in its meta; the text is in `commentary.json` |

## Everything else
| Task | Do or read |
|---|---|
| **New data** | `npm run status`; replace the input files where it shows each source (same names); `npm run pipeline`, `npm run check`, `npm run status` again: it lists notes that changed; tell the user which answers moved. Regenerate commentary if `commentary.json` exists. Update the map's `dashboard/` row |
| Data, report analytics, slow filters | `references/data.md` |
| Tables for the commentary skill | `npm run tables -- --sections <id,id> --by <column>`; use the file name it prints |
| An offline HTML report | `references/exports.md`; then add it to the map's `dashboard/` row |
| Hosting; many sections at once | `references/hosting.md`; `references/helpers.md` (optional helpers) |
| Remove a section | Ask first, then delete its `.jsx` (and its analytic, if any), its `index.js` line, and it from any report |
| User likes a visual, or says save it | Launch `design-librarian` with the files and the library folder (the map's optional `Design library:` line, for a library kept elsewhere; else `design-library` beside `.claude`, else `Toolkit Update/design-library`) |

## What to open
| | Files |
|---|---|
| **Edit** | `dashboard.config.json`, `Pipeline/<table>.py`, `Analysis/<tab>.py`, `Src/Sections/*.jsx`, `Src/Sections/index.js`, `Src/custom.css`, `Themes/`, `Reports/<name>.json`, `Reports/<name>.py`, `commentary.json` |
| **Run, don't read** | The commands below. Their output is the answer |
| **Never open** | `Src/` except `Sections/` and `custom.css`; `Analysis/Shared/`, `server.py`, `check.py`, `precompute.py`; `Pipeline/run_all.py`, `_dataset_io.py`; `Reports/_report.py`; `Tools/`; `index.html`, `package*.json`, `vite*.config.js`, `node_modules/`, `Data/` |

In this skill folder open only this page and the reference a step names. Helpers get a brief, never a folder.

## Commands (in the dashboard folder)
| Command | Does |
|---|---|
| `npm run status` / `npm run check` | Map of the dashboard / every section, filter and report is sound |
| `npm run shot -- <tab or id> [region=West]` | A screenshot in `Data/.shots/` (git-ignored, not kept); starts and stops its own server if needed |
| `npm run dev` / `npm run stop` | Open it live (keeps running; prints its `Local:` address) / stop it |
| `python Analysis/check.py --show <id> [--filter name=value]` | One section's numbers |
| `npm run pipeline` (`-- --try <script>`) | Refresh all data (try one script) |
| `python Reports/<name>.py` | Build one offline HTML report |
