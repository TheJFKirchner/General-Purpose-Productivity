# Features

Features built in this project, in the order they were built.

| # | Feature | Description | Built |
|---|---|---|---|
| 1 | [React port of the front end, then a visual polish pass](2026-11-13-react-port.md) | The Launchpad window now runs a React + Vite + TypeScript front end instead of one hand-written HTML file, with the same screens and behaviour. It also got a tidier, more consistent look on the same Orbit theme: one icon set, bundled fonts, keyboard-friendly dialogs and tabs, and empty and loading states. The old page is still available at `/classic`. | 2026-11-13 |
| 2 | [Plain agent names, agent registry and user-added agents, Crew cards, Planner / Claude Code switch, wider Visualizer](2026-11-13-agents-crew-visualizer.md) | Agents now have plain names, and the Crew tab shows each one as a colour-coded card with a count of how often it has been used. You can add your own agents from the app (with a "Draft for me" helper); the planner can assign plan steps to them. The Free Flight tab became a Planner / Claude Code switch on the chat screen, and the Visualizer can draw with Chart.js, D3, Plotly or Bokeh as well as ECharts, plus palettes and hero cards. | 2026-11-13 |
