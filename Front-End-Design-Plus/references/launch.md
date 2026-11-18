# Preparing and launching the whiteboard

## 1. Check the library first

| Supported (`--library`) | Not supported (do not launch) |
|---|---|
| `echarts`, `plotly`, `chartjs`, `vegalite`, `d3`, `html` | matplotlib, seaborn, ggplot2, Bokeh, Altair, pyecharts, plotly.py figures built in Python, Highcharts, Recharts, AG Charts, Power BI, Excel or PowerPoint charts, anything else |

- A recipe is browser JavaScript for that library. A Python wrapper (plotly.py, Altair, pyecharts) would need translating on merge, so it counts as unsupported.
- When unsupported, tell the user in two lines: the deliverable uses X; the whiteboard draws in the browser with one of the six above and does not translate designs. They can choose to switch that visual to a supported library and invoke the skill again.
- The launcher also refuses an unknown `--library` with a message and exit code 2.

## 2. Write the files (one session folder in the system temp folder)

| File | What goes in it |
|---|---|
| `<tmp>/fedp-<short name>/data.csv` | The whole table behind the visual: every column the user might want to chart, not only the ones the current visual uses, and the real rows after the deliverable's own filtering and joins. CSV with a header row, or a JSON array of row objects (`data.json`). Keep the deliverable's column names so recipes merge without renaming. |
| `<tmp>/fedp-<short name>/existing.js` | Always, whenever the visual already exists in the deliverable; only a brand-new visual has none. The existing visual as a `render(el, rows, lib)` body (example below), or a recipe JSON with a `code` field. It opens pinned as "Current visual", card G1, the starting point. |
| `<tmp>/fedp-<short name>/out/` | Output folder. The whiteboard creates it. |

- `<tmp>` is the system temp folder (`%TEMP%` on Windows, `$TMPDIR` or `/tmp` elsewhere).
- Write the data with a short script; do not print the rows into the conversation.
- Style note: pass a few words with `--style`, for example `"navy and grey, Segoe UI, light"`.

Turning an existing visual into a body: replace the library global with `lib`, the container with `el`, and the data loading with `rows`. Nothing else changes.

- Faithful, not improved: G1 must look the same as the visual does today (same chart type, series, colours, labels, sort order, formatting). Do not tidy, restyle or fix it; improvements are what the session is for.
- Keep any aggregation the deliverable does, now done from `rows` inside the body.
- If it cannot be converted faithfully (for example it depends on server-side code, a plugin that is not loaded, or a library other than the session's), tell the user what will differ before launching, and let them decide.

| Before (in the deliverable) | After (`existing.js`) |
|---|---|
| `const chart = echarts.init(document.getElementById('sales'));` | `const chart = lib.init(el);` |
| `fetch('sales.json').then(r => r.json()).then(data => { ... })` | the `...` part, using `rows` in place of `data` |
| `chart.setOption({ ... });` | unchanged, plus `new ResizeObserver(() => chart.resize()).observe(el);` |

## 3. Launch (in the background, from the skill folder)

```
cd <skill folder>
python -m whiteboard --data "<tmp>/fedp-x/data.csv" --library echarts --out "<tmp>/fedp-x/out" --existing "<tmp>/fedp-x/existing.js" [--style "<note>"]
```

- Leave out `--existing` only for a brand-new visual with nothing to start from.

- Run it as a background command; it opens a browser page and keeps running until the user presses Done.
- Tell the user: the whiteboard is open in their browser; ask for several visuals, iterate by ID ("G2 but stacked"), save the ones they like, then press Done.
- It prints `Whiteboard: <address>` first. `--no-open` skips opening the browser (give the user that address); `--port N` picks the port (default: any free port).
- First time on a machine: Python 3.10+ and `agentlib` installed (`pip install -e <repo>/agentlib`, then its one-time sign-in setup).
- Fake engine (zero tokens, no sign-in, scripted replies): add `--fake`, or set `WHITEBOARD_FAKE=1`. Use it for testing only.
- `python -m whiteboard --help` lists every flag.

## 4. When it ends

- It has ended when the launcher process exits. Its last output line is `RESULT: <path to result.json>`; read that file next, then see [merge.md](merge.md).
- `result.json` is written as the user works, so it can exist earlier with `done: false`. Do not act on it before the process exits.
- If the user closes the tab without Done, the server stops by itself after about 90 seconds. `result.json` then has `done: false` but still lists everything saved.

## Resuming

- Launch again with the same `--out` folder and the same `--library`: the board, its IDs and saved marks come back.
- The same folder with a different library is refused (exit code 2); use a new output folder.
- Rewrite the data file first if the deliverable's data has changed; recipes redraw on the new rows.
