# CT-03 · line-event

- Looks like: Two lines over time, the one that matters in blue, both ends labelled, an event marked with a dashed line.
- Good for: Showing the effect of a change against a group that did not change; Tying a movement to the moment that caused it
- Related: CT-04, CH-02

```json
{
  "xAxis": { "type": "category", "boundaryGap": false, "data": ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"] },
  "yAxis": { "type": "value", "min": 2, "max": 6, "interval": 1, "axisLabel": { "formatter": "{value}%" } },
  "grid": { "left": 8, "right": 150, "top": 30, "bottom": 8, "containLabel": true },
  "series": [
    { "type": "line", "name": "Old checklist", "data": [5.1, 5.0, 5.2, 5.0, 5.3, 5.1, 5.2],
      "itemStyle": { "color": "var(--chart-muted)" }, "showSymbol": false,
      "endLabel": { "show": true, "formatter": "{a}  {c}%", "color": "var(--muted)" } },
    { "type": "line", "name": "Guided setup", "data": [5.1, 5.0, 5.2, 4.1, 3.4, 3.2, 3.1],
      "itemStyle": { "color": "var(--blue)" }, "lineStyle": { "width": 5 }, "showSymbol": false,
      "endLabel": { "show": true, "formatter": "{a}  {c}%", "color": "var(--blue)", "fontWeight": 600 },
      "markLine": { "symbol": "none", "silent": true, "lineStyle": { "color": "var(--muted)", "type": "dashed", "width": 1.5 },
                    "label": { "formatter": "Launch", "color": "var(--muted)" }, "data": [{ "xAxis": "Jun" }] } }
  ]
}
```

- End labels replace a legend; `grid.right` makes room for them.
- With `min` and `max` on the value axis, set `interval` too. Mark a period with `markArea`, not one dashed line.
