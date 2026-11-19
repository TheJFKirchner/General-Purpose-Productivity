# CT-11 · range-bar

- Looks like: One low-to-high grey bar with the central figure as a dashed line and the chosen figure as a solid blue line.
- Good for: Showing where a chosen figure sits within a reasonable range; Making the size of the uncertainty visible
- Related: UN-01, UN-02

```json
{
  "grid": { "left": 20, "right": 20, "top": 34, "bottom": 34, "containLabel": false },
  "xAxis": { "type": "value", "min": 1040, "max": 1420, "show": false },
  "yAxis": { "type": "category", "data": ["Range"], "show": false },
  "series": [
    { "type": "bar", "stack": "range", "data": [1130], "itemStyle": { "opacity": 0 },
      "label": { "show": true, "position": "insideRight", "formatter": "Low  $1,130m", "color": "var(--muted)", "fontSize": 16 } },
    { "type": "bar", "stack": "range", "data": [200], "barWidth": 46,
      "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "right", "formatter": "High  $1,330m", "color": "var(--muted)", "fontSize": 16 },
      "markLine": { "symbol": "none", "silent": true, "data": [
        { "xAxis": 1212, "lineStyle": { "color": "var(--muted)", "type": "dashed", "width": 2 },
          "label": { "position": "start", "formatter": "Central  $1,212m", "color": "var(--muted)", "fontSize": 16 } },
        { "xAxis": 1248, "lineStyle": { "color": "var(--blue)", "type": "solid", "width": 4 },
          "label": { "position": "end", "formatter": "Chosen  $1,248m", "color": "var(--blue)", "fontWeight": 600, "fontSize": 17 } }
      ] } }
  ]
}
```

- A range is drawn as a range, never as two bars.
- The invisible first bar lifts the range to its low end; its label prints the low figure.
