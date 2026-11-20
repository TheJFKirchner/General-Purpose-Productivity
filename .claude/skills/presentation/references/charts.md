# Charts on a slide

A chart is an ECharts option in a `<script type="application/json">` inside `<div class="chart" data-echart>`. A copied library chart keeps its options; change them freely. Options reference: echarts.apache.org/en/option.html.

## Rules

- One chart, one claim; it shows the headline's own number.
- One item highlighted in `"var(--blue)"`, context in `"var(--chart-muted)"`. Colours only as tokens (`"var(--navy)"`, `"var(--orange)"`), never hex.
- Label series and line ends on the chart; no legend that needs reading. Draw any line the text cites (`markLine`).
- Value labels and axes carry units. Limits: 12 categories (24 periods on a time axis, never cut the window), 4 series, 5 pie slices.
- No `tooltip`, `toolbox`, `dataZoom`: the deck adds a light hover and nothing else.

## Number formats

`--format` on `deck.js add`: `$short` ($7.5M, $499), `short`, `$0` (whole dollars, $1,209), `0` (whole numbers), `,`, `%`. In a `formatter` of your own: `"${c:short}"`, `"{c:comma}"`, `"{c}%"`; on an axis `value` in place of `c`. For whole numbers in a chart of your own, put `data-format="$0"` (or `"0"`) on its spot: refill rounds the data. The build flags an axis or label that would print raw numbers.

## Common changes

| Want | Do |
| --- | --- |
| A third line or bar | Copy a series line, give it its `"name"` and `"col"` (the column), set `"data": []`, run `deck.js refill <deck> <slide>` |
| One line per group of a raw file | `deck.js add ... --by <column>`; a slide already added: `deck.js refill <deck> <slide> --by <column>`. Each series' `"col"` is then a group name |
| Rename an axis | `"yAxis": {"name": "Paid per month", "nameLocation": "middle", "nameGap": 50}`; give the grid room (`"grid": {"left": 30}`) |
| Room for line end labels | `"grid": {"right": 130}` |
| Highlight a bar by name | On the series: `"highlight": "Medicare"` (or a list), and `"itemStyle": {"color": "var(--chart-muted)"}` for the rest; refill keeps it on that name wherever it moves |
| Threshold line from the data | On the series: `"markLine": {"symbol": "none", "label": {"position": "insideEndTop", "formatter": "Average ${c:short}"}, "data": [{"yAxis": 0, "col": "paid_amount", "figure": "mean"}]}`. `figure`: `first`, `sum`, `mean`, `max`, `min` of that column; refill moves the line (`xAxis` for horizontal bars). A fixed line: `{"yAxis": 124}` and no `col` |
| Mark a period | `markArea` |
| Stacked bars | The same `"stack": "total"` on each series |
| Horizontal bars, sorted | `"yAxis": {"type": "category", "inverse": true}`, labels `"position": "right"`, `"grid": {"right": 70}` |

- A hidden value axis needs `max` set to the largest value, or the chart leaves a dead band.
- Bars start at zero; a cut axis is fine for lines. With `min` and `max`, also set `interval`.
- A chart of your own fills from data when you add `"col"` to each object that holds data and put `data-source` (and `data-format`) on the chart's spot; refill then keeps it current.
- Style put on one data item (`{"value": 7.5, "itemStyle": ...}`) stays with its position, not its name; use `"highlight"` for anything that must follow a name.

## Which chart

| The point is about | Use |
| --- | --- |
| One figure | No chart: a hero card (HC) or `.stat` |
| A few categories compared | Bars; horizontal when labels are long or there are more than 6 |
| Change over time | Line (1 to 3 lines), or columns |
| Parts of a whole | Stacked or sorted bars; a doughnut only for 2 or 3 parts |
| Two measures together | Scatter, with the pattern named in the headline |
| Exact figures that will be read | A table (TB) |

The build (`deck.js build`) and the drawn check (`deck.js check`) flag invalid JSON, too many points, raw numbers, missing room for end labels, cut-off axis names and overlapping labels.
