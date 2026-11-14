# Architecture: how Launchpad fits together

For a new developer. Rules and history: [CLAUDE.md](../CLAUDE.md), [decisions.md](decisions.md). Details per area: [app/agents/README.md](../app/agents/README.md) (agents), [frontend/README.md](../frontend/README.md) (front end), [app/README.md](../app/README.md) (module map), [tests/README.md](../tests/README.md).

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
3. **`app/hub.py`**: the centre. A `Hub` owns every `LaunchSession` (one planning conversation plus its run) and every Claude Code chat, broadcasts events to all connected pages, builds the reconnect `snapshot`, and dispatches each UI message (`user_message`, `plan_approve`, `queue_response`, ...). Several sessions in different folders can run at once.
4. **Planner**: a chat with its own tools (`explore`, `read_markdown`, `write_plan`, `edit_plan`, `show_visuals`, `promote_planner`). Starts on Sonnet and may promote itself once to Opus (criteria in `app/agents/planner/promotion.md`).
5. **Plan draft**: the planner writes `plan.md` (validated by `app/plan.py`); the page shows it; the user approves or sends back. A revised draft can be approved again.
6. **Orchestrator run**: on approve, `agents/orchestrator/run.py` starts the orchestrator, whose only tools are `run_builder` and `write_report`. Each step runs one **Builder** (or the folder agent the plan names; a missing one falls back to the Builder). Write and shell actions pass Launchpad's guards and may raise a permission card.
7. **Report**: step reports and `report.md` are written by code into the session folder.

## Where the other agents fit

- **Explorer** (haiku, read-only): called by the planner's `explore` tool; returns structured file links only, which code adds to the flight log.
- **Visualizer** (haiku, no tools): the planner's `show_visuals` starts it; it draws options (ECharts, Chart.js, D3, ...) shown beside the chat in sealed iframes. A pick sends one line back to the planner.
- **Claude Code session**: a plain Claude Code chat in a connected folder (the Planner / Claude Code switch on the Plan tab); separate from the planner. "Send plan to Claude Code" opens it with a plan as the first message.
- **Drafter** (haiku, no tools): the Crew tab's "Draft for me" fills the new-folder-agent form; nothing is saved until the user saves.
- **Folder agents**: `<folder>/.claude/agents/*.md` files, run only as plan-step workers through the Builder's code.

Agent files, role ids and the `crew.py` loader: [app/agents/README.md](../app/agents/README.md).

## Supporting modules (flat in `app/`)

- `plan.py` plan.md render / parse / validate / targeted edits · `sessionfiles.py` the session folder files
- `incoming.py` the question / permission / plan queue with server-side timers · `meter.py` per-agent tokens, cost, tool calls
- `activity.py` live one-line feed of every tool call · `settings.py` active settings · `store.py` per-user store
- `files.py` File Explorer back end (safe paths, conflict-safe `.md` saves, backups) · `demo.py` scripts for `--fake`

## State on disk

- `<folder>/.launchpad/<session-id>/`: written at run time inside each connected folder, ignored by git through its own `.gitignore`: `plan.md`, `flight-log.md`, `steps/`, `assumptions.md`, `operations-manual.md`, `report.md`, `activity.log`, `decisions.md`, `visuals/` (an older run's files move to `run-<k>/`).
- `<home>/.launchpad/`: per-user, outside every project: `settings.json` (connected folders, settings, agent use counts) and `backups/` of hand-edited files. `LAUNCHPAD_HOME` moves it.
- No database; the in-memory hub state is rebuilt for a reconnecting page from the snapshot.

## Fake engine (tests and demo)

`agentlib` ships a fake engine that plays scripted replies. The test suite (`tests/`) runs the whole loop on it with zero tokens, and `python -m app.launch --fake` runs `app/demo.py`'s scripts on it so the UI can be reviewed for free (own temp store, two scratch folders). Real-engine checks are in `tests/live/` and cost money.

## Websocket contract

The header of `app/server.py` is authoritative for every event and UI message. `frontend/src/contract.ts` mirrors it as types; change both together. New fields are documented in the header first.
