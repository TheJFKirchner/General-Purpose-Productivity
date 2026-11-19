# Design library

Reusable slides, charts, report sections, dashboard sections and themes for the analysis toolbox.

## Rules
- One item = one HTML file in its type folder, `<id>-<name>.html`, that renders by itself (ECharts from its CDN is the only outside file).
- Header block at the top: `id`, `type`, `name`, `purpose` (one sentence), `from` (the skill it came from).
- Ids: two capitals, a hyphen, two digits. Slides by group (FR EX LV CH CP BD UN DE BK); CT chart, RS report section, DS dashboard section, TH theme. An id never changes and is never reused (`retired-ids.txt`).
- Sample data inline: 4 to 6 points, made-up round values, no dates. No company names, no real data or wording.
- Colours and fonts only as tokens (`var(--blue)`, `var(--body-font)` ...), so every item takes any theme.
- Report and dashboard sections carry, in the SOURCE block, a generic definition of their shape (never the project's own calculation), with the command that recreates it as the first line.

## Themes
- A theme is an item (`themes/TH-nn-<name>.html`): its JSON block holds the CSS tokens and the chart series order. TH-01 is the default every item carries.
- Add one like any item: the librarian saves it (`save-item.js theme --from TH-01 --name <name>`, then edit the tokens).

## Use
- Read `index.md` (id, type, name, purpose). Open only the item you need; copy the part between `ITEM:START` and `ITEM:END`, or the SOURCE block.
- Slides into a deck: `add-slide.js <deck> --after <id> --pattern <id>`; several at once: `patterns.js <library> <id> ...` (presentation skill scripts).
- See every item, in every theme: open `index.html`.

## Save
- Launch the `design-librarian` agent with the visuals (source files, and the deck, slide, report or section ids). Never by hand.
- After any change: `node build-index.js`. It fails on a bad id or name, a missing purpose, an outside file, a hard-coded colour, and in saved items a date, over 6 points or a word recorded from the source (`denylist.json`, hashed). `original-samples.txt` lists the hand-made samples exempt from the last three.
