# Plotly and Bokeh (when installed, Visualizer)

- Used for: show_visuals libraries "Plotly" / "Bokeh" when the Python package is installed in the connected folder's `.venv` or Launchpad's own environment. Only their bundled JavaScript is served (GET /vendor/lib/plotly.js | bokeh.js with the access code); no Python is imported or run. Not installed -> drawn in ECharts, labelled "styled like Plotly / Bokeh"
- Files: `plotly/package_data/plotly.min.js` (global `Plotly`; about 4.3 MB in plotly 7.0 / plotly.js 4.0) · `bokeh/server/static/js/bokeh.min.js` + `bokeh-api.min.js` (global `Bokeh`, `Bokeh.Plotting`; about 1.5 MB together in bokeh 3.10)
- Links: https://plotly.com/javascript/getting-started/ · https://plotly.com/javascript/configuration-options/ · https://docs.bokeh.org/en/latest/docs/user_guide/advanced/bokehjs.html
- Gotchas
  - Bokeh's plotting API is a second file and both files start with `'use strict'`: they are served joined by `/*lp:next-script*/` and the page gives each its own script tag (concatenating them would drop the second file's strict mode)
  - BokehJS: `Bokeh.Plotting.figure({sizing_mode: "stretch_width", height})`, `p.line({field:"x"}, {field:"y"}, {source})`, `p.vbar({...})`, `Bokeh.Plotting.show(p, el)`; a fixed `width` overflows the panel
  - Plotly: `Plotly.newPlot(el, data, layout, {displaylogo: false, responsive: true})`; geo charts would fetch topojson from a CDN (blocked by the frame CSP)
  - Checked live in headless Chrome (2026-11-13, plotly 7.0.0, bokeh 3.10.0): both draw in the sealed frame (no `unsafe-eval` needed for plain charts), no outside requests
  - Plotly makes each frame's srcdoc about 4.3 MB; fine for 2-4 options, heavy for many sets open at once
