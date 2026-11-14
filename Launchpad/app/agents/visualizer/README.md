# Visualizer (role `visual`)

- What: draws one quick self-contained HTML visual (chart, palette, hero card, layout, tile, type sample) on made-up data per option, so the user can settle a design question beside the planner chat. Output is extracted, size-capped and validated in code; every version is saved under the session's `visuals/`.
- Model: `haiku` (from the file); `--visual-model` overrides it.
- Tools: none (`tools: []`); one one-shot call per option, in parallel, in the background.
- Files:
  - `agent.md`: definition (front-matter name `launchpad-visual`)
  - `visuals.py`: `VisualBoard` (sets, renders, tweak / retry, pick -> one line to the planner), `validate`, `extract_html`
  - `libraries.py`: chart libraries (ECharts default, Chart.js, D3 bundled in `app/vendor/`; Plotly / Bokeh from an installed Python package), `choose_library`, `library_files`, `libraries_note`
- Called by: the Planner's `show_visuals` tool (`ls.visuals.create`); pick / tweak / retry from the page via `app/hub.py`; `app/server.py` serves library files from `libraries.py` (GET /vendor/lib/<key>.js).
