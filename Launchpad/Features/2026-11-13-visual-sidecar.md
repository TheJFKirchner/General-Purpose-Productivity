# Visual sidecar for the planner

Status: built
Date: 2026-11-13

Lets the planner show quick visual options (charts, palettes, layouts) beside the chat, drawn by a cheap tool-free agent, so design questions are settled in seconds. It covers picks, tweaks and retries, saved versions, code validation of the HTML, locally served ECharts and sealed frames.

Later changed by: [2026-11-13-agents-crew-visualizer](2026-11-13-agents-crew-visualizer.md) (Cartographer is now Visualizer and can draw with other libraries)
Later changed by: [2026-11-14-code-organisation](2026-11-14-code-organisation.md) (its agent file is now app/agents/visualizer/agent.md)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Visual sidecar for the planner (2026-11-13)
- Purpose: settle design questions (chart type, palette, layout, tile look) in seconds during planning, without a plan/orchestrator/builders; the planner never writes or sees chart code
- Sixth agent `.claude/agents/launchpad-visual.md` (display name Cartographer): haiku by default (`--visual-model`), `tools: []`, lean setup with its own short prompt (not the Claude Code prompt); agentlib already supports this (no library change)
  - One-line brief + option label in, one self-contained HTML fragment out, on made-up sample data; ECharts for charts (global `echarts`, never its own script tag), plain HTML/CSS for palettes, layouts, tiles
  - One one-shot call per option, all options in parallel; nothing saved by the engine
- Planner tool `show_visuals(brief, options)` (1-4 labels): returns an acknowledgement at once; rendering runs in the background, the planner's turn is not blocked. Planner prompt: offer "want me to assume, or see some options?" instead of describing visuals in words
- Pick: recorded in the session's `decisions.md`, its file added to the flight log, and passed to the planner once, as one short line prefixed to the user's next message (set, option label, saved path), never HTML; no pick -> nothing said or assumed; clearing a pick already told -> one "pick cleared" line
- Tweak (one option, free text) and retry (failed or bad option) go straight to the visual agent with no planner turn; a tweak sends the previous HTML plus the change; a revised picked option re-informs the planner with the new file
- Every rendered version saved: `.launchpad/<session-id>/visuals/<set>-<option>[-rN].html` (header comment: brief, label, revision, "made-up data", needs ECharts)
- Validation in code: one fragment per option, max 40,000 characters, rejects any outside URL (http(s), ftp, ws, file, protocol-relative), script tags with src, @import, iframe/object/embed/link/base/form/meta refresh, and network calls (fetch, XMLHttpRequest, WebSocket, EventSource, sendBeacon, import()); SVG namespace URLs allowed
- Usage: one visual agent per session (role "visual"), working while any option renders, idle otherwise; an activity entry "render" per option; counted in the session total (everything but the planner)
- ECharts served locally, nothing from the internet at runtime: vendored Apache ECharts 6.1.0 official dist build `app/vendor/echarts.min.js` (1,121,883 bytes) + `app/vendor/ECHARTS-LICENSE` (Apache-2.0), from the npm package `echarts@6.1.0` via its jsDelivr npm mirror; SHA-256 matches jsDelivr's published file list (details: app/vendor/README.md). Served at GET /vendor/echarts.min.js (same access as the page)
- Frames: the page is sent with a Content-Security-Policy (only this app; websocket only on its own port; no outside hosts) that the locked-down srcdoc/blob frames inherit, so visual HTML cannot reach the network
- Considered and deferred: a personal visual library (house styles, past approved visuals) the agent could draw from; deferred to keep the agent tool-free and cheap. Later options: pass a short style note in the brief, or let the planner attach one approved file's HTML as an example
