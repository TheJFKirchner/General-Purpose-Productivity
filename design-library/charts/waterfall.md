# CT-06 · waterfall

- Looks like: Vertical bridge from a starting total to an ending total; totals dark grey, the step that matters blue, other steps light grey.
- Good for: Bridging from a starting figure to an ending figure by cause; Showing which driver accounts for most of a change
- Related: BD-01, BD-02, BD-03

```json
{
  "xAxis": { "type": "category", "data": ["Prior", "Trend", "Development", "Mix", "Current"] },
  "yAxis": { "type": "value", "axisLabel": { "formatter": "{value}%" } },
  "series": [
    { "type": "bar", "stack": "w", "itemStyle": { "opacity": 0 }, "data": [0, 52.0, 59.5, 66.0, 0] },
    { "type": "bar", "stack": "w", "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "top" },
      "data": [
        { "value": 52.0, "itemStyle": { "color": "var(--muted)" }, "label": { "formatter": "52.0%" } },
        { "value": 7.5, "itemStyle": { "color": "var(--blue)" }, "label": { "formatter": "+7.5" } },
        { "value": 6.5, "label": { "formatter": "+6.5" } },
        { "value": 5.0, "label": { "formatter": "+5.0" } },
        { "value": 71.0, "itemStyle": { "color": "var(--muted)" }, "label": { "formatter": "71.0%" } }
      ] }
  ]
}
```

- The first series is an invisible base (`opacity: 0`, not "transparent") that lifts each step.
- A step down: the base is the level after the fall, the visible value is the size of the fall, the label says "-2.0".
