# Change a slide

What this does
1. You edit one slide file in the deck's `slides/` folder by hand; no other file changes.
2. `build` copies every slide file into `presentation.html` again and lists what is left to fix.
3. `refill` (only after adding a data line) fetches that slide's data again; your other edits stay.

`<skill>` = this skill's folder, `.claude/skills/presentation`. `<deck>` = the deck's name (from `decks/`) or its folder.

Step 1: find the file
  node <skill>/scripts/deck.js list may-claims
  -> 2  slides/02-paid-by-month.html  [CH-01 CT-35]  (has data)
         Paid claims have eased since October
  Open only that file. Never edit presentation.html.

The parts of a slide file
  <section id="paid-by-month" data-section="Results" data-from="CH-01 CT-35">     <- id, bottom-bar section, library ids
    <h2 data-spot="headline">Paid claims have eased since October</h2>            <- a spot: text you word
    <div data-item="CT-35" data-source="../../data/claims.csv" data-format="$short" data-spot="chart">   <- the chart and its data source
      <script type="application/json">
      {
        "xAxis": {"type":"category","data":["2026-01","2026-02"],"col":"service_date"},   <- "col": the column refill puts here
        "yAxis": {"type":"value","axisLabel":{"formatter":"${value:short}"}},
        "series": [
          {"type":"line","name":"Paid amount","data":[1714406,1624508],"col":"paid_amount"}
        ]
      }
      </script>
    </div>
    <ul data-spot="bullets"><li>Paid peaked at $407K in October.</li></ul>
    <div class="footnote" data-spot="footnote">Paid by month of service. Source: claims extract.</div>
  </section>
  Each slide has its own spots (`deck.js show <slide id>` lists them). Text starting `WORD:` is still sample wording.

Step 2: worked edits
  a. Reword: replace the text inside the `data-spot` element, `WORD:` included.
  b. Add a line: copy a series line, change "name" and "col", set "data": [], put a comma between the lines, then
       node <skill>/scripts/deck.js refill may-claims paid-by-month
     {"type":"line","name":"Billed amount","data":[],"col":"billed_amount"}
  c. Name the value axis, and highlight one line or one bar:
       axis:  "yAxis": {"type":"value","name":"Paid per month","nameLocation":"middle","nameGap":50}  plus  "grid": {"left":30}
       a line (a whole series): on the line that matters add  "lineStyle":{"color":"var(--blue)","width":4},"itemStyle":{"color":"var(--blue)"}
         and on each other line  "lineStyle":{"color":"var(--chart-muted)"},"itemStyle":{"color":"var(--chart-muted)"}
         (an end label takes the same colour: "endLabel":{"show":true,"formatter":"{a}","color":"var(--blue)"}). Refill keeps them.
       a bar (one category): on the bar series add  "highlight":"Medicare", "itemStyle":{"color":"var(--chart-muted)"}, then refill;
         the blue follows Medicare wherever it moves in the data.

  | Part | Where it comes from |
  | --- | --- |
  | `paid-by-month` | the slide's id (or its number) from `list` |
  | `"col":"billed_amount"` | a column of the slide's data: `data-source` names the file or report; `show CT-35 <deck> --data <file>` lists columns |
  | `"var(--chart-muted)"` | a colour token: `var(--blue)` highlight, `var(--chart-muted)` context, `var(--navy)`, `var(--orange)`; never hex |
  | `"${value:short}"` | a number format: `${c:short}` $7.5M, `{c:comma}` 7,500,000, `{c}%` (axes use `value` for `c`) |
  Move a slide: change the number in its file name (`03b-` sits between `03-` and `04-`). Remove it: delete the file.

If a part is missing
  - A `MANUAL <slot>` (and `data-manual`) in the file: either change `MANUAL <slot>` to a column of the data and run
    `node <skill>/scripts/deck.js refill may-claims <slide id>`, or type your figures in, delete `MANUAL <slot>`, and change
    `data-manual="<slot>"` to `data-typed="<slot>"`. `build` lists it until one of the two is done.
  - Text the library sample wrote: `build` lists every one still unchanged, with or without its `WORD:` mark.
  - A "col" the data lacks: refill says so and leaves that slide as it was.
  - Invalid chart options: `build` prints the line; use double quotes and no trailing commas.

Step 3: build and look
  node <skill>/scripts/deck.js build may-claims    -> what is left: WORD lines, MANUAL slots, chart problems
  node <skill>/scripts/deck.js check may-claims    -> draws every slide: overflow, cut-off labels; exits 1 until clean
  node <skill>/scripts/screenshot.js may-claims    -> open decks/may-claims/shots/sheet.png and look
