# Writing an item by hand

For anyone filling the library by hand. Start every item with `node save-item.js new <type> --name <name>`; it writes a valid shell with the next free id. Then fill it, and run `node build-index.js` until it passes.

## Every item

- Edit only: the `purpose:` line (one sentence, true of the preview), the markup between `ITEM:START` and `ITEM:END`, `<style id="item-css">` and, if needed, `<script id="item-js">`. Never edit `tokens`, `kit-css`, `deck-css` or `item-engine`: `build-index.js` rewrites them.
- Colours, fonts, corners only through tokens. Allowed besides: `transparent`, `currentColor`, `font: inherit`. Inline `style` for sizes and positions only (`width: 80%`).
- Data: as little as draws the visual properly, made-up round values, neutral labels (`Group A`, `Measure B`, `Jan`). Label it as sample (`<p class="lib-source">Sample values</p>`).
- Name: short, says the visual (`plan-tiles`, `ledger-meters`), never a subject. Unique in the library.
- Item scripts reach the engine only through its public hook: `ItemEngine.chart(el)` (the ECharts instance of the chart holding `el`) and `ItemEngine.redraw()`; on `window`, `item:replay` fires after every replay (load, Replay, the index) and `item:draw` after every redraw (theme, resize: put any chosen state back). Never use `box._chart`, the Replay button or index messages directly.
- Reduced motion means no autoplay; an explicit action always plays. Gate autoplay on `ItemEngine.motion()` (never on the media query yourself); an item's own Play control calls `ItemEngine.play()`, its step or switch controls call `ItemEngine.force()` before moving.
- Hover is automatic on every chart (a one-line tooltip in the chart's own label format, a light mark emphasis) and table cell (a native tooltip); turn it off with `data-hover="off"` on the chart or `"tooltip": {"show": false}`, or give `"tooltip": {"formatter": ...}` where the default would read wrong.
- `from:` says where the item came from: a skill (`presentation`, `analysis`, `dashboard`), `design-library` for new designs, `james-themes` for kit imports.
- Worked examples to copy: `hero-cards/HC-01`, `tables/TB-01`, `animations/AN-01`, `layout/LY-04` (chart/table flip, CSV).

## By type

| Type | Must contain |
| --- | --- |
| chart (CT) | May add `<style id="item-css">` for its own extras (basis lines, a readout), tokens only; the shell has an empty one. One `<div class="chart" data-echart><script type="application/json">{ECharts option}</script></div>`; colours as `"var(--blue)"` strings; one highlight in `var(--blue)`, context in `var(--chart-muted)`; value labels with units; no `tooltip`, no hex |
| table (TB) | `table.lib-table` inside `.lib-panel` with a finding `h2` and `.cap`; numbers right-aligned (`.left` for text); lead row `tr.on`; total in `tfoot`; a `.lib-mini` CSV button that downloads the rows (copy `saveCsv` from TB-01) |
| hero card (HC) | `.lib-card` (status top bar: `good`, `bad`, `neutral`; lead card: `lead`) with `.lib-lab`, `.lib-big`, and a delta, tick or meter; several in `.lib-cards`; no icons |
| animation (AN) | Motion only under `html.play` in `item-css` (the engine adds `play` on load and on Replay; without it the final state shows); count-ups as `<span data-tick-up="1240" data-prefix="$" data-suffix="K">$1,240K</span>`; charts draw in automatically. The shell marks the body `data-animate`; never loop |
| any type, with motion | Mark the element (or `<body>`) `data-animate`: count-ups, chart draw-in and `html.play` CSS then run, and the item gets the Replay control like an animation |
| layout (LY) | One page piece or control, working in plain JS (no frameworks), on neutral sample content; after changing a chart's JSON or showing a hidden chart, call `window.itemRedraw()` |

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
| Barlow (not loaded) | `--heading-font`, `--body-font` (Barlow first, safe fallbacks) | | not mapped | `--menuSub`, `--menuEdge`, `--actBg/Fg`, `--menuHover`, `--leadTrack`, `--bandSoft`, `--goodMark/--badMark`, chart `ramp` |

TH-05 and TH-07 are made fully dark in the kit's navy and teal families (the kit's "dark" variants only darken the band and menu). In the light kit themes the series use darker shades of the kit cyan, green and amber so every series colour reads at 3:1 or more on cards; the bright amber stays `--orange` for the band tick. Focus ring: `--ink` (`--on-band` on the band).
