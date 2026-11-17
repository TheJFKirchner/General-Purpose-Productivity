# Builder (role `builder`)

- What: builds one step of an approved plan in the project folder, then reports what it built, its assumptions and issues (`submit_report`). One fresh session per step. The same code runs folder agents that a plan step names (step workers).
- Model: `sonnet` (from the file); a folder agent whose file says `inherit` or nothing gets the Builder's model.
- Tools: `Read`, `Write`, `Edit`, `Grep`, `Glob`, `Bash`; `Write` / `Edit` / `Bash` gated (every call reaches `StepContext.permission`). Launchpad tools: `ask_question`, `add_to_flight_log`, `submit_report`. Prompt: the harness's own system prompt + the file text, still lean (no project settings).
- Permissions: edits inside the project and ordinary shell commands run without a card; writes outside the project (or into `.launchpad/` / `.git/`) and deny-listed shell commands become timed permission cards (unanswered = denied); autopilot approves them and logs it. The session's additional folders count as inside the project (they also reach the agent as `add_dirs`). Read-only folder agents (exploring / reviewing) are refused any write or shell call in code.
- Skills: the worker gets its own allowlist (Crew tab) plus the skills the plan names for the step (`crew.session_kw`); none = loaded as before.

- Files:
  - `agent.md`: definition (front-matter name `launchpad-builder`)
  - `builder.py`: `run_step`, `StepContext`, `builder_tools`, `SUBMIT_SCHEMA`, `check_report`, `cap_result`, the step-worker rules for folder agents
  - `deny.py`: the shell deny list, `deny_match` (git commit / push, package installs, deletes outside the project)
- Called by: the Orchestrator's run loop (`app/agents/orchestrator/run.py` calls `run_step(run, n, brief)` after `run_builder`).
