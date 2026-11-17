# Deck

Worked example: `examples/deck_pptx/` in this skill folder.

- Order: plan the slides and the commentary first (`commentary_plan.md`, then the shell). This skill fills in commentary after the deck exists.
- Runs once, in session, per edition. No `as_of` needed; each run saves `commentary_outputs/commentary_<time>.json`.
- Grouping: slides on one subject share a generator (one writer call); each slide is its own unit and gets its own text.
- Executive summary: its own generator with `"inputs": "commentary"`, units with `"tables": []`. Runs last, from the other units' verified commentary only, and its numbers are checked against those.

## Review, then fill

1. `generate.py <shell>`
2. Show the user the Review section of `commentary_run.md`. Call out every `[unverified]` bullet and every "Writer says this is missing" note.
3. Changes: wording → `edit.py <shell> <unit> --bullet "..."`; a different take → `generate.py <shell> --override <unit>`.
4. `fill.py <shell>` (add `--drop-unverified` to leave unverified bullets out) → `<deck>_filled.pptx`.

- Fill keeps the placeholder paragraph's formatting; each bullet becomes its own paragraph in that text box. Put the placeholder alone in its paragraph, in a top-level text box (not inside a table or group).
- A rerun reuses saved commentary. Nothing regenerates without `--override`.
