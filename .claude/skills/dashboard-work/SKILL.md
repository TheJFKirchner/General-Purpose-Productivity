---
name: dashboard-work
description: "Change an existing dashboard (a folder with dashboard.config.json, Analysis/ and Src/Sections/). Mostly adding or editing a section; also new data, filters, looks, commentary tables, offline HTML reports and hosting. For a new dashboard, or porting work into one, use dashboard-new."
---

# Dashboard work

## How a dashboard is built
- Find it from the project's `CLAUDE.md` map (the `dashboard/` row). Run every command inside it.
- Tabs hold **sections**. A section is two files sharing an id such as `s3_paid_by_region`: its **analytic** (a
  function in `Analysis/<tab>.py` returning `data` and `metrics`) and its look (`Src/Sections/<id>.jsx`).
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
Run `npm run status`: tabs, sections, tables (source, as-of), filters, commentary ids, reports.
- "Show X", "add a chart of Y": **Add a section**. "Change", "fix", "move", "looks wrong": **Edit a section**.

## Add a section
1. Settle with the user: what it shows, its tab, and any new filter (its level, fast or slow).
2. Pick its tables from `npm run status`. No table has the data yet: add it first (`references/data.md`).
3. `npm run new-section -- <name> --title "<what it shows>" --page <tab> --tables <table> --chart echarts|table|kpi|text`.
4. Fill its analytic and its look (`references/sections.md`).
5. Add any new filter to the config; `npm run status` must list it on the section's `filters` line.
6. `npm run check`, fix what it names, show the user.

## Edit a section
First see what it does now: `python Analysis/check.py --show <id>`. Open only its two files. Then `npm run check`.

| The user wants | Change |
|---|---|
| Different numbers | Its analytic in `Analysis/<tab>.py` |
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
| Tables for the commentary skill | `npm run tables -- --sections <id,id> --by <column> --out <file>` |
| An offline HTML report | `references/exports.md`; then add it to the map's `dashboard/` row |
| Hosting; many sections at once | `references/hosting.md`; `references/helpers.md` (optional helpers) |
| Remove a section | Ask first, then delete its two files, its `index.js` line, and it from any report |

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
| `npm run shot -- <tab> <out.png> [region=West]` | A screenshot (uses or starts the dashboard) |
| `npm run dev` / `npm run stop` | Open it live (keeps running; prints its `Local:` address) / stop it |
| `python Analysis/check.py --show <id> [--filter name=value]` | One section's numbers |
| `npm run pipeline` (`-- --try <script>`) | Refresh all data (try one script) |
| `python Reports/<name>.py` | Build one offline HTML report |
