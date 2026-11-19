# CT-02 · bars-ranked

- Looks like: Horizontal bars sorted largest first, the leader in blue, values at the bar ends.
- Good for: Ranking items when the labels are long; Showing which item drives a result
- Related: CT-01, LV-06, BK-01

```json
{
  "grid": { "left": 8, "right": 70, "top": 8, "bottom": 8, "containLabel": true },
  "xAxis": { "type": "value", "show": false },
  "yAxis": { "type": "category", "inverse": true, "data": ["Setup took too long", "Price", "Missing feature", "Other"] },
  "series": [{
    "type": "bar",
    "itemStyle": { "color": "var(--chart-muted)" },
    "label": { "show": true, "position": "right", "formatter": "{c}%" },
    "data": [{ "value": 38, "itemStyle": { "color": "var(--blue)" } }, 24, 21, 17]
  }]
}
```

- `inverse: true` on the category axis puts the first item at the top.
- `grid.right` leaves room for the last value label.
