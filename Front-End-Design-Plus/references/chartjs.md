# Chart.js recipes

This session draws charts with Chart.js 4 (a local copy; no network).

## Contract
- Your `code` is the body of `function render(el, rows, lib)`.
- `lib` is the `Chart` constructor. `el` is an empty box already sized by the page; `rows` is every row of the real table.
- Mount: set `el.style.position = 'relative'`, append a `<canvas>` to `el`, then `new lib(canvas, config)`.
- Size and resize: `options.responsive: true` and `options.maintainAspectRatio: false`; the chart then fills `el` and follows its size.

## Conventions
- Aggregate from `rows` inside the recipe (group, sum, count, sort). Never type data values, category lists or totals into the code.
- Values may arrive as strings: coerce with `Number(r.col) || 0`. Dates are ISO text: `String(r.date).slice(0, 7)` gives the month. Use a category axis for dates (the time axis needs an adapter that is not loaded).
- Set `options.animation: false` so cards do not flicker on redraw.
- No network and no plugins beyond what Chart.js ships (no datalabels, zoom or annotation plugins).
- Set fonts and colours with `lib.defaults.font.family` and `lib.defaults.color`.
- Horizontal bars: `indexAxis: 'y'`. Stacked: `stacked: true` on both scales.
- Titles only through `plugins.title` (with `padding.bottom`), legend through `plugins.legend`: Chart.js then reserves their room. Never draw text onto the canvas at fixed positions; add `layout.padding` for headroom.
- One clear message per chart; hide the legend when there is one dataset.

## Default look (conservative, blue-led)
- Palette, in order: `#1F4E79`, `#2E75B6`, `#5B9BD5`, `#9DC3E6`, `#44546A`, `#8497B0`, `#A5A5A5`, `#D6DCE5`.
- Text `#333F4F`; grid lines `#E5E9F0`; font `Segoe UI, Arial, sans-serif`.
- A style note from the user overrides these. For dark, set `el.style.background` (for example `#1B2533`), light text and lighter blues first.

## Starter recipe (revenue by product line)
```js
const PALETTE = ['#1F4E79', '#2E75B6', '#5B9BD5', '#9DC3E6', '#44546A', '#8497B0', '#A5A5A5', '#D6DCE5'];
const totals = {};
for (const r of rows) {
  totals[r.product_line] = (totals[r.product_line] || 0) + (Number(r.revenue) || 0);
}
const items = Object.entries(totals).sort((a, b) => b[1] - a[1]);
el.style.position = 'relative';
const canvas = document.createElement('canvas');
el.appendChild(canvas);
lib.defaults.font.family = 'Segoe UI, Arial, sans-serif';
lib.defaults.color = '#333F4F';
new lib(canvas, {
  type: 'bar',
  data: {
    labels: items.map(d => d[0]),
    datasets: [{ label: 'Revenue', data: items.map(d => d[1]), backgroundColor: PALETTE[1], borderRadius: 2 }]
  },
  options: {
    indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
    layout: { padding: { top: 4, right: 12 } },
    plugins: {
      title: {
        display: true, text: 'Revenue by product line', align: 'start', color: '#1F4E79',
        font: { size: 14, weight: '600' }, padding: { bottom: 12 }
      },
      legend: { display: false },
      tooltip: { callbacks: { label: c => 'Revenue: ' + Math.round(c.parsed.x).toLocaleString() } }
    },
    scales: {
      x: { beginAtZero: true, grid: { color: '#E5E9F0' }, title: { display: true, text: 'Revenue' } },
      y: { grid: { display: false } }
    }
  }
});
```
Adapt: swap `product_line` and `revenue` for the session's columns; drop `indexAxis` for vertical bars, or use `type: 'line'` with month labels for a trend.
