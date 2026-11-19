# Sections

A section is defined by one file, `Src/Sections/<id>.jsx`: its `meta` (title, tab, tables, a short description,
its numbers), its note and its chart. An edit opens that file only; its Python function too only when it has one
and the numbers change. Never open other sections, components or helper files to copy from.

## Simple add (one chart, table or tile row from one table)
1. `npm run status`: the tabs, sections, and every table's columns with a sample and date range.
2. One command writes a working section:
   ```
   npm run new-section -- paid_by_month --page overview --tables claims --chart bar --x service_month --y paid_amount \
     --note "Paid in {latest_label|month} was {latest|compact}, {change|change} {change_label|name}. | Peak: {largest_label|month}."
   ```
   | Option | Means |
   |---|---|
   | `--chart` | `bar`, `line`, `table` or `kpi` |
   | `--x` | the category or month column (a month gives a time axis, latest and change) |
   | `--y` / `--agg` | the value column; `sum` (default), `mean`, or `count` (counts rows, no `--y`) |
   | `--by` | a second column: one series per value (stacked bars, lines, table columns) |
   | `--title`, `--desc` | what it shows (title), and 8 to 10 words for the status list |
   | `--note "a \| b"` | the bullets, split by ` \| `; without it, neutral generated lines (`--bullets N`, default 2) |
   | `--compare` | month x: change on the same month a year earlier (`year`, default with a year of data) or `prev` |
   | `--keep-filter` | by default a filter on the `--x`/`--by` column does not narrow it (it compares those values) |
   | more | `--size half`; `--report <name>` adds it to a report |
3. It prints the metrics and the note lines. To reword later, edit those lines in the `.jsx`; keep each `{metric|format}`.
4. `npm run check`, then `npm run shot -- <id>` (own server; saved in `Data/.shots/`, not kept) and look.

What the file holds, so you never need another one:
```jsx
export const meta = {
  id: 's8_paid_by_month', title: 'Paid by month', tab: 'overview', chart: 'bar', library: 'echarts',
  description: 'Paid amount by service month, summed, as bars',
  tables: ['claims'], x: 'service_month', y: 'paid_amount', agg: 'sum',   // the numbers, worked out in Python
};
export const note = `
- {latest|compact} in {latest_label|month}, {change|change} {change_label|name}.
`;
```
- Change the numbers: edit `x`, `y`, `agg`, `by`. Change the look: the chart code under the note.
- Metrics: `total` (or `average`), `largest`, `largest_label`, `count`; a month x adds `latest`, `latest_label`,
  `change`, `change_label` ("vs Jun 25"); other x adds `largest_share`, `smallest`, `smallest_label`; `--by` adds
  `top_series`, `top_series_share`.
- Note formats: `compact` money ($913.2K), `int` counts, `short`, `num:1`, `pct:1`, `change` (up 5.2%, down 3.1%,
  flat), `month` (Jun 26), `name`.

---
**STOP HERE for a simple add. Below: unusual sections only** (several tables, a calculation the options can't
say, a report's analytic).

---

## A hand-written analytic
`npm run new-section -- <name> --page <tab> --tables <t1,t2> --desc "..."` (no `--x`) writes a shell and a stub in
`Analysis/<tab>.py`. Fill the function; delete `x`/`y`/`agg` from the meta.
```python
@section("s3_paid_by_region", tables=["claims"], filters=["product"])   # filters=: only these reach it
def paid_by_region(t):
    """Which regions carry the most paid claims?"""
    by = t.claims.groupby("region", as_index=False)["paid_amount"].sum().sort_values("paid_amount", ascending=False)
    return {"data": {"rows": by.to_dict("records")}, "metrics": {"top_region": by["region"].iloc[0]}}
```
- Tables arrive filtered; never filter again. `t.filters["region"]` is the choice, `t.params` the slow filters.
- A section comparing regions leaves `region` out of `filters=[...]`; the page tags it "Region: all".
- `from Shared.periods import change, ratio, total, sum_by, last_periods, month_label`: `change(cur, prior)`,
  `ratio(a, b)`, `total(df, col)`, `sum_by(df, key, col)`, `last_periods(df, 12, offset=0)`, `month_label("2026-10")`
  ("Oct 2026"). All return `None` rather than fail.

## A report's analytic, live
One function serves the report and the dashboard; filters act on it. Load the report's sources under the same
names first (`write_source("claims", report="../reports/claims-review")` in `Pipeline/sources.py`). Then a shell
(`new-section` without `--x`) and, in its stub:
```python
from Shared.reuse import from_report

@section("s4_paid_by_region", tables=["claims"], filters=["product"])
def paid_by_region(t):
    r = from_report("../reports/claims-review", "s2_paid_by_region", t)   # report folder; section file or function name
    return {"data": {"rows": r["tables"]["by_region"]}, "metrics": r["metrics"]}
```
- Returns `params`, `question`, `tables` (lists of rows), `metrics`, `notes`. Params: `DEFAULTS` from the report's
  `sections/_shared.py`, then `"analyticsDefaults"` in the config, then a keyword for this call
  (`from_report(..., material=0.3)`).
- A slice too thin for it shows "Not enough data for this selection".

## Drawing by hand
| Need | Write |
|---|---|
| A chart | `<ChartECharts option={option} height={300} />` (`../Components/ChartECharts.jsx`), `option` in `useMemo(() => ..., [data])`; the theme colors series, no `itemStyle` |
| KPI tile | `<KpiTile label="Paid, Jun 26" value={metrics.paid} format={FORMATS.compact} change={metrics.change} goodWhen="down" changeLabel="vs Jun 25" />` inside `<div className="kpis">` |
| Formats | `import { FORMATS } from '../Lib/format.js'`: `FORMATS.compact(v)`, `.short`, `.int`, `.num(v, 1)`, `.pct(v, 1)`, `.month` |
| Percent axis | `axisLabel: { formatter: (v) => FORMATS.pct(v, 0) }` |
| Largest bar on top | `yAxis: { type: 'category', inverse: true, data }` with rows sorted largest first |
| Needs attention | `itemStyle: { color: fx().bad }` on one bar (`fx` from `../Lib/theme.js`); orange means only that |
| Table | `<table className="data">`; number cells `className="num"`; `good` / `bad` flags |
| Looks only | `Src/custom.css`, scoped to `#<id>`, with `--blue`, `--navy`, `--rule` ... |

One section's numbers: `python Analysis/check.py --show <id> [--filter region=East]`.
