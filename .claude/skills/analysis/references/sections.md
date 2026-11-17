# Sections (steps 3 and 5)

One file per piece of analysis: `sections/s1_<short_name>.py`, `s2_...`.

- The number is only a name; it never changes.
- The report shows sections as 1, 2, 3 in `REPORT` order; its footer lists the file behind each.

| Phase | A section file has | Run |
| --- | --- | --- |
| Analysis (step 3) | `TITLE`, `QUESTION`, `compute()`. No `charts()` needed | `python run.py s2`: prints its summary table. No HTML |
| Report (step 5) | Sections in `config.py` `REPORT` also get `charts()` and `NOTES` | `python run.py report` |

- `REPORT` sets which sections appear, in what order: `REPORT = ["s1", "s4", "s2"]`.
- Not in `REPORT`: kept, never loaded by the report, can be added later.
- No section file for every quick look. Only results worth keeping or rerunning.

## A section file

```python
TITLE = "Agreement between the two sources"          # short label, plain words
QUESTION = "How many claims appear in both sources, and how many in only one?"
NOTES = ""            # filled in after you have seen the results (see below)
EXPORT = []           # tables to save in full beside the report, e.g. ["differences"]


def compute(src, params):
    a = src("claims_a")                 # a source name from config.py
    b = src("claims_b")
    ...
    return {
        "match_status": match_status,   # feeds the chart
        "summary": summary,             # required: what the commentary is written from
    }


def charts(data):
    d = data["match_status"]            # the saved tables, read back from disk
    return [
        {"title": "Most claims appear in both sources",
         "option": {"xAxis": {"type": "category", "data": d["status"]},
                    "yAxis": {"type": "value", "name": "Claims"},
                    "series": [{"type": "bar", "data": d["claims"]}]}},
    ]
```

| Part | Rules |
| --- | --- |
| `TITLE` | A label, not a finding. The commentary step writes the finding heading |
| `QUESTION` | One plain sentence. No numbers, no answer. Name the comparison ("versus source B") |
| `compute(src, params)` | `src("name")`: the source as a DataFrame, exactly as read (dates are text; convert them). Returns `{table_name: DataFrame}`. No file reads or writes; `run.py` saves each table to `data/sections/s1_<table_name>.parquet` |
| `charts(data)` | Uses only `data`. May chart `data["summary"]` directly; do not save the same table twice. Returns a list of visuals (`charts.md`). `[]` when the commentary alone carries the claim |
| `NOTES` | Below |
| `EXPORT` | Full tables the reader will want as a file (the list of differing claims). Saved as CSV in `output/`, linked in the section |

## Shared logic

Steps several sections need (clean the keys, match the two sources): one optional file, `sections/shared.py`.

```python
import shared

def compute(src, params):
    matched = shared.matched(src, params)   # a function you wrote in shared.py
```

- `import shared` works as written; no path setup.
- Its functions take `src` and `params`, return DataFrames. No file reads or writes.
- Slow step: cache in a module-level dict so it runs once per run.

## The summary table

`summary` is the only data the commentary writer sees. Extra ones: `summary_<something>`.

- At most 50 rows, 15 columns; `run.py` stops if larger. Too wide: split into `summary` and `summary_<something>`.
- Holds every figure the commentary should state, including the comparison (both sources, both periods, the target).
- A real table: one row per thing compared (source, month, category), one named column per measure. Not `metric` / `value` pairs.
- Plain column names and category labels: `claims_only_in_a`, not `cnt_l_only`. The writer repeats what it sees.
- Ratios and differences as columns (`pct_of_total`, `gap`); nothing computed by eye.
- Each figure in the form it should be said (`times_normal`, not only a percent).
- A figure in two sections: same measure, same value in both. Two near-identical measures (98.6% and 98.9%): keep one.
- Headline figures with no natural rows: a one-row table with named columns.

## NOTES

What the tables cannot show: the cause found, a known data issue, what a code means. One to three plain sentences.

- Write after running the section and reading its tables.
- No figure unless the same figure is in a summary table. Uncheckable numbers are flagged.
- Unknown cause: say so. Do not guess.
- State any filter or adjustment `compute()` made that the table does not show ("large means paid at 10,000 or more", "voided claims removed"). The writer cites it in the commentary's `source`.
- A definition the reader must see ("a normal month is the average of the other five"): put it in a chart `note`. The writer may not repeat `NOTES`.

## Run

| Command | Does |
| --- | --- |
| `python run.py` | Run every section, print each summary table. No HTML |
| `python run.py s2` | Run section 2 only, print its summary table. No HTML |
| `python run.py status` | What exists, which sections are in the report, what is out of date |
| `python run.py report` | Run the `REPORT` sections, build the HTML. Stops if `REPORT` is empty |
| `python run.py build` | Rebuild the HTML from saved tables (after changing `charts()` only) |

A `STOP:` line names the file and the fix.

## Checklist

- [ ] `REPORT` matches the storyline: same sections, same order
- [ ] Each `REPORT` section's `summary` holds every figure its claim needs
- [ ] Each `REPORT` section has `charts()`, and `NOTES` written after seeing results
- [ ] No SQL, paths or file writes in any section or in `shared.py`
