# Dashboard

Worked example: `examples/dashboard_programmatic/` in this skill folder (`demo_calls.py` runs every call below on mock data, with no dashboard UI).

## Setup (once per dashboard)

- Plan must settle: the snapshot column, the commentary filters, when the refresh happens.
- Shell needs: `as_of`, and explicit `dimensions` on every generator (`shell.md` section 5).
- `generate.py <shell> --setup` stamps `run_commentary.py` (the no-argument run) into the dashboard folder. Nothing else is created until the first run.

## Each data refresh

```
python run_commentary.py                       # no arguments
python run_commentary.py --override lob_trend  # optional
```

- Runs on the user's machine (the writer uses their Claude login), by hand or a local scheduler. Never on view.
- Reads the snapshot (as-of) → lists each generator's filter combinations from the data (or its `combinations` list) → skips combinations that already have commentary → writes, checks and saves the rest.
- Saves one output file for the snapshot: `commentary_outputs/commentary_<snapshot>_<time>.json`, every commentary filter combination inside. New snapshot (February after January): its own file; January's files stay as they are.
- Same snapshot rerun: a newer file only if something changed. The newest file per snapshot is shown.
- More than 50 combinations for a generator: that generator stops and is reported. Nothing is sampled.
- Four writer calls at a time. A failed unit never stops the run; it is retried on the next run.
- Restated data for an existing snapshot: warning only.

## Run time (the hosted dashboard)

```python
from runtime import CommentaryRuntime          # scripts/runtime.py; standard library only, safe to copy
rt = CommentaryRuntime.from_outputs("commentary_shell.json")      # once, at startup
rt.lookup("lob_trend", {"paid_month": "2026-10", "line_of_business": "Medicare", "region": "West"})
```

- Loads the newest output file of every snapshot once. A failed latest version shows blank.
- Uses only the unit's own commentary filters; other filters (region above) are ignored. Nothing found → blank. Never generates.
- Unverified bullets hidden unless the shell sets `"show_unverified": true`.
- The dashboard needs read access to the shell and `commentary_outputs/` (copy or sync them with the dashboard).

## Standalone HTML export

- `fill.py <shell> --export dashboard.html [--fix dim=value ...]` bakes in commentary for every combination the export still lets readers change, plus a small lookup. The page calls `window.Commentary.update(filters)` when a filter changes.
