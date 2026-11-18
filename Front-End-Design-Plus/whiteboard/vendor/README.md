# Vendored libraries

Local, minified, pinned copies so the whiteboard works offline. Each file is the unmodified
build from the library's npm package (fetched through the jsDelivr npm mirror), except that
the trailing `sourceMappingURL` comment was removed so the browser makes no extra requests.
The server serves this folder at `/vendor/`.

| File | npm package | Version | Licence | Global (`lib`) |
|---|---|---|---|---|
| `echarts.min.js` | echarts (`dist/echarts.min.js`) | 6.1.0 | Apache-2.0 | `echarts` |
| `plotly.min.js` | plotly.js-dist-min | 4.3.0 | MIT | `Plotly` |
| `chart.umd.min.js` | chart.js (`dist/chart.umd.min.js`) | 4.6.1 | MIT | `Chart` |
| `vega.min.js` | vega (`build/vega.min.js`) | 6.4.0 | BSD-3-Clause | (needed by vega-embed) |
| `vega-lite.min.js` | vega-lite (`build/vega-lite.min.js`) | 6.5.0 | BSD-3-Clause | (needed by vega-embed) |
| `vega-embed.min.js` | vega-embed (`build/vega-embed.min.js`) | 7.3.0 | BSD-3-Clause | `vegaEmbed` |
| `d3.min.js` | d3 (`dist/d3.min.js`) | 7.9.2 | ISC | `d3` |

The `vegalite` library loads the three Vega files in the order above. The `html` library loads nothing.
