# Make your own section

What this does
1. Writes a new, working file `sections/sN_<name>.py` in the report folder and adds it to `SECTIONS` in `report.py`.
2. Its calculation counts the source's rows by its column with the fewest groups, so it draws straight away.
3. It holds either a plain bar chart (`CHART`, ECharts options) or a plain block of cards (`HTML`), for you to change.

Step 1: make the blank section (in the report folder)
  python run.py add-section product_mix --own chart --source claims
  -> prints the lines to edit: the description, the calculation, the title, the chart

  | Part | Where it comes from |
  | --- | --- |
  | `product_mix` | your name for the section, lower_snake_case |
  | `chart` | `chart` for a chart, `html` for cards, a list or a table |
  | `claims` | a source name in `report.py` SOURCES (`python run.py list`); left out, the first source |

Step 2: make the table, then the visual
  In the calculation, build the table the visual needs and return it in "tables"; put figures for the words in `m`;
  reword its "question" (the report's footer shows it).
  Wiring at the top: `DATA` names the table; `SLOTS` maps your slot names to its columns, e.g.
    SLOTS = {"label": "product", "value": ["avg_paid"]}
  Chart: in `CHART`, mark each object that takes a column with `"slot"`: an axis with `"slot": "label"`, a series
    with `"slot": "value"`; its `"data": []` is filled at build. Any ECharts option works (echarts.apache.org/en/option.html).
    The blank chart has upright bars: the labels on the `xAxis` (category), the numbers on the `yAxis` (value).
    For bars lying across, replace its `xAxis` and `yAxis` lines with these two (labels move to `yAxis`):
    "yAxis": {"type": "category", "slot": "label", "inverse": True, "data": []},
    "xAxis": {"type": "value", "name": "Average paid per claim", "nameLocation": "middle", "nameGap": 28},
    Room for an axis name: raise the matching margin in the `grid` line, e.g. "bottom": 36 for a name under the
    chart, "top": 36 for one above it.
  A reference line at a value from the data (e.g. the overall average), drawn full height:
    in the calculation:  m["overall_avg"] = df["paid_amount"].mean()
    in SLOTS add:        "avg": "overall_avg"     (a metric name, a column, or a number)
    on the bar series:   "markLine": {"symbol": "none", "lineStyle": {"type": "dashed", "color": "var(--muted)"},
                           "label": {"formatter": "Overall average", "position": "start"},
                           "data": [{"slot": "avg:xAxis", "xAxis": 0}]},
    `"slot": "avg:xAxis"` puts that value into `xAxis` (use `yAxis` for upright bars); the 0 is replaced at build.
  HTML: the element marked `data-rows` repeats its first child once per row; `data-slot="value"` puts that slot's
    value in; `data-slot="share@width"` sets a width in %. Classes come from the library's kit (`lib-panel`,
    `lib-cards`, `lib-card`, `lib-lab`, `lib-big`, `lib-table`).
  Words: TITLE and BULLETS use `{metric}` placeholders from `m`; set `FORMAT` for each number column.
    Reword the sample text the blank section came with: `BASIS` ("What is counted, the period and the basis") for a
    chart, the "Heading: what this shows" line in `HTML`; the build prints a `check:` line until you do.

If a part is missing
  A slot in `SLOTS` naming a column the table lacks: the build stops and lists the table's columns.
  An object marked with a slot that `SLOTS` does not have: its series is left out, with a `check:` line.
  A key ECharts does not know: ignored.

Step 3: build and look
  python run.py report
  python run.py shot
  -> `check:` lines are things to fix; `STOP:` names the file and the fix. Open the screenshot and look at the section.
