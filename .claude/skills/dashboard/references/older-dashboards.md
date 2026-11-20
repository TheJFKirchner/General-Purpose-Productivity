# Work on a dashboard made before library items

How to tell: it has no `Tools/library.mjs` and no `Tools/show.mjs`; its sections draw with `ChartECharts` or
`KpiTile` and its `new-section` only knows `--chart bar|line|table|kpi`.

What still works as it is
- It keeps running on its own copy of the tools: `npm run dev`, `check`, `status`, `shot`, `pipeline`, reports.
- Its sections are edited the same way: their numbers in the `meta` (or the function in `Analysis/<tab>.py`),
  their drawing in the section file.

To add library items to it, copy these from this skill's `starter/` folder into the dashboard, then run
`npm run theme -- TH-01` (or the theme wanted):
  Src/Lib/fill.js, Src/Lib/host-runtime.js, Src/Lib/theme.js
  Src/host.css, Src/styles.css, Src/Components/Item.jsx
  the three `host` / `custom` import lines at the top of Src/App.jsx
  Tools/*.mjs
  Analysis/Shared/shapes.py, Analysis/Shared/registry.py, Analysis/Shared/tables.py, Analysis/check.py
  the `theme` and `show` lines of package.json's "scripts"
Old sections keep working beside the new ones. Then use `add-a-section.md`.
