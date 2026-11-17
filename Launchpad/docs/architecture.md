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
4. **Planner**: a chat with its own tools (`explore`, `read_markdown`, `write_plan`, `edit_plan`, `show_visuals`, `promote_planner`). Starts on Sonnet and may promote itself once to Opus (criteria in `app/agents/planner/promotion.md`; only with auto-promote on). The picker under its chat box (`app/agents/planner/choices.py`; a "CLI" dropdown of harnesses, then that CLI's models) chooses the harness and start model for new plans and the auto-promote flag (per user); a plan nobody has written to yet takes a choice at once, a running one only promotion. The harness decides the agentlib engine the planner is loaded on (`--fake` forces the fake engine).
5. **Plan draft**: the planner writes `plan.md` (validated by `app/plan.py`); the page shows it; the user approves or sends back. A revised draft can be approved again.
6. **Orchestrator run**: on approve, `agents/orchestrator/run.py` starts the orchestrator, whose only tools are `run_builder` and `write_report`. Each step runs one **Builder** (or the folder agent the plan names; a missing one falls back to the Builder). Write and shell actions pass Launchpad's guards and may raise a permission card.
7. **Report**: step reports and `report.md` are written by code into the session folder; `report.md` lists the run's question files.
8. **Questions and Auto answers**: every answered (or timed-out) planner, builder or CLI question is saved by code as its own file in `<session folder>/questions/` (`sessionfiles.add_question`). The per-session Auto answers switch (state in the hub, replayed in the snapshot) is for builders only: `incoming.py` answers every question a plan-step worker asks (blocking ones too; the step never shows blocked) with the worker's own recommendation at once, saved as a question file marked as the worker's own decision and listed in the run's report, and the page shows a compact marked line in Incoming. `ask_question` rejects an empty recommendation or reason. Planner rounds, CLI chat questions and permission cards are never touched (permissions are Autopilot).
9. **Cost totals**: a cost comes from the engine per turn (agentlib Reply -> `Meter`); `costs.py` is the only place those are added up (session total = every agent but the planner, the planner's share, per CLI chat, app-wide) and formatted on the Python side; `hub.emit_totals` sends them live (usage scope app / session / chat) and on connect, and the page displays what it is sent.
10. **Undefined roles**: a plan step with no fitting listed agent may carry a `role` slug (set by the planner, which is shown the tally's 20 most recent role names). When such a step ends on the Builder, the step runner records the use in the per-user tally (`app/tally.py`): session, run, step, skills, how it ended, questions asked, assumptions logged, questions timed out; a draft written after a run marks that run's uses as sent back. A step naming an agent that does not exist is tallied under that name; steps run by registered agents are not tallied. The Crew tab lists roles used twice or more (`roles_list`).

```
 review_start {role} -> Reviews.start (agents/role_reviewer/reviewer.py)
      build_brief: tally lines + paths (5 most recent uses + every problem use; SKILL.md; Builder; defined agents)
      Role Reviewer (read-only, every Read / Grep / Glob checked against the brief; planner's CLI, reviewer_model)
        -> questions? -> question cards (Incoming.ask, never auto-answered) -> answers -> final case
      -> case file (<home>/.launchpad/role-cases/) -> review_case
 review_decide {role, define|keep|not_yet} -> tally verdict (keep / not yet: rests until 5 more uses or a problem use)
 define: agent_draft {dir_id, role} (drafter + case as context) -> user edits -> agent_create {dir_id, fields, role}
      -> entry removed, case copy at <folder>/.claude/agent-cases/<name>.md
```

The reviewer's cost goes through the standard `Meter` with no session, so it counts in the app-wide total only.

## Where the other agents fit

- **Explorer** (haiku, read-only): called by the planner's `explore` tool; returns structured file links only, which code adds to the flight log.
- **Visualizer** (haiku, no tools): the planner's `show_visuals` starts it; it draws options (ECharts, Chart.js, D3, ...) shown beside the chat in sealed iframes. A pick sends one line back to the planner.
- **CLI session** (role `pilot`, `app/agents/claude_code/`): a plain chat in the CLI harness in a connected folder (the Planner / CLI switch on the Plan tab); separate from the planner. "Send plan to CLI" opens it with a plan as the first message. The same CLI-then-model picker sits under its chat box (without auto-promote and New plan; `app/agents/claude_code/choices.py`, same harness table): per-user `pilot_harness` (default the launch engine's CLI) and `pilot_model`, independent of the planner's choice; a chat's CLI and model are fixed at its first message (an unstarted chat is reloaded at once, a chat in progress keeps its own and the choice is for the next new chat); `--fake` forces the fake engine.
- **Drafter** (haiku, no tools): the Crew tab's "Draft for me" fills the new-folder-agent form; nothing is saved until the user saves. On the define path of a role review it also gets the case as context.
- **Role Reviewer** (sonnet by default, on the planner's CLI; Read / Grep / Glob only, kept to the paths of its brief): judges one undefined role on five fixed tests, starting from "a skill plus the Builder is enough"; writes a case; the user decides.
- **Folder agents**: `<folder>/.claude/agents/*.md` files, run only as plan-step workers through the Builder's code.

Agent files, role ids and the `crew.py` loader: [app/agents/README.md](../app/agents/README.md).

## Folders and skills

- **Folders**: a session or CLI chat runs in one **primary** folder (its working directory; the default connected folder, or the one the folder menu picks) plus the connected folders ticked as **additional** in Settings (minus the primary). The set is fixed when it starts: agents get the extras as agentlib `add_dirs`, the Builder's write guard and shell deny list treat them as inside the project, and the planner's `read_markdown` may open `.md` files there. Session records stay in the primary's `.launchpad/`.
- **Skills** (`app/skills.py`): found only in the session's folders, primary first. Per folder: `.claude/skills` when it has a `.claude` folder (then `.agents` is ignored), else `.agents/skills`. A name found twice: the earlier folder wins, the other is listed as shadowed.
- **Who gets which**: each crew agent has a skill setting ("all" or a list of names; Planner all, everyone else none), set in the Crew tab and stored per user. The planner's first message lists the skills; a plan step may name some (`skills` in plan.md), and that step's worker gets its own allowlist plus those. Agents receive them through agentlib (`Agent(skills=..., skill_dirs=...)`, lean setup: names and descriptions in the prompt, read on demand). The CLI chat keeps the harness's own skill discovery.

## Supporting modules (flat in `app/`)

- `plan.py` plan.md render / parse / validate / targeted edits · `sessionfiles.py` the session folder files
- `incoming.py` the question / permission / plan queue with server-side timers · `meter.py` per-agent tokens, cost, tool calls · `costs.py` cost totals and their formatting
- `tally.py` the undefined-roles tally (per user; visibility rules; the planner's role list)
- `activity.py` live one-line feed of every tool call · `settings.py` active settings · `store.py` per-user store
- `skills.py` skill discovery in a session's folders + per-agent allowlists
- `files.py` File Explorer back end (safe paths, conflict-safe `.md` saves, backups) · `gitrepos.py` the Repos panel's git back end (a plain utility, not an agent: argument-list subprocesses only, repo ids issued by its own scan, paths checked inside the repo, never force push / pull / switch branch / reset; shown in the right-hand panel while the Files tab is open) · `demo.py` scripts for `--fake`

## State on disk

- `<folder>/.launchpad/<session-id>/`: written at run time inside each connected folder, ignored by git through its own `.gitignore`: `plan.md`, `flight-log.md`, `steps/`, `assumptions.md`, `operations-manual.md`, `report.md`, `activity.log`, `decisions.md`, `questions/` (one `NNN-<slug>.md` per answered question, kept across runs), `visuals/` (an older run's steps and report move to `run-<k>/`).
- `<home>/.launchpad/`: per-user, outside every project: `settings.json` (connected folders, `additional_dir_ids`, settings, agent use counts, `agent_skills`), `backups/` of hand-edited files, `roles.json` (the undefined-roles tally; written under `roles.json.lock` with re-read + atomic replace, so two Launchpad windows keep each other's updates) and `role-cases/` (one markdown case per review, with cost, date and the user's decision). `LAUNCHPAD_HOME` moves it; `--fake` uses its own temp home (sample roles seeded there).
- `<folder>/.claude/agent-cases/<agent>.md`: the review case of an agent created on the define path (beside `.claude/agents/`, never loaded as an agent).

- No database; the in-memory hub state is rebuilt for a reconnecting page from the snapshot.

## Fake engine (tests and demo)

`agentlib` ships a fake engine that plays scripted replies. The test suite (`tests/`) runs the whole loop on it with zero tokens, and `python -m app.launch --fake` runs `app/demo.py`'s scripts on it so the UI can be reviewed for free (own temp store, two scratch folders). Real-engine checks are in `tests/live/` and cost money.

## Websocket contract

The header of `app/server.py` is authoritative for every event and UI message. `frontend/src/contract.ts` mirrors it as types; change both together. New fields are documented in the header first.
