# Settings page, CLI connections and MCP library

Status: built
Date: 2026-11-17

Settings stops being a pop-up and becomes its own view. Its first section, Connections, lists the CLI tools (Claude Code and Cursor) by their real names, each with a Test button that checks the tool is installed and that Launchpad can reach it. A new MCP library in Settings holds the user's MCP servers, tests each one, and feeds a per-agent MCP picker on every Crew card, so any agent (the planner included) can be given specific servers and none has any by default.

Feature branch: `feature/settings-connections-mcp`.

## What was built, and where it differs from the plan

- Built as planned: the Settings view, Connections with one test script per tool (`app/connections/`), the MCP library (`app/mcplib.py`, saved in `<home>/.launchpad/mcp.json`), import from Claude Code (`app/mcpimport.py`), the zero-token test helper in agentlib (`agentlib/mcp_check.py`), and the same MCP picker on every agent's detail page in Crew.
- The picker sits on the agent's detail page under Skills (where the skills control is), not on the summary card. The card shows a small warning chip when an assigned server is failing.
- The older section listing servers from the agent's own file is kept, relabelled "MCP servers from the agent's file" and placed under the library picker.
- The websocket table had gaps that the front end filled and the back end matched; the full contract is in the "Shared interface" section below and the `app/server.py` header.
- `--fake` shows a sample library in its temp home, reset on every launch.
- Checked: fake-engine tests in Launchpad and agentlib, front-end tests and build, one UI review of the demo with one fix round (stacked warning boxes, doubled brackets in the version text, picker rows jumping, two MCP sections disagreeing), and one live Claude Code reachability test.
- Not checked: Cursor's "installed but not usable yet" message (Cursor not installed on the build machine), a failed Claude Code test, and the run-time warning when an assigned server is skipped (the fake engine skips MCP silently).

## Known limits, raised with the user

- MCP tools are pre-approved when given to an agent, so they bypass the Builder's permission cards and write guard, and a read-only agent can gain write ability through an assigned server.
- Secrets in `mcp.json` are stored in plain text in the user's home folder.
- A CLI chat whose session is dropped and resumed keeps the servers it was given at its first start.
- One test failure predates this build: `tests/test_agents.py` expects `Launchpad/.claude/agents/` not to exist and an empty folder of that name is present.

## Assumptions (shown to the user, uncorrected)

1. Settings becomes a fifth full view beside Plan, Missions, Crew and Files, opened from the same button; the pop-up goes away.
2. Page order: Connections, MCP library, Working directories, general settings. The last two behave as before.
3. Connections names "Claude Code" and "Cursor"; the rest of the app still says "CLI".
4. Test for Claude Code finds the program, reads its version, then makes one tiny request through agentlib. Test for Cursor checks the install only and reports that Launchpad cannot use it yet. Results show inline next to the button (found or not, version, reachable or not, error text); nothing runs until the user clicks.
5. MCP servers are added by form (command + arguments + environment variables, or URL + headers) or by import. Secret values are masked after saving.
6. An MCP test starts the server, reads its tool list and stops it, spending no tokens. It runs on add, on edit, on click, and for every server in the background when Launchpad starts. A pass shows the tool count.
7. Every agent card in Crew, planner included, gains the same MCP picker beside the skills control. Nothing is selected by default, and only servers whose last test passed are offered.
8. A server that later fails stays assigned and shows a warning on the card. At run time the agent goes ahead without it and the run shows a warning naming it.
9. Deleting a server removes it from every agent.
10. Assignments only take effect on the Claude engine; the UI says so for anything else (Cursor print mode cannot take servers per run).
11. All agent wiring goes through agentlib's existing `mcp_servers` option; tests use the fake engine and spend no tokens.
12. Out of scope: uniform Crew cards, any change to `agent.md` files, model pickers.

## Decisions from the interview

- **Brand names (Q1).** Connections is the one place the real tool names appear. Reason: a connections list is useless without them. The "UI never shows a harness brand" rule stays for everything else; CLAUDE.md is updated to state the exception.
- **What Test does (Q2).** Two steps for Claude Code: version check, then one minimal request through agentlib (a few tokens per click). The version check alone was rejected because it passes on a machine that is not signed in. Cursor: install check only, reported as "installed, but Launchpad cannot use it yet", because agentlib's Cursor engine is a stub.
- **Which agents can have MCP servers (Q3).** All of them, the planner included, with identical behaviour. The user's original wording ("without giving the planner access") meant only that the planner has none by default. The first draft (planner refused by the back end) was rejected.
- **One script per CLI test.** Each tool's test is its own small script that can also be run alone from a terminal; adding a tool later means adding one script.
- **Where MCP data lives.** The library, test statuses and agent assignments are saved in their own file in the user's `.launchpad` folder in their home directory, separate from `settings.json` and never in the repo.
- **Re-test at start (Q8).** Every server in the library is re-tested in the background each time Launchpad starts. Trusting the last manual test was rejected: a dead server would be found mid-run.
- **Failure during a run (Q9).** The run goes ahead without the failing server and shows a warning naming it. Stopping the run was rejected.
- **Import (Q10).** An "Import from Claude Code" button reads the user's existing Claude Code MCP setup and lets them tick servers to copy in. Import is built around a list of sources so other harnesses (Cursor) can be added later without changing the rest.
- **MCP test helper lives in agentlib.** Other projects need the same check; Launchpad calls it from there.
- **Dropped during the interview.** A uniform set of fields on every Crew card, and an `agent_definition.md` file (or a standard `agent.md` header) that Launchpad reads to build cards. The user set both aside for now. Findings worth keeping for a later request: built-in and folder cards are built by two separate code paths; purpose and display name are hard-coded in Python for built-ins; planner, CLI chat, visualizer and reviewer take their model from Settings while explorer, orchestrator and builder use their file.

## Shared interface (websocket)

| Sent by the page | Reply |
|---|---|
| `test_connection {id}` (`claude_code` or `cursor`) | `connection_test {id, installed, version, reachable, usable, detail}` |
| `get_mcp` | `mcp_library {servers, assignments}` |
| `save_mcp_server {server, original_name?}` | `mcp_library` |
| `remove_mcp_server {name}` | `mcp_library` |
| `test_mcp_server {name}` | `mcp_library` (status `testing`, then the result) |
| `list_mcp_imports {source}` | `mcp_imports {source, servers}` |
| `import_mcp_servers {source, names}` | `mcp_library` |
| `set_agent_mcp {agent, servers}` | `mcp_library` |

- A server: `name`, `kind` (`command` or `url`), its config with secret values masked, `status` (`connected`, `failed`, `untested`, `testing`), `detail`, `tool_count`, `tested_at`.
- `assignments`: agent name to a list of server names.
- An import candidate: `name`, `kind`, a one-line summary, and whether a server of that name is already in the library.
- The list of connections (id and display name) and the list of import sources come from the server, so adding one later needs no page change.
- The header of `app/server.py` is the authoritative contract and `frontend/src/contract.ts` mirrors it; if the back end has to deviate from this table, it records the change there and in this file.

Gaps in the table, filled during the build (front end first, back end matched it; no row above changed):

1. `connections` and `import_sources` (`[{id, name}]`) ride on every `mcp_library`; `mcp_library` is also sent on connect and broadcast whenever a test starts or ends. The Settings page sends `get_mcp` when it opens.
2. Server config: kind command `{command, args[], env{}}`, kind url `{url, headers{}}`, plus an optional `type: "sse"` for URL servers (absent = streamable HTTP; an edit without `type` keeps the stored one; a path ending in `/sse` defaults to sse). Servers also carry `tools` (tool names) beside `tool_count`.
3. Secrets are masked as `********` (env and header values, secret-looking args, URL credentials / secret query values; a pure `${VAR}` reference is shown). A masked value sent back unchanged keeps the stored secret; a mask with nothing stored behind it is refused.
4. `crew_list` agents carry `mcp_supported` (false = this agent's engine cannot take MCP servers) and `engine_label`.
5. A refused request is an optional `error` string on `mcp_library` (refusals other than a save also arrive as a system line "MCP: ...").
6. `connection_test` fields may be null (not checked). Assignment keys are agent names as in `crew_list` (e.g. `launchpad-builder`). An import candidate also has `scope` (local / project / user).
7. `save_mcp_server` answers `mcp_library` (untested) at once, then `testing`, then the result.
8. Run-time warnings for a skipped server are `system` events with the session or chat id; a step's warning is also in its step report.

## Tasks

### Task A: back end

- **Goal:** the CLI test scripts, the MCP library with testing and import, and passing each agent's working servers into its run.
- **Builder:** factory-builder, Opus (touches agent wiring).
- **Owns:** `app/`, `tests/`, Launchpad docs (CLAUDE.md, `app/README.md`, `docs/architecture.md`), and the MCP test helper in `../agentlib` with its README row.
- **Read first:** `app/server.py` header, `app/agents/crew.py`, `app/agents/planner/choices.py`, `app/store.py`, `../agentlib/README.md`, `../agentlib/EXTENDING.md`.
- **Done when:** each CLI test script runs alone from a terminal; every message in the table works; an agent launched with assigned servers receives only the passing ones; a failing server produces a warning, not a stopped run; deleting a server clears its assignments; `python -m pytest` passes on the fake engine in both Launchpad and agentlib.
- **Runs with:** Task B, in parallel.

### Task B: front end

- **Goal:** the Settings page with Connections and the MCP library, and the MCP picker on Crew cards.
- **Builder:** factory-builder, Sonnet, UI.
- **Owns:** `frontend/`.
- **Read first:** `frontend/README.md`, `frontend/src/views/Settings/Settings.tsx`, `views/Crew/Crew.tsx`, `App.tsx`, `store/types.ts`, `contract.ts`.
- **Done when:** Settings is a view, not a pop-up; both Test buttons show every result state; servers can be added, edited, tested, removed and imported; the picker appears on every card and lists only connected servers; a failing assigned server shows a warning on the card; the in-page demo data covers the new screens; `npx vitest run` passes and `npm run build` succeeds.
- **Runs with:** Task A, in parallel.
