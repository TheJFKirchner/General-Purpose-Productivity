# Writing an item by hand

For anyone filling the library by hand, and for the scripts that copy items into projects ("Adding an item to a project" is their contract). Start every item with `node save-item.js new <type> --name <name>`; it writes a valid shell with the next free id. Then fill it, and run `node build-index.js` until it passes.

## Every item

- Edit only: the `purpose:` line (one sentence, true of the preview), the `data:` and `recipe:` lines (below), the markup between `ITEM:START` and `ITEM:END`, `<style id="item-css">` and, if needed, `<script id="item-js">`. Never edit `tokens`, `kit-css`, `chart-css`, `deck-css` or `item-engine`: `build-index.js` rewrites them.
- Charts, tables and hero cards: a data note and slot markers; slides: spot markers. See "Adding an item to a project".
- Colours, fonts, corners only through tokens. Allowed besides: `transparent`, `currentColor`, `font: inherit`. Inline `style` for sizes and positions only (`width: 80%`).
- Data: as little as draws the visual properly, made-up round values, neutral labels (`Group A`, `Measure B`, `Jan`). Label it as sample (`<p class="lib-source">Sample values</p>`).
- Name: short, says the visual (`plan-tiles`, `ledger-meters`), never a subject. Unique in the library.
- Item scripts reach the engine only through its public hook: `ItemEngine.chart(el)` (the ECharts instance of the chart holding `el`) and `ItemEngine.redraw()`; on `window`, `item:replay` fires after every replay (load, Replay, the index) and `item:draw` after every redraw (theme, resize: put any chosen state back). Never use `box._chart`, the Replay button or index messages directly.
- Reduced motion means no autoplay; an explicit action always plays. Gate autoplay on `ItemEngine.motion()` (never on the media query yourself); an item's own Play control calls `ItemEngine.play()`, its step or switch controls call `ItemEngine.force()` before moving.
- Hover is automatic on every chart (a one-line tooltip in the chart's own label format, a light mark emphasis) and table cell (a native tooltip); turn it off with `data-hover="off"` on the chart or `"tooltip": {"show": false}`, or give `"tooltip": {"formatter": ...}` where the default would read wrong.
- `from:` says where the item came from: a skill (`presentation`, `analysis`, `dashboard`), `design-library` for new designs, `james-themes` for kit imports.
- Worked examples to copy: the plain items `charts/CT-34` to `CT-37`, `tables/TB-09`, `hero-cards/HC-15`; and `hero-cards/HC-01`, `tables/TB-01`, `animations/AN-01`, `layout/LY-04` (chart/table flip, CSV).

## By type

| Type | Must contain |
| --- | --- |
| chart (CT) | The block holds only: a `<div class="chart" data-echart><script type="application/json">{ECharts option}</script></div>`, an optional `<div class="key">` and a `<p class="basis">` (a wrapper `div` round a chart and its key is allowed). Colours as `"var(--blue)"` strings; one highlight in `var(--blue)`, context in `var(--chart-muted)` (plain items use the theme's series colours); value labels with units; no `tooltip`, no hex. Basis and key styles are shared (`chart-css`, key swatches `i`, `i.dash`, `i.mid`, `i.lite`, `i.box`); `item-css` only for anything else, tokens only. `node item.js <id>` must print under 6 KB |
| table (TB) | `table.lib-table` inside `.lib-panel` with a finding `h2` and `.cap`; numbers right-aligned (`.left` for text); lead row `tr.on`; total in `tfoot`; a `<button class="lib-mini" data-csv>` (the shared CSV script, which `new` writes, reads the rows as shown) |
| hero card (HC) | `.lib-card` (status top bar: `good`, `bad`, `neutral`; lead card: `lead`) with `.lib-lab`, `.lib-big`, and a delta, tick or meter; several in `.lib-cards` (marked `data-rows`, one card a row); no icons |
| slide | `<section id="<name>" data-component="<id>">`; every chart and piece of visible text in a `data-spot` (below) |
| animation (AN) | Motion only under `html.play` in `item-css` (the engine adds `play` on load and on Replay; without it the final state shows); count-ups as `<span data-tick-up="1240" data-prefix="$" data-suffix="K">$1,240K</span>`; charts draw in automatically. The shell marks the body `data-animate`; never loop |
| any type, with motion | Mark the element (or `<body>`) `data-animate`: count-ups, chart draw-in and `html.play` CSS then run, and the item gets the Replay control like an animation |
| layout (LY) | One page piece or control, working in plain JS (no frameworks), on neutral sample content; after changing a chart's JSON or showing a hidden chart, call `window.itemRedraw()` |

## Adding an item to a project

A project copies an item, never links to it: its block in a wrapper, its data note, its own CSS and script. A script fills the slots with real columns; after that the copy is edited freely.

### The data note

Every chart, table and hero card carries one header line, and a recipe line when the data must be shaped first:

```
data: label (text, one); value (number, one or more); target (figure, optional)
recipe: share: value as a % of the largest value
```

- Slots are separated by `; `, each `<name> (<kind>, <count>)`. Names: lowercase words and hyphens.
- Kind: `text` (a column of labels), `number` (a column of numbers), `figure` (one value, not a column).
- Count: `one`, `one or more`, `optional` (none or one), `any` (none or more).
- The data is one table of rows. A column slot takes one column per count; a figure takes a value given as is, or the first value of a column. Columns may differ in length: trailing empty values are dropped.
- The recipe says, in plain words, how to make columns the item can take: a waterfall's invisible base, a running total, a share, a bar's position on its scale.

### How slots are marked

Charts: a `"slot"` key on the object the data goes into (ECharts ignores it, so the item still draws by itself).

- `"slot": "label"`: the object's `data` becomes that column. On a category axis the values are de-duplicated, in order.
- `"slot": "x,y"` (any number of names): `data` becomes rows of `[x, y]`; a row with an empty cell is left out.
- `"slot": "target:yAxis"`: a figure; sets that property of the object (`yAxis`, `xAxis`, ...). The host supplies one value: a number given as is (`--slot target=85`, or `{ target: [85] }` from Node), or a column name, whose first value is used.
- A slot may mark several objects. Every marked axis takes the slot's first column (panels share one category axis column). A `one or more` slot's columns fill its marked series in order; more columns repeat the last one, without its fixed colours (the theme's series order colours them); marked series left over are removed.
- Filling keeps each sample point's own style by position (a highlight, an estimate's dashes) but drops its label text; names each series after its column; drops the sample's fixed `min`, `max` and `interval` on shown value axes. An optional slot given nothing: its series or data entries go.
- Style that means something (a total, a rise, a fall) goes in a series of its own, not on single points, so it survives any number of rows: the waterfalls CT-06 and CT-29 have `total`, `rise`, `fall` and `key` series, each with its own colour and signed label.
- Number formats: a formatter string may use `{value:short}` or `{c:short}` (7M, 1.2K) and `{value:comma}` or `{c:comma}` (7,000,000); `host-runtime.js` applies them, tooltips included. Mapping the host's own format names onto these (a `$short` column format becomes `"${value:short}"` on the axis and `"${c:short}"` on labels) is the host skill's job.

Tables and hero cards: attributes.

- `data-rows` on the element whose child repeats once per row: the child marked `data-template`, else the first. Copies drop the lead-row class `on` (choose the lead row by hand).
- `data-slot="name"`: the element's text. Inside `thead` it takes the column's name.
- `data-slot="name@prop"`: `@class` sets a state class (`good`, `bad`, `neutral`, `over`, `under`, `up`, `down`, `dn`); `@aria-label` and `@title` set that attribute; anything else is an inline style, a bare number in % (`share@width`). Several on one element: `data-slot="share@width status@class"`.
- A `one or more` slot's cells (`th` and `td`) repeat once per column; a sample row may show several, the copy keeps the first. A cell or header whose slot gets no column leaves the table; a figure outside the rows that gets nothing is emptied.
- HTML slots receive text: format numbers first (`$62K`, `▲ +6.00`).
- An item that builds itself from records (TB-02) keeps them in a `<script type="application/json">` marked like a chart.

### Slides

Each slide marks its parts with `data-spot`: `kicker`, `headline`, `chart`, `bullets` (a list, one item a line), `text` (a sentence or label), `figure` (a big number), `table`, `footnote`. Repeats are numbered in page order (`chart-2`, `text-3`). Every chart and every piece of visible text sits in a spot. Commentary goes in the `bullets` and `text` spots. To put a chart, table or hero card in a chart spot, replace that element with the item's wrapper and keep the `data-spot` on it (`node item.js swap`); the deck then needs the host files below.

### The item script

Run in the library folder.

- `node item.js <id> [<id> ...]` prints, for each: id, name and type; `data:`, `recipe:`, `spots:` (slides); `css:` (its own CSS, every selector prefixed `[data-item="<id>"]`); `js:` (its own script); `html:` (the block inside `<div data-item="<id>">`). Never the engine. Under 6 KB for every chart.
- `--json`: an array, one object per id: `{ id, type, name, purpose, data: [{ name, kind, count }], dataLine, recipe, css, js, html }`, plus `spots` for a slide.
- `node item.js fill <id> --data <rows.json|rows.csv> --slot label=region --slot value=paid,allowed`: the block with the sample data replaced. `--block <file>` fills a block already in a project (a refill after the data changes). Stops when a slot's count is not met. `--json`: the copy object with the filled `html`.
- `node item.js swap <slide id> <item id> [--spot chart-2]`: the slide with the item in that spot, plus the item's CSS and its basis line (for the footnote).
- `node item.js theme <TH id> [--json] [--fonts]`: the theme's tokens as `<style id="tokens">:root { ... }</style>`; `--json` gives `{ id, name, css, series, hasFonts, licence, fonts }`; `--fonts` adds its embedded font (about 90 KB), which travels with its licence file.
- From Node: `require('<library>/item.js')` gives `copyOf(get(id))`, `fill(html, rows, map)`, `check(note, map)`, `swap(slideHtml, copy, spot)`, `parseNote(line)`. `map` is `{ slot: [column, ...] }`; rows are objects keyed by column.

### What the host page provides

A copied block draws as it does in the library when the page carries, once:

1. ECharts from `https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js`, before the runtime.
2. The theme's tokens on `:root` (`node item.js theme <id>`), `--series` included.
3. `host.css`, copied verbatim (`build-index.js` writes it): the wrapper, a chart height (`--chart-height`, 340px; in a box with a set height the chart fills it), the basis line and key, and the kit classes tables and hero cards use.
4. Each item's own `css` once, and its `js` after its block. Keep the wrapper `<div data-item="<id>">`: the CSS is scoped to it. An item script that uses element ids (TB-02's pickers) works once per page.
5. `host-runtime.js`, copied verbatim, after the blocks. It resolves `var(--x)` strings in chart JSON, registers the theme (series colours, axes, fonts), adds a default grid and the one-line hover tooltip, applies the number formats above, wraps line end labels to the room `grid.right` leaves and pushes close ones apart, gives table cells a native tooltip, draws every `.chart[data-echart]` on load and resizes them with the window. `ItemHost.draw()` redraws after a theme or data change; `ItemHost.prepare(option, box)` returns a ready option for a page that draws its own charts (with `ItemHost.theme()` for `echarts.registerTheme`). Item scripts keep their `ItemEngine` hook; nothing moves on a host page.

The library's own engine is built from the same `host-runtime.js`, plus fit, motion, Replay, theme fonts and the index's messages. Edit `host-runtime.js` itself; never `host.css`.

## Kit classes (in every table, hero card, animation and layout item)

| For | Classes |
| --- | --- |
| Labels, text | `.lib-lab` (small caps label), `.lib-big` (the number), `.lib-sub`, `.lib-said`, `.lib-foot`, `.lib-good`, `.lib-bad` |
| Cards | `.lib-cards` (row), `.lib-card` + `good` / `bad` / `neutral` / `lead` |
| Deltas | `.lib-delta.good` / `.bad` / `.neutral` with `&#9650;` or `&#9660;` |
| Meters | `.lib-meter > b` (width in %; `b.bad`, `b.good`); `.lib-tick > .a` (actual, `.a.bad`) `.p` (plan tick) `.l` (last year) |
| Tables | `.lib-table`, `.left`, `tr.on`, `tfoot`, `.lib-bar` (title row with a button) |
| Controls | `.lib-btn.pri` / `.sec` (on white), `.lib-btn.solid` / `.line` (on the band), `.lib-mini`, `.lib-seg` (buttons with `aria-pressed`), `.lib-chips` / `.lib-chip`, `.lib-gate` (range sliders) |
| Page pieces | `.lib-panel`, `.lib-panelhead`, `.cap`, `.lib-pair`, `.lib-note`, `.lib-source`, `.lib-band`, `.lib-rail`, `.lib-btnrow` |

## Tokens

`--blue` primary and highlight · `--navy` headings, strong text, borders · `--green` `--teal` `--orange` accents (orange also focus) · `--ink` body text · `--muted` notes, axes · `--rule` lines · `--wash` page ground · `--paper` cards · `--chart-muted` context marks, last year · `--chart-grid` gridlines · `--good` `--bad` `--neutral` status · `--track` meter and tick background · `--tint` lead card, lead row, hover · `--shadow` hover shadow (`3px 3px 0 var(--shadow)`, nothing moves) · `--band` `--on-band` header band and its text · `--menu` `--on-menu` side menu · `--radius` corners · `--heading-font` `--body-font` `--heading-weight` · `--series` chart colour order (token names).

## A theme's embedded font

- Only in a theme item, as `<style id="theme-fonts">` holding `@font-face` rules whose `src` is `url(data:font/woff2;base64,...) format("woff2")`, one per weight in use (usually 400, 600, 700; Latin subset). Expect about 22 KB per weight, about 30 KB as base64: roughly 90 KB added to the theme item. The index and the engine carry it to every item; nothing else is copied.
- Only a font whose licence allows embedding (SIL Open Font License or similar). Start the block with a comment giving the copyright line, the licence name and `themes/<font>-OFL.txt`, and put that full licence text file in `themes/` (the OFL requires it with every copy). `build-index.js` fails a font block without its licence file, with anything but woff2 `data:` faces, or outside a theme item.

## james-themes mapping (TH-04 to TH-07)

| james-themes | Library | | james-themes | Library |
| --- | --- | --- | --- | --- |
| `--primary` | `--blue` | | `--track` | `--track` |
| `--ink` | `--navy` and `--ink` | | `--leadTint` (and `--rowTint`) | `--tint` |
| `--muted` | `--muted` | | `--shadow` | `--shadow` |
| `--hair` | `--rule` | | `--band` | `--band` (text on it: `--on-band`, white) |
| `--page` | `--wash` (cards stay `--paper`, white) | | `--menuBg`, `--menuFg` | `--menu`, `--on-menu` |
| `--prior` | `--neutral`; chart `dim` is `--chart-muted` | | `--tick` | `--orange` |
| chart `grid` | `--chart-grid` | | `--cat1` to `--cat5` | series `--navy --blue --teal --green --orange` (`--teal` = cat3, `--green` = cat4; the dark themes' cat5 becomes their tick colour) |
| `--good`, `--bad` (groundwork) | `--good`, `--bad` | | `--r-card` 14px | `--radius` |
| Barlow (embedded, see below) | `--heading-font`, `--body-font` (Barlow first, safe fallbacks) | | not mapped | `--menuSub`, `--menuEdge`, `--actBg/Fg`, `--menuHover`, `--leadTrack`, `--bandSoft`, `--goodMark/--badMark`, chart `ramp` |

TH-05 and TH-07 are made fully dark in the kit's navy and teal families (the kit's "dark" variants only darken the band and menu). In the light kit themes the series use darker shades of the kit cyan, green and amber so every series colour reads at 3:1 or more on cards; the bright amber stays `--orange` for the band tick. Focus ring: `--ink` (`--on-band` on the band).
