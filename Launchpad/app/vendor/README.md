# Vendored files (served locally; nothing loads from the internet at runtime)

The Visualizer's always-available charting libraries. The page fetches one per visual set from GET /vendor/lib/<key>.js
and inlines it into the sealed frame (app/server.py, frontend/src/views/Visuals/frames.ts).

| File | What | Version | Source | Size | SHA-256 (base64) |
|---|---|---|---|---|---|
| echarts.min.js | Apache ECharts, official minified dist build (npm package `echarts`); key `echarts`, global `echarts` | 6.1.0 | https://cdn.jsdelivr.net/npm/echarts@6.1.0/dist/echarts.min.js (npm registry package mirror) | 1,121,883 bytes | tmslrrTfhOMxmdwhaUAU0zbSIsvZ3rDlp8FL1qoND9A= |
| ECHARTS-LICENSE | Its licence (Apache-2.0), from the same package | 6.1.0 | https://cdn.jsdelivr.net/npm/echarts@6.1.0/LICENSE | 11,990 bytes | Y0KTg1tDpt0glPo5GCo9mmucpDt/25rDVOgDevKjCTo= |
| chart.umd.min.js | Chart.js, official minified UMD build `dist/chart.umd.min.js` (npm package `chart.js`); key `chartjs`, global `Chart` | 4.6.1 | `npm pack chart.js@4.6.1` (https://registry.npmjs.org/chart.js/-/chart.js-4.6.1.tgz) | 210,082 bytes | hzZMwrKnamaEkp59a4Cxiol3lNs4QAyv8fzxeRxpJdI= |
| CHARTJS-LICENSE | Its licence (MIT), `LICENSE.md` from the same package | 4.6.1 | same tarball | 1,093 bytes | QahKosq6ZF+WahjZwgVrc+bTqB2AvABGvAARomNNTM4= |
| d3.min.js | D3, official minified UMD bundle `dist/d3.min.js` (npm package `d3`); key `d3`, global `d3` | 7.9.2 | `npm pack d3@7.9.2` (https://registry.npmjs.org/d3/-/d3-7.9.2.tgz) | 280,622 bytes | kSERCY6plQOm9JZzYdK73J2/WM+cZ4yOJ+WwLRoH8ME= |
| D3-LICENSE | Its licence (ISC), `LICENSE` from the same package | 7.9.2 | same tarball | 731 bytes | Km0tXzK6C3Vd28HIM/dm4wzb5uvpptTj4kQnch8LY9M= |

- ECharts hashes match jsDelivr's published file list for npm `echarts@6.1.0`
- Chart.js and D3 tarballs checked against the npm registry's `dist.integrity` before unpacking:
  `chart.js@4.6.1` sha512-hJyniucsFmq//EvXYvJ6c6mahPoI3kaxdjVH8awTaJ/fDNWeSqqqArixMJWkWNN6fcYvPU3HneSANFNYtRi61g==,
  `d3@7.9.2` sha512-ZKb/mONPVKzaO5UlcWcwN8bS4ezvQaYu+bsou+XgNABdGC800kwH651ADTbbTxMPHW13UlvbQafdmJQDk1w7Mg==
- Served at GET /vendor/lib/<key>.js (and the older GET /vendor/echarts.min.js) by app/server.py; to upgrade, replace
  the file and its licence and update this table and record the change in a Features/ request file

## Available when installed (not vendored)

| Key | Global | Files served (inside the installed Python package) |
|---|---|---|
| plotly | `Plotly` | `plotly/package_data/plotly.min.js` |
| bokeh | `Bokeh` | `bokeh/server/static/js/bokeh.min.js` + `bokeh-api.min.js` (the plotting API; one script tag each) |

- Looked for in the connected folder's `.venv` (`Lib/site-packages` or `lib/python3*/site-packages`), then in
  Launchpad's own environment (its site-packages and user site-packages); never imported or run as Python
- Checks (app/agents/visualizer/libraries.py `library_files`): path resolved (symlinks, "..") and still inside the package folder, and for
  a `.venv` inside the connected folder too; a plain `.js` file of 1 KB to 20 MB; not HTML; names its library in its
  first 4 KB. Served only with the page's access code
- Not installed -> left out of the set's `libraries`; a set asking for it is drawn in ECharts, styled like it
