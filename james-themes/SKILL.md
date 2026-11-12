---
name: james-themes
description: James's personal dashboard themes and components (Cigna Light/Dark, Evernorth Light/Dark; Barlow, ECharts, React). Use when building or restyling a dashboard, report page or chart for James.
---

# james-themes

Stack: Vite + React + ECharts 5.5.x (pin). Font: Barlow. Read this file, then ONLY the paths the task needs.

## Route

| need | read |
|---|---|
| which theme / what differs | `<theme>/theme.md` (one theme only) |
| page colors for a theme | `<theme>/tokens.css` |
| chart colors for a theme | `<theme>/chart.js` |
| any component | `components/INDEX.md` (grouped by what you need to show) -> open only the named file |
| whole page wiring | `components/layout/BandConsole.jsx` |
| working example: overview page | `components/examples/ConsoleDemo.jsx` |
| working example: trend reporting | `components/examples/TrendDemo.jsx` |
| working example: state tiles, pivot, downloads | `components/examples/ExtrasDemo.jsx` |
| hover, lead swap, linking, motion | `components/behaviors/rules.md` |

- components by type: `layout/` `cards/` `indicators/` `controls/` `tables/` `charts/` `pictorial/` `behaviors/` `foundation/` `examples/`
- themes (folder = `data-theme` value): `cigna-light` (default) | `cigna-dark` | `evernorth-light` | `evernorth-dark`
- restyle to another theme = swap `<theme>/tokens.css` + `<theme>/chart.js`; components unchanged
- do not read theme folders you are not using

## Rules

- colors: only `var(--*)` in CSS, only the theme `chart.js` object in chart options. no raw hex in components or pages
- compose from `components/` only, by the names in `components/INDEX.md`. never hand-style a chart, card, button or table inline
- skeleton fixed: side menu | band (headline + buttons, lead card + trend chart card) | measure cards overlapping band 64px | panels
- one lead measure in band (`SpotlightCard`); others = `PlanTile`
- every chart sits on a white card/panel, never transparent on the band
- color has a job: green = favorable, orange = watch/over plan, primary = series to read, grey dashed = last year
- category palette only for multi-category charts (stacked columns)
- title = the finding; caption = the measure
- choose a chart by the reader's question (INDEX groups), never by axes
- periods not fully reported: `CompletionCap` / `estimateStyle`; never drawn like final values
- every panel: `source` line (data-through date + basis)
- `BodyLens`: never unless the user explicitly asks for it by name
- every table: `csv` button top right; every section with data: `download` ("Download all") top right
- label lines at their ends; no legend for <= 2 series
- numbers `tabular-nums`; labels 11px/600/uppercase/0.1em
- corners: cards, panels, chart cards 14px; buttons, menu items, plan bars 3px or square
- borders 1.5px `--ink`; 8px top bar on measure cards + panels
- hover = shadow `3px 3px 0 var(--shadow)` only; element must not move
- sample data must be labeled as sample

## Banned

- gradients, glass/blur, glow, soft drop shadows
- Recharts, Chart.js
- donut/pie, two-ring or sunburst breakdowns (too many slices to read), smoothed lines, area fills
- emoji; icons inside number cards
- Inter, Space Grotesk, IBM Plex
- different fill colors on side-by-side hero cards
- rainbow colors on single-series charts
- transform/translate on hover

## Not included

- outline map of states (use `TileAtlas`)
- official brand color values (see each `theme.md`)
