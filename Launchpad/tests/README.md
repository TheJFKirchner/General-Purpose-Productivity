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
| `test_frontend_routes.py` | `/`, `/classic` and `/assets` routes for the React build |

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
