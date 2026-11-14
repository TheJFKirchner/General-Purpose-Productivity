# Code organisation and documentation

Status: built

A readiness pass over Launchpad so the code is easy to develop on. No behaviour changes: files move, one large module is split, small clean-ups, and documentation is added where a new developer would look for it. The headline change is that every built-in agent lives in `app/agents/<agent>/`, one folder per agent, holding its definition file, its Python code and a README.

The user asked for this to run without an interview, so the points below were taken as assumptions.

## Assumptions

1. No behaviour change. The websocket contract, role ids (`planner`, `astronaut`, `orchestrator`, `builder`, `pilot`, `visual`), front-matter agent names (`launchpad-*`) and settings keys stay as they are.
2. Folder names use the current display names: `planner`, `explorer`, `orchestrator`, `builder`, `visualizer`, `claude_code`, `drafter`.
3. Built-in definitions move out of `Launchpad/.claude/agents/` into the agent folders. Agents a user adds to a connected folder still live in `<folder>/.claude/agents/`.
4. Old import paths (`app.planner`, `app.run`, ...) are not kept as aliases; every caller and test is updated.
5. The rest of `app/` (server, hub, store, files, ...) stays flat; it is about a dozen files and reads fine.
6. `prototype/` stays where it is: it is live code served at `/classic`.
7. `frontend/dist/` is rebuilt and committed after front-end changes.
8. Work stays on the session branch; nothing is merged to main.

## Shared interface (all builders build to this)

| Thing | New location |
|---|---|
| Agent definition | `app/agents/<folder>/agent.md` |
| Planner promotion criteria | `app/agents/planner/promotion.md` |
| Paths shown in the UI / File Explorer "app" root | `app/agents/<folder>/agent.md`, `app/agents/planner/promotion.md` |
| Agent Python code | package `app.agents.<folder>` |
| Shared agent code (registry, loading, display names) | `app/agents/crew.py` (and siblings as needed) |
| Live (token-spending) scripts | `tests/live/live_*.py` |
| Background docs | `docs/background/` |

Role id to folder: planner -> planner, astronaut -> explorer, orchestrator -> orchestrator, builder -> builder, visual -> visualizer, pilot -> claude_code, drafter (helper) -> drafter.

## Tasks

### 1. Back end: agents folder

- Goal: move every built-in agent into `app/agents/<folder>/` (definition, code, README); split `app/run.py` into orchestrator and builder code; move live scripts to `tests/live/`; small duplicate-constant clean-ups.
- Builder and model: factory-builder, Opus (touches agent loading).
- Owns: `app/`, `tests/`, `.claude/`, `sample/`.
- Done: `python -m pytest` passes with the same number of tests or more; `python -m app.launch --fake --no-window` starts; no `Launchpad/.claude/agents/`; each agent folder has `agent.md`, code and `README.md`; `app/agents/README.md` explains the layout and how to add an agent; no file in `app/` over about 450 lines unless justified.
- Runs with: task 2.

### 2. Front end tidy

- Goal: fix the organisation problems found in review (`modals.tsx` vs `Modal.tsx` name clash, `views2c.test.tsx` name, single-file `shell/` folder, demo data paths that disagree with the server, unused exports, stale README), rebuild `dist/`.
- Builder and model: factory-builder, Sonnet.
- Owns: `frontend/`.
- Done: `npm run typecheck`, `npx vitest run` and `npm run build` pass; `frontend/README.md` matches the tree; demo data uses the shared-interface paths.
- Runs with: task 1.

### 3. Documentation

- Goal: move the four background docs to `docs/background/`; write `docs/architecture.md`, `docs/README.md`, `app/README.md`, `tests/README.md`; bring `README.md` and `CLAUDE.md` in line with the new tree.
- Builder and model: factory-builder, Sonnet.
- Owns: all `.md` outside `app/agents/` and `frontend/`.
- Done: every path named in `README.md` and `CLAUDE.md` exists; no links to moved files are broken.
- Runs with: after tasks 1 and 2.
