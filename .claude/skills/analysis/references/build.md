# Building a report

```
<name>/
  report.py      brief (docstring), sources, the answer, the sections      you write
  analytics/     <name>.py: analytic functions, several per file            you write
  run.py         the one command                                            copied, never edit or read
  page.html      the look                                                    copied, edit only to restyle
  <name>.html    the report; CSV exports sit beside it                      built
```

Nothing else is created. `data/` appears only if `KEEP` names a source. `inputs/` or `sql/` only when a file or query needs a home.

## An analytic

One function, one question. Takes `(src, params)`, returns a dict:

```python
def monthly_paid(src, params):
    df = src("claims")                                   # a SOURCES name; a fresh copy each call
    df["month"] = pd.to_datetime(df["paid_date"]).dt.strftime("%b")
    by_month = df.groupby("month", sort=False, as_index=False)["paid_amount"].sum()
    is_m = by_month["month"] == params["month"]           # from DEFAULTS, not a literal
    paid = by_month.loc[is_m, "paid_amount"].sum() if is_m.any() else None
    normal = by_month.loc[~is_m, "paid_amount"].mean() if (~is_m).any() else None
    return {
        "question": "How does the month compare with a normal month?",
        "tables": {"by_month": by_month},                # DataFrames: charts and tables use these
        "metrics": {"paid": paid, "normal": normal,      # single values: text uses these
                    "times": paid / normal if paid and normal else None},
        "notes": "A normal month is the average of the other months.",
    }
```

- Plain names in tables and metrics, and plain category values ("Hospital stay", not "Inpatient" or "IP"); rename in the analytic, not in the chart.
- Every figure the text will state is a metric, ratios and differences included. Nothing worked out by eye.
- Every date window, cut-off and comparison period lives once, in `DEFAULTS` at the top of the analytics file (`DEFAULTS = {"month": "May"}`), never as a literal. A dashboard calling the analytic uses the same values.
- `PARAMS` in `report.py` only when this report differs; the analytic gets `{**DEFAULTS, **PARAMS}`.
- Take rows from `src` and do not assume they are the full file: a dashboard calls the same function on filtered rows.
- Cope with empty or tiny input: return empty tables and `None` metrics, never crash.
- No file reads or writes; no SQL. Helpers start with `_` (or live in `analytics/_helpers.py`).
- `python run.py` runs them all and prints questions, metrics and tables; `python run.py monthly_paid` runs one.

## report.py

| Setting | What |
| --- | --- |
| `TITLE`, `QUESTION` | Report title; the question in plain words (not shown when it restates the title) |
| `FOR` | The reader, shown at the top: "For finance leads · 19 November 2026" |
| `SOURCES` | `{"claims": "inputs/claims.csv"}`, relative to the report folder. `.csv .tsv .parquet .xlsx .sql`, or a function returning a DataFrame. A path outside the folder is fine for big files |
| `PARAMS` | Only values where this report differs from `DEFAULTS`. Analytics read `params["x"]`; `.sql` files use `{x}`; text uses `{params.x}` (either source) |
| `KEEP` | Sources to save in `data/` and reuse until `--refresh`. Only for slow queries. Default: nothing saved |
| `run_query(sql)` | Only for `.sql` sources: returns a DataFrame. Credentials stay out of the folder |
| `ANSWER` | `headline` (one sentence), `basis` (required: which date, compared with what, exclusions, data through when), `bullets` (optional, up to 3), `kpis` (optional, 2 to 4) |
| `SECTIONS` | List of dicts, below, in reading order |

## Figures in text

Every number in text is a placeholder that pulls a metric when the report builds.

| Write | Gives | Where |
| --- | --- | --- |
| `{times:.1f}` | 1.8 | A metric of the section's own analytic |
| `{monthly_paid.paid:$short}` | $4.1M | Any analytic's metric (needed in `ANSWER`) |
| `{share:.0%}` / `{claims:,}` / `{gap:$,.0f}` | 62% / 20,220 / $1,234 | Python formats; a leading `$` adds the sign (never with `%`) |
| `{change:abs.0%}` | 57% (from -0.57) | `abs` drops the sign: "fell {change:abs.0%}" |
| `{params.month}` | May | A parameter |

- `**Lead phrase.**` at the start of a bullet shows in bold.
- `run.py report` stops on a missing metric. It prints `check:` for a typed number that is not a year or a `DEFAULTS`/`PARAMS` value, and for a section figure that repeats an answer figure. Fix every `check:`.

## A section

```python
SECTIONS = [
    {"analytic": "monthly_paid",
     "title": "{params.month} paid {times:.1f} times a normal month",   # the finding, as a sentence
     "bullets": ["**One provider.** ...", "...", "..."],          # up to 3, about 25 words each
     "chart": {"type": "bar", "table": "by_month", "x": "month", "y": "paid_amount",
               "axis": "Paid amount", "format": "$short", "highlight": "{params.month}"},
     "kpis": [("Paid in {params.month}", "{paid:$short}", "vs {normal:$short} a normal month")],
     "note": "A normal month is the average of the other months.",
    },
]
```

| Key | What |
| --- | --- |
| `analytic` | Required. The function this section shows |
| `title` | Required. The finding, not a label |
| `bullets` | The reading of the result. Lead with the point |
| `chart` | Shorthand below, or a function of the tables returning an ECharts option (`charts.md`) |
| `kpis` | Figures that prove the point: `(label, value)` or `(label, value, note)`. Not the same figures as the bullets |
| `table` | `{"table": "top", "columns": {"provider": "Provider", "paid": "Paid"}, "format": {"paid": "$,.0f"}, "top": 10, "title": "..."}` |
| `layout` | `"side"` (default): bullets left, chart right. `"wide"`: chart full width, bullets as columns below. Wide suits time series and long category lists |
| `note` | One line under the chart: a definition or caveat |
| `export` | Table names saved in full as CSV beside the report, linked in the section |

## Chart shorthand

| Key | What |
| --- | --- |
| `type` | `bar`, `hbar` (long labels; sorted largest on top), `line`, `stack`, `scatter` |
| `table`, `x`, `y` | Table name, category column, value column (or a list for several series) |
| `axis` | Value-axis name with unit, about 25 characters. `x_axis` for scatter |
| `format` | Value format for axis, labels and tooltips: `$short`, `.0%`, `,` |
| `highlight` | Category (or list): the bar drawn orange; on lines and stacks, the band shaded |
| `ref` | Threshold line: `0.25` or `(0.25, "Material")` |
| `sort`, `top` | Sort by the first value column; keep the first N rows |
| `names` | `{"paid_a": "Source A"}`: legend names |
| `title`, `height` | Caption above the chart; pixels (default 300 side, 340 wide) |

Value labels show on single-series bars of 15 or fewer. Colours, fonts, axes and tooltips come from `page.html`.

## Commands

| Command | Does |
| --- | --- |
| `python run.py` / `python run.py NAME` | Run analytics, print results. No report |
| `python run.py report` | Build `<name>.html`. Rewrites it each time |
| `python run.py text` | The report as plain text (for a cold read) |
| `python run.py shot [OUT.png]` | Screenshot of the built report with Edge or Chrome (default `<name>_shot.png`). Charts load from the internet |
| `python run.py data NAME [TABLE] [--json] [--out FILE]` | One table (or `metrics`) as CSV or JSON, for a deck or dashboard. Prints unless `--out` |
| `--refresh` | Pull `KEEP` sources again |

Rerun: see `SKILL.md`, "Existing report folder".
