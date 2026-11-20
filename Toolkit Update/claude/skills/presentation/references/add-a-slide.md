# Add a slide

What this does
1. Copies a library slide, chart, table or hero card into the deck as a new file in the deck folder's `slides/` (for example `decks/may-claims/slides/02-paid-by-month.html`), after the last slide or after the one you name, and renumbers the files so the order stays right.
2. With data, fills the chart or table from a data file or a report table (summing raw rows, working out slots the item's recipe asks for) and records on it where the data came from, so a refresh works later.
3. Marks every text still to write with WORD, prints those lines with their numbers, prints a MANUAL line for anything it could not fill, and rebuilds `presentation.html`.

`<skill>` = this skill's folder, `.claude/skills/presentation`. `<deck>` = the deck's name (from `decks/`) or its folder. Run from the project folder.

| You give | You get |
| --- | --- |
| a slide id (`LV-05`) | that slide with its own sample chart: a picture that never takes data |
| a slide id and a chart, table or hero card id (`CH-01 CT-35`) | the slide with the item in its chart spot |
| a chart, table or hero card id alone (`CT-35`) | a plain slide: headline, the item, a commentary heading and bullets |
| any of these plus `--data` or `--from` | the chart, table or hero card filled with your data |

Step 1: pick the ids
  The library is the first that exists: the folder on the project map's `Design library:` line; `design-library` beside `.claude`; `Toolkit Update/design-library`.
  Its lists: `index/slides.md`, `index/charts.md`, `index/tables.md`, `index/hero-cards.md`. Each line reads
    - CT-35 | chart | plain-line | Use for one or more measures over time ... | data: label (text, one); value (number, one or more)
  that is: the id, its type, its name, what it is for, and (charts, tables, cards) the data it needs.

Step 2: see the item's parts and the columns that fit
  node <skill>/scripts/deck.js show CT-35 may-claims --data data/claims.csv
  -> its data slots, each with kind and required or optional; slots marked "worked out first" with how
  -> the columns of your data that fit each slot, and a ready-to-copy add command
  Each item has its own spots or slots: run `show` on it. For a slide it prints its spots and whether it has a chart spot.

Step 3: add it (the commonest request: a chart slide, one line per group)
  node <skill>/scripts/deck.js add may-claims CH-01 CT-35 --data data/claims.csv --slot label=paid_date --slot value=paid_amount --by line_of_business --headline "Medicare paid claims spiked in May"
  -> Added slides/02-medicare-paid-claims-spiked.html (CH-01 CT-35, data from ...)
  -> Grouped: sum by paid_date month, one series per line_of_business (Medicare, Commercial, Medicaid), 6 rows, in order.
  -> Facts for the words: largest, smallest, latest and total of each series; then the lines still marked WORD

  | Part | Where it comes from |
  | --- | --- |
  | `may-claims` | the deck's name |
  | `CH-01` | a slide id from `index/slides.md` (leave it out for a plain chart slide) |
  | `CT-35` | a chart, table or hero card id from `index/charts.md`, `index/tables.md` or `index/hero-cards.md` |
  | `--data data/claims.csv` | your CSV or JSON file, path from where you run the command |
  | `--from "reports/may-claims::monthly::totals"` | in place of `--data`: a report folder, section and table; `--from "reports/may-claims"` alone lists them |
  | `label`, `value` | the slot names `show CT-35` printed |
  | `paid_date`, `paid_amount`, `line_of_business` | column names in the data file or report table |
  | `--headline "..."` | optional: the headline, so it is not left to word |
  Optional too: `--after 3` (slide number or id; `0` puts it first), `--id paid-by-month` (file name), `--section Results` (bottom bar).

When the data needs shaping first
  | Option | Use it when |
  | --- | --- |
  | none | raw rows where the label repeats: they are summed by the label, and many dates become months |
  | `--by line_of_business` | one line or bar per group of another column (items whose value slot takes one or more columns) |
  | `--agg mean` | the average per label instead of the sum |
  | `--top 8` | only the first N rows (tables keep 8 unless told) |
  | `--format $short` | $7.5M; `$0` whole dollars ($1,209); `0` whole numbers; `,` with decimals; `%` percents |
  | `--spot chart-2` | the slide has two chart spots and the item goes into the second |
  Slots "worked out first": add works them out for CT-02 and CT-24 (sorted, share), CT-08 (low, gap), CT-11 (range: also give `--slot high=<column>`),
  CT-19 (part as %), CT-22 (running), TB-08 (incurred, pmpm), AN-01 and AN-10 (value-number). For any other, put the worked-out figure in your data as a column first.

If a part is missing
  - A required slot with no column (or a worked-out slot add cannot work out): it goes in on placeholder data marked `MANUAL <slot>`, with a MANUAL line.
  - An optional slot not given: left out quietly. A slot the item does not have: ignored, with a note.
  - A chart id with a slide that has no chart spot: both go in, the chart on a plain slide right after.
  - Data with a slide id and no chart id: the slide goes in without the data; the MANUAL line gives the add command that would take it.
  - It stops only for an unknown id, or a data file or report that is not there.

Acting on a MANUAL line
  Route 1, name a column: in the slide file change `MANUAL <slot>` to a column of your data (add the column to the data first if
  none fits), then run the refill command the line printed, e.g.
    node <skill>/scripts/deck.js refill may-claims targets
  Route 2, type the figures: replace the placeholder figures in that item with yours, delete `MANUAL <slot>` (the "col" in a chart,
  the data-cols entry in a table), and change `data-manual="<slot>"` to `data-typed="<slot>"` on the item; then build.
  `build` and `check` list the slot until one route is done; renaming the placeholder alone does not count.

Step 4: word it, build and look
  Open the printed file (inside the deck folder: `decks/may-claims/slides/...`) and replace each text that starts `WORD:`, the `WORD:` too.
  Headline: the point as a sentence with its number. Bullets: what to look at, with its number, and what it means. Footnote: what is measured, the period, the source.
  node <skill>/scripts/deck.js build may-claims    -> lists what is left: WORD lines, sample wording, MANUAL slots, chart problems
  node <skill>/scripts/deck.js check may-claims    -> draws every slide: overflow, cut-off labels; exits 1 until clean
  node <skill>/scripts/screenshot.js may-claims    -> open decks/may-claims/shots/sheet.png and look at every slide
