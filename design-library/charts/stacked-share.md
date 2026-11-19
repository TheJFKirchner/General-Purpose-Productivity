# CT-09 · stacked-share

- Looks like: Two 100% stacked horizontal bars, the part that changed in blue with its label inside, the other parts grey.
- Good for: Showing how the make-up of a total shifted between two points; Showing that a result changed because the mix changed
- Related: BD-05

```json
{
  "grid": { "left": 8, "right": 8, "top": 4, "bottom": 4, "containLabel": true },
  "xAxis": { "type": "value", "show": false, "max": 100 },
  "yAxis": { "type": "category", "inverse": true, "data": ["2021", "2025"], "axisLabel": { "fontSize": 18, "fontWeight": 600 } },
  "series": [
    { "type": "bar", "stack": "total", "name": "Online", "barWidth": "62%", "data": [18, 27],
      "itemStyle": { "color": "var(--blue)", "borderColor": "var(--paper)", "borderWidth": 2 },
      "label": { "show": true, "position": "inside", "formatter": "{a}\n{c}%", "color": "var(--paper)", "fontWeight": 600, "fontSize": 16, "lineHeight": 22 } },
    { "type": "bar", "stack": "total", "name": "Stores", "data": [46, 38],
      "itemStyle": { "color": "var(--chart-muted)", "borderColor": "var(--paper)", "borderWidth": 2 },
      "label": { "show": true, "position": "inside", "formatter": "{a}\n{c}%", "fontSize": 15, "lineHeight": 22 } },
    { "type": "bar", "stack": "total", "name": "Phone", "data": [24, 23],
      "itemStyle": { "color": "var(--chart-muted)", "borderColor": "var(--paper)", "borderWidth": 2 },
      "label": { "show": true, "position": "inside", "formatter": "{a}\n{c}%", "fontSize": 15, "lineHeight": 22 } },
    { "type": "bar", "stack": "total", "name": "Other", "data": [12, 12],
      "itemStyle": { "color": "var(--chart-muted)", "borderColor": "var(--paper)", "borderWidth": 2 },
      "label": { "show": true, "position": "inside", "formatter": "{a}\n{c}%", "fontSize": 15, "lineHeight": 22 } }
  ]
}
```

- The white borders separate the parts; labels sit inside, so no legend is needed.
- Keep to five parts or fewer; group the rest as "Other".
