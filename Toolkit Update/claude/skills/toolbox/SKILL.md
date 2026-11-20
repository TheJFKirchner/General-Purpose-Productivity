---
name: toolbox
description: Use when starting a new analysis project or fully rescoping one ("new project", "set up this project", "start over on the scope"). Asks what is being made, agrees the fewest folders, writes the "## Map" into the project's CLAUDE.md and writes a project plan. Not for work inside a project that already has a map, except to add one map line for a new kind of output.
---

# Toolbox

One short talk, a map in `CLAUDE.md`, a plan. Skip any question the request already answers.

## New project

1. Ask what is being made: analysis, data asset, Excel file, dashboard, deck, or a mix. Propose the fewest folders (table below). The user edits.
2. Ask who it is for, what it should answer, what success looks like. "Exploration" is a fine answer.
3. Goals with a date, rise, rate, "material" or "fastest": ask the date basis (when it happened or when it was paid), the periods compared, any threshold. Unknown: `Open: <question>` in Choices.
4. Show the plan; the user edits. Write `plan.md` and the `## Map` section of `CLAUDE.md`, replacing only that section. No `CLAUDE.md`: create it as `# <plan title>`, then the map.

| Making | Folders, at most |
| --- | --- |
| Analysis report | `reports/` (one folder per report, made by `analysis`) |
| Data asset | `pipeline/`, `data/` |
| Excel file | `exports/` |
| Dashboard | `dashboard/` (inner folders are made by `dashboard`) |
| Deck | `deck/` |

- A mix: join the rows. `pipeline/` only when data must be joined or cleaned before more than one deliverable uses it. `analytics/` only for scripts shared by more than one output (such as prep code a dashboard runs). Other names only if the user asks.
- Create no folders except `inputs/`: files handed over go there now, unchanged. Live or large sources (a database, a shared file that updates) are not copied; name them in Choices.

## Files

```markdown
## Map
- Project plan: [plan.md](plan.md)

| Folder or file | Holds |
| --- | --- |
| `inputs/` | `sales.csv` from finance, 2026-11-18. Replaced 2026-12-01: adds December |
| `reports/review/` | Report: Quarterly review. Refresh: new input files go where `report.py` SOURCES points (same names), then `python run.py report` in this folder |
```

- The map lists only what exists. Planned deliverables go in Making; each skill adds its own row when it makes the file or folder (Findings, Design library).
- Map and plan use relative or shared paths only, never one person's computer. One exception: a dashboard kept outside a synced project folder (`dashboard`).
- Anything run again (a report, a dashboard): end its row with `Refresh: <one command or step>`.

```markdown
# Plan: <project>
- For: <audience>. Success: <how we know it worked>
- Making: <deliverables>
## Goals
1. <question or goal>
## Choices
- <working choices: date basis, periods, thresholds, assumptions, live sources; Open: <question>>
```

## Later

- New kind of output: propose one map line and add it to the plan's Making line, when the user says yes.
- Rescope: rewrite `plan.md` in place. New goals continue the numbering; never reuse one, findings cite them. Add a dated line under `## History`: what changed, who asked, why, dropped goals with their old numbers.
- Then rewrite the map. A folder that leaves scope keeps its row as `Old since <date>: <what it held>, not maintained (<reason>)`. Never delete or move files. Match the `CLAUDE.md` title to the plan.
