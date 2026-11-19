# CT-01 · bar-highlight

- Looks like: Vertical bars, one highlighted in blue, the rest grey, values on top.
- Good for: Showing which category stands out; Comparing a handful of groups on one measure
- Related: CT-02, LV-05

```json
{
  "xAxis": { "type": "category", "data": ["North", "South", "East", "West"] },
  "yAxis": { "type": "value", "axisLabel": { "formatter": "{value}%" } },
  "series": [{
    "type": "bar",
    "itemStyle": { "color": "var(--chart-muted)" },
    "label": { "show": true, "position": "top", "formatter": "{c}%" },
    "data": [81, 79, 84, { "value": 91, "itemStyle": { "color": "var(--blue)" } }]
  }]
}
```

- Highlight one bar by making its data item an object with its own `itemStyle.color`.
- Bars start at zero. Four bars or fewer make a short chart: give it the smaller share of the space.
