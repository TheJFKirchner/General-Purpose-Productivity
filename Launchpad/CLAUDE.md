# CLAUDE.md — Launchpad (COSMO)

Local Windows desktop app: planner chat + request queue over a Python planner/orchestrator/worker loop (Claude Agent SDK).

## Rules
- ALL planning (features, architecture, scope, trade-offs, "how should we…") → grill first (rounds of numbered questions, recommended answer each); never jump to a plan
  - Max 3 questions per round; no new round while the user has open feedback or questions
- Decisions live in docs/decisions.md → read before planning; add new decisions there; newer overrides older
- All agent loops in Python; front end is display + input only
- ALL agent building in this folder uses agentlib (shared library at ../agentlib/, editable install; never call claude_agent_sdk directly outside its engines/) → read ../agentlib/README.md first
  - Agent definitions = standard .claude/agents or .cursor/agents files; library-only settings passed at load time
  - Missing capability → add it to agentlib (engine-neutral where possible), not around it
- Local only: bind 127.0.0.1, access code + origin check, no hosting
- Skills/agent docs: machine-readable bullets, lightweight, detail pushed to reference files

## Current state
- V1 loop built (2026-11-12): planner -> draft plan -> Approve -> orchestrator -> one builder per step -> report.md; Astronaut explorer; question + permission cards; session folder; live per-agent cost
- Fake-engine suite: `python -m pytest` (zero tokens); live smoke run passed 2026-11-13 (tests/live_smoke.py, about $0.08 per full run)
- Live `activity` feed of every tool call (2026-11-13)
- Visual sidecar (2026-11-13): planner's show_visuals -> Cartographer (haiku, no tools) draws ECharts / HTML options beside the chat; pick -> one line to the planner; tweak / retry without the planner; live check passed
- Regular session "Pilot" (2026-11-13): plain Claude Code chat in the launch folder (project setup, Claude Code permissions and modes, no Launchpad guards); live check passed
- Builder permissions (2026-11-13): timed cards (default 180 s, unanswered = denied), outside writes ask instead of being refused, per-session autopilot (approves everything, no exceptions by the user's choice)
- Send-back -> revised draft -> approve again works (draft revisions; reconnect replays a pending draft)
- Planner (2026-11-13): starts on Sonnet, promotes itself once to Opus when app/planner-promotion.md criteria are met (first 2 turns) or by hand; revises drafts with edit_plan instead of rewriting
- Connected folders + settings store + File Explorer with markdown hand-editing (2026-11-13): sessions run in a chosen folder; settings in `<home>/.launchpad/settings.json`, backups in `<home>/.launchpad/backups/`
- Zero-token demo for UI review: `python -m app.launch --fake` (two scratch folders, its own temp store)
- Front end (2026-11-13): React + Vite + TypeScript in frontend/, built to frontend/dist/ and served at `/`; after a front-end change run `npm run build` in frontend/ (running the app needs Python only). The old vanilla page is at `/classic` (reference and fallback, no longer updated)
- Agent display names (2026-11-13): Planner, Explorer, Orchestrator, Builder, Visualizer, Claude Code (were Navigator, Astronaut, Flight Director, Flight Engineer, Cartographer, Pilot; older lines and file names such as astronaut.py / pilot.py keep the old words)
- Agent registry + folder agents (2026-11-13): built-ins + `<folder>/.claude/agents/*.md` (front matter `purpose:` planning | exploring | building | reviewing); the planner sees the registry and may name an agent per plan step, the orchestrator invokes it (exploring / reviewing = read-only, building = Builder guards; missing agent -> Builder, noted in the report); add / draft / remove from the Crew tab; per-user use counts in `<home>/.launchpad/`
- Planner / Claude Code switch on the Plan tab replaces the Free Flight tab (2026-11-13); "Send plan to Claude Code" on a plan draft
- Visualizer (2026-11-13): show_visuals takes an optional library; ECharts (default), Chart.js, D3 bundled in app/vendor/; Plotly / Bokeh served from an installed Python package when found; anything else drawn in ECharts and labelled; palettes, hero cards and layouts are first-class
- Websocket contract: app/server.py header is authoritative

## Where things are
- Read order for a new session: this file → docs/decisions.md → background docs only when their topic comes up

### Current (source of truth)
- docs/decisions.md — all decisions so far, dated; newer overrides older; wins over v1plan.md where they conflict
- frontend/ — the front end: React + Vite + TypeScript ("Orbit" look); read frontend/README.md first (state, hooks, actions, shared components, tokens, icons, commands)
  - src/store/ (Zustand + immer; one reducer for every server event) · src/bridge.ts (websocket) · src/demo/ (in-page demo when the URL has no port / code) · src/views/<Screen>/ · src/components/ · src/theme.css (tokens)
  - dist/ — the build served by app/server.py; rebuild with `npm run build`; tests `npx vitest run`
- prototype/launchpad-orbit.html — the earlier vanilla front end, one file; served at `/classic` and as the fallback when frontend/dist is missing; not updated any more
- Features/ — one spec per feature built in factory mode + README.md (the list)
- .claude/agents/ — the six built-in agent definitions + launchpad-drafter.md (fills the add-agent form) (standard front matter; Launchpad tools added at load time)
  - app/folderagents.py — draft / create / remove for folder agents
  - planner, Astronaut, orchestrator, Cartographer: own prompt only (lean); builder: Claude Code prompt + its file text, still lean (agentlib `engine_prompt`); Pilot: full Claude Code (project setup)
  - launchpad-planner.md (Navigator; file says opus, Launchpad starts it on sonnet and may promote) · launchpad-astronaut.md (Astronaut, haiku) · launchpad-orchestrator.md (Flight Director, sonnet) · launchpad-builder.md (Flight Engineer, sonnet)
  - launchpad-pilot.md (Pilot, sonnet) — regular session; empty body, no tools line: Claude Code's own prompt and tools
  - launchpad-visual.md (Cartographer, haiku) — visual sidecar; `tools: []`, own short prompt
- app/ — Python back end
  - launch.py — entry point: store + launch options → server thread → pywebview window (folder picker); `python -m app.launch` · `--cwd <folder>` (adds it, default for this launch) · `--browser` · `--fake` (demo) · `--question-timeout N` · `--permission-timeout N` · `--autopilot` · `--planner-start M` · `--planner-top M` · `--promotion-window N` · `--promotion-criteria FILE` · `--model M` (pin the planner) · `--pilot-model M` · `--visual-model M` · dev: `--no-window --port 8765 --code dev`
  - server.py — FastAPI: page (frontend/dist, with a CSP the visual frames inherit) + /assets + /classic + /vendor/echarts.min.js + websocket, 127.0.0.1 + access code + origin check; header = websocket contract
  - hub.py — all sessions (LaunchSession = planner chat + plan + run) and regular chats, event broadcast, reconnect snapshot, UI message dispatch, approve / stop / new session / report to planner
  - pilot.py — regular session (Pilot): Claude Code chat, permission / plan / question cards, modes, interrupt
  - planner.py — planner chat + its tools (explore, read_markdown limited to .md in the project, write_plan, edit_plan, show_visuals, promote_planner) + Sonnet -> Opus promotion
  - planner-promotion.md — editable criteria for promoting the planner (shown in the Crew tab)
  - visuals.py — visual sidecar: sets, background renders, validation, tweak / retry, pick -> planner line, saved files
  - vendor/ — echarts.min.js (Apache ECharts 6.1.0, served at /vendor/echarts.min.js) + ECHARTS-LICENSE + README (version, source, hashes)
  - astronaut.py — explorer session (structured links only) → flight log + operations manual
  - run.py — orchestrator loop, builder steps, builder tools, permission checks, shell deny list, capped hand-off, report.md
  - crew.py — loads the agent files + Launchpad tools; display names; crew_list
  - plan.py — plan.md render / validate / parse / status updates / targeted edits (edit_plan)
  - sessionfiles.py — `<project>/.launchpad/<session-id>/` files (plan, flight log, steps, assumptions, operations manual, report, activity.log, decisions.md, visuals/)
  - activity.py — one-line summaries + statuses for the live `activity` feed (every tool call)
  - incoming.py — question / permission / plan queue (runs and chats) with server-side timers
  - meter.py — per-agent tokens, cost, tool calls → agent_usage
  - settings.py — the active settings for this launch (defaults; filled from the store + launch options)
  - store.py — per-user store: connected folders + settings (`<home>/.launchpad/settings.json`, env LAUNCHPAD_HOME)
  - files.py — File Explorer back end: roots, safe paths, list / read, conflict-safe .md saves, agent / plan validation, backups
  - demo.py — fake-engine scripts for `--fake`
  - requirements.txt — fastapi, uvicorn, pywebview, pyyaml, pytest, editable agentlib; install from this folder: `pip install -r app/requirements.txt`
- tests/ — fake-engine pytest suite for the whole loop (zero tokens): `python -m pytest` from this folder
  - live_smoke.py — LIVE (spends tokens, ~7 min), not collected by pytest: `python tests/live_smoke.py [--part planner|run] [--quick]`; scratch project in a temp folder
  - live_visuals.py — LIVE check of the visual sidecar (opus planner turn + haiku renders + one tweak, ~$0.03): `python tests/live_visuals.py [--out <folder>]`
  - live_planner_study.py — LIVE planner cost study, conversations A (short) / B (long), per-turn table + breakdown, `--effort` override: `python tests/live_planner_study.py --conv A|B [--turns N] [--effort low]`
  - live_planner_cost.py — LIVE Opus planner cost, own prompt vs Claude Code preset (~$0.15 each): `python tests/live_planner_cost.py --variant lean|preset`
  - live_pilot.py — LIVE check of the regular session (haiku, a few cents): `python tests/live_pilot.py [--turns 1,5] [--model sonnet]`
- Launchpad.bat (Windows) / Launchpad.command (Mac, `chmod +x` once) — double-click launchers for `python -m app.launch`; keep app code cross-platform (OS-specific bits guarded by sys.platform)
- .claude/launch.json — preview configs: "launchpad-dev" (live, port 8765) · "launchpad-fake" (fake demo, port 8766); code `dev`
- `<connected folder>/.launchpad/` — session folders written at run time (git-ignored by its own .gitignore)
- `<home>/.launchpad/` — per-user settings.json and backups/ of hand-edited files (outside every project)

### Background (older than decisions.md; history and reasoning)
- v1plan.md — original V1 design interview (2026-11-04, older "Mission Control" naming, numbered D-decisions referenced elsewhere)
- cursor-vs-agent-sdk-research.md — answers v1plan.md §9: Claude Agent SDK vs Cursor SDK, 15 questions, risks, recommendations
- claude-cursor-orchestrator-summary.md — short design for one Python orchestrator that picks Claude or Cursor per role; early library sketch that became agentlib
- planpal-extraction.md — what to reuse from Plan Pal (../Planning Chatbot/interviewer_sdk/); reference only, V1 is a fresh build

### Outside this folder
- agentlib: ../agentlib/ (subfolder of the General-Purpose-Productivity repo; Claude engine live, Cursor stub, fake for tests); tests: `python -m pytest` from that folder
