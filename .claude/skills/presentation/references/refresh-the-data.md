# Refresh the data

What this does
1. For every chart, table, hero card and animation that records where its data came from (`data-source` on it), reads that source again: the data file, or `python run.py data` in the report folder.
2. Puts the new figures into that item in its slide file. Series names, colours, axis names and ranges, formats, highlights and headings stay as you left them.
3. Prints the facts for every series, lists figures typed in headlines, bullets and footnotes that matched the old data and no longer do, and rebuilds `presentation.html`.

`<skill>` = this skill's folder, `.claude/skills/presentation`. `<deck>` = the deck's name (from `decks/`) or its folder.

Step 1: the same source has new figures
  node <skill>/scripts/deck.js refill may-claims
  -> slides/02-paid-by-lob.html: CT-34 refilled from ../../data/claims.csv (3 rows).
  ->   Facts for the words (Paid amount): largest $10M (Commercial); second $7.5M (Medicare); ...
  -> Figures in the words that matched the old data and no longer do: slides/02-paid-by-lob.html line 10: "$5.2M"
  One slide only: add its id or number after the deck name.

Step 2: point it at a new file or report
  node <skill>/scripts/deck.js refill may-claims --data data/claims_june.csv
  node <skill>/scripts/deck.js refill may-claims paid-by-month --from "reports/june-claims::monthly::totals"

  | Part | Where it comes from |
  | --- | --- |
  | `may-claims` | the deck's name |
  | `paid-by-month` | optional: one slide's id or number, from `deck.js list may-claims` |
  | `--data data/claims_june.csv` | the new file, path from where you run the command; every item that used a file now uses it (with a slide named: only that slide's items) |
  | `--from "reports/june-claims::monthly::totals"` | a report folder, section and table; every item that used a report now uses it (or that slide's) |
  The new source needs the same column names; `show <item id> <deck> --data <file>` lists its columns.

Step 3 (when needed): one line or bar per group on a slide already added
  node <skill>/scripts/deck.js refill may-claims paid-by-month --by line_of_business
  -> the chart's value series becomes one series per line of business; the source must hold the raw rows

If a part is missing
  - A column the new source lacks: that item is not refilled and the line says which column; the rest go ahead.
  - A `MANUAL <slot>` placeholder: change it to a real column name in the slide file, then refill that slide.
  - A new group in the data (a new region): listed; copy a series line, set its "name" and "col", refill again.
  - Figures you worked out by hand (ratios, differences) are not checked: read them against the facts.

Step 4: reword, build and look
  Fix every figure it listed, using the facts it printed.
  node <skill>/scripts/deck.js build may-claims    -> what is left to word or fix
  node <skill>/scripts/deck.js check may-claims    -> draws every slide; exits 1 until clean
  node <skill>/scripts/screenshot.js may-claims    -> open decks/may-claims/shots/sheet.png and look
