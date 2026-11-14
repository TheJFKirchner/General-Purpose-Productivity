# Chart.js (vendored, Visualizer)

- Used for: one of the Visualizer's always-available charting libraries (show_visuals library "Chart.js", key `chartjs`). Vendored as `app/vendor/chart.umd.min.js` 4.6.1 (MIT, `app/vendor/CHARTJS-LICENSE`); inlined into the sealed visual frame as the global `Chart`
- Source: `npm pack chart.js@4.6.1`, tarball checked against the registry's `dist.integrity` (hashes in app/vendor/README.md)
- Links: https://www.chartjs.org/docs/latest/ · https://www.chartjs.org/docs/latest/configuration/responsive.html · https://www.npmjs.com/package/chart.js
- Gotchas
  - The UMD build is `dist/chart.umd.min.js` (4.5+; older 4.x shipped only `chart.umd.js`); it registers every chart type, so `new Chart(canvas, cfg)` works with no imports
  - Responsive charts need a parent with a set height plus `maintainAspectRatio: false`, else the canvas grows with the frame
  - No `eval` / `new Function`: runs under the frame CSP (`script-src 'unsafe-inline'` only)
