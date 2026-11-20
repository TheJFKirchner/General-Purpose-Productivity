# Picking a visual, and the page's look

## Pick the visual from the claim

| The claim is about | Start from |
| --- | --- |
| One or a few headline figures | A hero card (HC-15 plain figure tiles), or `ANSWER` kpis |
| Size across a few categories | CT-34 plain bars; CT-02 ranked bars when labels are long |
| Change over time | CT-35 plain line, `LAYOUT = "above"` |
| From one total to another, by cause | CT-06 waterfall (its `recipe:` says how to shape the table) |
| Parts of a whole across groups | CT-36 stacked bars (`--by COL` splits a column by group) |
| A relationship between two measures | CT-37 scatter |
| The records to act on | TB-09 plain table, plus `EXPORT` for the full list |

The library's `index/charts.md`, `index/tables.md` and `index/hero-cards.md` list every item with the data it needs.

- One visual per section, proving its claim. Plot what the claim is about.
- At most 6 series; top N beats a crowded chart.
- Plain words in titles, axis names, legends and table headings (`NAMES`). No column names or codes.
- One highlight colour for the one thing the claim is about; context in `var(--chart-muted)`.
- A threshold the claim is judged against: draw it, not in words only.

## The page's look

| To change | Do |
| --- | --- |
| Colours and fonts | `python run.py theme TH-02` (ids in the library's `index/themes.md`). A theme with its own font copies the font's licence file beside the report |
| Space between sections, widths | The settings block at the top of `page.html`: `--section-gap`, `--text-share`, `--visual-share`, `--page-width`, `--chart-height` |
| Where a visual sits | `LAYOUT` in the section file: `side`, `flip`, `above`, `below` |
| One chart's height | `HEIGHT = 420` in its section file |

- Keep every `__TOKEN__` in `page.html`; the build stops if one is missing. Leave its `host-css` and `host-runtime` blocks alone: they are the library's, so copied items draw as they do there.
- No logo or company name.
- No internet where the report is read: put `echarts.min.js` beside `run.py` and rebuild; it is embedded.
