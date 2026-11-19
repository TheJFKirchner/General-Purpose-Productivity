# CT-07 · bars-target-tick

- Looks like: Horizontal bars with a dark tick marking each item's target, the miss in blue with its value inside the bar.
- Good for: Showing performance against a target or plan for each item; Picking out the one item that missed
- Related: CT-05, CP-02

```json
{
  "grid": { "left": 8, "right": 30, "top": 24, "bottom": 8, "containLabel": true },
  "xAxis": { "type": "value", "show": false, "min": 0, "max": 90 },
  "yAxis": { "type": "category", "inverse": true, "data": ["Team A", "Team B", "Team C", "Team D"] },
  "series": [
    { "type": "bar", "barWidth": "46%",
      "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "insideRight", "formatter": "{c}%", "color": "var(--navy)", "fontWeight": 600 },
      "data": [{ "value": 79, "itemStyle": { "color": "var(--blue)" }, "label": { "color": "var(--paper)" } }, 66, 61, 55] },
    { "type": "scatter", "symbol": "rect", "symbolSize": [4, 58], "z": 5,
      "itemStyle": { "color": "var(--navy)" },
      "label": { "show": true, "position": "top", "distance": 3, "formatter": "Target {@[0]}%", "color": "var(--muted)" },
      "data": [[70, "Team A"], [68, "Team B"], [62, "Team C"], [57, "Team D"]] }
  ]
}
```

- The tick is a scatter series with a thin rectangle symbol; size its height to the bar width.
- In a scatter label, `{@[0]}` prints the value.
- The same target for every item: one `markLine` instead of ticks.
