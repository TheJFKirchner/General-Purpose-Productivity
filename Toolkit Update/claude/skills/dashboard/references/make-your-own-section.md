# Make a section with no library item to start from

What this does
1. Writes a working blank section, `Src/Sections/sN_<name>.jsx`, and adds it to the tab's list in
   `Src/Sections/index.js`: a plain bar chart (`--own chart`) or a plain table (`--own html`).
2. Wires it to a table: a text column with few values (never an id) as the groups, the first number column as the
   value, unless you name them.
3. From then on it is changed like any section: edit the file.
Use it only when nothing in the library's `index/charts.md`, `index/tables.md`, `index/hero-cards.md` fits.
Run commands in the dashboard folder.

Step 1: see the tables and tabs
  npm run status
  -> each tab and its sections; each table with its columns, their type and a sample

Step 2: make it
  npm run new-section -- claims_per_lob --own chart --page overview --tables claims --slot label=line_of_business --slot value=rows

  | Part | Where it comes from |
  | --- | --- |
  | `claims_per_lob` | a short name you choose |
  | `--own chart` | `chart` for an ECharts chart, `html` for a table or cards |
  | `--page overview`, `--tables claims` | a tab and a table from `npm run status` |
  | `label`, `value` | the blank's two parts: label (text) and value (number, one or more) |
  | `line_of_business`, `rows` | columns of that table; `rows` counts rows; leave both `--slot`s out to let it choose |
  The options of `add-a-section.md` work here too (`--agg`, `--by`, `--month`, `--top`, `--size half` ...).

If a part is missing
  - A required part not given, or its column not in the table: made anyway on sample data, with a MANUAL line.
  - An optional part not given: left out, nothing said.
  - A part it does not have: ignored, with a note.

Step 3: make it your own
  Chart: edit `const chart` with ECharts options (echarts.apache.org/en/option.html). Mark where a column goes with
  `slot: 'label'` (a category axis) or `slot: 'value'` (a series); everything else is yours. Colours only as theme
  tokens: 'var(--blue)', 'var(--orange)', 'var(--muted)'.
  Table or cards: edit `const html`. The element marked `data-rows` repeats its first child once per row;
  `data-slot="label"` puts that part's value in; `data-slot="value@width"` sets a width in %. Use the library's
  classes: lib-panel, lib-table, lib-cards, lib-card, lib-lab, lib-big (the library's `AUTHORING.md` lists them).
  Words: `meta.title`, `names`, `format`, `note`, `basis`, as in `change-a-section.md`.

  Worked example: horizontal bars with a dashed line at their average. The blank's chart is
    xAxis: { slot: "label", type: "category", data: [...] },
    yAxis: { type: "value" },
    series: [{ slot: "value", type: "bar", barMaxWidth: 64, label: { show: true, position: "top" }, data: [...] }],
  Change it to (swap the axes, labels at the bar ends, one markLine worked out from the data):
    xAxis: { type: "value" },
    yAxis: { slot: "label", type: "category", inverse: true, data: [] },
    series: [{ slot: "value", type: "bar", barMaxWidth: 40, label: { show: true, position: "right" }, data: [],
      markLine: { symbol: "none", lineStyle: { type: "dashed", color: "var(--muted)" },
        label: { position: "start", formatter: "Average {c:fmt}" }, data: [{ type: "average" }] } }],
  `inverse: true` puts the first row at the top (and `position: "start"` its label there); `{ type: "average" }` is the average of the bars drawn, worked out
  again at every filter change, never typed in; `{c:fmt}` prints it in the column's `format`. Other built-in lines:
  `{ type: "max" }`, `{ type: "min" }`, `{ type: "median" }`. Rows come largest first; `sort: 'label'` in `meta` for A to Z.

Step 4: check and look
  npm run check   -> no ERROR; reword what the warnings name
  npm run shot -- s3_claims_per_lob   (the id: the first word new-section printed)
  -> open the picture; fix any `check` line printed under it
  If the user likes it, save it to the library: `save-a-visual-to-the-library.md`.
