# Add to CLAUDE.md

- Paste everything below the line into the workspace or user-level CLAUDE.md. Fill the two `<...>` places.
- Paste nothing into a project's CLAUDE.md: the `toolbox` skill writes each project's map, and the other skills add their rows.

---

## Analysis toolkit

### Installed
- Skills: `<.claude folder>/skills/`. Agents: `<.claude folder>/agents/`.
- `design-library/` and `brain/`: beside that `.claude` folder.

### Needed before first use (once per machine)
- Reports: Python with pandas; pyarrow for kept or `.parquet` sources; openpyxl for `.xlsx` sources and Excel exports.
- Dashboards: Node.js; Python 3.10+ with fastapi, uvicorn, duckdb, pyarrow, pandas.
- Decks, design library: Node.js.
- Screenshots: Edge or Chrome. Opening a report, deck or library item: internet (charts load from a CDN).
- Agents: a sign-in that allows the `sonnet` and `haiku` models.
- No environment variables anywhere; settings live in each output's own files.

### Synced folders
- Workspace dashboards folder, outside OneDrive and every synced folder: `<path>`. `dashboard-new` puts dashboards for projects in a synced folder there.

### Project layout
Folders appear only when they hold a file. Other names only if the user asks.

| Folder | Holds |
| --- | --- |
| `inputs/` | Files handed over, unchanged, even when one output uses them. A replacement keeps the name; add `Replaced <date>: <what changed>` to the map's `inputs/` row |
| `reports/`, `deck/` | One folder per report, per deck |
| `dashboard/` | One dashboard. Its own `Exports/` holds only its offline HTML files |
| `exports/` | Excel files and other tables handed out |
| `pipeline/`, `data/` | A data asset |
| `analytics/` | Code shared by more than one output |

- Never anywhere: an empty folder, saved query results, intermediate tables, scratch files.
