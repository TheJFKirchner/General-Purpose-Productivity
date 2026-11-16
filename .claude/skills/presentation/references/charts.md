# Charts

Read all of this before adding any chart. Charts are drawn by ECharts, which the scaffold loads. A slide chart proves the headline; it is not for exploring.

## Rules

- One chart, one claim. It shows one metric or one relationship.
- One item highlighted: the one the headline is about, in `var(--primary-color)`. Everything else is `var(--chart-muted)`.
- The headline reads the same without the chart: cut the chart, or use a big number.
- The text beside or under the chart says what it proves, with the number, in the same words the chart uses.
- A visual the user picked from an analysis or dashboard is rebuilt as the one cut they chose: see "Visuals from an analysis or dashboard". Never screenshot, embed or link the live one.
- Numbers come from a source listed in `plan.md`. Never from memory; never rounded differently on two slides.
- No tooltips, toolbox, zoom, or legends that need reading. Label the bars and the line ends directly. The deck turns hover effects off.
- Colours are theme variables only. Never a hex value in chart JSON.

## Visuals from an analysis or dashboard

The usual case. The visual exists; the user has said which one and which cut (`plan.md`, the slide's "Visual from" and "Cut" lines).

1. Find the table behind the visual (an analysis section's saved table, the dashboard's summary table or query result). Not the rendered chart.
2. Take only the rows for the chosen cut: the dropdown, filter and tab settings in the plan. One cut. No other settings come along.
3. Hard-code those values in the slide's chart JSON. Nothing on the slide loads data, and nothing lets the audience change the view.
4. Keep the source's chart kind and its measure names unless they cannot fit a slide. Then make the smallest change that fits (fewer categories with the rest as "Other", a shorter period) and report it; do not redesign the visual.
5. Highlight the item the cut was chosen for.
6. Footnote: what is measured, the cut in plain words ("West region, new customers only"), the as-of date, the source.

| Not on a slide | Why |
| --- | --- |
| Dropdowns, filters, tabs, toggles, sliders | A slide shows one cut, chosen for a reason |
| Tooltips, zoom, clickable legends | The audience cannot hover; the point must be readable as shown |
| An embedded or linked live dashboard, a screenshot of one | It changes after the meeting, and carries controls and clutter |
| A second cut "for reference" | A second cut is a second slide, with its own reason, or a backup |

- The same visual at two cuts the user wants compared: one slide, two series or two small charts, the comparison in the headline.
- The user's pick is not second-guessed. The rules below ("one item highlighted", the limits) are defaults for visuals you design; for a visual the user chose, apply them only as far as they do not change what the user asked to show.

## Which chart

| The point is about | Use |
| --- | --- |
| One figure | No chart: big number (`.stat`) |
| A few categories compared | Bar. Horizontal bar when labels are long or there are more than 6 |
| Change over time | Line, 1 to 3 lines |
| Two states | Two bars, two lines, or two big numbers |
| Parts of a whole | Horizontal bar, sorted. Pie or doughnut only for 2 or 3 parts |
| Relationship between two measures | Scatter, with the pattern named in the headline |
| Exact figures that will be read | No chart: `table.data` |

| Limit | Value |
| --- | --- |
| Points in a chart | 12; aim for 4 to 8 |
| Series | 4; aim for 1 or 2 |
| Pie slices | 5 |
| Charts on a slide | 1; 2 only on a comparison slide |

More than the limit: the claim is too wide. Split it, or group the rest into "Other".

## How a chart is declared

A `div` with `class="chart"` and `data-echart`, holding the ECharts option as JSON:

```html
<div class="chart" data-echart>
  <script type="application/json">
  {
    "xAxis": { "type": "category", "data": ["North", "South", "East", "West"] },
    "yAxis": { "type": "value", "axisLabel": { "formatter": "{value}%" } },
    "series": [{
      "type": "bar",
      "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "top", "formatter": "{c}%" },
      "data": [81, 79, 84, { "value": 91, "itemStyle": { "color": "var(--primary-color)" } }]
    }]
  }
  </script>
</div>
```

- The JSON is a normal ECharts option. Anything ECharts supports works.
- `"var(--name)"` as a whole string value resolves to that variable in `styles.css`. Change the theme and the charts follow.
- Fonts, axis colours, gridlines, bar corners, line width and the default palette come from the theme. Do not restate them.
- A default `grid` is added when the option has none. Set `grid` only to make room, for example `"right": 150` for line end labels.
- Highlight one bar: make that data item an object with its own `itemStyle.color`.
- The chart redraws with its animation each time its slide is shown. `?export` in the URL turns animation off.

## Sizing (important)

The `.chart` div fills whatever space its parent gives it. The parent must have a definite size:

1. The chart sits inside `<div class="content">`, which fills the slide below the headline.
2. Inside a grid, the grid is `flex: 1; min-height: 0; min-width: 0;`.
3. Never set a height on the chart itself.

### Full slide

```html
<section id="s04-west-kept-most" data-section="Results">
  <p class="kicker">Results</p>
  <h2>The West region kept the most new customers after the change</h2>
  <div class="content">
    <div class="chart" data-echart> ... </div>
  </div>
  <div class="footnote">What is measured, the period, the source.</div>
</section>
```

### Half slide: text beside the chart

```html
<div class="content">
  <div style="flex: 1; display: grid; grid-template-columns: 1fr 2fr; gap: 30px; min-height: 0; min-width: 0;">
    <div class="callout" style="display: flex; flex-direction: column; justify-content: center;">
      <div class="stat">
        <p class="stat-value">3.1%</p>
        <p class="stat-label">monthly early churn in October</p>
        <p class="stat-note">Down from 5.1% before launch.</p>
      </div>
    </div>
    <div class="chart" data-echart> ... </div>
  </div>
</div>
```

### Half slide: text above the chart

```html
<div class="content">
  <div style="flex: 1; display: grid; grid-template-rows: 1fr 3fr; gap: 20px; min-height: 0; min-width: 0;">
    <div class="callout" style="display: flex; align-items: center;"><p>The one sentence the chart proves.</p></div>
    <div class="chart" data-echart> ... </div>
  </div>
</div>
```

| Split | Use for |
| --- | --- |
| `1fr 3fr` | One sentence |
| `1fr 2fr` | A number and a note, or two bullets |
| `1fr 1fr` | Two charts on a comparison slide |

## Patterns

### Horizontal bar, sorted, one highlighted

```json
{
  "xAxis": { "type": "value", "show": false },
  "yAxis": { "type": "category", "inverse": true, "data": ["Setup took too long", "Price", "Missing feature", "Other"] },
  "series": [{
    "type": "bar",
    "itemStyle": { "color": "var(--chart-muted)" },
    "label": { "show": true, "position": "right", "formatter": "{c}%" },
    "data": [{ "value": 38, "itemStyle": { "color": "var(--primary-color)" } }, 24, 21, 17]
  }]
}
```

### Line, one highlighted, ends labelled, an event marked

```json
{
  "xAxis": { "type": "category", "boundaryGap": false, "data": ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"] },
  "yAxis": { "type": "value", "min": 2, "max": 6, "axisLabel": { "formatter": "{value}%" } },
  "grid": { "left": 8, "right": 150, "top": 30, "bottom": 8, "containLabel": true },
  "series": [
    { "type": "line", "name": "Old checklist", "data": [5.1, 5.0, 5.2, 5.0, 5.3, 5.1, 5.2],
      "itemStyle": { "color": "var(--chart-muted)" }, "showSymbol": false,
      "endLabel": { "show": true, "formatter": "{a}  {c}%", "color": "var(--muted-color)" } },
    { "type": "line", "name": "Guided setup", "data": [5.1, 5.0, 5.2, 4.1, 3.4, 3.2, 3.1],
      "itemStyle": { "color": "var(--primary-color)" }, "lineStyle": { "width": 5 }, "showSymbol": false,
      "endLabel": { "show": true, "formatter": "{a}  {c}%", "color": "var(--primary-color)", "fontWeight": 600 },
      "markLine": { "symbol": "none", "silent": true, "lineStyle": { "color": "var(--muted-color)", "type": "dashed", "width": 1.5 },
                    "label": { "formatter": "Launch", "color": "var(--muted-color)" }, "data": [{ "xAxis": "Jun" }] } }
  ]
}
```

### Common options

| Want | Option |
| --- | --- |
| Units on an axis | `"axisLabel": { "formatter": "{value}%" }` |
| Value on each bar | `"label": { "show": true, "position": "top", "formatter": "{c}%" }` |
| Hide an axis | `"show": false` on that axis |
| A target line | `"markLine": { "data": [{ "yAxis": 85 }], "label": { "formatter": "Target 85%" } }` on the series |
| A legend (two or more series, no end labels) | `"legend": {}` |
| Bars side by side | Two `bar` series; give each its own `itemStyle.color` |
| Stacked bars | Same `"stack": "total"` on each series |

- Say what is measured in the footnote or the text beside the chart, not in an axis title.
- A truncated value axis (`min` above zero) is fine for lines. For bars, start at zero. The one exception is a waterfall between two large totals: cut the axis, set an explicit `interval`, and say so in the footnote.
- `{c}` prints the raw number: no thousands separator, no trailing zero, no plus sign. For "$4,510", "5.0%" or "+1.5", make the data item an object with its own `"label": { "formatter": "+1.5" }`.
- `"var(--name)"` must be the whole string. `"transparent"` is a named colour: hide a series with `"itemStyle": { "opacity": 0 }` instead.
- Text inside a primary-coloured bar: `"color": "var(--background-color)"`.
- Two lines that end close together: `"endLabel": { "offset": [0, -12] }` on one of them.
- Negative bars: raise `"axisLabel": { "margin": 14 }` on the category axis so labels clear the bars.
- The footnote is one line. Two lines run into the chart's axis labels.
- With `min` and `max` on a value axis, also set `interval`, or the ticks come out uneven.
- Start and end labels on a line are the same size.
- Mark a period (a storm quarter, the least developed quarters) with `markArea`, not one dashed line.
- Horizontal bars with value labels: `"grid": { "right": 70, ... }` so the last label is not clipped.
- A chart with 4 or fewer bars is short: give it the smaller share of the slide, or it leaves a dead band. This overrides the split in the library component being copied.
- Negative values in bars: put the category labels at the axis end (`"axisLabel": { "margin": 14 }`), and value labels outside the bar on the side it points.
- A range is drawn as a range (a band or a line between two points), not as two bars.
- A legend swatch must match what it labels. With one highlighted item in a series, drop the legend and label directly.

### Waterfall (bridge from one figure to another)

Two stacked bar series: a hidden base that lifts each step, and the visible step. Totals in `var(--muted-color)`, the step the headline is about in `var(--primary-color)`, other steps in `var(--chart-muted)`.

```json
{
  "xAxis": { "type": "category", "data": ["Prior", "Trend", "Development", "Mix", "Current"] },
  "yAxis": { "type": "value", "axisLabel": { "formatter": "{value}%" } },
  "series": [
    { "type": "bar", "stack": "w", "itemStyle": { "opacity": 0 }, "data": [0, 52.0, 59.5, 66.0, 0] },
    { "type": "bar", "stack": "w", "itemStyle": { "color": "var(--chart-muted)" },
      "label": { "show": true, "position": "top" },
      "data": [
        { "value": 52.0, "itemStyle": { "color": "var(--muted-color)" }, "label": { "formatter": "52.0%" } },
        { "value": 7.5, "itemStyle": { "color": "var(--primary-color)" }, "label": { "formatter": "+7.5" } },
        { "value": 6.5, "label": { "formatter": "+6.5" } },
        { "value": 5.0, "label": { "formatter": "+5.0" } },
        { "value": 71.0, "itemStyle": { "color": "var(--muted-color)" }, "label": { "formatter": "71.0%" } }
      ] }
  ]
}
```

A step down: base is the level after the fall, the visible value is the size of the fall, the label says "-2.0".

### Dumbbell and target tick (movement between two points, or actual against expected)

Scatter series on a category axis. Worked slides: `dumbbell-callout` and `bars-target-tick` in `library/compare/slides.html`. In a scatter label, `{@[0]}` prints the value.

### Heatmap (a development triangle)

Colour cells with a piecewise `visualMap` (`"pieces"`, each with a `"color": "var(--name)"`), not `inRange`. Worked slide: `heatmap-callout` in `library/backup/slides.html`. Keep it to one highlighted diagonal or cell.

- A dashed marker cannot sit between two bars on a category axis. Colour the bars before and after differently instead.

## Check

```bash
node <skill>/scripts/check-charts.js <folder>/presentation.html
```

Flags invalid JSON, too many points or series, charts with nothing highlighted, and leftover exploring features.

Layouts adapted from github.com/ryanbbrown/revealjs-skill (MIT), moved from Chart.js to ECharts.
