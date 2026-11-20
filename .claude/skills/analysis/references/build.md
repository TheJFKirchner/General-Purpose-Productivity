# Report folder: the rarer parts

Everyday section changes are in `section.md`. This page is for settings, sources, sharing and commands.

```
<name>/
  report.py          brief (docstring), SOURCES, PARAMS, ANSWER, SECTIONS (the order)
  sections/          sN_<name>.py: one file per section; _shared.py: DEFAULTS and helpers
  run.py, page.html  copied; never edit or read run.py; page.html only its settings block
  <name>.html        the report; CSV exports sit beside it
```

`data/` appears only if `KEEP` names a source; `inputs/` or `sql/` only when a file or query needs a home.

## report.py

| Setting | What |
| --- | --- |
| `LIBRARY` | The design library, relative to the report folder; set by `new_report.py`, searched for when empty |
| `TITLE`, `QUESTION`, `FOR` | Title; the question (hidden when it restates the title); the reader, shown at the top |
| `SOURCES` | `{"claims": "inputs/claims.csv"}`, relative to the report folder. `.csv .tsv .parquet .xlsx .sql`, or a function returning a DataFrame |
| `PARAMS` | Only where this report differs from `DEFAULTS`. Sections read `params["x"]`; `.sql` files `{x}`; text `{params.x}` |
| `KEEP` | Sources saved in `data/` and reused until `--refresh`. Slow queries only |
| `run_query(sql)` | For `.sql` sources: returns a DataFrame. Credentials stay out of the folder: ask the user how this machine connects; never write a password, token or connection string into the project, the map or a skill |
| `ANSWER` | `headline` and `basis` (which date, compared with what, exclusions, data through when) are required; `bullets` (up to 3) and `kpis` (2 to 4) optional. Figures as `{section_name.metric}` |
| `SECTIONS` | Section file ids in reading order: `["s1_hospital_stays", "s2_paid_by_month"]` |

## Shared values and dashboards

- Every threshold, period and cut-off lives once, in `DEFAULTS` in `sections/_shared.py`; a section gets `{**DEFAULTS, **PARAMS}`.
- A section may import helpers: `from _shared import DEFAULTS, my_helper`.
- A dashboard calls a section's analytic live: add `<report>/sections` to the import path, then `from s2_paid_by_month import paid_by_month` and call `paid_by_month(src, {**DEFAULTS, **params})` with its filtered rows behind `src`.
- Another skill that only needs numbers: `python run.py data NAME [TABLE] [--json] [--out FILE]`.

## Rerun with new data

- Compare the new file's date range and row count with the old one and update `DEFAULTS` (or `PARAMS`, if only this report differs).
- `python run.py report`, then reread the headline, `basis`, titles and bullets: placeholders and visuals update, words do not. A section that changes the answer means rewriting `ANSWER`.
- New question: new folder.

## Checks

- `run.py report` stops on a missing metric, an empty `basis`, or a format mixing `$` and `%`.
- It prints `check:` for a typed number that is not a year or a `DEFAULTS`/`PARAMS` value, a section figure that repeats an answer figure, a section with no `DESCRIPTION`, words left from the library sample, and a `TODO`. Fix every `check:`.

## Commands

| Command | Does |
| --- | --- |
| `python run.py list` | The registry: sections in order (file, library id, title, description), then sources with columns, types and date ranges |
| `python run.py add-section NAME --use ID --source SRC --slot SLOT=COL[,COL] ... [--period month\|quarter\|year] [--top N] [--compare COL=A,B] [--agg sum\|mean\|count] [--by COL] [--where COL=VALUE] [--library DIR] [--desc "..."] [--bullets N] [--after N]` | Copies a library chart, table or hero card into a working `sections/sN_NAME.py` and adds it to `SECTIONS`. A date column in a text slot is grouped by `--period`. `--top N` keeps the N largest groups. `--compare` puts two periods or values side by side: for a waterfall (CT-06) it builds the base, total, rise, fall and key columns and starts the axis where the bars do; for figure cards (HC-15) it makes A, B and the change. `--where` (repeatable, `=`, `>=`, `<=`) limits the rows. `--by` splits the number column into one column per group (top five, the rest summed). `--library` is saved in `report.py` |
| `python run.py add-section NAME --own chart\|html [--source SRC]` | A blank section to make your own (the first source unless named) |
| `python run.py theme TH-02` | Puts a library theme on `page.html` (needs Node.js, as `--use` does; building does not) |
| `python run.py NAME` | Runs one section's analytic: question, metrics, table columns, 3 rows (`--rows N`) |
| `python run.py report` | Builds `<name>.html` (rewritten each time); with no sections yet, the page shell |
| `python run.py shot [OUT.png]` | Screenshot of the built report with Edge or Chrome. Charts load from the internet |
| `python run.py data NAME [TABLE] [--json] [--out FILE]` | One table (or `metrics`) as CSV or JSON. Prints unless `--out`. `--out <file>.xlsx`: a workbook (needs openpyxl), one sheet per table when TABLE is left out; files handed out go in the project's `exports/` |
| `--refresh` | Pull `KEEP` sources again |
