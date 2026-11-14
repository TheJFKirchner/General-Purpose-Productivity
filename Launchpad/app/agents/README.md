# app/agents: Launchpad's built-in agents

One folder per built-in agent. Each folder holds the agent's definition (`agent.md`, a standard Claude Code agent file), its Python code and a short `README.md`. Code shared by all agents sits directly in this folder.

## Layout

```
app/agents/
  crew.py            shared: role registry (ROLES / HELPERS), loading (load, load_step_worker), display names,
                     purposes, folder-agent registry, crew_list event, shared tool constants
  folder_agents.py   shared: folder agents' form fields, create, remove (<folder>/.claude/agents/<name>.md)
  planner/           agent.md, promotion.md, planner.py
  explorer/          agent.md, astronaut.py
  orchestrator/      agent.md, run.py, report.py
  builder/           agent.md, builder.py, deny.py
  visualizer/        agent.md, visuals.py, libraries.py
  claude_code/       agent.md, pilot.py
  drafter/           agent.md, drafter.py
```

## Role id to folder

Role ids, front-matter names and websocket fields did not change when the folders were introduced; the folders use the display names.

| Role id | Folder | Display name | Front-matter name | Python module |
|---|---|---|---|---|
| `planner` | `planner/` | Planner | `launchpad-planner` | `app.agents.planner.planner` |
| `astronaut` | `explorer/` | Explorer | `launchpad-astronaut` | `app.agents.explorer.astronaut` |
| `orchestrator` | `orchestrator/` | Orchestrator | `launchpad-orchestrator` | `app.agents.orchestrator.run` (+ `report`) |
| `builder` | `builder/` | Builder | `launchpad-builder` | `app.agents.builder.builder` (+ `deny`) |
| `visual` | `visualizer/` | Visualizer | `launchpad-visual` | `app.agents.visualizer.visuals` (+ `libraries`) |
| `pilot` | `claude_code/` | Claude Code | `launchpad-pilot` | `app.agents.claude_code.pilot` |
| `drafter` (helper) | `drafter/` | Agent drafter | `launchpad-drafter` | `app.agents.drafter.drafter` |

- Python modules are named after the role id (astronaut, pilot), or after what they hold where a folder has several modules
- Paths shown in the UI and the File Explorer's "app" root: `app/agents/<folder>/agent.md` and `app/agents/planner/promotion.md` (`crew.editable_files()`); Python files are not shown there
- The fake demo (`python -m app.launch --fake`) copies those same files, in the same layout, to a temp folder and points `crew.use_app_root` at it

## What is shared

- `crew.load(role, ...)`: loads `<folder>/agent.md` through agentlib's `load_claude_agent` and appends Launchpad's own tools (Tool objects) to the file's tool list. Library-only settings (setup, gated tools, output schema, model overrides) are passed at load time, never written into the file
- `crew.ROLES` / `crew.HELPERS`: role id -> folder, front-matter name, display name. The registry and crew cards cover ROLES; HELPERS (the drafter) load the same way but are not crew cards
- `crew.WRITE_TOOLS`, `crew.WRITE_SHELL`, `crew.BUILDER_GATED`: the one place for the write / shell tool lists used by the Builder, read-only folder agents and the new-agent form
- Import direction: each agent imports `crew`; the orchestrator imports the builder (`run_step`); `crew.crew_list` imports the agents lazily (inside the function) to avoid import cycles

## How to add a built-in agent

1. Make `app/agents/<folder>/` with `agent.md` (standard front matter: `name: launchpad-<role>`, `description`, `tools`, `model`; the body is the prompt), an `__init__.py`, the agent's Python code and a `README.md` like the others
2. Add the role to `crew.ROLES` (folder, front-matter name, display name) and `crew.BUILTIN_PURPOSE`; use `crew.HELPERS` instead for a helper that is not a crew card
3. Load it with `crew.load("<role>", engine=..., project=..., tools=[...])` from the code that runs it, with a `Meter` for its usage
4. If it should appear in the Crew tab, add it to the `built` dict in `crew.crew_list`
5. Add a fake-engine script for its front-matter name in `app/demo.py` and tests under `tests/` (zero tokens)
6. Document new websocket fields in the `app/server.py` header (authoritative contract)

## Folder agents (`<folder>/.claude/agents/*.md`) are different

- They belong to a connected folder, not to Launchpad: written by the user or by the Crew tab's add form (`folder_agents.create`), removed with a backup (`folder_agents.remove`)
- They have no Python code of their own. Launchpad runs them only as plan-step workers through the Builder's code (`app/agents/builder/builder.py`), loaded by `crew.load_step_worker`
- Their front matter adds `purpose:` (planning | exploring | building | reviewing; default building). Exploring / reviewing ones are read-only (write, edit and shell tools removed and refused); building ones get the Builder's gated tools, permission cards, guards and shell deny list
- A file whose name matches a built-in's front-matter name is skipped; a broken file is listed with its problems and never runs
