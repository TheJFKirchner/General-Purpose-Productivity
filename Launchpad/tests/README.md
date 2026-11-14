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
| `test_agents.py` | built-in agent files: format, minimum tools, one folder per agent |
| `test_agent_registry.py` | registry, folder agents, step routing and fallback, read-only agents, use counts, draft / create / remove |
| `test_activity.py` | activity feed, `activity.log`, reconnect replay |
| `test_visuals.py` | visual sidecar: render, pick, tweak, retry |
| `test_visual_libraries.py` | Visualizer libraries, availability, fallback label, `/vendor/lib` route |
| `test_pilot.py` | Claude Code chat: streaming, permissions, modes, plans, questions |
| `test_files_settings.py` | connected folders, settings store, file browsing and editing |
| `test_frontend_routes.py` | `/`, `/classic` and `/assets` routes for the React build |

Front-end tests are separate: `npx vitest run` in `frontend/`.

## Live scripts (spend tokens)

In `tests/live/`, not collected by pytest. Run from the Launchpad folder; they need the Claude sign-in. Costs are from each script's docstring.

| Command | What it checks | Cost |
|---|---|---|
| `python tests/live/live_smoke.py [--part planner\|run] [--quick]` | planner + Explorer, then an approved-plan run with guards and cards | about $0.50-1.50, ~7 min (about $0.08 in a later run) |
| `python tests/live/live_visuals.py [--out <folder>]` | opus planner turn, haiku renders, one tweak | a few cents |
| `python tests/live/live_pilot.py [--turns N] [--model sonnet]` | the Claude Code chat: cards, modes, settings (haiku) | a few cents |
| `python tests/live/live_planner_cost.py --variant lean\|preset` | Opus planner cost, own prompt vs Claude Code preset | a few tens of cents |
| `python tests/live/live_planner_study.py --conv A\|B [--turns N] [--effort low]` | planner cost study, per-turn table | not stated; run A first |
