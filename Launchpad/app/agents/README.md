# app/agents: Launchpad's built-in agents

One folder per built-in agent. Each folder holds the agent's definition (`agent.md`, a standard Claude Code agent file), its Python code and a short `README.md`. Code shared by all agents sits directly in this folder.

## Layout

```
app/agents/
  crew.py            shared: role registry (ROLES / HELPERS), loading (load, load_step_worker), display names,
                     purposes, folder-agent registry, crew_list event, shared tool constants
  folder_agents.py   shared: folder agents' form fields, create, remove (<folder>/.claude/agents/<name>.md)
  planner/           agent.md, promotion.md, planner.py, choices.py (the harness-and-model picker)
  explorer/          agent.md, astronaut.py
  orchestrator/      agent.md, run.py, report.py
  builder/           agent.md, builder.py, deny.py
  visualizer/        agent.md, visuals.py, libraries.py
  claude_code/       agent.md, pilot.py, choices.py
  drafter/           agent.md, drafter.py
  role_reviewer/     agent.md, reviewer.py (the Role Reviewer: reviews an undefined role from the tally)
```

## Role id to folder

Role ids, front-matter names and websocket fields did not change when the folders were introduced, nor when "Claude Code" was renamed "CLI" (2026-11-16, so the app reads harness-neutral); the folders use the older display names.

| Role id | Folder | Display name | Front-matter name | Python module |
|---|---|---|---|---|
| `planner` | `planner/` | Planner | `launchpad-planner` | `app.agents.planner.planner` |
| `astronaut` | `explorer/` | Explorer | `launchpad-astronaut` | `app.agents.explorer.astronaut` |
| `orchestrator` | `orchestrator/` | Orchestrator | `launchpad-orchestrator` | `app.agents.orchestrator.run` (+ `report`) |
| `builder` | `builder/` | Builder | `launchpad-builder` | `app.agents.builder.builder` (+ `deny`) |
| `visual` | `visualizer/` | Visualizer | `launchpad-visual` | `app.agents.visualizer.visuals` (+ `libraries`) |
| `pilot` | `claude_code/` | CLI (was Claude Code) | `launchpad-pilot` | `app.agents.claude_code.pilot` |
| `drafter` (helper) | `drafter/` | Agent drafter | `launchpad-drafter` | `app.agents.drafter.drafter` |
| `role_reviewer` (helper) | `role_reviewer/` | Role Reviewer | `launchpad-role-reviewer` | `app.agents.role_reviewer.reviewer` |

- Role Reviewer (2026-11-17): reviews one undefined role (a plan step `role`, tallied in `app/tally.py`) on five fixed tests and writes a case; read-only (Read / Grep / Glob, each call checked against its brief's paths); model = setting `reviewer_model` (default sonnet) on the planner's chosen CLI; metered with role `reviewer`, no session (app-wide cost only). Its display name is deliberately not "Reviewer", so it is not confused with the folder-agent purpose `reviewing`. Its usage events and activity carry role `reviewer`

- Python modules are named after the role id (astronaut, pilot), or after what they hold where a folder has several modules
- Paths shown in the UI and the File Explorer's "app" root: `app/agents/<folder>/agent.md` and `app/agents/planner/promotion.md` (`crew.editable_files()`); Python files are not shown there
- The fake demo (`python -m app.launch --fake`) copies those same files, in the same layout, to a temp folder and points `crew.use_app_root` at it

## What is shared

- `crew.load(role, ...)`: loads `<folder>/agent.md` through agentlib's `load_claude_agent` and appends Launchpad's own tools (Tool objects) to the file's tool list. Library-only settings (setup, gated tools, output schema, model overrides) are passed at load time, never written into the file
- `crew.session_kw(ls, name, role=, step_skills=)`: what every agent of a session gets at load time: `add_dirs` = the session's additional folders, and `skills` + `skill_dirs` = its allowlist (store `agent_skills`, keyed by agent name; Planner default all, others none) plus a plan step's skills, limited to the skills found in the session's folders (`app/skills.py`). Nothing to add = loaded exactly as before. The CLI chat (pilot) gets only `add_dirs` (its skills are the harness's own)
- `crew.ROLES` / `crew.HELPERS`: role id -> folder, front-matter name, display name. The registry and crew cards cover ROLES; HELPERS (the drafter, the Role Reviewer) load the same way but are not crew cards
- `crew.agent_exists(name, folder)`: is a name a registered agent here (a plan step naming one that is not is tallied under that name)
- `crew.WRITE_TOOLS`, `crew.WRITE_SHELL`, `crew.BUILDER_GATED`: the one place for the write / shell tool lists used by the Builder, read-only folder agents and the new-agent form
- Import direction: each agent imports `crew`; the orchestrator imports the builder (`run_step`); `crew.crew_list` imports the agents lazily (inside the function) to avoid import cycles

## How to add a built-in agent

1. Make `app/agents/<folder>/` with `agent.md` (standard front matter: `name: launchpad-<role>`, `description`, `tools`, `model`; the body is the prompt), an `__init__.py`, the agent's Python code and a `README.md` like the others
2. Add the role to `crew.ROLES` (folder, front-matter name, display name) and `crew.BUILTIN_PURPOSE`; use `crew.HELPERS` instead for a helper that is not a crew card
3. Load it with `crew.load("<role>", engine=..., project=..., tools=[...], **crew.session_kw(ls, <its agent name>, role="<role>"))` from the code that runs it (session_kw: additional folders + skills), with a `Meter` for its usage; right before it starts, `await hub.give_mcp(agent, who=<display name>, session_id=...)` (its assigned MCP servers that passed their last test, warnings for the rest; `crew.attach_mcp`)

4. If it should appear in the Crew tab, add it to the `built` dict in `crew.crew_list`
5. Add a fake-engine script for its front-matter name in `app/demo.py` and tests under `tests/` (zero tokens)
6. Document new websocket fields in the `app/server.py` header (authoritative contract)

## Folder agents (`<folder>/.claude/agents/*.md`) are different

- They belong to a connected folder, not to Launchpad: written by the user or by the Crew tab's add form (`folder_agents.create`), removed with a backup (`folder_agents.remove`)
- They have no Python code of their own. Launchpad runs them only as plan-step workers through the Builder's code (`app/agents/builder/builder.py`), loaded by `crew.load_step_worker`
- Their front matter adds `purpose:` (planning | exploring | building | reviewing | other; a missing or unknown purpose = other, shown under "Other" in the Crew tab). Exploring / reviewing ones are read-only (write, edit and shell tools removed and refused); building and other ones get the Builder's gated tools, permission cards, guards and shell deny list
- A file whose name matches a built-in's front-matter name is skipped; a broken file is listed with its problems and never runs
- A Role Reviewer case saved for an agent created on the define path goes to `<folder>/.claude/agent-cases/<name>.md`, beside `.claude/agents/` and never inside it, so neither Launchpad nor the CLI harness reads it as an agent

## Plan steps without a listed agent: roles

- The planner may give a step with no fitting listed agent a `role` slug (never together with `agent`); the step runs on the Builder and the step runner records the use in the per-user tally (`app/tally.py`); a step naming an agent that does not exist is tallied under that name; steps run by registered agents are not tallied
- The Crew tab lists roles used twice or more; Review runs the Role Reviewer; "define" drafts an agent through the drafter with the case as context, and creating it removes the tally entry
