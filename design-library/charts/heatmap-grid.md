# CT-10 · heatmap-grid

- Looks like: A small grid of figures on light grey cells, the cells that matter in blue with white text.
- Good for: Showing a pattern across two dimensions, such as period by age; Pointing at one part of a grid of figures
- Related: BK-02

```json
{
  "grid": { "left": 8, "right": 8, "top": 34, "bottom": 4, "containLabel": true },
  "xAxis": { "type": "category", "position": "top", "axisLine": { "show": false }, "data": ["Month 1", "Month 2", "Month 3", "Month 4"] },
  "yAxis": { "type": "category", "inverse": true, "axisLine": { "show": false }, "data": ["2022", "2023", "2024", "2025"] },
  "visualMap": { "show": false, "type": "piecewise", "dimension": 3, "pieces": [{ "value": 0, "color": "var(--rule)" }, { "value": 1, "color": "var(--blue)" }] },
  "series": [{
    "type": "heatmap",
    "itemStyle": { "borderColor": "var(--paper)", "borderWidth": 4 },
    "label": { "show": true, "formatter": "{@[2]}", "fontSize": 17, "color": "var(--navy)" },
    "data": [
      [0, 0, 1.51, 0], [1, 0, 1.21, 0], [2, 0, 1.07, 0], { "value": [3, 0, 1.04, 1], "label": { "color": "var(--paper)", "fontWeight": 600 } },
      [0, 1, 1.52, 0], [1, 1, 1.22, 0], { "value": [2, 1, 1.12, 1], "label": { "color": "var(--paper)", "fontWeight": 600 } },
      [0, 2, 1.53, 0], { "value": [1, 2, 1.27, 1], "label": { "color": "var(--paper)", "fontWeight": 600 } },
      { "value": [0, 3, 1.69, 1], "label": { "color": "var(--paper)", "fontWeight": 600 } }
    ]
  }]
}
```

- Each cell is `[x, y, value, flag]`; the piecewise `visualMap` colours by the flag, so only the chosen cells stand out.
- Keep it to one highlighted diagonal, row or cell.
