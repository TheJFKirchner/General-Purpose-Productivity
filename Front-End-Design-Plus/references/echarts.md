# ECharts recipes

This session draws charts with Apache ECharts 6 (a local copy; no network).

## Contract
- Your `code` is the body of `function render(el, rows, lib)`.
- `lib` is the `echarts` global. `el` is an empty box already sized by the page; `rows` is every row of the real table.
- Mount with `const chart = lib.init(el);` then `chart.setOption({...})`.
- Size: the chart fills `el`. Never set fixed pixel sizes on `el`.
- Resize: end with `new ResizeObserver(() => chart.resize()).observe(el);`.

## Conventions
- Aggregate from `rows` inside the recipe (group, sum, count, sort). Never type data values, category lists or totals into the code.
- Values may arrive as strings: coerce with `Number(r.col) || 0`. Dates are ISO text: `String(r.date).slice(0, 7)` gives the month.
- Set `animation: false` so cards do not flicker on redraw.
- No network: no `fetch`, maps, remote images, fonts or themes.
- Set margins with `grid: { left, right, top, bottom }` (pixels). Do not use `containLabel` (deprecated in ECharts 6).
- Stack the top in bands so nothing collides: short `title` at `top: 4`, `legend` at `top: 32`, `grid.top` at least 76 (about 48 with no legend). A y-axis `name` sits in the same band as the legend, so with a legend drop it and put the measure in the title. Value labels (`label: { position: 'top' }`) need the grid margin above the tallest bar.
- Format large numbers on axes and tooltips (`120k`, thousands separators).
- One clear message per chart; a legend only when there is more than one series.

## Default look (conservative, blue-led)
- Palette, in order: `#1F4E79`, `#2E75B6`, `#5B9BD5`, `#9DC3E6`, `#44546A`, `#8497B0`, `#A5A5A5`, `#D6DCE5`.
- Text `#333F4F`; axis lines `#8497B0`; grid lines `#E5E9F0`; font `Segoe UI, Arial, sans-serif`.
- A style note from the user overrides these. For dark, set `backgroundColor` (for example `#1B2533`), light text and lighter blues first.

## Starter recipe (monthly revenue by region)
```js
const PALETTE = ['#1F4E79', '#2E75B6', '#5B9BD5', '#9DC3E6', '#44546A', '#8497B0', '#A5A5A5', '#D6DCE5'];
const month = r => String(r.order_date).slice(0, 7);
const months = [...new Set(rows.map(month))].sort();
const regions = [...new Set(rows.map(r => r.region))].sort();
const totals = {};
for (const r of rows) {
  const key = r.region + '|' + month(r);
  totals[key] = (totals[key] || 0) + (Number(r.revenue) || 0);
}
const chart = lib.init(el);
chart.setOption({
  animation: false,
  color: PALETTE,
  textStyle: { fontFamily: 'Segoe UI, Arial, sans-serif', color: '#333F4F' },
  tooltip: { trigger: 'axis', valueFormatter: v => (v == null ? '' : Math.round(v).toLocaleString()) },
  title: { text: 'Monthly revenue by region', left: 0, top: 4, textStyle: { fontSize: 14, fontWeight: 600, color: '#1F4E79' } },
  legend: { top: 32, left: 0 },
  grid: { left: 64, right: 24, top: 76, bottom: 40 },
  xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#8497B0' } } },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: '#E5E9F0' } },
    axisLabel: { formatter: v => (v >= 1000 ? v / 1000 + 'k' : v) }
  },
  series: regions.map(reg => ({
    name: reg, type: 'line', showSymbol: false,
    data: months.map(m => Math.round(totals[reg + '|' + m] || 0))
  }))
});
new ResizeObserver(() => chart.resize()).observe(el);
```
Adapt: swap `order_date`, `region` and `revenue` for the session's columns; change `type: 'line'` to `'bar'` (add `stack: 'total'` to stack).
