# CLAUDE.md — Launchpad (COSMO)

Local desktop app (Windows + Mac launchers): planner chat + request queue over a Python planner/orchestrator/worker loop (Claude Agent SDK).

## Rules
- ALL planning (features, architecture, scope, trade-offs, "how should we…") → grill first (rounds of numbered questions, recommended answer each); never jump to a plan
  - Max 3 questions per round; no new round while the user has open feedback or questions
- Each conversation / feature request = its own file `Features/<YYYY-MM-DD>-<slug>.md` (Status, Date, summary, detail) + one row in Features/README.md (#, Request, two-sentence Summary)
  - Before planning: read Features/README.md, open only the request files that bear on the task; newer overrides older
- All agent loops in Python; front end is display + input only
- ALL agent building in this folder uses agentlib (shared library at ../agentlib/, editable install; never call claude_agent_sdk directly outside its engines/) → read ../agentlib/README.md first
  - Agent definitions = standard agent files: built-ins at app/agents/<agent>/agent.md, folder agents at `<folder>/.claude/agents/`; library-only settings passed at load time
  - Missing capability → add it to agentlib (engine-neutral where possible), not around it
- Local only: bind 127.0.0.1, access code + origin check, no hosting
- Skills/agent docs: machine-readable bullets, lightweight, detail pushed to reference files

## Current state
- V1 loop built (2026-11-12): planner -> draft plan -> Approve -> orchestrator -> one builder per step -> report.md; Astronaut explorer; question + permission cards; session folder; live per-agent cost
- Fake-engine suite: `python -m pytest` (zero tokens); live smoke run passed 2026-11-13 (tests/live/live_smoke.py, about $0.08 per full run)
- Live `activity` feed of every tool call (2026-11-13)
- Visual sidecar (2026-11-13): planner's show_visuals -> Cartographer (haiku, no tools) draws ECharts / HTML options beside the chat; pick -> one line to the planner; tweak / retry without the planner; live check passed
- Regular session "Pilot" (2026-11-13): plain Claude Code chat in the launch folder (project setup, Claude Code permissions and modes, no Launchpad guards); live check passed
- Builder permissions (2026-11-13): timed cards (default 180 s, unanswered = denied), outside writes ask instead of being refused, per-session autopilot (approves everything, no exceptions by the user's choice)
- Send-back -> revised draft -> approve again works (draft revisions; reconnect replays a pending draft)
- Planner (2026-11-13): starts on Sonnet, promotes itself once to Opus when app/agents/planner/promotion.md criteria are met (first 2 turns) or by hand; revises drafts with edit_plan instead of rewriting
- Connected folders + settings store + File Explorer with markdown hand-editing (2026-11-13): sessions run in a chosen folder; settings in `<home>/.launchpad/settings.json`, backups in `<home>/.launchpad/backups/`
- Zero-token demo for UI review: `python -m app.launch --fake` (two scratch folders, its own temp store)
- Front end (2026-11-13): React + Vite + TypeScript in frontend/, built to frontend/dist/ and served at `/`; after a front-end change run `npm run build` in frontend/ (running the app needs Python only). The old vanilla page is at `/classic` (reference and fallback, no longer updated)
- Agent display names (2026-11-13, CLI since 2026-11-16): Planner, Explorer, Orchestrator, Builder, Visualizer, CLI (were Navigator, Astronaut, Flight Director, Flight Engineer, Cartographer, Pilot, then "Claude Code" for the CLI; older lines, role ids and Python file names keep the old words: astronaut.py in app/agents/explorer/, pilot.py in app/agents/claude_code/; mapping in app/agents/README.md). The UI never shows a harness brand for the CLI; text about it says "the CLI harness"
- Agent registry + folder agents (2026-11-13): built-ins + `<folder>/.claude/agents/*.md` (front matter `purpose:` planning | exploring | building | reviewing); the planner sees the registry and may name an agent per plan step, the orchestrator invokes it (exploring / reviewing = read-only, building = Builder guards; missing agent -> Builder, noted in the report); add / draft / remove from the Crew tab; per-user use counts in `<home>/.launchpad/`
- Planner / Claude Code switch on the Plan tab replaces the Free Flight tab (2026-11-13); "Send plan to Claude Code" on a plan draft
- Visualizer (2026-11-13): show_visuals takes an optional library; ECharts (default), Chart.js, D3 bundled in app/vendor/ (served at /vendor/lib/{key}.js); Plotly / Bokeh served from an installed Python package when found; anything else drawn in ECharts and labelled; palettes, hero cards and layouts are first-class
- Reorganisation (2026-11-14): built-in agents moved to app/agents/<agent>/ (agent.md + code + README.md; shared crew.py, folder_agents.py); Launchpad/.claude/agents/ removed; live scripts in tests/live/; test files renamed by topic; sample/ deleted; background docs in docs/background/; front end src/shell/ removed (Header in components/); READMEs added (docs/, app/, tests/, app/agents/, frontend/); docs/architecture.md added
- Request records (2026-11-14): the combined decisions file was split into one file per request in Features/, listed in Features/README.md
- Folders and skills (2026-11-16): sessions / Claude Code chats run in the primary folder + folders ticked as additional (Settings; agentlib add_dirs; Builder guard treats them as inside); skills found in those folders (app/skills.py: .claude/skills, else .agents/skills; primary wins a clash); per-agent skill setting in the Crew tab (Planner all, others none; settings agent_skills); planner sees the skills, plan steps may name `skills`, the step's worker gets allowlist + step skills (agentlib skill_dirs). Claude Code chat keeps native discovery
- CLI naming and planner picker (2026-11-16): "Claude Code" reads "CLI" everywhere in the app (Planner / CLI switch, Send plan to CLI, CLI model, crew, feed); internal ids unchanged. New plan, the model chip and Promote left the top of the Plan view for one picker under the planner's chat box (views/Plan/PlannerPicker.tsx): harness-and-model options from app/agents/planner/choices.py (availability from agentlib; Cursor listed, disabled), Auto-promote to <top model> + Rules, New plan. An unstarted plan takes a choice at once, the top model on a running plan = promote by hand, anything else applies to the next new plan (noted under the button). Per-user settings planner_harness, planner_start_model, planner_auto_promote; the harness picks the planner's agentlib engine (--fake still forces fake); auto-promote off = the planner never promotes itself
- Repos panel (2026-11-16): while the Files tab is open the right-hand panel shows Repos instead of In orbit / Incoming (a compact "N waiting" line keeps queue cards reachable): repos found in every connected folder (app/gitrepos.py: the folder itself or up to two levels down), per repo branch, ahead / behind, changed files with +/- and tick boxes, Refresh, Check remote (fetch), Commit, Commit and push, Push; no remote / upstream = "Not linked", commit only; never force push, pull or switch branches; git is a back-end utility (no agent, no agentlib). `--fake` builds two demo repos in its temp folders
- CLI-then-model picker (2026-11-17): both pickers are one component (frontend/src/components/ModelPicker.tsx): a "CLI" dropdown (harnesses grouped in the page from the server's flat options; Cursor listed, "not available yet", not selectable), then that CLI's models; changing the CLI picks its first model. The planner's keeps auto-promote + Rules and New plan, rules for when a choice applies unchanged. The CLI chat's picker sits under its box (the model chip is gone): per-user settings pilot_harness (default the launch engine's CLI; `--pilot-harness`) + pilot_model (`--pilot-model`), same table (app/agents/claude_code/choices.py over planner/choices.py), independent of the planner; fixed at the chat's first message (unstarted chat reloaded at once; in progress -> next new chat, noted); websocket cli_choice / cli_choose / chat_model, chat_started + snapshot chats gain harness, label, option_id, started
- "Other" purpose, question files, Auto answers (2026-11-17): fifth agent purpose `other` (addable in Crew, own section; a folder agent with a missing or unknown purpose shows there; run-time guards like building; planner may assign it to steps); Missions activity feed capped at about a third of the panel; every answered or timed-out planner / builder / CLI question is saved as `<session folder>/questions/NNN-<slug>.md` (planner rounds one file per question; kept across runs; report.md lists its run's files); per-session "Auto answers" switch under the planner's chat box (websocket set_auto_answers / auto_answers / auto_answer; off by default; answers questions that have a recommendation at once, others wait; permission cards untouched, separate from Autopilot); CLI chat placeholder neutral, Crew's CLI card shows the CLI and model chosen. Undefined-subagents tally (assumption 23) not built
- Websocket contract: app/server.py header is authoritative (mirrored by frontend/src/contract.ts)


## Where things are
- Read order for a new session: this file → Features/README.md (then only the relevant request files) → docs/architecture.md → background docs only when their topic comes up

### Current (source of truth)
- Features/ — one file per conversation / feature request (decisions + specs), dated; README.md = the list (#, Request, Summary); newer overrides older; wins over docs/background/v1plan.md where they conflict
- docs/architecture.md — request flow, modules, state on disk; docs/README.md = index; docs/research/ = library notes
- frontend/ — React + Vite + TypeScript ("Orbit" look); read frontend/README.md first (state, hooks, actions, components, tokens, commands)
  - dist/ — the build served by app/server.py; rebuild with `npm run build`; tests `npx vitest run`
- prototype/launchpad-orbit.html — the earlier vanilla front end, one file; served at `/classic` and as the fallback when frontend/dist is missing; not updated any more
- app/ — Python back end; module map in app/README.md (launch, server, hub, plan, sessionfiles, incoming, meter, activity, settings, store, files, demo)
  - launch.py — entry point: `python -m app.launch` · `--cwd <folder>` · `--browser` · `--fake` (demo) · `--question-timeout N` · `--permission-timeout N` · `--autopilot` · `--planner-start M` · `--planner-top M` · `--planner-harness H` · `--no-auto-promote` · `--promotion-window N` · `--promotion-criteria FILE` · `--model M` · `--pilot-model M` · `--pilot-harness H` · `--visual-model M` · dev: `--no-window --port 8765 --code dev`
  - server.py — header = websocket contract (authoritative)
  - agents/ — built-in agents, one folder each (planner, explorer, orchestrator, builder, visualizer, claude_code, drafter): agent.md (standard front matter; Launchpad tools added at load time), code, README.md; shared crew.py (loader, display names, registry), folder_agents.py; read app/agents/README.md (role id → folder map, how to add an agent)
  - vendor/ — ECharts, Chart.js, D3 + licences; served at /vendor/lib/{key}.js (app/vendor/README.md)
  - requirements.txt — install from this folder: `pip install -r app/requirements.txt`
- tests/ — fake-engine pytest suite (zero tokens): `python -m pytest` from this folder; file list in tests/README.md
  - tests/live/live_*.py — LIVE (spend tokens), not collected by pytest: `python tests/live/live_smoke.py [--part planner|run] [--quick]` (~7 min) · `live_visuals.py [--out <folder>]` · `live_planner_study.py --conv A|B [--turns N] [--effort low]` · `live_planner_cost.py --variant lean|preset` · `live_pilot.py [--turns 1,5] [--model sonnet]`; costs in tests/README.md
- Launchpad.bat (Windows) / Launchpad.command (Mac, `chmod +x` once) — double-click launchers for `python -m app.launch`; keep app code cross-platform (OS-specific bits guarded by sys.platform)
- .claude/launch.json — preview configs: "launchpad-dev" (live, port 8765) · "launchpad-fake" (fake demo, port 8766); code `dev`
- `<connected folder>/.launchpad/` — session folders written at run time (git-ignored by its own .gitignore)
- `<home>/.launchpad/` — per-user settings.json and backups/ of hand-edited files (outside every project)

### Background (docs/background/; older than the Features/ request files; history and reasoning)
- v1plan.md — original V1 design interview (2026-11-04, older "Mission Control" naming, numbered D-decisions referenced elsewhere)
- cursor-vs-agent-sdk-research.md — answers v1plan.md §9: Claude Agent SDK vs Cursor SDK, 15 questions, risks, recommendations
- claude-cursor-orchestrator-summary.md — short design for one Python orchestrator that picks Claude or Cursor per role; early library sketch that became agentlib
- planpal-extraction.md — what to reuse from Plan Pal (../Planning Chatbot/interviewer_sdk/); reference only, V1 is a fresh build

### Outside this folder
- agentlib: ../agentlib/ (subfolder of the General-Purpose-Productivity repo; Claude engine live, Cursor stub, fake for tests); tests: `python -m pytest` from that folder
