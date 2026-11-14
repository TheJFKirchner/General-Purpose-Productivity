# Plain agent names, agent registry and user-added agents, Crew cards, Planner / Claude Code switch, wider Visualizer

Status: built

Built as planned, with these choices made during the build: plan steps can name only the Builder and folder agents; Planner and Claude Code uses are counted at their first turn; folder agent display names come from the file name; the tab holding the switch is still called "Plan"; editing a folder agent uses the existing file editor (no update message); step entries also carry `agent_purpose` and `agent_fallback`; the fake demo starts clean on every launch.

Makes the agents easier to understand and extend. Agent display names become plain (Planner, Explorer, Orchestrator, Builder, Visualizer, Claude Code) while the space look of the app stays. The Crew tab becomes colour-coded cards with a running use count, and the user can add their own agents from the app; added agents become step workers the planner can name in a plan. The separate Free Flight tab is replaced by a Planner / Claude Code switch on the chat screen. The Visualizer becomes a general "workshop any visual or design" tool with an optional charting library.

Interviewed and approved by James on 2026-11-13.

## Assumptions and decisions

1. Renames change display names only (`ROLES` in `app/crew.py` and every hard-coded copy). Agent files keep their `launchpad-*` names. Tab names such as Missions and the space visuals stay.
2. Names: Navigator -> Planner, Astronaut -> Explorer, Flight Director -> Orchestrator, Flight Engineer -> Builder, Cartographer -> Visualizer, Pilot -> Claude Code.
3. Use counter: one count each time an agent is started (one per builder step, per explore, per visual drawn, per planner session opened, per Claude Code chat opened). Kept per user in `<home>/.launchpad/`, survives restarts, starts from zero (no back-counting). Keyed by agent name.
4. Purposes: planning, exploring, building, reviewing. Built-ins: planning = Planner, Visualizer; exploring = Explorer; building = Builder, Orchestrator, Claude Code; reviewing = none yet.
5. Crew cards show name, description, model, purpose colour and count. Clicking a card opens the full definition the Crew tab shows today, with the edit pen.
6. Registry: one list of every agent's name, display name, purpose and description, built from the six built-ins plus the connected folder's `.claude/agents/*.md`. The planner is given it to write the plan and may name an agent per step; the planner never starts an agent. The orchestrator invokes. It refreshes when an agent is added, edited or removed and applies to new plans.
7. Added agents are step workers. Exploring and reviewing agents are read-only (no write, edit or shell tools, whatever their file lists). Building agents get the Builder's permission cards, guards and shell deny list. Planning agents cannot be added in this version.
8. Added agents are saved in the connected project's `.claude/agents/<name>.md`. The purpose is stored in the file's front matter (a `purpose:` field; Claude Code and Cursor ignore it). A folder agent with no purpose field counts as building.
9. Added agents can be edited and removed from their card; removing keeps a backup copy as file edits do. Built-ins can be edited, not removed.
10. A plan step naming an agent that no longer exists falls back to the Builder, and the report says so.
11. Creating an agent: a form (name, description, purpose, model, tools as tick boxes, instructions) checked by the existing agent-file validation, plus a "Draft for me" button: the user types a sentence or two, a cheap one-shot agent call (haiku, no tools, through agentlib) returns the filled form, the user edits before saving.
12. One chat screen with a Planner / Claude Code switch. Two separate conversations; flipping loses nothing on either side. The Free Flight tab is removed; its chat, cards, keyboard handling and modes move under the switch unchanged. Several chats and plans can still run at once.
13. A "Send plan to Claude Code" button on a plan draft opens the folder's Claude Code chat with the plan as its first message (in Plan mode), as an alternative to Approve and launch.
14. Claude Code modes: Plan, Ask before edits, Auto-accept edits. No bypass (agentlib does not offer it).
15. Visualizer: `show_visuals` gains an optional `library`. ECharts is the default. Always available: ECharts, Chart.js, D3 (bundled in `app/vendor/`). Available when installed: Plotly and Bokeh, found in Launchpad's own Python environment or the connected folder's `.venv`. Anything else is drawn in ECharts and labelled "drawn in ECharts, styled like <library>". No Python code is run. The planner is told the default and what is available for the folder. Design briefs (colour palettes, hero cards, layouts, tiles, any design question) are first-class, not only charts.
16. The Visualizer keeps its safety rules: sealed frames, nothing from the internet, made-up sample data, no tools.
17. Everything agent-side stays on agentlib.
18. The React app and its in-page demo are updated; the old `/classic` page is not.
19. Launchpad is not a git repo: no branch, commit or security review.

Later, not in this feature: a "run this chart script" tool behind a permission card for matplotlib and other Python libraries; a setting to let frames load JavaScript libraries from the internet.

## Shared websocket messages (tasks A and B build to these; A records them in the `app/server.py` header)

- `crew_list` (server -> UI): each agent gains `purpose` ("planning" | "exploring" | "building" | "reviewing"), `uses` (integer), `builtin` (boolean). Folder agents carry the same fields as built-ins where they apply. The event also carries `dir_id` (whose folder agents are included) and `tool_choices` (the tool names the form may offer).
- `agent_uses` (server -> UI): `{name, uses}` whenever a count changes.
- `agent_draft` (UI -> server): `{dir_id, text}` -> `agent_drafted` `{ok, fields: {name, description, purpose, model, tools: [..], instructions}}` or `{ok: false, error}`.
- `agent_create` (UI -> server): `{dir_id, fields}` (same field set) -> `agent_saved` `{ok, name}` followed by a fresh `crew_list`, or `{ok: false, error, problems: [..]}`.
- `agent_remove` (UI -> server): `{dir_id, name}` -> `agent_removed` `{ok, name}` followed by a fresh `crew_list`, or `{ok: false, error}`.
- `chat_from_plan` (UI -> server): `{session_id}` -> the usual `chat_started` (mode `plan`) with the plan sent as the first message.
- Plan steps gain an optional `agent` (agent name; absent = Builder). `plan_draft` and run events carry it, with `agent_display`.
- Task C adds to the visual events: `library` (asked for), `drawn_with` (actually used) and, on the set, `libraries` (available for the folder).

## Tasks

### A. Agents back end
- Goal: decisions 1 to 4, 6 to 11, 13 on the Python side: renames; registry and folder-agent loading; optional agent per plan step in `plan.py`, the planner's guidance and tools, and the orchestrator's hand-off with purpose-based permissions and fallback; the use counter in the per-user store; agent draft / create / remove; `chat_from_plan`; `app/demo.py` scripts for the new flows; the contract header.
- Builder: factory-builder, Opus (agent design).
- Owns: `app/` except `app/visuals.py`, the `show_visuals` tool in `app/planner.py` and the vendor route in `app/server.py`; `.claude/agents/` except `launchpad-visual.md` (may add a drafter agent file); `tests/`.
- Done when: `python -m pytest` passes, with new fake-engine tests for the registry, step routing and fallback, read-only enforcement for exploring / reviewing agents, the counter surviving a restart, agent draft / create / validate / remove, and `chat_from_plan`.
- Runs: first, in parallel with B.

### B. Front end: switch and Crew
- Goal: decisions 2, 4, 5, 9, 11 to 14 on the React side: the Planner / Claude Code switch replacing the Free Flight tab; the send-plan button; Crew as colour-coded cards with counts, the detail view, and the add / draft / edit / remove flow; new names everywhere; the per-step agent shown on plan cards and Missions; the in-page demo updated to the shared messages.
- Builder: factory-builder, Opus.
- Owns: `frontend/` except `frontend/src/views/Visuals/`.
- Done when: `npm run build` and `npx vitest run` pass; every Free Flight control still exists under the switch and sends the same messages; the Crew flows work in the in-page demo; four purpose colours come from tokens in `theme.css` and fit the Orbit palette.
- Runs: in parallel with A.

### C. Visualizer
- Goal: decisions 15 and 16.
- Builder: factory-builder, Opus (agent design).
- Owns: `app/visuals.py`, `.claude/agents/launchpad-visual.md`, the `show_visuals` tool and its guidance in `app/planner.py`, the vendor route in `app/server.py`, `app/vendor/`, `frontend/src/views/Visuals/`, the visual parts of the demo, related tests.
- Done when: all tests pass; each bundled library draws in a sealed frame with no outside requests; Plotly is picked up when installed and absent from the list when not; an unavailable library produces the labelled ECharts version; a palette brief and a hero-card brief render.
- Runs: after A and B.

### Then
- Orchestrator: build, both test suites, the fake demo; `factory-ui-reviewer` once; one fix round; update `CLAUDE.md`, `docs/decisions.md`, `Features/README.md`.
