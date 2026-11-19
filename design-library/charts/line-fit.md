# CT-04 · line-fit

- Looks like: Actual line in blue with a dashed grey fitted line, both ends labelled.
- Good for: Showing a steady rate of change; Showing how closely actuals follow a fitted or expected path
- Related: CT-03, CH-01, CH-03

```json
{
  "xAxis": { "type": "category", "boundaryGap": false, "data": ["Q1 24", "Q2 24", "Q3 24", "Q4 24", "Q1 25", "Q2 25", "Q3 25", "Q4 25"] },
  "yAxis": { "type": "value", "min": 700, "max": 820, "interval": 30, "axisLabel": { "formatter": "${value}" } },
  "grid": { "left": 8, "right": 130, "top": 30, "bottom": 8, "containLabel": true },
  "series": [
    { "type": "line", "name": "Fitted", "data": [722, 733, 744, 755, 766, 778, 790, 802],
      "itemStyle": { "color": "var(--muted)" }, "lineStyle": { "type": "dashed", "width": 2 }, "showSymbol": false,
      "endLabel": { "show": true, "formatter": "Fitted +6.0%", "color": "var(--muted)", "offset": [0, 16] } },
    { "type": "line", "name": "Actual", "data": [725, 731, 748, 752, 763, 781, 786, 805],
      "itemStyle": { "color": "var(--blue)" }, "lineStyle": { "width": 4 }, "symbolSize": 7,
      "endLabel": { "show": true, "formatter": "Actual ${c}", "color": "var(--blue)", "fontWeight": 600, "offset": [0, -12] } }
  ]
}
```

- Two lines that end close together: offset one end label up and the other down.
- A truncated value axis is fine for lines; say what is measured in the footnote.
