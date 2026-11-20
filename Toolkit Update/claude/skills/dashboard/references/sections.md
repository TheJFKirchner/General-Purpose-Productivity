# A section file

Each section is one file, `Src/Sections/sN_<name>.jsx`, holding everything for that block. `npm run status` says
which file is which. Change a section by editing its file, then `npm run check` and `npm run shot -- <id>`.

| Part | What |
| --- | --- |
| `meta` | `id`, `title` (what is shown), `tab`, `size: 'half'` (optional), `use` (the library id it came from), `description` (8 to 10 words for status), `commentary` (optional commentary.json id), and the numbers (below) |
| `slots` | Which column fills which slot of the item: `{ label: 'region', value: ['paid_amount', 'billed_amount'] }`. `'*'`: every column not used by another slot (the columns `by` makes). A number: a figure given as is (`target: 80`) |
| `names` | Words the reader sees for a column (legend, table headings, tile labels): `{ paid_amount: 'Paid' }` |
| `format` | Number format per column: `$short` ($4.1M), `short`, `comma`, `$comma`, `pct` (12%, values 0 to 100), `.1%` (a fraction), `month` (2025-06 as Jun 25), or a pattern like `'{value} days'`. `'*'`: any column not listed |
| `note` | The text above the item. Figures only as `{metric|format}` (formats: `compact`, `short`, `int`, `money`, `pct:1`, `change`, `month`, `name`) |
| `basis` | The line under a chart; may hold `{metric|format}` |
| `chart` | The copied ECharts option, with its `"slot"` marks. May also be a function `(rows, metrics) => option`; `slots`, `names` and `format` still fill and format what it returns |
| `html` | A copied table or hero card (`css`, `script`: its own styles and script) |
| `<Item ... />` | Draws it. `height={300}` sets this chart's height |

## The numbers (meta)

Worked out in Python on the filtered table; no Python to write.

| Key | Means |
| --- | --- |
| `tables` | `['claims']`: the table (the first one is used) |
| `x` | The column to group by. `period: 'month'` (or `quarter`, `year`) groups a date column first |
| `y` | `['paid_amount']`, one or more columns; `'rows'` counts rows |
| `agg` | `sum` (default), `mean`, `count` |
| `by` | A second column: one value column per value of it (a line or a stacked part each). Its slot then takes `'*'` (`slots: { value: '*' }`) |
| `compare` | `'service_date=2026-04,2026-05'`: two values of one column (dates match by their start). With `shape: 'waterfall'` a bridge from A through each group's change to B; with `shape: 'totals'` rows for A, B and the change; otherwise a column for A and one for B. Metrics: `start`, `end`, `start_label`, `end_label`, `change`, `change_amount`, and for a bridge `largest_step`, `largest_step_label` |
| `top` | The N largest; with `by`, `pareto` or `waterfall` the rest become "All other". Shares in the note are of every row, not of the top N |
| `shape` | `share` adds `share` (% of the total); `pareto` sorts largest first and adds the running `share`; `waterfall` gives `base`, `rise`, `fall`, `total`, `key` up to a Total bar (the value axis starts near the lowest bar when all sit well above zero); `totals` (no `x`) gives one row per `y` column: `label`, `value` |
| `sort` | `value` (largest first; default unless dates), `label`, `none` |
| `ignore` | `['region']`: filters that must not narrow it (it compares their values); the page tags it "Region: all". The way for every section, with or without its own analytic |

Metrics for the note: `total` (or `average`), `largest`, `largest_label`, `count`; dates add `latest`,
`latest_label`, `change`, `change_label`; other groups add `largest_share`, `smallest`, `smallest_label`; `by`
adds `top_series`, `top_series_share`. One section's numbers: `python Analysis/check.py --show <id>`.

## Filling at every draw

- In `chart`, an object with `"slot": "value"` gets its `data` from the columns in `slots.value`, one column per
  marked series, in order. A category axis gets the column's values. `"slot": "x,y"` takes rows of pairs;
  `"slot": "target:yAxis"` sets one property from a figure.
- More columns than marked series: the last series repeats for each extra column. A series with no column goes.
- In `html`, the element marked `data-rows` repeats its first child once per row. `data-slot="name"` puts the value
  in; `name@class` sets a state class (`good`, `bad`, `neutral`); `name@width` a width in %. Headings take `names`.
- Only the data lists and the repeated rows are replaced. Names, colours (`"var(--blue)"`, `"var(--orange)"`,
  `"var(--chart-muted)"`), axis names and ranges, label styles stay as written.
- A series keeps a `name` you give it; without one it takes `names`.
- `{c:fmt}` and `{value:fmt}` in a formatter take the column's `format`; a label or value axis without a
  formatter gets it too. A formatter you write yourself wins.

## A visual of your own

`npm run new-section -- NAME --own chart` (or `html`) writes a working blank section. For a chart, write ECharts
options (echarts.apache.org/en/option.html) and mark where columns go with `"slot"`. For HTML, use the library's
kit classes (`lib-panel`, `lib-cards`, `lib-card`, `lib-lab`, `lib-big`, `lib-table`; the library's
`AUTHORING.md` lists them). Colours only as theme tokens.

## A hand-written analytic

For several tables or a calculation the meta can't say: `--use <id>` without `--slot` writes the copy and a stub
in `Analysis/<tab>.py`. Make it return rows whose columns the `slots` name, and delete the numbers from the meta.
```python
@section("s3_paid_by_region", tables=["claims"])
def paid_by_region(t):
    """Which regions carry the most paid claims?"""
    by = t.claims.groupby("region", as_index=False)["paid_amount"].sum().sort_values("paid_amount", ascending=False)
    return {"data": {"rows": by.to_dict("records")}, "metrics": {"top_region": by["region"].iloc[0]}}
```
- Tables arrive filtered; never filter again. `t.filters["region"]` is the choice, `t.params` the slow filters.
- A section comparing regions: `ignore: ['region']` in its meta, as for any section.
- `from Shared.periods import change, ratio, total, sum_by, last_periods, month_label`. All return `None` rather
  than fail.

## A report's analytic, live
One function serves the report and the dashboard; filters act on it. Load the report's sources under the same
names first (`write_source("claims", report="../reports/claims-review")` in `Pipeline/sources.py`), then in the stub:
```python
from Shared.reuse import from_report

@section("s4_paid_by_region", tables=["claims"])
def paid_by_region(t):
    r = from_report("../reports/claims-review", "s2_paid_by_region", t)   # report folder; section file or function
    return {"data": {"rows": r["tables"]["by_region"]}, "metrics": r["metrics"]}
```
- Returns `params`, `question`, `tables` (lists of rows), `metrics`, `notes`. Params: `DEFAULTS` from the report's
  `sections/_shared.py`, then `"analyticsDefaults"` in the config, then a keyword (`from_report(..., material=0.3)`).
- A slice too thin for it shows "Not enough data for this selection".

## Older sections
Sections made before library items (a `chart: 'bar'` meta, `ChartECharts` or `KpiTile` in the file) keep working
and are edited the same way: their numbers in the meta or analytic, their drawing in the file.

## Older dashboards
A dashboard made before library items has no `Tools/library.mjs`; its `new-section` knows only `--chart`. It
keeps running as it is. To add library items to it, copy from this skill's `starter/`: `Src/Lib/fill.js`,
`Src/Lib/host-runtime.js`, `Src/Lib/theme.js`, `Src/host.css`, `Src/styles.css`, `Src/Components/Item.jsx`, the three `host`/`custom`
import lines at the top of `Src/App.jsx`, `Tools/*.mjs`, `Analysis/Shared/shapes.py`, `Analysis/check.py`, and the
`theme` line of `package.json`'s scripts; then `npm run theme -- TH-01`.
