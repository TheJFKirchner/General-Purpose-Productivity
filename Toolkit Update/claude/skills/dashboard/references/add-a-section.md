# Add a chart, table or hero card

What this does
1. Copies one design library item (by its id) into a new file, `Src/Sections/sN_<name>.jsx`, and adds that file
   to the tab's list in `Src/Sections/index.js`.
2. Writes into the file's `meta` which table and columns the numbers come from; Python works them out on the
   filtered table every time the page or a filter changes. No Python to write.
3. Fills the copy with the real numbers once, writes a title and a note, and prints what to reword.
Run every command in the dashboard folder.

Filters and sections
  A filter narrows every section whose table has its column, except a section that compares that column's values
  (bars per line of business): new-section writes `ignore: ['lob']` into that section's meta, so it keeps all
  its bars. A section split `--by` the filter's column still follows it (it shows the chosen group). If check
  warns "filter ... narrows no section", every section ignores it: delete the name from one section's `ignore`
  if it should follow, or delete the filter.

Step 1: find the item
  The library: the project map's `Design library:` line; else `design-library` beside `.claude`; else
  `Toolkit Update/design-library`. Read the index files there that the request needs: `index/charts.md`,
  `index/tables.md`, `index/hero-cards.md`. Pick by the claim the section makes; note the id (CT-34, TB-09, HC-15).

Step 2: see what the item takes
  npm run show -- CT-35
  -> its parts (each item has its own), the columns of your tables that fit each part, and a command to copy.
     A part marked "worked out by new-section" is computed for you; a part marked "WORK OUT FIRST" needs a
     column that already holds that rule (or numbers written by hand, below); the copy command leaves it out.

Step 3: add it. The commonest request, a line by month with one line per group:
  npm run new-section -- paid_by_month --use CT-35 --page overview --tables claims --slot label=service_date --slot value=paid_amount --by line_of_business --month

  | Part | Where it comes from |
  | --- | --- |
  | `paid_by_month` | a short name you choose; the file becomes `s<next number>_paid_by_month.jsx` |
  | `--use CT-35` | the id from the library's index (step 1) |
  | `--page overview` | a tab id from `npm run status`; the first section of a new dashboard makes the tab |
  | `--tables claims` | a table from `npm run status` |
  | `label`, `value` | the item's part names, exactly as `show` prints them |
  | `service_date`, `paid_amount` | columns of that table that `show` lists as fitting; `rows` counts rows |
  | `--by line_of_business` | one line per value of this column |
  | `--month` | group the date in the text part (`label`) by month |
  Another: bars per group, two measures:
  npm run new-section -- paid_by_lob --use CT-34 --page overview --tables claims --slot label=line_of_business --slot value=paid_amount,billed_amount
  -> a "numbers:" line saying what it worked out, then "Reword in that file:" with the title, the note, the
     column names readers will see and the sample text left in the copy. Reword them all.

When the data needs shaping first
  | Option | Use it when |
  | --- | --- |
  | `--agg mean` or `--agg count` | an average or a count instead of a sum |
  | `--by line_of_business` | one line, bar or column per value of a column |
  | `--month` | the date column in the text part should be grouped by month (a daily date is, without asking) |
  | `--top 10` | only the 10 largest groups |
  | `--share` | the item has a `share` part: each group's % of all rows |
  | `--compare service_date=2026-04,2026-05` | two periods or values: a bridge (CT-06), A/B/change tiles (HC-15), A and B bars |
  | `--size half` | half width, beside another half |
  Worked out for you when you give the plain columns: a waterfall (CT-06, CT-29: `--slot step=<groups> --slot
  total=<amount>`), a pareto's running share (CT-24: give `value`), a dumbbell's low and gap (CT-08: give `start`
  and `end`), a running total (CT-22: give `variance`), parts as % of each period (CT-19: give `part` with `--by`).

If a part is missing
  - A required part not given, or its column not in the table: the section is still made; that part shows the item's
    sample data under a "Not filled yet" line, and a `MANUAL:` line says what to type.
  - An optional part not given: left out, nothing said.
  - A part the item does not have: ignored, with a note.

Acting on a MANUAL line
  MANUAL: target not filled - edit Src/Sections/s3_paid_vs_target.jsx: no column was given for it. Type: in slots,
  change target: null to target: '<a number column of claims>'; in meta, change y: ['paid_amount'] to
  y: ['paid_amount', '<a number column of claims>'] (add to the list, keep what is there); in format, add
  '<that column>': '$short' (money) or 'comma' (counts).
  Before:  export const slots = { label: 'line_of_business', value: 'paid_amount', target: null };
           export const format = { paid_amount: '$short' };
           tables: ['claims'], x: 'line_of_business', y: ['paid_amount'], agg: 'sum',
  After:   export const slots = { label: 'line_of_business', value: 'paid_amount', target: 'billed_amount' };
           tables: ['claims'], x: 'line_of_business', y: ['paid_amount', 'billed_amount'], agg: 'sum',
           export const format = { paid_amount: '$short', billed_amount: '$short' };
  A part with a rule ("Work it out first: high minus low") needs a column holding that result: add it to the table
  in a Pipeline script (`df["range"] = df["high"] - df["low"]`), then name it as above.

If the numbers need more than the options
  Leave out every `--slot`: the copy is made with a stub function in `Analysis/<tab>.py`; make it return
  `{"data": {"rows": [...]}, "metrics": {}}` with one column per part name.

Step 4: check and look
  npm run check   -> fix every ERROR; warnings name sample words, column words, MANUAL parts and formats to fix
  npm run shot -- s1_paid_by_month   (the section id: the first word new-section printed)
  -> the path of a picture in Data/.shots/; open it. `check` lines under it name text that is cut off,
     overlapping, hidden, or a label whose format does not suit its numbers.
  Then reword the lines it printed: titles, `names`, the `basis` line (see `change-a-section.md`).
