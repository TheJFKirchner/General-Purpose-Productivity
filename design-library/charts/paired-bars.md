# CT-05 · paired-bars

- Looks like: Two bars per category (expected in light grey, actual darker), the category that matters in blue, legend at top left.
- Good for: Comparing actual with expected across a few groups; Showing where two measures agree and where they part
- Related: CT-07, CP-01

```json
{
  "legend": { "top": 0, "left": 8 },
  "grid": { "left": 8, "right": 8, "top": 56, "bottom": 4, "containLabel": true },
  "xAxis": { "type": "category", "axisLabel": { "interval": 0 }, "data": ["North", "South", "East", "West", "Central"] },
  "yAxis": { "type": "value", "show": false },
  "series": [
    { "type": "bar", "name": "Expected", "barGap": "8%",
      "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "top", "color": "var(--muted)" },
      "data": [62, 48, 40, 35, 20] },
    { "type": "bar", "name": "Actual",
      "itemStyle": { "color": "var(--muted)" },
      "label": { "show": true, "position": "top" },
      "data": [{ "value": 81, "itemStyle": { "color": "var(--blue)" }, "label": { "color": "var(--blue)", "fontWeight": 600 } }, 55, 31, 30, 21] }
  ]
}
```

- Long category names: break them with `\n` and keep `axisLabel.interval` at 0.
- The legend swatch for Actual shows the darker grey; say in the text which bar is highlighted and why.
