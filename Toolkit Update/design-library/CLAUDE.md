# Design library

Reusable slides, charts, tables, hero cards, animations, layout pieces and themes for the analysis toolbox. In its repo this folder (`Toolkit Update/design-library/`) is the only copy: edit it here. Installed, it sits beside the `.claude` folder.

## Rules
- One item = one HTML file in its type folder, `<id>-<name>.html`, that renders by itself (ECharts from its CDN is the only outside file).
- Header block at the top: `id`, `type`, `name`, `purpose` (one sentence), `from` (the skill or kit it came from); charts, tables and hero cards add `data` (the data note) and, when the data must be shaped first, `recipe`.
- Ids: two capitals, a hyphen, two digits; never changed, never reused (`retired-ids.txt`). Slides by group (FR EX LV CH CP BD UN DE BK); CT chart, TB table, HC hero card, AN animation, LY layout, TH theme.
- Colours and fonts only as tokens (`var(--blue)`, `var(--good)`, `var(--body-font)` ...), so every item takes any theme. No company names, except the imported themes TH-04 to TH-07, named by the owner.
- Charts, tables and hero cards mark where data goes (slots); a chart's block is only its options, key and basis line; slides mark their chart and text spots. Wording and markers: `AUTHORING.md`, "Adding an item to a project".
- Saved items (by the librarian): sample data of 4 to 6 points, made-up round values, no dates, no real names or wording.
- Hand-made items (`original-samples.txt`): as little data as draws the visual properly, made-up round values, no real names.
- A saved report or dashboard section becomes the chart, table or hero card it showed, with its data note and slots; never the project's calculation, and no recreate commands.

## Themes
- A theme is an item (`themes/TH-nn-<name>.html`) whose JSON block holds every token and the chart series order. TH-01 is the default every item carries.
- A theme may embed its font (TH-04 to TH-07 carry Barlow, licence in `themes/barlow-OFL.txt`); copying a theme into a template means copying its `theme-fonts` block and that licence file with its tokens.
- Add one: `node save-item.js theme --from TH-01 --name <name>`, then edit its tokens. Token list and the james-themes mapping: `AUTHORING.md`.

## Use
- Read `index.md` (id, type, name, purpose and, for charts, tables and hero cards, the data each needs), or one type only: `index/charts.md`, `index/tables.md` ...
- Into a project: `node item.js <id>` prints the item's block, data note, recipe and own CSS (never the engine); `node item.js fill <id> --data <file> --slot <name>=<column>` puts real columns in; `node item.js theme <TH id>` prints a theme's tokens; `node item.js shot <id>` takes a picture of it. The page carries `host.css` and `host-runtime.js` once, and `host-motion.js` when it has an animation. All in `AUTHORING.md`.
- Each skill adds by id, then you edit the file: analysis `python run.py add-section NAME --use <id> --source SRC --slot ...`; presentation `deck.js add <deck> <id> [<chart id>]`; dashboard `npm run new-section -- NAME --use <id> ...`. A chart into a slide's chart spot: `node item.js swap <slide id> <chart id>`.
- See every item in every theme: open `index.html` (theme and type dropdowns; click an item for a popup with previous and next).

## Save
- A visual the user liked: launch the `design-librarian` agent with the files. Never by hand.
- The exact shape of an item, how to make a copied chart fit it, and what each check failure means: `ITEM-SHAPE.md`.
- An item written by hand: `node save-item.js new <chart|table|hero-card|animation|layout|slide> --name <name>`, then fill it as `AUTHORING.md` says.
- After any change: `node build-index.js`. It fails on a bad id or name, a missing purpose, an outside file, a hard-coded colour or font; a chart, table or hero card without a data note whose slots are all marked; a chart block holding more than its options, key and basis line, or printing over 6 KB; a slide without its spots; and in saved items a date, over 6 points or a word recorded from the source (`denylist.json`, hashed).
- Files the build writes, never edited: `index.md`, `index/`, `index.html`, `host.css`. `host-runtime.js` and `host-motion.js` are edited by hand; the item engine is built from the first.
- Animations also carry `attaches:` and `fits:` lines; the build checks them.
- Proof that every item can be added: `node sweep-add.js [--target report|deck|dashboard] [--only ids]` builds a scratch report, deck and dashboard in a temp folder and adds every item through each skill's own add command (all slots, optional slots left out, one required slot left out).
- It prints PASS, MANUAL or FAIL per case and a summary, writes `results.txt` in that temp folder, and exits 1 on any FAIL. Run it after changing the library or the skills' add commands.
