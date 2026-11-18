# tests

## Fake-engine suite (zero tokens)

`python -m pytest -q` from the Launchpad folder. Runs the whole loop on agentlib's fake engine (setup in `conftest.py`: throwaway project folder, recording UI client).

| File | Covers |
|---|---|
| `test_loop.py` | planner -> draft -> approve -> orchestrator -> builders -> report |
| `test_demo.py` | the `--fake` demo script end to end |
| `test_questions_permissions.py` | builder questions (timed / blocking), write and shell guards |
| `test_cards_and_static_routes.py` | card fields, plain names, Explorer trips, snapshot, favicon, one session total |
| `test_plan_format_and_session_folder.py` | plan.md format and the session folder basics |
| `test_planner_edits_promotion.py` | edit-based draft revisions, Sonnet -> Opus promotion |
| `test_planner_picker.py` | the planner picker: options + availability, choices before / after the first message (next plan), promotion by hand, auto-promote off, harness -> engine |
| `test_agents.py` | built-in agent files: format, minimum tools, one folder per agent |
| `test_agent_registry.py` | registry, folder agents, step routing and fallback, read-only agents, the Other purpose (guards like building, unknown purpose = Other), use counts, draft / create / remove |
| `test_activity.py` | activity feed, `activity.log`, reconnect replay |
| `test_visuals.py` | visual sidecar: render, pick, tweak, retry |
| `test_visual_libraries.py` | Visualizer libraries, availability, fallback label, `/vendor/lib` route |
| `test_pilot.py` | CLI chat: streaming, permissions, modes, plans, questions |
| `test_cli_picker.py` | the CLI chat's picker: options from the planner's table, launch CLI default, a choice before the first message reloads the chat (mode kept), during a chat it applies to the next new chat, `pilot_harness` / `pilot_model` persist, independent of the planner, CLI -> engine (fake forces fake), refusals |
| `test_files_settings.py` | connected folders, settings store, file browsing and editing |
| `test_gitrepos.py` | Repos panel back end on temporary repos only (skipped without git): clean, modified / untracked / deleted counts, no remote (not linked), local bare remote for ahead / behind / fetch / push, subset commit, refused paths, nesting and duplicate detection, hub messages |
| `test_skills_folders.py` | skill discovery (`.claude` / `.agents` rules, shadowing), per-agent skill settings, plan-step skills reaching the worker, additional folders (add_dirs, write guard) |

| `test_question_files_auto_answers.py` | question files (planner round one file per question, builder, timed-out, CLI chat; numbering after a restart; files stay across runs; the report lists its run's files) and the Auto answers switch, builders only (blocking and non-blocking builder questions take the recommendation and the step never blocks, an empty recommendation or reason is rejected, planner rounds and CLI chat questions are never auto-answered, permission cards unaffected, switching on answers a waiting question, the question-file wording, replay) |
| `test_costs.py` | cost totals are summed in one place: the server's session / planner / chat / app totals equal the sum of the meters, live and on connect; the formatting helper |
| `test_roles_review.py` | undefined roles: plan step `role` (round trip, old plans, `agent` + `role` refused), a role step recorded from a run with its evidence, registered agents not recorded, a missing agent tallied under its name, the two-use threshold, dismiss and reappear, keep / not yet resting then resurfacing (five more uses; a failed, blocked or sent-back use), define until created, merge, two processes writing the tally, send-back marked on the right use, the planner's 20 recent role names; the Role Reviewer (case with five sections, verdict, tokens and cost, app-wide only; questions as cards never auto-answered; read-only and kept to its brief; reading depth and missing session folders; one review per role, a failed review stays reviewable); the define path through the drafter (case context, entry removed, case copy not loaded as an agent); the demo's sample roles and three verdicts; `--fake` never touching the real store |
| `test_connections_mcp.py` | Settings > Connections (the list from the server; Claude Code's three steps on the fake engine, unreachable, missing = nothing sent; Cursor install check only; each script run alone in a subprocess; `test_connection`) and the MCP library (secrets masked and kept through a masked edit, refused hidden values, names, rename / delete following assignments, sse, `${VAR}` expansion, the file beside settings.json; every websocket message with a scripted tester; the background re-test at start; Claude Code import candidates and precedence; run-time wiring on a fake engine that takes MCP servers: only passing servers reach the Builder, the planner and the CLI chat, warnings in the session and the step report, nothing unassigned, the plain fake engine skips cleanly; Crew `mcp_supported`; agentlib's real check on the demo's local server; the demo's sample library in temp only) |
| `test_frontend_routes.py` | `/`, `/classic` and `/assets` routes for the React build |
| `test_workflows.py` | workflows: files with mistakes shown as cards that cannot run (bad JSON, structural errors, unknown agent, missing attachment); a full run (dated folder, result files, review record, run summary, run.json, inputs and attachments reaching every agent stage, earlier results handed on, Missions events, bookkeeping in `.launchpad/`, the remembered sign-off name); bad inputs and one run at a time; test runs (clears and reuses Launchpad's own `test` folder, refuses one without the marker and deletes nothing, records labelled); an attachment deleted before Run blocks it; Unattended answers questions and approves permission requests but the review still stops; send-back re-runs from the chosen stage only and keeps the rejected results; a run waiting at a review survives a reconnect and stops from Missions; the form's save / edit (backup) / remove and its refusals; the shipped example is valid; Explorer and folder-agent stages load and run for real; the review "needs you" card, `waiting_for`, the `workflow` marker and `auto_answers` on Missions events; the `--fake` seed waits at its review and finishes after approval, and a fresh run of the demo sample (unattended) reaches its review |

Front-end tests are separate: `npx vitest run` in `frontend/`.

## Live scripts (spend tokens)

In `tests/live/`, not collected by pytest. Run from the Launchpad folder; they need the Claude sign-in. Costs are from each script's docstring.

| Command | What it checks | Cost |
|---|---|---|
| `python tests/live/live_smoke.py [--part planner\|run] [--quick]` | planner + Explorer, then an approved-plan run with guards and cards | about $0.50-1.50, ~7 min (about $0.08 in a later run) |
| `python tests/live/live_visuals.py [--out <folder>]` | opus planner turn, haiku renders, one tweak | a few cents |
| `python tests/live/live_pilot.py [--turns N] [--model sonnet]` | the CLI chat: cards, modes, settings (haiku) | a few cents |
| `python tests/live/live_planner_cost.py --variant lean\|preset` | Opus planner cost, own prompt vs Claude Code preset | a few tens of cents |
| `python tests/live/live_planner_study.py --conv A\|B [--turns N] [--effort low]` | planner cost study, per-turn table | not stated; run A first |
