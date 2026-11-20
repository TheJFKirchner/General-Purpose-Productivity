# Item shape: what a library item must look like, and how to make a chart fit

Follow this literally. Edit only the item you are working on, and only its header and the part between `<!-- ITEM:START -->` and `<!-- ITEM:END -->` (plus `<style id="item-css">` if needed). To read it, `Read` the file up to the line of `<script id="item-engine">` (find it with Grep); never read the engine. Background and full rules: `AUTHORING.md`.

## 1. A chart item (copy this shape)

`CT-XX` stands for the id the script gave your item; keep that id.

```html
<!-- ITEM
id: CT-XX
type: chart
name: bars-by-group
purpose: Use to compare one measure across a few groups: vertical bars with value labels and a reference line.
from: analysis
data: label (text, one); value (number, one); target (figure, optional)
recipe: target: the overall figure the bars are read against
-->
...
<h2>Heading: what is measured, the period</h2>
<!-- ITEM:START -->
<div class="chart" data-echart>
<script type="application/json">
{
  "xAxis": { "slot": "label", "type": "category", "data": ["Group A", "Group B", "Group C", "Group D"] },
  "yAxis": { "type": "value", "axisLabel": { "formatter": "${value}K" } },
  "series": [
    { "slot": "value", "type": "bar", "name": "Value", "label": { "show": true, "position": "top", "formatter": "${c}K" },
      "data": [60, 45, 80, 35],
      "markLine": { "symbol": "none", "data": [{ "slot": "target:yAxis", "yAxis": 55 }] } }
  ]
}
</script>
</div>
<div class="key"><span><i></i>Value</span><span><i class="dash mid"></i>Target</span></div>
<p class="basis">What is measured, the period and the basis. Sample values.</p>
<!-- ITEM:END -->
```

- Fixed text, never change: `<!-- ITEM`, the field names `id: type: name: purpose: from: data: recipe:`, `-->`, `<!-- ITEM:START -->`, `<!-- ITEM:END -->`, `<div class="chart" data-echart>`, `<script type="application/json">`, `<p class="basis">`, `<div class="key">`.
- Written by the script, never change: `id`, `type`, `from` (where it came from: `presentation`, `analysis`, `dashboard`). Change: `purpose` (`node save-item.js purpose <id> "<sentence>."`), `recipe` (`node save-item.js recipe <id> "<line>"`), `data` (edit the line), the JSON, the key, the basis text.
- `name` (and the file name) when the script's guess is wrong (`bars-by-month` for a stacked area): `node save-item.js rename <id> <new-name>`. Never rename the file by hand.
- Allowed in the block: the chart div (only its JSON inside), at most one `<div class="key">` (optional), one `<p class="basis">`. One plain `<div>` around a chart and its key is allowed. Nothing else: no headings, lists, tables or text.
- `recipe:` is optional: leave the line out when the columns go in as they are.

**Table** (block): `<div class="lib-panel">` with `<h2>`, `<p class="cap">`, a `<button type="button" class="lib-mini" data-csv>CSV</button>`, then `<table class="lib-table">`; `<tbody data-rows>`; the first row's cells carry `data-slot="label"`, `data-slot="value"`; the matching `<th>` carry the same `data-slot`. Text cells `class="left"`. Example: `tables/TB-09`.
**Hero card** (block): `<div class="lib-cards" data-rows>` holding cards `<div class="lib-card" data-slot="status@class">` with `<div class="lib-lab" data-slot="label">`, `<div class="lib-big" data-slot="value">`, `<div class="lib-sub" data-slot="note">`. Example: `hero-cards/HC-15`.

## 2. The data note

`data: <name> (<kind>, <count>); <name> (<kind>, <count>)` — kind is `text`, `number` or `figure` (one value, not a column); count is `one`, `one or more`, `optional` or `any`. Names: lowercase, hyphens, no spaces.

| Chart | Data note | Slots in the JSON |
| --- | --- | --- |
| One category, one value | `label (text, one); value (number, one)` | category axis `"slot": "label"`; the series `"slot": "value"` |
| One label, several values (lines, grouped bars) | `label (text, one); value (number, one or more)` | the axis `label`; each sample series `"slot": "value"` |
| Points | `x (number, one); y (number, one); name (text, one)` | the scatter series `"slot": "x,y,name"`, data `[[10, 40, "Group A"], ...]` |
| A target line | `...; target (figure, optional)` | the markLine entry `{ "slot": "target:yAxis", "yAxis": 55 }` |
| An optional column | `...; prior (number, optional)` | the prior-year series `"slot": "prior"` (dropped when not given) |
| Slope chart (one line per group, two points) | `label (text, one); value (number, one or more)` | the axis `label` (the two periods); every line `"slot": "value"`: one column per group |
| Stacked bands (stacked area or bars) | `label (text, one); part (number, one or more)` | the axis `label`; every layer `"slot": "part"` (each keeps its `stack` and `areaStyle`) |
| Lollipop (stem + dot, largest highlighted) | `label (text, one); value (number, one)` + `recipe: Sort rows largest first: the first dot keeps the highlight colour` | the stem bar `"slot": "value"`, the dot `"slot": "=value"` (a follower: it takes the same column, so `--slot value=v` fills both); the highlight on the dot's first data entry, no separate slot |
| Needs a recipe (waterfall) | `step (text, one); base (number, one); total (number, one); rise (number, optional); fall (number, optional)` | + `recipe: base: 0 on totals, the running total before a rise, after a fall; rise and fall: the step's size, always positive` |

## 3. Changing a chart to fit (do every step, in order)

1. **Sample data.** 4 to 6 points, made-up round values, neutral labels. Before `"data": ["North Region", "South Region", ...]`, `[1234567, 987654, ...]` → after `"data": ["Group A", "Group B", "Group C", "Group D"]`, `[60, 45, 80, 35]`. Months may stay as `Jan` … `Jun`; never years.
2. **Colours and fonts as tokens.** `"color": "#0170BC"` → `"color": "var(--blue)"`; highlight `var(--blue)`, the rest `var(--chart-muted)`, totals `var(--muted)`, good/bad `var(--good)` / `var(--bad)`. `"fontFamily": "Arial"` → delete it (the theme sets fonts). No `rgb()`, no colour names.
3. **Formatters as strings, with a format.** Functions cannot live in JSON. `formatter: v => '$' + (v/1e6).toFixed(1) + 'M'` → `"formatter": "${value:short}"` on an axis, `"${c:short}"` on a label; with commas `"{value:comma}"` / `"{c:comma}"`. Give every label you write a format (`{c:short}`, `{c:comma}`), never a bare `{c}`: real data has long decimals. Also `"{c}%"`, `"{b}: {c:short}"`, `"{a}"` (series name), `"{@[2]}"` (third value of a point). On a point `[value, "name"]`, `{c}` prints the value, not the name. Anything else: drop the formatter (the script writes `{c:short}` for it).
4. **Slots.** Put `"slot"` as the first key of each object a column feeds: the category axis, each series, a markLine entry. Choose the name from what the column is (`label`, `period`, `value`, `actual`, `plan`, `prior`, `target`), not from the project's column name. Every slot in the JSON must be in the data note and the other way round.
5. **Several series.** Same role (several measures, several years) → the same slot on each, count `one or more`. Different roles (actual and plan) → different slots, count `one` or `optional`. An invisible helper series (opacity 0, a waterfall base) gets its own slot and a recipe line.
6. **Per-point styles.** A style on single points stays at that position whatever the data, so keep at most one highlight. A style that means something (totals, estimates, rises and falls) goes in its own series: before one series with `{ "value": 480, "itemStyle": { "color": "var(--muted)" } }` on the totals → after a `total` series coloured `var(--muted)` and a `rise` series, each with its own label formatter (`"+${c}"`).
7. **Axis limits.** Delete `min`, `max`, `interval` copied from the project (`"min": 1200000` → gone). Keep them only on hidden layout axes (`"show": false`).
8. **Project words.** Remove every name, column, product, region, client, year and date: in axis `name`, `title.text`, series `name`, label text, the key and the basis. `"name": "FY2025 Paid Claims"` → `"name": "Value"`. If a word cannot be removed without breaking the chart: STOP and report it.
9. **Key and basis.** Use the ECharts legend, end labels or a key (`<span><i></i>Name</span>`; swatch classes `i`, `i.dash`, `i.mid`, `i.lite`, `i.box`). The basis line says what is measured and how, generically, ending `Sample values.`
10. **Outside the block.** Headings, bullets, commentary, tables, filters, buttons around the chart: drop them (the heading stays the placeholder `<h2>` above the block). Two charts side by side: one JSON with two `grid`s, or keep only the main chart.
11. **6 KB.** The text `node item.js <id>` prints (not the item file) must be under 6 KB. Cut points to 6, panels to 4, delete repeated styles that equal the theme's (font sizes, label colours `var(--ink)`).

## 4. When the check fails (`node build-index.js`)

| Message | Fix |
| --- | --- |
| `no data note ("data: ...")` | Add the `data:` line under `from:` (section 2). |
| `data note: "..." is not "<name> (<text\|number\|figure>, ...)"` | Rewrite that slot exactly as `name (kind, count)`. |
| `data note: slot X named twice` | Rename one of them. |
| `slot X is in the data note but marked nowhere in the block` | Add `"slot": "X"` to the object it feeds, or remove X from the note. |
| `slot X is marked in the block but not in the data note` | Add `X (kind, count)` to the note, or remove the marker. |
| `<tag ...> is not the chart, its key or its basis line` / `text outside the options, key and basis line` | Delete that element or text (step 10). |
| `no chart (div.chart[data-echart]) in the block` | Restore `<div class="chart" data-echart>` round the JSON. |
| `chart JSON does not parse` | Fix the JSON: double quotes, no trailing commas, no functions. |
| `node item.js prints N KB for it; a chart stays under 6 KB` | Step 11. |
| `N points; sample data is 4 to 6 points` | Step 1. |
| `date "..."` | Step 8 (use `Jan`, `Group A`). |
| `"..." comes from the project it was copied from` | Step 8, for that word. |
| `hard-coded colour ...` / `hard-coded font ...` / `font shorthand without a font token` | Step 2. |
| `loads "..." from outside the item` | Remove that `src` / `href` / `url(...)`. |
| `no purpose sentence` | `node save-item.js purpose <id> "<sentence>."` |
| `a recipe without a data note` | Add the data note, or delete the recipe line. |

## 5. Confirm it worked

Run in the library folder, after your last edit and `node build-index.js` passes:

1. `node item.js <id>` — prints the id, `data:` (your note), `html:` with the block inside `<div data-item="<id>">`; no engine; short.
2. Make a tiny CSV in a scratch folder with one column per slot and 3 rows, e.g. `g,v` / `North,10` / `South,20` / `East,15`, then `node item.js fill <id> --data <that file> --slot label=g --slot value=v` (several columns: `--slot value=a,b,c`; one column for two series: `--slot value=v,v`; a figure: `--slot target=12`). Good: no `STOP:` and no `NOTE:` line; the printed JSON has `"data":["North","South","East"]` and `[10,20,15]` where the sample was; and it has as many series (`"type":"bar"`, `"type":"line"` ...) as the source chart. Each filled series is named after its column header. `STOP:` names a slot that is missing or wrong; `NOTE: series ... left out` means a series got no column: give it one, or mark it with a slot that has one.
3. `node item.js shot <id> --out <scratch folder>/<id>.png`, then Read the picture. Good: it looks like the source chart (same kind of marks, stacking, colours by role, labels), with sample values.
