# A section file

Each section is one file, `sections/sN_<name>.py`, holding everything for that block. `python run.py list` says which file is which. Change a section by editing its file, then `python run.py report` and `python run.py shot`.

| Part | What |
| --- | --- |
| `DESCRIPTION` | 8 to 10 words, shown by `list` |
| `DATA` | The table (returned by the calculation) that fills the visual |
| `SLOTS` | Which column fills which slot of the visual: `{"label": "region", "value": ["paid", "allowed"]}`. `"*"`: every other column (for a split by group) |
| `NAMES` | Words the reader sees for a column: legend, table headings. `{"paid": "Paid amount"}` |
| `FORMAT` | Number format per column, in labels, tooltips, axes and table cells: `$short` ($4.1M), `.0%`, `,`, `$,.0f`. `"*"`: any column not listed |
| `def <name>(src, params)` | The calculation: reads `src("source")`, returns `question`, `tables`, `metrics`, `notes` |
| `TITLE`, `BULLETS` | The finding as a sentence; up to 3 bullets. Figures are placeholders |
| `LAYOUT` | `side` (text, then the visual beside it), `flip` (visual left), `above`, `below` |
| `HEIGHT` | Optional: this chart's height in pixels |
| `CHART` | A chart's ECharts options, copied from the library. `BASIS`: the line under it; `KEY`: a hand-written legend |
| `HTML` | A table or hero card (or a block holding a chart), copied from the library |
| `CSS`, `SCRIPT` | The item's own styles and script, if it has any |
| `KPIS`, `EXPORT` | Optional: `[("Label", "{metric:$short}", "note")]` figures; `["table"]` saved as CSV beside the report |

## Filling at build time

- In `CHART`, an object with `"slot": "value"` gets its `data` from the columns in `SLOTS["value"]`, one column per marked series, in order. A category axis gets the column's values. `"slot": "x,y"` takes rows of pairs; `"slot": "target:yAxis"` sets one property from a figure: `SLOTS["target"]` is a number (`85`), a column (its first value is used) or one of the section's metric names (`"overall_avg"`).
- More columns than marked series: the last series repeats for each extra column. A series with no column is left out.
- In `HTML`, the element marked `data-rows` repeats its first child once per table row. `data-slot="name"` puts the value in; `name@class` sets a state class (`good`, `bad`, `neutral`); `name@width` a width in % (a bare number). Table headings take `NAMES`.
- Data lists in `CHART` and the sample row in `HTML` are replaced at every build. Change everything else freely: styles, axis names, series order, colours (`"var(--blue)"`, `"var(--orange)"`, `"var(--chart-muted)"`).
- A series keeps a `"name"` you give it; without one it takes `NAMES`.
- Label and axis formats follow `FORMAT`: on adding, `"${c}"` becomes `"${c:short}"` for a `$short` column (the library's own number codes).
- Python, not JSON: `True`, `False`, `None`.

## Words and figures

- Placeholders: `{metric:format}`; another section's `{name.metric}`; a setting `{params.x}`. Formats as in `FORMAT`, plus `abs.0%` (drops the sign). Placeholders also work in `BASIS` and in the text of `HTML`.
- Another figure: add a key to the metrics dict (`m["share"] = ...`) and use `{share}`.
- Thresholds and periods come from `params` (`DEFAULTS` in `sections/_shared.py`), never literals. Empty input returns empty tables and `None` metrics.
- `check:` lines flag a typed number, words left from the library sample, and a `TODO`.

## A visual of your own

`python run.py add-section NAME --own chart` (or `html`) writes a working section to start from. For a chart, write ECharts options (echarts.apache.org/en/option.html) and mark where columns go with `"slot"`. For HTML, use the library's kit classes (`lib-panel`, `lib-cards`, `lib-card`, `lib-lab`, `lib-big`, `lib-table`); its `AUTHORING.md` lists them. `CHART` may also be a function of the tables returning options, when slots cannot express it.

Picking a visual, themes and spacing: `charts.md`. Settings, sources, reruns and commands: `build.md`.
