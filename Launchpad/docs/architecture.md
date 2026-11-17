# Architecture: how Launchpad fits together

For a new developer. Rules and history: [CLAUDE.md](../CLAUDE.md), [Features/README.md](../Features/README.md) (one file per request). Details per area: [app/agents/README.md](../app/agents/README.md) (agents), [frontend/README.md](../frontend/README.md) (front end), [app/README.md](../app/README.md) (module map), [tests/README.md](../tests/README.md).

## The idea

Launchpad is a local desktop app. The user chats with a **planner**, approves the plan it drafts, and an **orchestrator** hands each step to a **builder** agent, then writes a report. All agent loops are Python (Claude Agent SDK, through the shared `agentlib` library in `../agentlib/`); the React front end only displays state and sends input.

## Request flow

```
 pywebview window / browser          (React, frontend/dist, built from frontend/src)
        |  websocket (JSON, ?code=)  ^
        v                            |  events: snapshot, planner_message, plan_draft, run_started, ...
 app/launch.py  -> app/server.py  -> app/hub.py  (Hub: sessions, chats, broadcast, snapshot, dispatch)
                                        |
                  user_message          v
                  ----------> planner chat (agents/planner)  --explore-->  Explorer (agents/explorer)
                                 |  \--show_visuals-->  Visualizer (agents/visualizer)
                           write_plan / edit_plan  -> plan draft (app/plan.py) -> UI
                                 |
                  plan_approve   v
                          Orchestrator run (agents/orchestrator/run.py)
                                 |  run_builder(step n) for each step
                                 v
                          Builder (agents/builder) or a named folder agent  -> permission / question cards (incoming.py)
                                 |
                          report.md (agents/orchestrator/report.py) -> UI; "send to planner" can start a revised draft
```

1. **`app/launch.py`**: entry point. Reads launch options, opens the per-user store, picks a free port and an access code, starts the server on a background thread and opens a pywebview window (`--browser`, `--no-window` also exist). `--fake` swaps in the fake engine.
2. **`app/server.py`**: FastAPI. Serves the built page at `/` (plus `/assets`, `/classic`, `/vendor/...`) and one websocket. Binds 127.0.0.1 only; the websocket needs the access code and a matching Origin. It only moves JSON in and out.
3. **`app/hub.py`**: the centre. A `Hub` owns every `LaunchSession` (one planning conversation plus its run) and every CLI chat, broadcasts events to all connected pages, builds the reconnect `snapshot`, and dispatches each UI message (`user_message`, `plan_approve`, `queue_response`, ...). Several sessions in different folders can run at once.
4. **Planner**: a chat with its own tools (`explore`, `read_markdown`, `write_plan`, `edit_plan`, `show_visuals`, `promote_planner`). Starts on Sonnet and may promote itself once to Opus (criteria in `app/agents/planner/promotion.md`; only with auto-promote on). The picker under its chat box (`app/agents/planner/choices.py`) chooses the harness and start model for new plans and the auto-promote flag (per user); a plan nobody has written to yet takes a choice at once, a running one only promotion. The harness decides the agentlib engine the planner is loaded on (`--fake` forces the fake engine).
5. **Plan draft**: the planner writes `plan.md` (validated by `app/plan.py`); the page shows it; the user approves or sends back. A revised draft can be approved again.
6. **Orchestrator run**: on approve, `agents/orchestrator/run.py` starts the orchestrator, whose only tools are `run_builder` and `write_report`. Each step runs one **Builder** (or the folder agent the plan names; a missing one falls back to the Builder). Write and shell actions pass Launchpad's guards and may raise a permission card.
7. **Report**: step reports and `report.md` are written by code into the session folder.

## Where the other agents fit

- **Explorer** (haiku, read-only): called by the planner's `explore` tool; returns structured file links only, which code adds to the flight log.
- **Visualizer** (haiku, no tools): the planner's `show_visuals` starts it; it draws options (ECharts, Chart.js, D3, ...) shown beside the chat in sealed iframes. A pick sends one line back to the planner.
- **CLI session** (role `pilot`, `app/agents/claude_code/`): a plain chat in the CLI harness in a connected folder (the Planner / CLI switch on the Plan tab); separate from the planner. "Send plan to CLI" opens it with a plan as the first message.
- **Drafter** (haiku, no tools): the Crew tab's "Draft for me" fills the new-folder-agent form; nothing is saved until the user saves.
- **Folder agents**: `<folder>/.claude/agents/*.md` files, run only as plan-step workers through the Builder's code.

Agent files, role ids and the `crew.py` loader: [app/agents/README.md](../app/agents/README.md).

## Folders and skills

- **Folders**: a session or CLI chat runs in one **primary** folder (its working directory; the default connected folder, or the one the folder menu picks) plus the connected folders ticked as **additional** in Settings (minus the primary). The set is fixed when it starts: agents get the extras as agentlib `add_dirs`, the Builder's write guard and shell deny list treat them as inside the project, and the planner's `read_markdown` may open `.md` files there. Session records stay in the primary's `.launchpad/`.
- **Skills** (`app/skills.py`): found only in the session's folders, primary first. Per folder: `.claude/skills` when it has a `.claude` folder (then `.agents` is ignored), else `.agents/skills`. A name found twice: the earlier folder wins, the other is listed as shadowed.
- **Who gets which**: each crew agent has a skill setting ("all" or a list of names; Planner all, everyone else none), set in the Crew tab and stored per user. The planner's first message lists the skills; a plan step may name some (`skills` in plan.md), and that step's worker gets its own allowlist plus those. Agents receive them through agentlib (`Agent(skills=..., skill_dirs=...)`, lean setup: names and descriptions in the prompt, read on demand). The CLI chat keeps the harness's own skill discovery.

## Supporting modules (flat in `app/`)

- `plan.py` plan.md render / parse / validate / targeted edits · `sessionfiles.py` the session folder files
- `incoming.py` the question / permission / plan queue with server-side timers · `meter.py` per-agent tokens, cost, tool calls
- `activity.py` live one-line feed of every tool call · `settings.py` active settings · `store.py` per-user store
- `skills.py` skill discovery in a session's folders + per-agent allowlists
- `files.py` File Explorer back end (safe paths, conflict-safe `.md` saves, backups) · `gitrepos.py` the Repos panel's git back end (a plain utility, not an agent: argument-list subprocesses only, repo ids issued by its own scan, paths checked inside the repo, never force push / pull / switch branch / reset; shown in the right-hand panel while the Files tab is open) · `demo.py` scripts for `--fake`

## State on disk

- `<folder>/.launchpad/<session-id>/`: written at run time inside each connected folder, ignored by git through its own `.gitignore`: `plan.md`, `flight-log.md`, `steps/`, `assumptions.md`, `operations-manual.md`, `report.md`, `activity.log`, `decisions.md`, `visuals/` (an older run's files move to `run-<k>/`).
- `<home>/.launchpad/`: per-user, outside every project: `settings.json` (connected folders, `additional_dir_ids`, settings, agent use counts, `agent_skills`) and `backups/` of hand-edited files. `LAUNCHPAD_HOME` moves it.

- No database; the in-memory hub state is rebuilt for a reconnecting page from the snapshot.

## Fake engine (tests and demo)

`agentlib` ships a fake engine that plays scripted replies. The test suite (`tests/`) runs the whole loop on it with zero tokens, and `python -m app.launch --fake` runs `app/demo.py`'s scripts on it so the UI can be reviewed for free (own temp store, two scratch folders). Real-engine checks are in `tests/live/` and cost money.

## Websocket contract

The header of `app/server.py` is authoritative for every event and UI message. `frontend/src/contract.ts` mirrors it as types; change both together. New fields are documented in the header first.
