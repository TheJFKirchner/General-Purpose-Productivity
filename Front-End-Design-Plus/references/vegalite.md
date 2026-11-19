# Vega-Lite recipes

This session draws charts with Vega-Lite 6 through vega-embed (local copies; no network).

## Contract
- Your `code` is the body of `function render(el, rows, lib)`.
- `lib` is the `vegaEmbed` function. `el` is an empty box already sized by the page; `rows` is every row of the real table.
- Mount with `return lib(el, spec, { mode: 'vega-lite', actions: false, renderer: 'svg' });` (return the promise so errors reach the card).
- Size: `width: 'container', height: 'container', autosize: { type: 'fit', contains: 'padding' }`. Vega then follows the box when it resizes.
- Data: `data: { values: rows }` (or a cleaned copy of rows). Never `data: { url }`.

## Conventions
- Aggregate from `rows`: either in the spec (`aggregate`, `timeUnit`, `transform`) or in JS before the spec. Never type data values, category lists or totals into the code.
- Values may arrive as strings: map rows to clean objects with `Number(r.col) || 0`, or set `type: 'quantitative'` and let Vega parse.
- Dates are ISO text, which Vega reads as UTC: use `utc` time units (`utcyearmonth`, `utcyear`), or months shift a day in some time zones.
- Omit `$schema` (it would name a version; the local copy is what runs).
- No network: no `url` data, remote images or geo shapes from the web.
- No `params` that animate; selections are fine but keep them simple.
- Titles only through the spec's `title` with `anchor: 'start'` and `offset` of at least 10, legend `orient: 'top'`: Vega then reserves their room. Value labels go in a `text` layer inside the bars (`baseline: 'top', dy: 4`), never above the plot where they meet the title.
- One clear message per chart; drop the legend when there is one series.

## Default look (conservative, blue-led)
- Palette, in order: `#1F4E79`, `#2E75B6`, `#5B9BD5`, `#9DC3E6`, `#44546A`, `#8497B0`, `#A5A5A5`, `#D6DCE5` (`scale: { range: PALETTE }`).
- Text `#333F4F`; domain `#8497B0`; grid `#E5E9F0`; font `Segoe UI, Arial, sans-serif`; `background: 'transparent'`; `view: { stroke: null }`.
- A style note from the user overrides these. For dark, set `background` (for example `#1B2533`), light text and lighter blues first.

## Starter recipe (monthly revenue by channel)
```js
const PALETTE = ['#1F4E79', '#2E75B6', '#5B9BD5', '#9DC3E6', '#44546A', '#8497B0', '#A5A5A5', '#D6DCE5'];
const values = rows.map(r => ({
  order_date: String(r.order_date).slice(0, 10),
  channel: r.channel,
  revenue: Number(r.revenue) || 0
}));
const spec = {
  width: 'container', height: 'container',
  autosize: { type: 'fit', contains: 'padding' },
  background: 'transparent',
  title: { text: 'Monthly revenue by channel', anchor: 'start', offset: 12, fontSize: 14, color: '#1F4E79' },
  data: { values },
  mark: { type: 'bar' },
  encoding: {
    x: { field: 'order_date', timeUnit: 'utcyearmonth', type: 'ordinal', title: null, axis: { format: '%b %y', labelAngle: 0 } },
    y: { aggregate: 'sum', field: 'revenue', type: 'quantitative', title: 'Revenue', axis: { format: '~s' } },
    color: { field: 'channel', type: 'nominal', title: null, scale: { range: PALETTE } },
    tooltip: [
      { field: 'order_date', timeUnit: 'utcyearmonth', type: 'temporal', title: 'Month' },
      { field: 'channel', type: 'nominal', title: 'Channel' },
      { aggregate: 'sum', field: 'revenue', type: 'quantitative', title: 'Revenue', format: ',.0f' }
    ]
  },
  config: {
    font: 'Segoe UI, Arial, sans-serif',
    axis: { labelColor: '#333F4F', titleColor: '#333F4F', gridColor: '#E5E9F0', domainColor: '#8497B0' },
    legend: { orient: 'top', labelColor: '#333F4F', titleColor: '#333F4F' },
    view: { stroke: null }
  }
};
return lib(el, spec, { mode: 'vega-lite', actions: false, renderer: 'svg' });
```
Adapt: swap `order_date`, `channel` and `revenue` for the session's columns; use `mark: 'line'` for a trend or `mark: 'area'` for a stacked area.
