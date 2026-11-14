# Foundation: naming, app stack, architecture

Status: decided
Date: 2026-11-08

The first design conversation for the app. It names the workspace (COSMO) and the app (Launchpad), fixes the stack (local-only Python app in a pywebview window, React front end served by Python over a localhost websocket), sets the overall architecture (one Python process, a separate agent library with swappable engines, Claude first), records the Agent SDK facts the design leans on, and parks the questions to ask later.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

Rule: orchestrator = same app as the Launchpad planner (inside COSMO). Build off everything below; newer decisions override older ones.

## Naming
- Project/workspace: COSMO (Claude/Cursor shared memory orchestration)
- App: Launchpad (2026-11-08; overrides earlier "Mission Control" app / "Launchpad" planner-screen split)
- Files/folders keep plain names: plans, briefs, runs

## App stack (decided 2026-11-08)
- Local only, never hosted
- Windows only for now; Mac later (keep code cross-platform)
- ALL agent loops in Python
- Window: pywebview (WebView2 on Windows); Electron + Tauri ruled out
- Front end: React + Vite + TypeScript; built to static files served by Python
- Built front-end files committed to the repo → coworkers need Python only, never Node (rebuild before pushing)
- Page ↔ Python: localhost websocket (FastAPI), bind 127.0.0.1, access code + origin check
- Multiple local apps: each picks a free OS-assigned port at launch → passed to window with access code; no fixed ports
- Launch: own window + own icon via thin launcher; code lives in the repo, updates = git pull
- Sharing: the full GitHub repo, not a packaged installer → no code signing / installer build
- One-time setup script after clone: create Python env, install packages, check Claude Code installed + logged in, put Launchpad desktop shortcut with icon
- Claude Code CLI must be installed on the machine (Agent SDK runs it); not bundled

## Architecture
- One Python process: web server, agents, file writing
- Agent wrapper library + app in one repo, separate folders
- Library: define an agent with a simple variable (Claude or Cursor); simpler than the raw Agent SDK
- Engine swappable per role (orchestrator, planner, workers); long-term settings menu for custom workers
- Launcher and engine independent; can be called from Claude Code or Cursor
- Tools = one MCP server usable by both engines
- Claude is the main engine (Agent SDK, Python, via company gateway); Cursor adapter second, pending Cursor CLI research
- Models chosen per role via gateway (e.g. Opus planner, Haiku reader)
- Fake engine in library for free scripted testing + a few real end-to-end runs by hand

## Agent SDK facts (checked 2026-11-08)
- SDK spawns Claude Code CLI as subprocess → inherits CLI login (gateway), no API key
- CLI-equivalent general agent: system_prompt preset "claude_code" + setting_sources user/project/local
- Permissions + AskUserQuestion both route through can_use_tool callback; agent pauses until answered → natural fit for the queue
- Callback never fires for auto-approved tools (allow rules / acceptEdits / bypass)
- PermissionRequest hook can push external notifications while waiting

## Parked questions (ask later)
- Basepoint build scope: loop engine only (headless) vs with window
- Worker work type: analysis deliverables w/ Databricks vs file/code work vs both
- Engine for first orchestrator build: Claude-only behind engine interface?
- First users: James only vs coworkers
- Queue: blocking items (worker permissions/questions) vs non-blocking (planner rounds) — how they coexist
