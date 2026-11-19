---
name: front-end-design-plus
description: Opens a local whiteboard page where the user designs charts and tables for a deliverable with an agent that sees only column names and a few sample rows, then merges the saved designs back into the deliverable.
disable-model-invocation: true
---

# Front-end design plus

A local page where the user asks an agent for several ID'd visuals (G1, G2, ...), iterates on the ones they like, and saves some. Every card is drawn on the full real data; the agent never sees it, and neither should you.

## Steps

| # | Do | Reference |
|---|---|---|
| 1 | Identify the visual being worked on (new, or an existing one to tweak) and the table behind it. | |
| 2 | Pick the library (rules below). If it is not supported, do not launch: tell the user why and stop. | [launch.md](references/launch.md) |
| 3 | Write the whole table behind the visual (real rows, every column the user might chart, not only those the current visual uses) to one data file. If the visual already exists, always rewrite it faithfully (same type, series, colours, labels; not improved) as a `render(el, rows, lib)` body in one file; if that cannot be done faithfully, tell the user before launching. Optionally a few lines of style note (colours, font, light or dark). | [launch.md](references/launch.md) |
| 4 | Launch the whiteboard in the background (with `--existing` whenever the visual exists; it opens pinned as "Current visual", G1) and tell the user it is open. Do not read the data into the conversation. | [launch.md](references/launch.md) |
| 5 | When the process exits (last line `RESULT: <path>`), read `result.json` and the saved recipe files, tell the user which IDs were saved, and merge them into the deliverable or replace the existing visual, as the user directs. Then tell the user the saved `<id>.json` files in the output folder are the only record of the session, and give its path. | [merge.md](references/merge.md) |

## Picking the library

1. Tweaking an existing visual: that visual's library.
2. Otherwise: what the deliverable already uses.
3. Otherwise: ECharts.

| Library | `--library` | Agent's notes |
|---|---|---|
| ECharts (default) | `echarts` | [echarts.md](references/echarts.md) |
| Plotly (JavaScript) | `plotly` | [plotly.md](references/plotly.md) |
| Chart.js | `chartjs` | [chartjs.md](references/chartjs.md) |
| Vega-Lite | `vegalite` | [vegalite.md](references/vegalite.md) |
| D3 | `d3` | [d3.md](references/d3.md) |
| Plain HTML / SVG | `html` | [html.md](references/html.md) (tables, in every session) |

## Rules

- Keep files few: one data file, one output folder (plus the existing-visual file when there is one).
- Once written, never read the data file back; the recipe files hold no data and are safe to read.
- Merge saved recipes as they are, in the same library. Never translate a design into another library.
- Every launch is a fresh board in a new, empty output folder; nothing resumes. To continue from a saved visual, pass its `<id>.json` as `--existing`.
