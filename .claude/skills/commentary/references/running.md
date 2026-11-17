# Running: generate, review, edit, fill

Scripts are in `scripts/`, take the shell path, run from anywhere.

| Script | What it does |
| --- | --- |
| `status.py <shell>` | What is planned and what is shown now. Reads only the shell and the output files |
| `validate_shell.py <shell>` | Checks the shell; fix or ask about every error |
| `generate.py <shell>` | Writes missing commentary, checks every number, saves one output file, writes the run report |
| `generate.py <shell> --override <unit ...\|all>` | New commentary on purpose |
| `generate.py <shell> --use-version <unit> <n> [--dim k=v] [--as-of X]` | Go back to an earlier version |
| `edit.py <shell> <unit> --bullet "..." [--bullet "..."]` | Save a hand edit (`--from-file bullets.txt` for one bullet per line) |
| `fill.py <shell>` | Decks and reports: write `<name>_filled.pptx` / `.html` from the newest output file |

## What a run does

1. Reads the shell and the newest output file.
2. Finds units with no commentary yet, or whose last attempt failed. Everything else is reused.
3. Sends each group's tables to the writer (Claude, headless, no tools), one call per group, per filter combination on dashboards.
4. Checks every number against the tables. Failed check: one retry with the problems listed. Still failing: the unit is saved as failed and shows blank.
5. Saves **one new output file** if anything changed, and replaces `commentary_run.md`.

Rerun with nothing to do: no output file, only the report.

## Output files

The output to place: `commentary.json` beside the shell (`SKILL.md`, "The output"). Its history, in `commentary_outputs/`:

- Decks, reports: `commentary_<YYYYMMDD-HHMMSS>.json`
- Dashboards: `commentary_<snapshot>_<YYYYMMDD-HHMMSS>.json`, one per snapshot; every other filter lives inside

- Each file: a copy of the shell with the commentary written in. Complete: the newest file (per snapshot) holds everything shown.
- Never changed after it is written.

```json
{
  "deliverable": "dx_cost_dashboard", "medium": "dashboard", "snapshot": "2026-10",
  "saved_at": "2026-11-10T14:10:45.000000+00:00", "saved_by": "jdoe", "reason": "batch --override lob_trend",
  "units": [
    {"id": "lob_trend", "generator": "2", "placement": "tab: line of business / trend",
     "covers": "how this line of business's PMPM and membership moved versus last month",
     "filters": ["paid_month", "line_of_business"],
     "commentary": [
       {"filters": {"paid_month": "2026-10", "line_of_business": "Medicare"},
        "version": 2, "source": "generated", "status": "ok",
        "bullets": [{"text": "...", "unverified": false, "numbers": [], "verified_values": [], "flags": []}],
        "missing": [], "error": null, "input_hash": "...", "plan_hash": "...",
        "model": "claude-sonnet-5-5", "created_at": "...", "created_by": "jdoe"}
     ]}
  ]
}
```

- `version`: per unit and filter combination. Goes up each time that piece is regenerated, edited or rolled back.
- `source`: `generated` or `edited`. `status`: `ok` or `failed` (failed shows blank).
- `unverified` bullets: hidden on dashboards unless the shell sets `"show_unverified": true`. Shown in decks and reports unless filled with `--drop-unverified`.
- Unit removed from the shell: kept in later files, marked `"removed_from_shell": true`.

## Frozen by default

- Saved commentary: reused on every run.
- Data restated (same snapshot, tables changed) → warning in the report, commentary left alone.
- Shell changed for a unit → warning, commentary left alone.
- Last attempt failed → tried again on the next run.

## Changing commentary on purpose

- `--override all`: new version of every unit (at the current snapshot), except units whose shown version is a hand edit (listed in the report).
- `--override <unit> ...`: the unit's whole group goes to the writer; only the named units get a new version. Naming a hand-edited unit regenerates it.
- `--use-version <unit> <n>`: re-saves version n as the newest, so it shows again.
- Hand edits: `edit.py`, saved as a new version with `source = edited`, not number-checked. Dashboards: pass every filter of the unit with `--dim` (for example `--dim paid_month=2026-10 --dim line_of_business=Medicare`).

Each saves one new output file.

## After every run

Read `commentary_run.md` and report back:
- Counts: generated, reused, failed, unverified, stale.
- Every unverified bullet: ask keep, edit or drop.
- Every "Writer says this is missing" note: usually a table or comparison the plan should add.
- Never call a number verified unless the checker verified it.
