# Plotly recipes

This session draws charts with plotly.js (a local copy; no network).

## Contract
- Your `code` is the body of `function render(el, rows, lib)`.
- `lib` is the `Plotly` global. `el` is an empty box already sized by the page; `rows` is every row of the real table.
- Mount with `return lib.newPlot(el, traces, layout, config);` (return the promise so errors reach the card).
- Size: set `layout.autosize: true` and no fixed `width`/`height`; the plot fills `el`.
- Resize: pass `config: { responsive: true, displayModeBar: false }`.

## Conventions
- Aggregate from `rows` inside the recipe (group, sum, count, sort). Never type data values, category lists or totals into the code.
- Values may arrive as strings: coerce with `Number(r.col) || 0`. Dates are ISO text: `String(r.date).slice(0, 7)` gives the month.
- No transitions or frames: they flicker when cards redraw.
- No network: no map tiles (`scattermapbox`, `choroplethmap`), remote images or fonts.
- Hide the mode bar; use `hovertemplate` with `<extra></extra>` for clean tooltips.
- Format large numbers (`tickformat: '~s'`, `%{y:,.0f}`).
- Stack the top in bands so nothing collides: title pinned to the box top (`yref: 'container', y: 1, yanchor: 'top'`), a horizontal legend just above the plot (`y: 1, yanchor: 'bottom'`), and `margin.t` at least 72 (about 44 with no legend). Value labels go `textposition: 'inside'` or `'auto'`, never above the plot.
- One clear message per chart; a legend only when there is more than one trace.

## Default look (conservative, blue-led)
- Palette, in order: `#1F4E79`, `#2E75B6`, `#5B9BD5`, `#9DC3E6`, `#44546A`, `#8497B0`, `#A5A5A5`, `#D6DCE5`.
- Text `#333F4F`; axis lines `#8497B0`; grid lines `#E5E9F0`; font `Segoe UI, Arial, sans-serif`; transparent backgrounds.
- A style note from the user overrides these. For dark, set `paper_bgcolor` (for example `#1B2533`), light text and lighter blues first.

## Starter recipe (revenue by region and channel)
```js
const PALETTE = ['#1F4E79', '#2E75B6', '#5B9BD5', '#9DC3E6', '#44546A', '#8497B0', '#A5A5A5', '#D6DCE5'];
const regions = [...new Set(rows.map(r => r.region))].sort();
const channels = [...new Set(rows.map(r => r.channel))].sort();
const sums = {};
for (const r of rows) {
  const key = r.channel + '|' + r.region;
  sums[key] = (sums[key] || 0) + (Number(r.revenue) || 0);
}
const traces = channels.map((ch, i) => ({
  type: 'bar', name: ch, x: regions,
  y: regions.map(reg => Math.round(sums[ch + '|' + reg] || 0)),
  marker: { color: PALETTE[i % PALETTE.length] },
  hovertemplate: '%{x}<br>' + ch + ': %{y:,.0f}<extra></extra>'
}));
const layout = {
  barmode: 'group', autosize: true,
  title: {
    text: 'Revenue by region and channel', x: 0, xref: 'paper', xanchor: 'left',
    y: 1, yref: 'container', yanchor: 'top', pad: { t: 6 }, font: { size: 14, color: '#1F4E79' }
  },
  margin: { l: 64, r: 16, t: 72, b: 44 },
  font: { family: 'Segoe UI, Arial, sans-serif', color: '#333F4F', size: 12 },
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  legend: { orientation: 'h', x: 0, y: 1, yanchor: 'bottom' },
  xaxis: { linecolor: '#8497B0' },
  yaxis: { title: { text: 'Revenue' }, gridcolor: '#E5E9F0', tickformat: '~s', zeroline: false }
};
return lib.newPlot(el, traces, layout, { responsive: true, displayModeBar: false });
```
Adapt: swap `region`, `channel` and `revenue` for the session's columns; use `barmode: 'stack'` to stack, or `type: 'scatter', mode: 'lines'` for a trend.
