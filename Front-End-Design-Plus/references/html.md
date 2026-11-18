# HTML tables and plain SVG

Every session can draw styled tables, whatever its chart library. In an `html` session, charts are plain SVG.

## Contract
- Your `code` is the body of `function render(el, rows, lib)`. For HTML there is no library: `lib` is absent, do not use it.
- A table card always has `kind: "table"` and `library: "html"`, even in an ECharts or Plotly session.
- A plain SVG chart (html sessions only) has `kind: "chart"` and `library: "html"`.
- Mount: build markup as a string and set `el.innerHTML` once. `el` is an empty box sized by the page; `rows` is every row of the real table.
- Size: the outer wrapper takes `height: 100%; overflow-x: hidden; overflow-y: auto`, so long tables scroll down inside the box but never sideways. SVG uses `viewBox` with `width` and `height` at `100%`.
- Fit the width: tables must fit the card with no sideways scrolling; the smallest card is about 520 px wide. Use `width: 100%`, let text wrap (`overflow-wrap: anywhere` on cells), use 12 px text and tighter padding when there are many columns, and keep to about 6 columns (drop or combine the rest).

## Conventions
- Aggregate from `rows` inside the recipe (group, sum, count, sort). Never type data values, category lists or totals into the code.
- Values may arrive as strings: coerce with `Number(r.col) || 0`. Dates are ISO text: `String(r.date).slice(0, 7)` gives the month.
- Escape every value taken from `rows` before putting it in markup (`&`, `<`, `>`, `"`).
- Put a `<style>` block inside the markup and prefix every class with `fdp-` so the styles do not leak when merged into a page.
- Numbers right-aligned with `font-variant-numeric: tabular-nums`; thousands separators; percentages to one decimal.
- Sticky header row; a totals row in `<tfoot>` when the columns add up.
- Show at most about 50 rows. For longer detail tables, sort by the column that matters and say "top 50" in the title.
- No network, no scripts inside the markup, no external fonts or images.
- SVG charts: title baseline at y 20, plot from y 56 down, value labels at most 6 px above a bar, so labels never meet the title.

## Default look (conservative, blue-led)
- Header fill `#1F4E79` with white text; zebra rows `#F4F7FB`; row lines `#E5E9F0`; text `#333F4F`.
- SVG chart palette, in order: `#1F4E79`, `#2E75B6`, `#5B9BD5`, `#9DC3E6`, `#44546A`, `#8497B0`, `#A5A5A5`, `#D6DCE5`.
- Font `Segoe UI, Arial, sans-serif`, 13px. A style note from the user overrides these.

## Starter recipe (summary table by region)
```js
const groups = {};
for (const r of rows) {
  const g = groups[r.region] || (groups[r.region] = { orders: 0, units: 0, revenue: 0, cost: 0 });
  g.orders += 1;
  g.units += Number(r.units) || 0;
  g.revenue += Number(r.revenue) || 0;
  g.cost += Number(r.cost) || 0;
}
const data = Object.entries(groups)
  .map(([region, g]) => ({ region, ...g }))
  .sort((a, b) => b.revenue - a.revenue);
const total = data.reduce((t, d) => ({
  orders: t.orders + d.orders, units: t.units + d.units, revenue: t.revenue + d.revenue, cost: t.cost + d.cost
}), { orders: 0, units: 0, revenue: 0, cost: 0 });
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = n => Math.round(n).toLocaleString();
const pct = d => (d.revenue ? ((d.revenue - d.cost) / d.revenue) * 100 : 0).toFixed(1) + '%';
const cells = d => `<td class="fdp-num">${num(d.orders)}</td><td class="fdp-num">${num(d.units)}</td>` +
  `<td class="fdp-num">${num(d.revenue)}</td><td class="fdp-num">${pct(d)}</td>`;
el.innerHTML = `
<style>
  .fdp-wrap { height: 100%; overflow-x: hidden; overflow-y: auto; font: 13px/1.4 'Segoe UI', Arial, sans-serif; color: #333F4F; }
  .fdp-table { border-collapse: collapse; width: 100%; }
  .fdp-table th, .fdp-table td { overflow-wrap: anywhere; }
  .fdp-table th { position: sticky; top: 0; background: #1F4E79; color: #fff; font-weight: 600; text-align: left; padding: 8px; }
  .fdp-table td { padding: 7px 8px; border-bottom: 1px solid #E5E9F0; }
  .fdp-table tbody tr:nth-child(even) td { background: #F4F7FB; }
  .fdp-table .fdp-num { text-align: right; font-variant-numeric: tabular-nums; }
  .fdp-table tfoot td { font-weight: 600; border-top: 2px solid #1F4E79; border-bottom: none; }
</style>
<div class="fdp-wrap"><table class="fdp-table">
  <thead><tr><th>Region</th><th class="fdp-num">Orders</th><th class="fdp-num">Units</th><th class="fdp-num">Revenue</th><th class="fdp-num">Margin</th></tr></thead>
  <tbody>${data.map(d => `<tr><td>${esc(d.region)}</td>${cells(d)}</tr>`).join('')}</tbody>
  <tfoot><tr><td>Total</td>${cells(total)}</tr></tfoot>
</table></div>`;
```
Adapt: swap `region`, `units`, `revenue` and `cost` for the session's columns. For a plain SVG chart, build an `<svg viewBox="0 0 W H">` string the same way, with `W = el.clientWidth || 600` and `H = el.clientHeight || 360`.
