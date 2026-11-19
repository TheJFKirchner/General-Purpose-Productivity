# Charts

Charts are drawn by ECharts, which the scaffold loads. A slide chart proves its headline; it is not for exploring. With a design library, use its chart recipe or slide pattern and read this page only for a chart neither has.

## Rules

- One chart, one claim: one metric or one relationship. It shows the headline's own number.
- One item highlighted: the one the headline is about, in `var(--blue)`. Everything else `var(--chart-muted)`.
- Label series, periods and line ends on the chart. Never explain colours or dots in a sentence; no legend that needs reading.
- Draw any threshold or "normal" level the text cites, as a `markLine`.
- A hidden value axis gets `max` set to the largest value, or the chart leaves a dead band at the top.
- Value labels carry units ("$805K", "91%"), not bare numbers.
- Drop near-zero value labels (+0.3, -0.5): label the items the text talks about.
- Light hover is built in (a one-line tooltip). Do not set `tooltip`, `emphasis` or `silent` in chart JSON. The tooltip takes its format from the series `label.formatter`, else the value axis `axisLabel.formatter`; give every series one, and a `name` when there are two or more.
- Colours are theme tokens only (`var(--blue)`, `var(--navy)`, `var(--muted)`, `var(--chart-muted)`, `var(--paper)`). Never a hex value. Series order when several need colour: blue, green, navy, teal, orange, muted.
- No dropdowns, filters, tabs, zoom, clickable legends, embedded or screenshot dashboards. A slide shows one cut; a second cut is a second slide.

## Numbers for a chart

In this order. Never write a script to call analytics.

1. A row in `findings.md`.
2. The series already in the report's chart: grep `"data": [` in the report HTML; it holds the full series.
3. `python run.py data <analytic> [<table>]` in the report folder (`--json` for JSON). It prints the whole table with the report's own parameters.

None of these has the number: tell the user it is missing. Take only the rows of the chosen cut and hard-code them. The footnote names what is measured, the cut in plain words, the period and the source as file, function, table and finding: `analytics/claims_cost.py, nov_rise, by_month (finding 1)`.

- From a report chart: take its series and keep its kind, period and measure name. Restyle only, and draw any line the text cites. The user's pick is not second-guessed.
- A ratio of two cited numbers ("13 times") is allowed when both are on the slide or in its cited findings rows. Round down and give the sum in the speaker notes. Otherwise add a findings row first.

## Which chart

| The point is about | Use |
| --- | --- |
| One figure | No chart: `.stat` |
| A few categories compared | Bar. Horizontal when labels are long or there are more than 6 |
| Change over time | Line (1 to 3 lines) or columns, full width when over 12 periods |
| Parts of a whole | Horizontal bar, sorted. Pie or doughnut only for 2 or 3 parts |
| Relationship between two measures | Scatter, with the pattern named in the headline |
| Exact figures that will be read | No chart: `table.data` |

| Limit | Value |
| --- | --- |
| Categories | 12; aim for 4 to 8. Over that, group the rest as "Other" |
| Time periods | Keep the source's period, up to 24, full width (`chart-callout`, or CH-04) when over 12. Never shorten a period to meet a limit |
| Series | 4; aim for 1 or 2 |
| Pie slices | 5 |
| Charts on a slide | 1; 2 only on a comparison slide |

## How a chart is declared

```html
<div class="chart" data-echart>
  <script type="application/json">
  {
    "xAxis": { "type": "category", "data": ["North", "South", "East", "West"] },
    "yAxis": { "type": "value", "show": false, "max": 91 },
    "series": [{
      "type": "bar",
      "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "top", "formatter": "{c}%" },
      "data": [81, 79, 84, { "value": 91, "itemStyle": { "color": "var(--blue)" } }]
    }]
  }
  </script>
</div>
```

- A normal ECharts option. `"var(--name)"` as a whole string resolves to that token in `styles.css`.
- Fonts, axis colours, gridlines and the palette come from the theme; do not restate them. A default `grid` is added; set one only to make room (`"right": 150` for line end labels).
- The chart fills its parent: it sits in `.content`, or in a grid with `flex: 1; min-height: 0; min-width: 0;`. Never set a height on it.

Line, one highlighted, ends labelled, an event marked:

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

Horizontal bars, sorted: `"yAxis": { "type": "category", "inverse": true, ... }`, value labels `"position": "right"`, and `"grid": { "right": 70 }` so the last label is not clipped.

## Common options

| Want | Option |
| --- | --- |
| Units on an axis | `"axisLabel": { "formatter": "{value}%" }` |
| Value on each bar | `"label": { "show": true, "position": "top", "formatter": "{c}%" }` |
| A threshold or normal line | `"markLine": { "symbol": "none", "data": [{ "yAxis": 124 }], "label": { "formatter": "Normal month $124K" } }` on the series |
| Mark a period | `markArea`, not one dashed line |
| Bars side by side | Two `bar` series, each its own `itemStyle.color` |
| Stacked bars | Same `"stack": "total"` on each series |

- `{c}` prints the raw number: no thousands separator, trailing zero or plus sign. For "$4,510" or "+1.5", give the data item its own `"label": { "formatter": "+1.5" }`.
- Stacked bars with one highlight: label the highlighted segment inside the bar in `var(--paper)` if it is tall enough; otherwise label the stack total above the bar.
- Bars start at zero; a truncated axis is fine for lines. With `min` and `max`, also set `interval`.
- Hide a series with `"itemStyle": { "opacity": 0 }`, not `"transparent"`. Text inside a blue bar: `"color": "var(--paper)"`.
- Two line ends close together: `"endLabel": { "offset": [0, -12] }` on one. Negative bars: `"axisLabel": { "margin": 14 }` on the category axis.
- A chart with 4 or fewer bars is short: give it the smaller share of the slide.
- A range is drawn as a range, not as two bars. The footnote is one line.

## Check

`node <skill>/scripts/check-charts.js <deck>/presentation.html` flags invalid JSON, too many points (24 for a time axis), nothing highlighted, and leftover controls.

Adapted from github.com/ryanbbrown/revealjs-skill (MIT), moved from Chart.js to ECharts.
