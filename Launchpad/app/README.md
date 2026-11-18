# app: the Python back end

Entry point: `python -m app.launch` (options in the `launch.py` docstring). Overview of the flow: [docs/architecture.md](../docs/architecture.md). Install: `pip install -r app/requirements.txt`.

| File | What it does |
|---|---|
| `launch.py` | entry point: store + launch options, server thread, pywebview window |
| `server.py` | FastAPI: page, assets, vendor files, websocket; localhost + access code + origin check; header = websocket contract |
| `hub.py` | all sessions and chats, event broadcast, reconnect snapshot, UI message dispatch, approve / stop / new session, the planner picker (`planner_choose`, `planner_choice`), the CLI chat's picker (`cli_choose`, `cli_choice`; unstarted chats reloaded, `chat_model`), undefined roles (`record_role_use`, `roles_list`, `role_dismiss` / `role_merge`, `review_start` / `review_decide` through the Role Reviewer, `agent_draft` / `agent_create` with `role` on the define path), Connections (`test_connection`), the MCP library messages (tests on add / edit / click / at start, import, assignments) and `give_mcp` (an agent's passing servers right before it starts, warnings for the rest), workflow messages (handed to `workflows/manager.py`; `session_like` finds a workflow run by its Missions id) |
| `plan.py` | plan.md render, parse, validate, status updates, targeted edits; per step optional `agent`, `skills`, `role` (never `agent` and `role` together) |
| `tally.py` | undefined roles: the per-user tally (`<home>/.launchpad/roles.json`, lock + re-read + atomic replace so two Launchpad processes keep each other's updates), what a use records, visibility (listed at 2 uses; dismiss; rest after keep / not yet until 5 more uses or a new problem use; merge), the planner's role list; review cases in `<home>/.launchpad/role-cases/` |
| `sessionfiles.py` | the files in `<folder>/.launchpad/<session-id>/`, incl. one `questions/NNN-<slug>.md` per answered question (`add_question`; numbering from disk) |
| `incoming.py` | question / permission / plan queue with server-side timers; the per-session Auto answers switch (builders only) answers plan-step workers' questions with the worker's own recommendation at once (`ask(auto_ok=True)`, `set_auto_answers` in `hub.py`) |
| `meter.py` | per-agent tokens, cost and tool-call counts (the engine's per-turn cost, via agentlib's Reply, stays the one source of a cost) |
| `costs.py` | the one place cost totals are added up and formatted: which roles count toward a session, the usage events (app / session / chat) `hub.emit_totals` sends, `usd()` / `wire()`; the page only displays them |
| `activity.py` | one-line summaries for the live activity feed and `activity.log` |
| `settings.py` | active settings for this launch |
| `store.py` | per-user store: connected folders (+ which are ticked as additional), settings (incl. the planner picker's `planner_harness`, `planner_start_model`, `planner_auto_promote`, the CLI chat picker's `pilot_harness`, `pilot_model`, and `reviewer_model`), agent use counts, per-agent skill settings (`<home>/.launchpad/settings.json`) |
| `skills.py` | skill discovery in a session's folders (`.claude/skills`, else `.agents/skills`; primary wins a name clash), per-agent allowlists, the planner's skill list |

| `files.py` | File Explorer back end: roots, safe paths, conflict-safe `.md` saves, backups |
| `gitrepos.py` | Repos panel back end (Files tab): finds git repos in the connected folders (folder itself + two levels down), reads status (branch, ahead / behind, changed files with +/- counts), commit / push / fetch through `git` argument-list subprocesses (no shell, timeouts, no prompts, no force push / pull / branch switch); the hub runs it off-thread (`git_scan`, `git_refresh`, `git_fetch`, `git_commit`, `git_push`) |
| `mcplib.py` | the MCP library: servers, last test results and per-agent assignments in `<home>/.launchpad/mcp.json` (lock + re-read + atomic replace); secret masking (and keeping a stored secret when a masked value comes back); validation; `${VAR}` expansion; `for_agent` = assigned servers whose last test passed + what was skipped; `TESTER` runs agentlib's `mcp_check` in a worker thread |
| `mcpimport.py` | "Import from ...": a list of sources, each finding candidates; Claude Code now (local scope + `.mcp.json` per connected folder, then user scope, its own precedence); a Cursor source = one function + one row |
| `connections/` | Settings > Connections: one test script per CLI tool (`claude_code.py`, `cursor.py`), each runnable alone (`python -m app.connections.<tool>`); `__init__.py` lists them (id + name) and runs one for `test_connection` |
| `demo.py` | fake-engine scripts for `--fake`, incl. the sample undefined roles (`seed_tally`, demo temp home only), the fake Role Reviewer, the sample MCP library + Claude Code setup to import from (`seed_mcp`, temp only), and the sample workflow with a run waiting at its review (`workflow_files`, `seed_workflow_run`, `workflow_stage_turn`) |
| `demo_mcp_server.py` | a tiny local MCP server (notes / glossary tools) the demo's library lists, so its tests really pass with zero tokens |
| `requirements.txt` | Python dependencies |

Other folders:
- [workflows/](workflows/README.md): workflows (one JSON file per workflow in a connected folder's `workflows/`): the file format and checking (`format.py`), the runner with review stops, send-back and test runs (`runner.py`), the run folder's records (`records.py`), the hub's messages (`manager.py`), and the shipped `example-workflow.json`
- [agents/](agents/README.md): the built-in agents (one folder each) plus the shared `crew.py` and `folder_agents.py`; the harness-and-model table is `agents/planner/choices.py` (the planner's picker), shared by `agents/claude_code/choices.py` (the CLI chat's picker)
- `vendor/`: bundled chart libraries (ECharts, Chart.js, D3) served at `/vendor/lib/<key>.js`; versions and hashes in [vendor/README.md](vendor/README.md)
