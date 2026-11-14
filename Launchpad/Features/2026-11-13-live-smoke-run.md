# Live smoke run

Status: built
Date: 2026-11-13

The first full run of the loop on the real Claude engine against a scratch project, which passed and cost about $0.08. It records what was checked and the two fixes made after the run.

Later changed by: [2026-11-14-code-organisation](2026-11-14-code-organisation.md) (tests/live_smoke.py is now tests/live/live_smoke.py)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Live smoke run (2026-11-13; tests/live_smoke.py, real Claude engine, scratch project in a temp folder)
- Passed: planner turn -> explore -> Astronaut (haiku) Grep + structured links; orchestrator offered only run_builder + write_report (`tools: []` works); builder's gated Write/Edit reach Launchpad's check (in-project write + edit allowed, outside write refused); `git push` raised a permission card; timed question expired at 180 s and the builder proceeded; blocking question unanswered 130 s, then answered, turn resumed (not backgrounded, not killed); report.md + run_finished; real token and cost numbers; activity events for real tool calls
- Full run cost about $0.08 (planner $0.01, Astronaut $0.0004, orchestrator $0.017, builder $0.049)
- Fixed after the run: agentlib's end-of-turn reason said "waiting for the user" after any ends_turn tool, and the orchestrator reported it as an issue; now that wording is only for ask_user (agentlib/prompts/stop_*.md). Orchestrator prompt: capped "(+N more)" lines are not issues; the app copies builder issues itself
