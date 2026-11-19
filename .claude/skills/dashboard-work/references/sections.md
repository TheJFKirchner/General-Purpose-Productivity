# Writing a section

A section is two files sharing an id, e.g. `s3_paid_by_region`. Start one with:
```
npm run new-section -- paid_by_region --page costs --tables claims_monthly --chart echarts
```
It picks the next number, writes both files as shells ("Not built yet") and adds the section to
`Src/Sections/index.js` (and the tab if new). Options: `--title "Paid by region"`, `--size half`,
`--chart echarts | table | kpi | text`.

## 1. The analytic: `Analysis/<tab>.py`
One function per section, one question. It gets its tables already filtered and returns `data` (for the
drawing) and `metrics` (single named values for the note).
```python
from Shared.registry import section

@section("s3_paid_by_region", tables=["claims_monthly"])
def paid_by_region(t):
    """Which regions carry the most paid claims?"""
    by = t.claims_monthly.groupby("region", as_index=False)["paid"].sum().sort_values("paid", ascending=False)
    return {"data": {"rows": by.to_dict("records")},
            "metrics": {"top_region": by["region"].iloc[0], "total_paid": by["paid"].sum()}}
```
- **Filters are already applied**; never filter again. `t.filters["region"]` is the choice ("All" when unset).
- A section that compares one dimension (regions) is not narrowed by that filter: `@section(..., filters=["product"])`
  lists the filters it takes. The page then tags it "Region: all" when Region is set.
- Group, total and sort here, so the `.jsx` only draws. `None` for a value that can't be worked out ("n/a").
- Helpers (`from Shared.periods import ...`): `total`, `sum_by`, `last_periods(df, 12)`, `change(cur, prior)`,
  `ratio(a, b)`, `month_label("2026-10")`. They return `None`, not errors.

**A report analytic, live.** The analysis skill's `fn(src, params)` runs here on the filtered tables, so one
function serves both places and filters act on it:
```python
from Shared.reuse import from_report

@section("s4_cost_by_region", tables=["claims", "membership"], filters=["product"])   # the report's SOURCES names
def cost_by_region(t):
    r = from_report("../report/analytics/claims_cost.py", "region_cost", t)
    return {"data": {"rows": r["tables"]["by_region"]}, "metrics": r["metrics"]}
```
- `from_report(script, function, t, **overrides)` returns `params`, `question`, `tables` (lists of rows),
  `metrics`, `notes`. Params: the analytics file's `DEFAULTS`, then `"analyticsDefaults"` in the config, then a
  keyword for this call only (`from_report(..., material=0.3)`). Read `r["params"]["month"]`; never retype one.
- A slice too thin for it shows "Not enough data for this selection".

## 2. The look: `Src/Sections/s3_paid_by_region.jsx`
```jsx
export const meta = { id: 's3_paid_by_region', title: 'Paid by region', tab: 'costs', library: 'echarts', size: 'half', commentary: 'C2' };

export const note = `{top_region|name} had the most paid claims, out of {total_paid|compact} in total.`;

export default function Section({ data, metrics }) { /* draw data.rows */ }
```
- `library`: `echarts`, or `none` for tables, tiles and text. `tab`: the tab id (none on a one-page dashboard).
- `note`: one line of takeaway. It names metrics; it never types numbers in.
- `commentary` (optional): one id from `commentary.json`; the matching item shows under the section.
- No filter dropdowns here. A view switch (count vs amount) inside the section is fine.

## Note formats
| Write | Shows |
|---|---|
| `{x\|compact}` / `{x\|money}` | $913.2K / $1,234 (money: both add $) |
| `{x\|short}` / `{x\|int}` / `{x\|num:2}` | 913.2K / 12,345 / 4.64 (counts: no $) |
| `{x\|pct:1}` / `{x\|pts:1}` | 5.2% (size only; pair with direction) / 2.4 points |
| `{x\|direction}` / `{x\|month}` / `{x\|name}` | rose, fell, was flat / Jun 26 / the text as it is |

## Drawing
- **Readout first:** KPI tiles (`<div className="kpis">` with `<KpiTile label value format change goodWhen="up" />`)
  lead a tab. Short category bars (a few regions) go `size: 'half'` at about 220px high.
- **ECharts:** `<ChartECharts option={option} height={300} />`, `option` built in `useMemo(() => ..., [data])`. The
  theme colors series in order (blue, green, navy, teal, muted): no `itemStyle` needed. Orange only means "needs
  attention": `color: fx().bad` (`fx` from `../Lib/theme.js`) on the one bar or cell.

## Cookbook
| Need | Write |
|---|---|
| KPI tile | `<KpiTile label="Paid, Jun 26" value={metrics.paid} format={FORMATS.compact} change={metrics.change} goodWhen="down" changeLabel="vs Jun 25" />` (`format` is a `FORMATS` function) |
| Percent axis | `axisLabel: { formatter: (v) => FORMATS.pct(v, 0) }` |
| Largest bar on top (horizontal) | `yAxis: { type: 'category', inverse: true, data: rows.map((r) => r.region) }` with rows sorted largest first |
| Highlight one bar | `data: rows.map((r) => ({ value: r.paid, itemStyle: r.flag ? { color: fx().bad } : undefined }))` |
| Count rows | in the analytic: `df.groupby("month").size()` (or `["claim_id"].nunique()`) |
- **Axes and labels:** `FORMATS.compact` for money, `FORMATS.short` for counts, `FORMATS.month` for months.
  `FORMATS` is in `../Lib/format.js`.
- **Tables:** `<table className="data">`; number cells `className="num"` (right-aligned); `good` / `bad` flags.
- Looks-only tweaks: `Src/custom.css`, scoped to `#<id>`, with the theme variables (`--blue`, `--navy`, `--rule`).

## Checking
`npm run check` once when done. One section's numbers: `python Analysis/check.py --show <id> [--filter region=East]`.
