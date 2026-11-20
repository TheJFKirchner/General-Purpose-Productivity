# Make your own slide

What this does
1. Writes a new slide file in the deck's `slides/` folder: a headline, a chart spot holding empty chart options, a commentary heading and two bullets, all marked `WORD:`.
2. You write the chart's options yourself (or put a table or other HTML in the chart spot).
3. Optionally you point the chart at a data file or report table, grouped or averaged as you say, so `refill` fills and refreshes it; `build` puts it into `presentation.html`.

`<skill>` = this skill's folder, `.claude/skills/presentation`. `<deck>` = the deck's name (from `decks/`) or its folder.

Step 1: add the blank slide
  node <skill>/scripts/deck.js own may-claims --headline "Medicare pays the most per claim" --id avg-claim
  -> Added slides/05-avg-claim.html, then the line numbers of its WORD lines (in decks/may-claims/slides/05-avg-claim.html)
  The chart's options are the short block between <script type="application/json"> and </script> (empty "series": []).

  | Part | Where it comes from |
  | --- | --- |
  | `own` | the command for a blank slide |
  | `may-claims` | the deck's name |
  | `--headline "..."` | optional: the point as a sentence with its number |
  | `--id avg-claim` | optional: the file name; otherwise made from the headline |
  Optional too: `--after 3` (slide number or id; `0` puts it first), `--section Results` (bottom bar).

Step 2: write the chart (worked example: bars with a dashed line at the average)
  Replace everything between <script type="application/json"> and </script> with ECharts options (echarts.apache.org/en/option.html):
    {
      "grid": {"left": 8, "right": 30, "top": 30, "bottom": 8, "containLabel": true},
      "xAxis": {"type": "category", "data": ["Medicare", "Medicaid", "Commercial"]},
      "yAxis": {"type": "value", "axisLabel": {"formatter": "${value:comma}"}},
      "series": [
        {"type": "bar", "name": "Average paid", "itemStyle": {"color": "var(--chart-muted)"}, "highlight": "Medicare", "label": {"show": true, "position": "top", "formatter": "${c:comma}"}, "data": [1194, 498, 476],
         "markLine": {"symbol": "none", "lineStyle": {"type": "dashed", "color": "var(--navy)"}, "label": {"position": "insideEndTop", "formatter": "Average ${c:comma}"}, "data": [{"yAxis": 723}]}}
      ]
    }
  Label formats that work: "${c:short}" $7.5M · "{c:short}" 7.5M · "${c:comma}" $1,209 · "{c:comma}" 1,209 · "{c}%" 38% · "{c}" as is ·
  "{a}" the series name · "{b}" the category · "{@[1]}" the second number of an [x, y] point. On an axis write `value` for `c`.
  Anything else after a colon (`{c:0}`) prints as typed; `build` flags it, and a % on values in the thousands.
  Colours only as tokens: "var(--blue)" the point, "var(--chart-muted)" context, "var(--navy)"; never hex. No "tooltip".

Step 3 (optional): fill it from data, grouped or averaged
  On the chart spot's <div class="chart" data-echart data-spot="chart"> add
    data-source="../../data/claims.csv" data-shape="agg=mean; by=line_of_business; order=paid_amount" data-format="$0"
  On each object that holds data add "col": the category axis "col": "line_of_business", the bar series "col": "paid_amount",
  and the average line's entry {"yAxis": 0, "col": "paid_amount", "figure": "mean"}. Then run
    node <skill>/scripts/deck.js refill may-claims avg-claim

  | Part | Where it comes from |
  | --- | --- |
  | `data-source` | the data file, path from the deck folder (`decks/may-claims/`); or `<report folder>::<section>::<table>` |
  | `data-shape` | how rows are combined: `agg=sum` or `agg=mean`, `by=<label column>`, `month` (days to months), `order=<column>` (largest first) or `order=label`; leave it out for one row per point |
  | `data-format` | `$short`, `$0` (whole dollars), `0` (whole numbers), `,` or `%`: refill rounds the data to suit |
  | `"col"` | a column of the data, after grouping; for [x, y] points `"col": "billed,paid_share"` |
  | `"figure"` | one number from a column for a line: `first`, `sum`, `mean`, `max` or `min` |

If a part is missing
  - Empty options: `build` lists "chart has no series yet" until you write them.
  - A "col" the data lacks: refill says so and leaves the slide as it was.
  - Invalid JSON: `build` prints the line; use double quotes and no trailing commas.

Step 4: build and look
  node <skill>/scripts/deck.js build may-claims    -> what is left: WORD lines, chart problems
  node <skill>/scripts/deck.js check may-claims    -> draws every slide: overflow, cut-off labels; exits 1 until clean
  node <skill>/scripts/screenshot.js may-claims    -> open decks/may-claims/shots/sheet.png and look
