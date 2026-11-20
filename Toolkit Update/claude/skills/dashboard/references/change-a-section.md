# Change a section

What this does
1. Every section is one file, `Src/Sections/sN_<name>.jsx`. A change is an edit of that file only.
2. When the page draws (and whenever the data or a filter changes), the rows Python worked out are put into the
   copied item's data lists. Everything else in the file (names, colours, labels, axis settings) stays as you wrote it.
3. `npm run check` and `npm run shot` then show whether it works and how it looks.
Find the file: `npm run status` lists each section's id, file, title and item. Run commands in the dashboard folder.

The parts of a section file (a shortened example)
  export const meta = {
    id: 's1_paid_by_lob', title: 'Paid amount by line of business', tab: 'overview', use: 'CT-34', size: 'half',
    tables: ['claims'], x: 'line_of_business', y: ['paid_amount'], agg: 'sum', ignore: ['lob'],
  };                                  <- the numbers: table, group-by column (x), number columns (y), how added up
                                         (also possible: keys: ['product'] more columns to group by, one row per
                                         combination; shape: 'rows' the table's rows as they are, for points)
  export const slots = { label: 'line_of_business', value: ['paid_amount'] };   <- which column feeds each part
  export const names = { paid_amount: 'Paid' };      <- the words readers see for a column (legend, headings)
  export const format = { paid_amount: '$short' };   <- how numbers print (the list below)
  export const note = `- {largest_label|name} is largest, with {largest|compact}.`;   <- text above, live figures
  const basis = 'Paid claims by line of business, Jan to Jun 2026.';                   <- the line under the chart
  const chart = { xAxis: {...}, yAxis: {...}, series: [{ slot: 'value', type: 'bar', ... }] };  <- the copied item
  (a table or hero card has `const html = \`...\`` instead of `chart`)
  The metrics a note may use are listed by `npm run status` ("metrics ...") for each section.

Edit 1: reword
  title: 'Paid claims are highest for Medicare'; names: { line_of_business: 'Line of business', paid_amount: 'Paid' };
  basis: say what is measured and the period. Remove every "Sample values" and caption text the copy brought.

Edit 2: a third line on a line chart
  1. Add the column to `meta.y`:  y: ['paid_amount', 'billed_amount', 'rows'],
  2. and to the part:             value: ['paid_amount', 'billed_amount', 'rows']
  3. Optional, its own look: add one more object to `chart.series`, copied from the one above, with
     `name: 'Claims', yAxisIndex: 1, lineStyle: { type: 'dashed', color: 'var(--orange)' }` and `data: []`, and make
     `yAxis` a list of two axes: `[{ type: 'value', name: 'Dollars' }, { type: 'value', name: 'Claims' }]`.
     With a second axis on the right, make `grid.right` bigger (e.g. `right: 200`) so the line-end names clear
     its numbers. Without step 3 the extra column repeats the last series in the next theme colour.
  4. format: { rows: 'comma' }; names: { rows: 'Claims' }.
  One line per category instead: `by: 'line_of_business'` in `meta`, and `value: '*'` in `slots`.

Formats (in `format`, per column; `'*'` for any column not listed)
  | Name | Prints 1234567.8 as | Use for |
  | --- | --- | --- |
  | `$short` | $1.2M | money in a chart |
  | `$comma` | $1,234,568 | money in whole dollars |
  | `short` | 1.2M | large counts in a chart |
  | `comma` | 1,234,567.8 | counts and plain numbers |
  | `pct` | 12% (for 12) | values already in % (0 to 100) |
  | `.1%` | 12.3% (for 0.123) | fractions |
  | `month` | Jun 26 (for 2026-06) | a month column |
  | `'{value} days'` | 1,234,567.8 days | anything else: a pattern |
  Whole dollars, e.g. a table of paid amounts: format: { paid_amount: '$comma' } -> $7,475,803.

Edit 3: axis name, range, colour
  yAxis: { type: 'value', name: 'Paid ($)', min: 0, max: 8000000 } ; a series colour: itemStyle: { color: 'var(--blue)' }.
  Colours only as theme tokens: var(--blue), var(--navy), var(--orange), var(--muted), var(--chart-muted) ...

If a part shows "Not filled yet"
  The add command left it on sample data: put a column in `slots.<part>` and add it to `meta.y` (a number) or
  `meta.x` (text); `npm run check` warns until it is done.

Check and look
  npm run check   -> no ERROR; warnings about sample words or column words gone
  npm run shot -- s1_paid_by_lob   and   npm run shot -- s1_paid_by_lob lob=Medicare
  (`lob=Medicare`: a filter's name in dashboard.config.json and one of its values; skip it with no filters)
  Open both pictures: the edit is there with and without the filter. Fix any `check` line printed under them.
