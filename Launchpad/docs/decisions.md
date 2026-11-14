# Launchpad — decisions so far

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

## UI direction (2026-11-08)
- Chosen look: "Orbit" (picked from 3 concepts: Mission Control / Orbit / Flight Manual)
- Light lavender-grey ground #F4F3FA, white rounded cards, indigo #3B3FB6 primary, coral #E8664A = waiting on you, green #4BAE7F = done; Sora headings, Inter body; big pill buttons
- Layout: planner chat (left) + side panel (right): "Crew in orbit" status graphic + "Incoming" request queue
- Queue holds 3 kinds:
  - permission: tool + command, Allow / Deny / Always allow
  - question: options, worker's suggestion highlighted, Other… free text
  - info/done: view summary, dismiss
- Planner question rounds render as cards in chat: Yes / Change per question, Accept all, Skip (skipped stays open)
- Prototype: prototype/launchpad-orbit.html — vanilla HTML/JS, still being refined before React port
  - Bridge object: websocket to 127.0.0.1 when ?port=&code= in URL, else demo mode with scripted fake planner
  - Event contract in the file header — DRAFT, to be grilled:
    - in: planner_message, typing, question_round, queue_item, queue_resolved, crew, usage, plan_meta, system
    - out: user_message, round_answer, queue_response, queue_dismiss
- Concept canvas (all 3 looks): https://claude.ai/artifact/XpsWhXKF2rw8pLzur1VkE3

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

## Planner
- Interviews in rounds (up to 5 questions, recommended answer + one-line reason); never decides on its own, incl. replans
- Tools only: ask user, explore (Haiku reader), save note, write plan. No bash/edit/write/general sub-agents
- Haiku reader = separate background session started by the app via the library (not SDK subagents); summary ≤300 words as bullets, full report in runs; picked up with next user message
- Playbooks/modes: list of questions + plan format; default playbook always available
- Done checklist: goal, audience, inputs, outputs, done criteria per step, sign-off points; user can say "draft now"

## Plan files (the orchestrator's input contract)
- plans folder per project; two files per plan:
  - plan.md — read by workers/other agents
  - interview notes — decisions + reasons, planner-only (replans, resume)
- Plan header data block: name, draft/approved status, date, link to notes, one line per step (number, title, skill, dependencies, status)
- Plain Python validates header before save
- Three tiers: project plan (big picture) → briefs (one piece, linked, propose approved changes) → tiny cosmetic changes in chat, nothing recorded
- Future router: tiny → worker/general agent; one piece → planner brief mode; big/new → planner project-plan mode

## Runs / state
- Top-level runs folder outside Git; retention a user setting, default 7 days; cleanup on launch
- Session scoreboard file in runs drives the live panel (display-only)
- Full transcripts kept in runs for retention window
- Settings per user, always persist; no project overrides in V1
- Resume only on explicit request = fresh session catching up from scoreboard + notes

## Failure / cost
- Gateway failure: one auto retry, then chat message + retry button
- Cost counter = local approximation from token counts (incl. cached); never poll gateway for spend
- Long-conversation warning offering fresh restart from notes
- Earlier intent: own Python hook system + kill-switch scripts for usage limits

## Agent library: agentlib (built 2026-11-08; details in ../agentlib/README.md)
- Location: General-Purpose-Productivity/agentlib/ (moved out of Launchpad 2026-11-12, into the General-Purpose-Productivity repo; shared by all projects, editable install `pip install -e ../agentlib`) — ALL agent building in this folder goes through it
- Engines: claude (Agent SDK, real) · cursor (stub: declares capabilities, raises "not available") · fake (agentlib/fake/, self-contained, deletable)
- Agent definitions: Agent(...) in code, or standard files via load_claude_agent() (.claude/agents) / load_cursor_agent() (.cursor/agents)
  - Files hold standard fields only, so the same file works in Claude Code / Cursor / agentlib (supersedes D68's custom front matter)
  - Library-only settings (engine, setup, cwd, tool functions) passed at load time; engine defaults to matching program
  - Cursor-style files run on claude until the cursor engine exists; readonly → Read/Grep/Glob
- Setup modes: lean (default; no folder settings, only listed tools) | project (Claude Code in cwd: CLAUDE.md, settings, native skills)
- Calls: ask / ask_sync (one-shot) · session() with send / stream / answer · resume=id · fork (Claude only)
- Tools: @tool Python functions (schema from type hints, docstring = description, errors → error result); one mixed tools: list (built-ins, custom names, ask_user, mcp__x__y); custom tools served as mcp__agentlib__<name> (renamed from mcp__launchpad__ 2026-11-12 so the shared library is app-neutral)
- Two separate "asking" features:
  - ask_user = material questions (scope, data, objective) — our own tool on every engine; used in all agent files (never AskUserQuestion)
    - Parks: ends the turn → Reply.status needs_input + questions → session.answer() resumes; nothing runs while waiting; survives restarts
    - Shape: list of {id, question, why, options (0 or 2-4), recommended, multi_select}; answers {id, answer, kind: option|recommended|free_text|skipped}; code-validated, bad calls go back to the agent
    - Where questions land (queue, checklist) = app's job later
    - Later: small stdio MCP version so ask_user works inside Claude Code / Cursor directly
  - on_permission = tool-run permission (Bash, Edit…) — Claude only; no hook → anything not pre-approved denied
- Skills/references: native in project setup; lean setup reads only listed skill folders on demand; references = relative paths the agent reads itself (agent body → cwd, skill → skill folder), never inlined
- Events (stream): text_delta, text, tool_call, tool_result, rate_limit, done(Reply)
- Sign-in: same as typing `claude`; opt-in use_login_only() strips API-key env vars
- Model-facing library text in agentlib/prompts/*.md
- Verified live 2026-11-08 (Haiku): lean offers only our tools, ask_user parks/answers, custom tool runs, resume by id, streaming, project setup loads CLAUDE.md

## First working app (2026-11-08)
- app/launch.py + app/server.py: Orbit page served by FastAPI on 127.0.0.1; websocket checks access code + Origin; pywebview window (or --browser)
- Planner chat = agentlib agent from app/agents/planner.md: Opus, lean, tools: ask_user only
- ask_user questions → question_round cards (why, options, pick; Yes / Change / option buttons; Accept all; Skip) → round_answer → session.answer()
- Chat window header shows that agent's own prompt-cache tokens (read / written, conversation totals; tooltip = last turn + uncached input/output) via `agent_usage` event; header pill stays app-wide total
- Planner text rendered with a minimal escape-first markdown subset (stand-in for D66 DOMPurify renderer)
- Verified: security rejects bad code/origin; chat → question round → answers → reply, in the browser pane

## Next up (paused 2026-11-08)
- James refining the Orbit front end first
- Then: orchestrator branch — lean = planner is the front door, starts the orchestration loop; orchestrator reaches user only via the queue; general agent beside planner

## Parked questions (ask later)
- Basepoint build scope: loop engine only (headless) vs with window
- Worker work type: analysis deliverables w/ Databricks vs file/code work vs both
- Engine for first orchestrator build: Claude-only behind engine interface?
- First users: James only vs coworkers
- Queue: blocking items (worker permissions/questions) vs non-blocking (planner rounds) — how they coexist

## V1 loop (decided 2026-11-12; overrides older Planner / Runs / plan-file items where they conflict)
- Loop: planner -> draft plan -> user approves in the UI -> fresh orchestrator session -> one builder session per step, one step at a time -> report.md
- Four agents, each a standard `.claude/agents/launchpad-*.md` file (standard front matter only, usable outside Launchpad); Launchpad-only tools are Python tools appended at load time, so the file used elsewhere simply lacks them (app/crew.py)
  - Navigator = planner (opus): ask_user (max 3 questions per round) + explore + read_markdown + write_plan; no shell, no write/edit, no general Read
    - read_markdown: .md files inside the project only (checked in code after resolving the path)
    - write_plan saves a draft only; only the Approve button starts a run
  - Astronaut = explorer (haiku): Read, Grep, Glob; its own agentlib session started by the app (agentlib has no sub-agents); returns ONLY file links (path, optional line, 1-2 sentence answer) via structured output, plus optional routing_notes
    - Writes no file in the session folder (no Haiku report file; replaces the "full report in runs" idea); code adds its links to the flight log
    - Runs inside the planner's explore tool call (not in the background)
  - Flight Director = orchestrator (sonnet): run_builder + write_report only, both end its turn; code runs the builder and sends back only the capped result as its next message; never reads code, never asks the user
  - Flight Engineer = builder (sonnet): Read, Write, Edit, Grep, Glob, Bash + ask_question, add_to_flight_log, submit_report; fresh session per step
- Session = one planning conversation + its run; id = timestamp + 4 hex chars; several sessions can be in flight (New session while earlier runs continue); steps within a run are sequential
- Session folder = `<project>/.launchpad/<session-id>/` in the project the app was launched for (`--cwd`, default current folder); replaces the top-level runs folder outside Git / home-folder runs
  - `.launchpad/.gitignore` = `*` (ignores itself); folder created on first write
  - plan.md · flight-log.md · steps/step-NN.md · assumptions.md · operations-manual.md · report.md; deliverables go in the project, never here
  - A second run in the same session moves the old steps/ and report.md into run-<k>/
- plan.md header: plan, status (draft | approved), date, session, one line per step {n, title, skill, after, status}; validated in Python before saving; code updates step status during the run (header = scoreboard); interview-notes file not used yet
- Flight log: link + one line why; fed by Astronaut results (code) and the builder's add_to_flight_log; passed to the orchestrator and every builder with the plan; a later session can start from an old one (planner reads it via read_markdown)
- Builder hand-off enforced in code: submit_report fields built [{item, does}], assumptions, issues, notes_for_orchestrator, routing_notes, status done | blocked | failed; code writes steps/step-NN.md; the orchestrator receives only {step, status, report_path, built ≤8, assumptions ≤5, issues ≤5 (≤160 chars each), notes ≤300 chars}
  - No submit_report -> one nudge, then the step is marked failed with an automatic report
- Assumptions (timer auto-answers + builder-reported ones) and routing lessons (+ tool-call count and cost per sub-agent) are written by code, not left to agents
- Questions (builders only): ask_question {title, body, recommended, options?, blocking}
  - Timed (blocking false): waits for the question timeout (setting, default 180 s; 30 s in the fake demo), then returns the recommendation, tells the builder to proceed, logs the assumption; the step stays in progress
  - Blocking: no timer; step marked blocked; the run waits for the user
  - Timers live on the server; the UI only displays expires_at
  - Builder turns have no per-turn time limit (they contain user waits); the Stop button ends a run; Claude Code's auto-backgrounding of long MCP tool calls is switched off for agents that wait inside a tool (CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS=0)
- Permissions: Write/Edit/Bash are "gated" (offered but never pre-approved; new agentlib `gated_tools`), so every call reaches Launchpad code
  - Writes outside the project, or into .launchpad/ or .git/, are refused (recorded as an issue in the step report); writes inside are auto-approved
  - Shell deny list -> permission card with no timer (allow / deny / always): git commit, git push, package installs (pip/uv/npm/yarn/pnpm/conda/winget/...), deletes outside the project (or of the project itself); "always" = that category for the rest of the run (kept in Launchpad, not as an engine rule); everything else runs
- Cost: per agent session tokens (input, output, cache read, cache write), cost_usd and tool calls, pushed live as agent_usage; report.md has a per-agent table; session total = orchestrator + builders + astronauts, planner shown separately
- Fake demo: `python -m app.launch --fake` runs the whole loop on the fake engine (draft, approval, 3 steps, timed + blocking question, permission card, usage, report) at zero tokens
- Websocket contract: header of app/server.py is authoritative (prototype header follows it)

## Builder write / shell guard: known limits (2026-11-13)
- "Inside the project" = inside the folder the user picks at launch (`--cwd`, default the current folder); launching on a broad folder (home, a drive root) makes nearly everything "inside"
- `.launchpad/` (session records) sits inside that folder: Write/Edit into it are refused, but Bash can still write there
- Path checks cover the file tools only (Write, Edit; NotebookEdit / MultiEdit if ever offered): path resolved (incl. `..` and symlinks) before the check
- The Bash deny list is best-effort pattern matching, not a sandbox. Still possible without a card:
  - redirection / tee: `echo x > ../file`, `cat notes >> C:/Users/x/file`, `tee ../file`
  - interpreters and scripts: `python -c "open('../x','w').write('x')"`, a script the builder writes inside the project and then runs, `node -e ...`, PowerShell `Set-Content` / `Out-File`
  - copies / moves out: `cp file ../`, `mv file ~/`, `Copy-Item`, `robocopy`
  - deletes the list does not know: `find .. -delete`, `git clean` aimed elsewhere, `python -c "import shutil; shutil.rmtree(...)"`
  - installs it does not know (e.g. `pipx install`, `go install`)
- Closing the gap later (pick one, in order of strength): run builders' shell in an OS sandbox (Claude Code's `sandbox` option, to be added to agentlib engine-neutrally) or a container / separate user / scratch worktree; switch Bash from a deny list to an allow list of rules (`Bash(npm test:*)`) with everything else as a card; after each step, diff file timestamps outside the project (detects, does not prevent)

## Activity feed (2026-11-13)
- `activity` event per tool call of every agent: `started`, then the same id with done | denied | failed; one-line summary (command / path / pattern / short label, max 140 chars, never file contents)
- Recent events replayed on reconnect; every finished call also appended to `<session folder>/activity.log` (pairs with operations-manual.md)

## Live smoke run (2026-11-13; tests/live_smoke.py, real Claude engine, scratch project in a temp folder)
- Passed: planner turn -> explore -> Astronaut (haiku) Grep + structured links; orchestrator offered only run_builder + write_report (`tools: []` works); builder's gated Write/Edit reach Launchpad's check (in-project write + edit allowed, outside write refused); `git push` raised a permission card; timed question expired at 180 s and the builder proceeded; blocking question unanswered 130 s, then answered, turn resumed (not backgrounded, not killed); report.md + run_finished; real token and cost numbers; activity events for real tool calls
- Full run cost about $0.08 (planner $0.01, Astronaut $0.0004, orchestrator $0.017, builder $0.049)
- Fixed after the run: agentlib's end-of-turn reason said "waiting for the user" after any ends_turn tool, and the orchestrator reported it as an issue; now that wording is only for ask_user (agentlib/prompts/stop_*.md). Orchestrator prompt: capped "(+N more)" lines are not issues; the app copies builder issues itself

## UI review fix round (2026-11-13)
- queue_item carries agent_id; agent / name fields are the plain display name ("Flight Engineer"); the page adds the step
- One Astronaut per session: a single meter with cumulative usage, working during a lookup, idle between lookups (never "done")
- Reconnect: first event is `snapshot {current_session_id, sessions:[{session_id, chat, report_sent, ...}], chats:[...]}`; planner chat history kept per session
- /favicon.ico served (small SVG)
- One session total everywhere (run_finished, snapshot, report.md): orchestrator + builders + astronauts; planner separate as planner_cost_usd / "Planner (separate, not in the session total)"
- Permission cards carry rec null (no recommended choice); questions keep their recommendation

## Regular session: Pilot (2026-11-13)
- Fifth agent `.claude/agents/launchpad-pilot.md` (display name Pilot): a plain Claude Code chat in the launch folder; no plan, no orchestrator
- Runs exactly as Claude Code does: setup="project" (Claude Code system prompt, all built-in tools, the folder's CLAUDE.md, user + project + local settings incl. the user's own permission rules, skills, hooks); empty agent body and no ask_user, so nothing is layered on top; model sonnet by default (`--pilot-model`)
- Deliberately has NONE of the builder guards: no Launchpad write check, no shell deny list, no gated tools on Claude; permissions are purely Claude Code's (rules, modes, prompts)
- Permission modes default | accept_edits | plan, switchable any time incl. mid-turn (chat_set_mode); starts in default; no bypass mode
- Permission prompts, plan proposals and Claude's own questions (AskUserQuestion) become queue items tied to the chat (chat_id, session_id null), no timer; "always allow" offers this session or the project's local settings (.claude/settings.local.json); for edits the session choice is Claude Code's "allow all edits" (switch to accept_edits)
- Plan mode: edits reach the permission callback (the engine does not hard-block them) and are denied without a card; plan approval picks the next mode (default or accept_edits); rejection keeps plan mode and sends the feedback
- AskUserQuestion answers go back as the tool input (new agentlib `PermissionDecision(input=...)`)
- Interrupt (chat_stop): open cards cleared, the engine interrupted, the turn cancelled if it does not end within 5 s (the next turn resumes the conversation)
- Streaming (chat_delta), activity feed + usage (role pilot, chat_id set, session_id null), activity.log in `.launchpad/<chat-id>/`; several chats and runs can coexist; listed in crew_list with setup + prompt_note
- Fake engine: Claude Code-style prompts are made visible by gating Write/Edit/NotebookEdit/Bash/WebFetch/AskUserQuestion on the fake only
- Known Claude Code behaviour (live 2026-11-13): allow rules in the checked-in `.claude/settings.json` are ignored until the folder is trusted in Claude Code (deny rules and `.claude/settings.local.json` apply regardless); file rules use `Edit(...)` (covers Write); in plan mode Claude Code writes its plan file under the user's `~/.claude/plans/` without asking

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

## Send-back and approve again (2026-11-13, from the first live use)
- Every saved draft has a revision number; any draft written after the last approval can be approved, also after a finished run (send-back -> revise -> approve starts run k+1; the old steps/ and report.md move to run-<k>/). Approving again with no new draft is refused with a system message
- A reconnect or reload replays a pending draft after the finished run's events (before: a revised draft written after a run was never replayed, so a reloaded page had nothing to approve)
- plan_draft carries revision + previous_runs; run_started carries run, revision, autopilot; errors handled by the hub are also printed to the console
- Planner prompt: deliverables go in the project folder, never under .launchpad/ (the first live plan put the dashboard in the session folder, so the write was refused)

## Costs (audit 2026-11-13)
- One source: every dollar figure is the engine's own per-turn cost (Claude Code's total_cost_usd, turned into a per-turn delta in agentlib); no local price table. Per-turn token counts are the turn's own (not cumulative); verified live against published prices (Haiku 5.5, Sonnet 5.5, 1-hour cache writes) to the cent
- The app-wide `usage` event is the plain sum of all agent_usage (all sessions, chats, planner) and now carries the same four token counts; most "tokens" are cache reads, which are cheap
- Floors (1-hour cache writes, 2x base input): Claude Code system prompt + tools (Pilot) is about 30K tokens: about $0.12 to write cold on Sonnet 5.5 ($0.24 Opus 5.5, $0.006 Haiku 5.5), then about $0.003 per model call to read; a lean builder step about 7K tokens cold (about $0.03 on Sonnet 5.5), paid again every step (fresh session); output tokens are $10/M on Sonnet 5.5, so a 5K-token file costs about $0.05 to write plus its later cache write and reads
- Candidate savings (not built): 5-minute instead of 1-hour cache writes (-37.5% on writes, if Claude Code allows choosing), one builder session per run instead of per step, planner on Sonnet instead of Opus, cheaper Pilot model, trimmed tool lists

## Builder permissions: timed cards and autopilot (2026-11-13, decided by the user)
- Builder permission requests are cards with a timer (setting `permission_timeout_s`, default 180 s, separate from the question timeout; `--permission-timeout`; 45 s in the fake demo); unanswered = DENIED, the builder is told in plain words, the step records it as an issue. No more builder cards that wait forever
- Writes outside the project folder (and into .launchpad/ or .git/) are no longer refused silently: they raise a card the user can allow
- Unchanged: edits inside the project and ordinary shell commands run without a card; the deny list (git commit/push, package installs, deletes outside the project) still raises cards; questions (timed / blocking) unchanged; the Pilot keeps Claude Code's own permissions
- Autopilot: per session, default off (`--autopilot` / setting `autopilot_default`), switchable before launch and while a run is in flight (set_autopilot). When on, EVERY builder permission request is approved without a card, including git push, package installs, deletes outside the project and writes outside the project: the user explicitly chose no exceptions. Turning it on approves the run's open cards. Each auto-approval goes to assumptions.md (tag autopilot), the report's "Approved by autopilot" section, and the activity feed (auto: true). Autopilot never answers questions

## Planner prompt: no Claude Code preset (2026-11-13)
- Checked: the planner already runs on its own file body only (lean setup, a plain-string system prompt); so do the Astronaut, orchestrator, builder and Cartographer. Only the Pilot uses the Claude Code preset (by design: "no difference from Claude Code"). A test now asserts the planner is built without the preset
- Planner gaps the preset would have covered, now filled leanly: today's date in the first-message context line (code, so the agent file stays standard); prompt lines "never say what a file contains unless explore / read_markdown showed it" and "short, plain, light markdown only"
- Live (Opus 5.5, same 3-turn exchange: ask_user round, answers, explore + write_plan): own prompt $0.113 (cold prompt 2.9K tokens) vs with the preset $0.147 (cold prompt 5.2K, built-in tools excluded); same tool use, rounds and format; the preset version was a little wordier
- Cold first-call sizes (Haiku tokenizer, incl. ~0.5K request framing): planner 2.8K (prompt 1.1K + tools 1.7K), Astronaut 3.7K (0.8K + 2.9K), orchestrator 1.7K (1.0K + 0.7K), builder 6.7K (1.0K + 5.7K), Pilot 29.9K (preset 3.7K + built-in tools 26.2K), Cartographer 0.9K (no tools)

## Builder on the Claude Code system prompt (2026-11-13, user decision)
- The builder runs on Claude Code's own system prompt with its file text appended (the Launchpad part: flight log, questions, approvals, submit_report, routing notes); the file was trimmed of what Claude Code covers and stays a standard agent definition
- Still lean: new agentlib option `Agent(engine_prompt=True)` = the engine's own agent prompt + instructions, with no folder settings. What loads: the Claude Code prompt (incl. its environment block), the file text, the same 6 built-ins + 3 Launchpad tools. What does not: project CLAUDE.md, user / project / local settings (so no user plugins, hooks or permission rules), skills, claude.ai connectors, auto memory
- Unchanged: fixed tool list, write / shell guard, timed permission cards, autopilot
- Cold start on Sonnet 5.5 (live): 6,654 tokens / $0.0267 before -> 8,128 tokens / $0.0325 now (+$0.006 per builder step)
- Agents on the Claude Code prompt: builder (lean, engine_prompt) and Pilot (full project setup); planner, Astronaut, orchestrator, Cartographer run on their own prompt only

## Thinking / effort (facts, 2026-11-13)
- No agent sets effort: agent files cannot hold it, agentlib passes none by default, lean agents do not read the user's settings (their modelSettings effort "high" for Opus 5.5 does not apply), and CLAUDE_CODE_EFFORT_LEVEL is not set; so every agent runs its model's Claude Code default: medium for Opus 5.5 / Sonnet 5.5 / Haiku 5.5, with adaptive thinking (cannot be turned off on these models). The Pilot reads the user's settings, so it gets "high" on Opus 5.5 if it ever runs Opus
- agentlib already sets effort per agent at load time (`Agent(effort=...)`, levels low | medium | high | xhigh | max); not used yet
- Live: planner at effort low, conversation A turns 1-2: $0.0447 vs $0.0540 at default (-17%), same tool use and 3-question round, shorter plan

## Planner cost study (2026-11-13, live, Opus 5.5 planner as it runs; tests/live_planner_study.py)
- Short conversation A (3 turns): $0.096; longer conversation B (8 turns, 3 rounds incl. typed push-back, 2 lookups, a visual set + pick, draft + 2 revisions): $0.405; both reconcile to published prices exactly
- Where it goes (B): visible output 38%, cache writes (1-hour) 30%, thinking ~24% (inferred), cache reads 6%, sub-agents 2%, uncached input ~0%. The three plan-draft turns cost $0.267 (66% of the planner): each revision rewrites the whole plan (~6K characters) as tool input, then caches it
- Candidate savings (not built): revise plans by edits, effort low, Sonnet planner, shorter replies after a draft, tighter plan text; 5-minute cache only if replies come within 5 minutes (gaps would rewrite the whole context), tool definitions and lookup results are minor

## Planner: edit-based revisions (2026-11-13, user decision)
- New planner tool edit_plan: targeted edits to the current draft (replace an exact passage, rename, set_goal, set_step, add_step, remove_step, move_step); step dependencies are remapped by code; the result is re-validated exactly like write_plan and refused with an actionable message if it would be invalid (nothing changes). Each successful edit is a new revision and sends plan_draft as before
- write_plan stays for the first draft and genuine rewrites; prompt: edit when the change is local; after a draft or edit reply in one or two lines on what changed (no recap: the user sees the plan card)
- Live (conversation B shape): first draft + two revisions $0.143 vs $0.267 this morning (rename $0.015 vs $0.074)

## Planner: start on Sonnet, promote to Opus (2026-11-13, user decision)
- Every planner session starts on `planner_start_model` (default sonnet; `--planner-start`) and may be promoted once to `planner_top_model` (default opus; `--planner-top`); never twice, never down; same value or `--model X` = promotion off (always one model)
- Criteria in one editable markdown file `app/planner-promotion.md` (setting / `--promotion-criteria` for a replacement); shown in the Crew tab (crew_list planner.promotion)
- The Sonnet planner decides: tool promote_planner(reason), whose description carries the criteria; allowed only in the first `promotion_window_turns` turns (default 2, `--promotion-window`); the tool stays offered all session (so the cached tool list never changes) and refuses after the window. The user can promote by hand any time (planner_promote)
- Mechanics: new agentlib Session.set_model (engine-neutral, capability model_switch, fake engine + tests): same process, same conversation; mid-turn the next model call already uses the new model, so the planner simply continues. Chosen over resume / fork: no second process, no synthetic "continue" message, no lost pending question round
- Cost split: new agentlib Reply.usage_by_model; the planner's one agent_usage entry carries by_model (e.g. Sonnet then Opus)
- Switch cost (live): the new model writes the conversation so far to its own cache once; in conversation B that was 5,194 tokens on Opus ($0.042, of which the ~3.3K prompt / tools prefix any cold Opus start pays too) plus $0.005 of Sonnet before the switch
- Live: small clear request stayed on Sonnet: $0.043 vs $0.096 all-Opus; messy request promoted on turn 1 ("Open-ended goal, unclear scope; needs data and requirements discovery"): $0.312 vs $0.405 all-Opus; Sonnet's first-turn questions on the small request were comparable to Opus's (Opus added more context to each question)

## Connected folders, settings store, File Explorer and hand-editing (2026-11-13, decided with the user)
- Per-user store `<home>/.launchpad/settings.json` (env LAUNCHPAD_HOME moves the folder; outside every project and out of git): connected folders + the settings that were launch options
- Connected folders: the File Explorer shows them all; each new planning session or Free Flight chat picks one (default = the last used, saved). A session's agents, write guard, permission rules and `.launchpad/<id>/` folder live in its own folder; sessions in different folders run at once. `--cwd` adds its folder and makes it this launch's default. Add by typed path, or the native picker in the window; removing never deletes anything and is refused while a session is busy there; the last folder cannot be removed
- Settings from the page: question_timeout_s, permission_timeout_s, visual_model apply now; autopilot_default, planner_start_model, planner_top_model, promotion_window_turns, promotion_criteria_path, pilot_model apply to new sessions. A launch option overrides for that launch (flagged) until the setting is changed from the page
- File browsing: roots = connected folders + "app" (Launchpad's agent files and the promotion criteria only); every path resolved (symlinks, "..") and kept inside its root; .launchpad session folders included; binary files and files over 1 MB are listed but never sent; behind the existing local-only + access code + origin checks
- Hand-editing: .md only; conflict-safe (the page sends the version it opened; changed on disk -> conflict with the current content); agent files (.claude/agents/*.md) and plan files are validated, a broken one is refused with the reason; every save keeps the previous version as a backup in `<home>/.launchpad/backups/<root>/<path>/<timestamp>.md` with list and restore (restore is itself a backed-up save)
- Agent files and the criteria apply to NEW sessions (file_content / file_saved say so); crew_list is re-sent after a save of an app file
- Fake demo: its own store in the temp folder and two scratch folders ("Demo shop", "Demo clinic")

## React front end (2026-11-13; built while the user was away, on recorded assumptions: Features/2026-11-13-react-port.md)
- The front end is now `frontend/`: React + Vite + TypeScript, built to `frontend/dist/` (kept in the project, so running the app needs Python only; run `npm run build` in `frontend/` after any front-end change)
- Serving: `GET /` = `frontend/dist/index.html` when it exists, else the vanilla page; `GET /assets/<file>` = the build's hashed files; `GET /classic` = the vanilla page, always. Port and access code still come from the URL query. Page CSP unchanged
- `prototype/launchpad-orbit.html` is kept as the reference and fallback and is no longer updated; new UI work goes in `frontend/`
- State: Zustand + immer, one reducer for every server event (`src/store/`); views only read state and call actions. The in-page demo (no port / code in the URL) is ported, so `npm run dev` works without the back end
- Visual frames: same security model as before (sandboxed srcdoc iframes, own meta CSP, ECharts inlined, navigation guard)
- Look: same Orbit colours, fonts and layout; spacing / radius / type / shadow / motion tokens in `src/theme.css`; icons = lucide-react; dialogs = @radix-ui/react-dialog (unstyled); Sora and Inter bundled (@fontsource-variable, Latin). Nothing fetched from the internet at run time
- Front-end tests: vitest + happy-dom (`npx vitest run` in `frontend/`)
- Library notes: docs/research/ (vite, zustand, immer, vitest, lucide-react, radix-dialog, fontsource)

## Plain agent names, registry, folder agents, Planner / Claude Code switch, wider Visualizer (2026-11-13, decided with the user; spec: Features/2026-11-13-agents-crew-visualizer.md)
- Display names are plain: Planner, Explorer, Orchestrator, Builder, Visualizer, Claude Code (overrides the space names for agents; tab names and the space look stay). File names, `launchpad-*` names and role keys unchanged
- Purposes: planning (Planner, Visualizer), exploring (Explorer), building (Builder, Orchestrator, Claude Code), reviewing (none built in). Crew tab = purpose-coloured cards with a per-user use count (one per agent start; Planner / Claude Code counted at their first turn)
- Registry = built-ins + the connected folder's `.claude/agents/*.md` (`purpose:` in front matter, default building). The planner sees it and may name an agent per step (the Builder or a folder agent only); it never starts one. The orchestrator invokes: exploring / reviewing agents read-only, building agents get the Builder's guards; a missing agent falls back to the Builder and the report says so
- Users add agents from the Crew tab: form + "Draft for me" (haiku, no tools, launchpad-drafter.md); saved in the project's `.claude/agents/`; removable with a backup; built-ins editable, not removable; planning agents cannot be added yet
- One chat screen with a Planner / Claude Code switch: two separate conversations (overrides the separate Free Flight tab). "Send plan to Claude Code" opens the folder's chat in Plan mode with the plan as the first message. Modes: Plan, Ask before edits, Auto-accept edits; no bypass
- Visualizer: optional `library` on show_visuals, default ECharts. Bundled: ECharts, Chart.js, D3. When installed (Launchpad's environment or the folder's `.venv`): Plotly, Bokeh, served from the package's own JavaScript file. Anything else: drawn in ECharts, labelled "Drawn in ECharts, styled like <library>". No Python is run; frames stay sealed; each frame inlines only its own library and reports its height
- `--fake` starts clean each launch (counts, scratch folders, old temp copies)
- Later, not built: a permissioned "run this chart script" tool for matplotlib and other Python libraries; an off-by-default setting to let frames load JavaScript libraries from the internet

## Code organisation: agents in app/agents/<agent>/ (2026-11-14, spec: Features/2026-11-14-code-organisation.md)
- Built-in agents live in `app/agents/<agent>/` (planner, explorer, orchestrator, builder, visualizer, claude_code, drafter): `agent.md` (standard agent file), code, README.md. Shared: `app/agents/crew.py`, `app/agents/folder_agents.py`. This overrides the earlier `.claude/agents/` location for built-ins; `Launchpad/.claude/agents/` no longer exists. Folder agents stay in `<folder>/.claude/agents/`
- Paths in older entries above (`.claude/agents/launchpad-*.md`, `app/planner.py`, `app/run.py`, `app/crew.py`, `app/planner-promotion.md`, `tests/live_*.py`) are historical; the planner criteria are now `app/agents/planner/promotion.md`, live scripts are `tests/live/live_*.py`, background docs are in `docs/background/`. Role ids, `launchpad-*` front-matter names and websocket fields are unchanged
