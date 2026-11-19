# CT-08 · dumbbell

- Looks like: Two dots per item joined by a short bar, the earlier point light grey, the later dark, the item that matters in blue.
- Good for: Showing movement between two points for several items at once; Showing which items moved most and in which direction
- Related: CT-07, CP-05

```json
{
  "grid": { "left": 8, "right": 40, "top": 8, "bottom": 4, "containLabel": true },
  "xAxis": { "type": "value", "min": 80, "max": 120, "interval": 10, "axisLabel": { "formatter": "{value}%" } },
  "yAxis": { "type": "category", "inverse": true, "data": ["Product A", "Product B", "Product C", "Product D"] },
  "series": [
    { "type": "bar", "stack": "range", "barWidth": 6, "silent": true, "itemStyle": { "opacity": 0 }, "data": [99, 98, 90, 87] },
    { "type": "bar", "stack": "range", "barWidth": 6, "itemStyle": { "color": "var(--chart-muted)" },
      "data": [{ "value": 13, "itemStyle": { "color": "var(--blue)" } }, 6, 2, 1] },
    { "type": "scatter", "name": "2024", "symbolSize": 17, "z": 4,
      "itemStyle": { "color": "var(--chart-muted)", "opacity": 1 },
      "label": { "show": true, "formatter": "{@[0]}%", "color": "var(--muted)", "position": "right", "distance": 8 },
      "data": [{ "value": [112, "Product A"], "label": { "formatter": "2024: 112%" } }, { "value": [104, "Product B"] }, { "value": [92, "Product C"] }, { "value": [88, "Product D"] }] },
    { "type": "scatter", "name": "2025", "symbolSize": 17, "z": 5,
      "itemStyle": { "color": "var(--muted)", "opacity": 1 },
      "label": { "show": true, "formatter": "{@[0]}%", "color": "var(--navy)", "fontWeight": 600, "position": "left", "distance": 8 },
      "data": [{ "value": [99, "Product A"], "itemStyle": { "color": "var(--blue)", "opacity": 1 }, "label": { "formatter": "2025: 99%", "color": "var(--blue)" } }, { "value": [98, "Product B"] }, { "value": [90, "Product C"] }, { "value": [87, "Product D"] }] }
  ]
}
```

- The joining bar is a stacked pair: an invisible base at the lower value, then the gap.
- An item that moved up: swap which label sits left and right so the labels clear the dots.
