# agentlib

Define an agent once; run it on Claude (Agent SDK) now, Cursor later. Half the team uses Claude Code, half
Cursor, so agent code must not depend on one vendor's SDK. agentlib wraps the Claude Agent SDK
(`claude_agent_sdk`) behind engine-neutral functions; a Cursor engine slots in later without rewriting agents.

**Rule for every project in this workspace:** never import `claude_agent_sdk` directly; use agentlib. If
agentlib lacks something, add it engine-neutrally (see [EXTENDING.md](EXTENDING.md)). If it truly cannot be
expressed engine-neutrally, stop and tell the user.

Runnable samples: [examples/](examples/README.md). All paths below are relative to this repo root.

## Before the library will work
Each person connects to their AI engine differently (a personal login at home, a company gateway at work).
Do this once per computer:

1. Read the setup guide for your engine and follow it (install, then say how you sign in):

   | Engine | Setup guide |
   |---|---|
   | Claude | [setup/claude-setup.md](setup/claude-setup.md) |

2. Run the check: `python -m agentlib.check`. It sends one tiny message on the cheapest model and prints
   `RESULT: WORKS` or what to fix (`--status` = show the setup only, send nothing).

How you sign in lives in **one local file, `setup/local.toml`** (copy it from
[setup/local.example.toml](setup/local.example.toml)). Git ignores it, so it is never committed and library
updates never overwrite it. No file = the ordinary Claude Code login.

## Rules (library design)
- Agent files stay standard: `.claude/agents/*.md` (Claude Code) or `.cursor/agents/*.md` (Cursor), standard fields only
- Library-only settings (engine, setup, cwd, tool functions, timeouts) are passed at load time, never written in the file
- Model-facing text the library adds lives in `agentlib/prompts/*.md`, not code
- `claude_agent_sdk` is imported only in `agentlib/engines/claude.py`; everything else is engine-neutral
- `agentlib/fake/` is test-only and self-contained: the core never imports it

## Install
- From another project: `pip install -e <path to this folder>` (for example `pip install -e ../General-Purpose-Productivity/agentlib` when the repo is cloned beside your project; editable, so library edits apply immediately)
- Working on the library itself (from this folder): `pip install -e .[dev]` then `python -m pytest`
- Needs Python 3.11+ (`requires-python = ">=3.11"`), Claude Code installed and signed in for real (non-fake) runs
- Auth: set per person in `setup/local.toml` (see "Before the library will work"); apps do nothing.
  `[claude] auth = "login"` (default: like typing `claude`), `"settings-file"` (only the sign-in parts of a
  Claude Code settings file: its `env` block + `apiKeyHelper` and other credential keys) or `"env"`
  (`[claude.env]`). Read by `agentlib/local_setup.py` + `agentlib/engines/claude_setup.py` each time a
  `claude` process starts. A caller's `Agent(env=...)` wins over it, variable by variable.
  `use_login_only()` (`agentlib/auth.py`) removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
  `ANTHROPIC_BASE_URL` from this process's environment (opt-in, at app start); it does not touch the local
  setup file, which still applies

## Quick start
```python
from agentlib import Agent, tool

@tool
def run_sql(query: str) -> str:
    """Run a read-only SQL query."""
    return "3 rows"

agent = Agent("analyst", instructions="Answer with SQL.", model="haiku", tools=[run_sql, "ask_user"])
reply = agent.ask_sync("How many orders last week?")      # in async code: await agent.ask(...)
print(reply.status, reply.text, reply.cost_usd)           # status: done | needs_input | error
```
Zero-cost version: add `from agentlib import fake` and `engine="fake"` (see `examples/01_one_shot.py`).

## Lookup: raw Claude Agent SDK -> agentlib

| Raw SDK thing | agentlib equivalent | Lives in |
|---|---|---|
| `query(prompt, options)` | `await agent.ask(msg)` / `agent.ask_sync(msg)` -> `Reply` (new conversation each call) | `agentlib/agent.py` |
| `ClaudeSDKClient` connect / query / receive_response / disconnect | `async with agent.session() as s: reply = await s.send(msg)` | `agentlib/agent.py`, `agentlib/session.py` |
| `client.interrupt()` | `await s.interrupt()` | `agentlib/session.py` |
| `ClaudeAgentOptions(...)` | `Agent(...)` fields (next table) | `agentlib/agent.py` |
| `@tool(name, desc, schema)` + `create_sdk_mcp_server` + `allowed_tools=["mcp__srv__x"]` | `@agentlib.tool` on a plain function; put it in `Agent(tools=[...])`. Server built for you | `agentlib/tools.py` |
| `ToolAnnotations(readOnlyHint=True)` | `@tool(read_only=True)` | `agentlib/tools.py` |
| Hook that stops after a tool (`continue_=False`) | `@tool(ends_turn=True)` | `agentlib/tools.py` |
| External MCP servers: `mcp_servers={...}` + `allowed_tools` | `Agent(mcp_servers={"db": {config} or "path/server.py"})`; all its tools pre-approved | `agentlib/agent.py`, `agentlib/engines/claude.py` |
| `can_use_tool` + `PermissionResultAllow` / `PermissionResultDeny` / `PermissionUpdate` | `Agent(on_permission=fn)`; `fn(PermissionRequest) -> "allow" \| "deny" \| "always_allow"` (or bool), sync or async | `agentlib/permissions.py` |
| `ToolPermissionContext.decision_reason` | `PermissionRequest.reason` | `agentlib/permissions.py` |
| `include_partial_messages=True` + iterate messages | `async for ev in s.stream(msg)` (always on) | `agentlib/session.py` |
| `StreamEvent` (`text_delta`) | `TextDelta(text)` | `agentlib/events.py` |
| `AssistantMessage` -> `TextBlock` | `Text(text)` | `agentlib/events.py` |
| `AssistantMessage` -> `ToolUseBlock` | `ToolCall(id, name, input)` (custom tools: short name) | `agentlib/events.py` |
| `UserMessage` -> `ToolResultBlock` | `ToolResult(id, name, text, is_error)` | `agentlib/events.py` |
| `RateLimitEvent` | `RateLimit(status, resets_at, utilization, limit_type)` | `agentlib/events.py` |
| `ResultMessage` | `Done(reply)` (last event) / return value of `send()` | `agentlib/events.py`, `agentlib/reply.py` |
| `ResultMessage.total_cost_usd` (cumulative) | `Reply.total_cost_usd`; `Reply.cost_usd` = this turn (delta) | `agentlib/reply.py` |
| `ResultMessage.usage` dict | `Reply.usage` -> `Usage(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cache_write_5m_tokens, cache_write_1h_tokens)`; `Usage + Usage`; `.total_input_tokens` | `agentlib/reply.py` |
| `ResultMessage.session_id / stop_reason / num_turns` | `Reply.session_id / stop_reason / api_calls` | `agentlib/reply.py` |
| `ResultMessage.is_error`, `.result`, `.errors` | `Reply.status == "error"`, `Reply.error` | `agentlib/reply.py` |
| `options.resume=id` | `agent.session(resume=id, cost_base=prev_total)` (same cwd) | `agentlib/agent.py` |
| `options.fork_session=True` | `agent.session(resume=id, fork=True)` | `agentlib/agent.py` |
| `SystemMessage(subtype="init")` | `s.info` -> `SessionInfo(tools, mcp_servers, model)` (custom tools by short name; `mcp_servers` = name -> status); filled once the first turn starts | `agentlib/session.py`, `agentlib/engines/claude.py` |
| `AgentDefinition` / `agents=` (subagents) | not supported (see Not yet supported) | - |
| `.claude/agents/*.md` agent files | `load_claude_agent(name_or_path, project=..., tools=[impls], **overrides)` | `agentlib/loaders/claude.py` |
| `.cursor/agents/*.md` agent files | `load_cursor_agent(name_or_path, project=..., tools=[impls], ask_user=True, **overrides)` | `agentlib/loaders/cursor.py` |
| `skills=` / `.claude/skills/<name>/SKILL.md` | `Agent(skills=["name"])` or `skills:` in the agent file | `agentlib/skills.py`, `agentlib/engines/claude.py` |
| `setting_sources`, `strict_mcp_config`, `system_prompt` preset, `tools` preset | `Agent(setup="lean" \| "project")` | `agentlib/engines/claude.py` |
| `hooks=` | internal only (ends_turn, lean skill guard); not user-facing | `agentlib/engines/claude.py` |
| `CLINotFoundError`, `ProcessError`, `CLIConnectionError`, ... | `AgentError` (`.short` one-line message; `.reply` = partial turn if it failed midway) | `agentlib/errors.py` |
| "No conversation found" on resume | `ConversationMissing` | `agentlib/errors.py` |
| `claude_agent_sdk.__version__` | `agentlib.engines.claude.sdk_version()` | `agentlib/engines/claude.py` |
| `max_budget_usd` + `ResultMessage.subtype == "error_max_budget_usd"` | `Agent(max_budget_usd=0.05)`; a cap stop -> `Reply.status == "error"`, `Reply.error_kind == "budget"` | `agentlib/agent.py`, `agentlib/reply.py`, `agentlib/engines/claude.py` |
| `ResultMessage.subtype == "error_max_turns"` | `Reply.error_kind == "max_turns"` (other bad endings: `"other"`) | `agentlib/reply.py` |
| `permission_mode="dontAsk"` | `Agent(permission_mode="never_ask")`: unlisted tools denied, nobody asked (not with `on_permission`) | `agentlib/agent.py`, `agentlib/engines/claude.py` |
| `ClaudeSDKClient.get_server_info()["models"]` | `await list_models(engine)` / `list_models_sync(engine)` -> `list[ModelInfo]`; no request, no tokens | `agentlib/models.py`, `agentlib/engines/claude.py` |
| `output_format={"type": "json_schema", ...}` + `ResultMessage.structured_output` | `Agent(output_schema=S)` -> `Reply.data` (parsed + schema-checked); bad reply -> `Reply.error_kind == "output_shape"` | `agentlib/structured.py`, `agentlib/engines/claude.py` |
| `claude -p --json-schema ... --tools "" --no-session-persistence` (one-shot JSON call) | `await ask_structured(msg, schema, instructions=, model=, ...)` / `ask_structured_sync(...)` -> `Reply` (`.data`, `.usage`, `.cost_usd`) | `agentlib/structured.py` |
| `--no-session-persistence` (`extra_args`) | `Agent(save_conversation=False)` (cannot be resumed) | `agentlib/agent.py`, `agentlib/engines/claude.py` |
| Sign-in via `env={ANTHROPIC_*...}` / `settings=` (`apiKeyHelper`) / user `settings.json` | nothing in app code: each person's `setup/local.toml` `[claude]` (`auth = "login" \| "settings-file" \| "env"`) | `agentlib/local_setup.py`, `agentlib/engines/claude_setup.py`, `setup/claude-setup.md` |
| "Is Claude set up / does it answer?" (no SDK equivalent) | `connection_status(engine)` (free) / `check_connection_sync(engine)` (one tiny message); CLI `python -m agentlib.check` | `agentlib/connection.py`, `agentlib/check.py` |

### `ClaudeAgentOptions` field -> `Agent` field (`agentlib/agent.py`)

| Options field | `Agent` field | Notes |
|---|---|---|
| `system_prompt` | `instructions` | lean: the whole prompt (>30K chars goes via temp file); project: appended to the `claude_code` preset |
| `model` | `model` | alias (`opus`/`sonnet`/`haiku`) or full id; `None` = engine default |
| `tools`, `allowed_tools` | `tools` | one mixed list: `Tool` objects, built-in names/rules (`"Read"`, `"Bash(npm run build:*)"`), custom names (need `available_tools`), `"ask_user"`, `"mcp__x__y"`. Listed = offered and pre-approved |
| (implementations) | `available_tools` | `Tool`s for custom names in `tools` (what loaders fill from `tools=`) |
| - | `include_ask_user` | only when `tools is None`: add `ask_user` automatically (default True) |
| `disallowed_tools` | `disallowed_tools` | passed through (deny rules: win over `tools` and `on_permission`) |
| `mcp_servers` | `mcp_servers` | `{name: config dict \| path to .py server}`; relative paths resolve against `cwd` |
| `cwd` | `cwd` | also where resume looks for saved conversations |
| `add_dirs` | `add_dirs` | |
| `env` | `env` | merged over the local setup's sign-in variables and the lean defaults (caller wins) |
| `max_turns` | `max_turns` | hitting it -> `Reply.status == "error"`, `Reply.error_kind == "max_turns"` |
| `max_budget_usd` | `max_budget_usd` | spending cap per opened session (one `ask()` = one run); `None` = no cap. Hitting it -> `Reply.status == "error"`, `Reply.error_kind == "budget"`. Checked between model calls (can overshoot a little). Capability `budget` |
| `permission_mode` | `permission_mode` | `"default"` (unlisted tools -> `on_permission`, else denied) or `"never_ask"` (Claude `dontAsk`: unlisted tools denied, nothing asked; `ValueError` with `on_permission`). Capability `never_ask` |
| `output_format` | `output_schema` | a JSON Schema dict (checked when the Agent is built); reply parsed + validated into `Reply.data`. Capability `structured_output` |
| `extra_args={"no-session-persistence": None}` | `save_conversation` | default True; False = engine stores nothing (cannot resume; not in session lists). Capability `unsaved` |
| `effort` | `effort` | passed only if set |
| `skills` | `skills` | lean: listed in prompt, read on demand; project: native |
| `setting_sources` etc. | `setup` | `"lean"` (default) or `"project"` |
| `can_use_tool` | `on_permission` | Claude + fake only |
| - | `timeout_s` | per turn, default 600; `None` = no limit. Timeout -> `AgentError` |
| - | `engine` | `"claude"` (default), `"fake"`, `"cursor"` (stub), or a registered name |
| - | `tool_server` | MCP server name for custom tools, default `DEFAULT_SERVER` = `"agentlib"` (`agentlib/tools.py`) |
| - | `name`, `description`, `source`, `extra`, `warnings` | metadata; `description` is not sent to the model |
| `include_partial_messages` | - | always on |

## Public exports (`from agentlib import ...`)

| Export | Lives in | What it is |
|---|---|---|
| `Agent` | `agentlib/agent.py` | Dataclass defining an agent; `.ask()`, `.ask_sync()`, `.session(resume=, fork=, cost_base=)` |
| `Session` | `agentlib/session.py` | One conversation: `send`, `stream`, `answer`, `answer_stream`, `interrupt`, `close`, `session_id`, `pending_questions`, `last_reply`, `info` |
| `SessionInfo` | `agentlib/session.py` | `s.info`: `tools` (offered; custom by short name), `mcp_servers` (name -> status), `model`; `.to_dict()`. Empty until the first turn starts |
| `Reply` | `agentlib/reply.py` | Finished turn: `status, text, questions, session_id, usage, cost_usd, total_cost_usd, tool_calls, api_calls, duration_s, engine, model, stop_reason, error, error_kind, data`; `.to_dict()`. `error_kind` (only when `status == "error"`): `"budget" \| "max_turns" \| "output_shape" \| "other"`; `data`: parsed JSON when `output_schema` is set |
| `ModelInfo` | `agentlib/models.py` | One offered model: `id` (for `Agent(model=)`), `name`, `description`, `aliases`, `is_default`, `effort_levels`; `.to_dict()` |
| `list_models` / `list_models_sync` | `agentlib/models.py` | `await list_models(engine="claude", *, env=None, timeout_s=60) -> list[ModelInfo]`; no request sent. `CapabilityError` / `EngineUnavailable` / `AgentError` |
| `ask_structured` / `ask_structured_sync` | `agentlib/structured.py` | `await ask_structured(message, schema, *, instructions="", model=None, engine="claude", name="structured", effort=None, max_budget_usd=None, timeout_s=600, env=None, cwd=None) -> Reply`: no tools, `never_ask`, not saved |
| `Usage` | `agentlib/reply.py` | Per-turn token counts, same names on every engine; supports `+`; `.total_input_tokens` |
| `ToolCallRecord` | `agentlib/reply.py` | One tool call in `Reply.tool_calls`: `id, name, input, result, is_error` |
| `Tool` | `agentlib/tools.py` | A custom tool: `name, description, schema, handler, ends_turn, read_only`; `await t.call(args) -> (text, is_error)` |
| `tool` | `agentlib/tools.py` | Decorator `@tool` / `@tool(name=, description=, schema=, ends_turn=, read_only=)` -> `Tool` |
| `load_claude_agent` | `agentlib/loaders/claude.py` | `.claude/agents/<name>.md` -> `Agent` |
| `load_cursor_agent` | `agentlib/loaders/cursor.py` | `.cursor/agents/<name>.md` -> `Agent` (runs on claude engine for now) |
| `Question` | `agentlib/questions.py` | An `ask_user` question: `id, question, why, options, recommended, multi_select`; `.to_dict()` |
| `Answer` | `agentlib/questions.py` | An answer: `id, answer, kind` (`option \| recommended \| free_text \| skipped`) |
| `PermissionRequest` | `agentlib/permissions.py` | Passed to `on_permission`: `agent, tool, input, reason` |
| `Event` | `agentlib/events.py` | Type alias: union of the six event classes |
| `TextDelta` | `agentlib/events.py` | `.type == "text_delta"`: live text chunk (top-level agent only) |
| `Text` | `agentlib/events.py` | `.type == "text"`: a finished text block |
| `ToolCall` | `agentlib/events.py` | `.type == "tool_call"`: `id, name, input` |
| `ToolResult` | `agentlib/events.py` | `.type == "tool_result"`: `id, name, text, is_error` |
| `RateLimit` | `agentlib/events.py` | `.type == "rate_limit"`: `status, resets_at, utilization, limit_type` |
| `Done` | `agentlib/events.py` | `.type == "done"`: last event, `.reply` |
| `AgentError` | `agentlib/errors.py` | Base error for infrastructure failures (process died, timeout, sign-in); `.short`; `.reply` (partial `Reply` when a turn failed midway: text/tool calls so far, best-effort usage, `cost_usd` 0; else `None`) |
| `AgentFileError` | `agentlib/errors.py` | Agent/skill file missing or bad, or a listed custom tool has no function |
| `CapabilityError` | `agentlib/errors.py` | Agent needs something its (available) engine cannot do; raised by `agent.session()` |
| `ConversationMissing` | `agentlib/errors.py` | `resume=` id not found (wrong id or different cwd) |
| `EngineUnavailable` | `agentlib/errors.py` | Unknown engine name, or a stub engine (cursor: raised by `agent.session()`, message lists what it would also lack) |
| `QuestionShapeError` | `agentlib/errors.py` | Bad question/answer shape (subclass of `ValueError`, not `AgentError`) |
| `get_engine` | `agentlib/engines/__init__.py` | `get_engine(name) -> Engine` (cached instance) |
| `register_engine` | `agentlib/engines/__init__.py` | `register_engine(name, factory)` adds or replaces an engine |
| `use_login_only` | `agentlib/auth.py` | Strip API-key env vars so the Claude Code login is used; returns names removed |
| `connection_status` | `agentlib/connection.py` | `connection_status(engine="claude") -> ConnectionStatus`; reads `setup/local.toml` + checks the install; sends nothing |
| `ConnectionStatus` | `agentlib/connection.py` | `engine, ok, method, summary, env_names, setup_file, setup_doc, version, problems, notes`; `.to_dict()`. Never holds secret values |
| `check_connection` / `check_connection_sync` | `agentlib/connection.py` | `await check_connection(engine="claude", *, model=None, timeout_s=90) -> CheckResult`: status, then one tiny message on the engine's cheapest model (Claude: haiku). Never raises for a failed connection |
| `CheckResult` | `agentlib/connection.py` | `ok, engine, status, sent, model, reply_text, cost_usd, duration_s, error, fix`; `.report()` (plain text the CLI prints), `.to_dict()` |
| `SetupError` | `agentlib/errors.py` | `setup/local.toml` is broken or points at something missing (raised when a session / `list_models` starts; nothing sent); message says what to fix |

Useful non-root imports: `agentlib.fake` (fake engine: `script, say, call, ask, rate_limit, fail, spend, output,
models, reset, DEFAULT_MODELS, FakeEngine`),
`agentlib.engines` (`Capabilities, Engine, EngineSession, TurnState, EngineSetup, Connection, get_setup,
register_setup`; `agentlib.engines.base.requirements`), `agentlib.local_setup` (`connection, require,
setup_file, read`), `agentlib.connection.CHECK_AGENT` (agent name the check uses; script it on the fake engine),
`agentlib.tools.DEFAULT_SERVER`,
`agentlib.structured` (`check_output, check_schema, validate, parse_text`: shared JSON checking for engines),
`agentlib.engines.claude.sdk_version`.

## I want to... -> use...

| I want to... | Use | Example |
|---|---|---|
| Ask once and get an answer | `agent.ask_sync(msg)` / `await agent.ask(msg)` | `examples/01_one_shot.py` |
| Hold a conversation | `async with agent.session() as s: await s.send(msg)` | `examples/02_multi_turn_session.py` |
| Continue a conversation after a restart | save `s.session_id` (+ `reply.total_cost_usd`); `agent.session(resume=id, cost_base=total)` | `examples/02_multi_turn_session.py` |
| Branch a conversation | `agent.session(resume=id, fork=True)` | `examples/02_multi_turn_session.py` |
| Show live output in a UI | `async for ev in s.stream(msg)`; `ev.to_dict()` for JSON | `examples/03_streaming_events.py` |
| Stop a running turn | `await s.interrupt()` | - |
| Give the agent a Python function | `@tool` + `Agent(tools=[fn])` | `examples/04_custom_tools.py` |
| End the turn right after a tool succeeds | `@tool(ends_turn=True)` | `examples/04_custom_tools.py` |
| Let the agent ask the user material questions | `ask_user` (automatic when `tools` is None, else list `"ask_user"`); check `reply.status == "needs_input"`; `s.answer({...})` | `examples/05_ask_user.py` |
| Answer questions after a restart | `agent.session(resume=id)` then `s.answer(answers, questions=saved_dicts)` | `examples/05_ask_user.py` |
| Approve/deny tools at run time | `Agent(on_permission=fn)` | `examples/06_permissions.py` |
| Allow only some shell commands | `tools=["Bash(git status:*)"]` (pre-approves matching commands only) | `examples/06_permissions.py` |
| Use an external MCP server | `Agent(mcp_servers={"name": config_or_path})` | `examples/07_external_mcp_server.py` |
| Reuse an agent file from Claude Code / Cursor | `load_claude_agent(...)` / `load_cursor_agent(...)` | `examples/08_agent_file.py` |
| Test an agent without spending tokens | `from agentlib import fake`; `fake.script(...)`; `engine="fake"` | `examples/09_test_with_fake_engine.py` |
| Behave like Claude Code in a folder (CLAUDE.md, settings, all built-ins) | `Agent(setup="project", cwd=...)` | - |
| Give the agent skills | `Agent(skills=["name"])` (folder `<cwd or ~>/.claude/skills/<name>/SKILL.md` or `.cursor/skills`) | - |
| Track spend | `reply.cost_usd`, `reply.total_cost_usd`, `reply.usage` | `examples/01_one_shot.py` |
| Cap what a run may spend | `Agent(max_budget_usd=...)`; check `reply.error_kind == "budget"` | `examples/10_spending_cap.py` |
| Run non-interactively (deny anything not pre-approved) | `Agent(permission_mode="never_ask")` | `examples/11_never_ask.py` |
| Fill a model menu without spending tokens | `list_models_sync("claude")` / `await list_models("claude")` | `examples/12_list_models.py` |
| Get a reply in a fixed JSON shape (one-shot, no tools, nothing saved) | `ask_structured_sync(msg, schema, ...)` -> `reply.data`; or `Agent(output_schema=...)` | `examples/13_structured_output.py` |
| Run without saving the conversation | `Agent(save_conversation=False)` | `examples/13_structured_output.py` |
| Force subscription login | `use_login_only()` at app start | - |
| Set up how I sign in (login, company settings file, gateway variables) | `setup/local.toml` from `setup/local.example.toml`; guide `setup/claude-setup.md` | `setup/local.example.toml` |
| Check that my engine works | `python -m agentlib.check` (`--status` = free, sends nothing) | - |
| Show sign-in status / a "Test connection" button in an app | `connection_status(engine)`; `check_connection_sync(engine)` -> `result.ok`, `.report()` | `examples/14_connection_check.py` |
| Check what an engine supports | `get_engine("cursor").capabilities`; `get_engine(name).check(agent)` raises before a run | - |
| See which tools / MCP servers a session actually got | `s.info` after the first turn starts | `agentlib/tests/smoke_claude.py` |
| Keep usage from a failed turn | `except AgentError as e: e.reply` (may be `None`) | `examples/09_test_with_fake_engine.py` |
| Do something agentlib does not expose | add it via [EXTENDING.md](EXTENDING.md); never import `claude_agent_sdk` | - |

## Key behaviour
- `setup="lean"` (default): no folder settings, no CLAUDE.md, no auto-memory, no slash commands, strict MCP,
  only listed tools. `setup="project"`: like Claude Code in `cwd` (claude_code system prompt + your
  instructions appended, user/project/local settings, native skills, all built-ins unless `tools` narrows them)
- `tools` absent (`None`) = all given custom tools + `ask_user` (+ all built-ins in project setup). An explicit
  list gives exactly that list: add `"ask_user"` yourself if wanted
- Tool permissions: listed tools are pre-approved; anything else -> `on_permission`, or denied if none
  (same as headless Claude Code). In lean setup an unlisted built-in is not even offered.
  `permission_mode="never_ask"` denies anything not pre-approved without any callback (Claude `dontAsk`)
- Structured output (`output_schema`): Claude uses its native JSON-schema output (the CLI's internal
  `StructuredOutput` tool is hidden from events and `tool_calls`); the value is checked again with `jsonschema`.
  Engines without a native option would parse the reply text (`structured.check_output`). `Reply.text` may be
  empty; the answer is in `Reply.data`
- `list_models()` on Claude starts and stops a `claude` process (a few seconds), sends no request
- `ask_user` = material questions (scope, data, decisions), not permissions. Calling it ends the turn:
  `Reply.status == "needs_input"`, `Reply.questions`. Answer with `s.answer(...)`; unanswered ids -> skipped
- Answer shapes: `{id: "text"}` | `[Answer | {id, answer, kind}]` | `{"answers": [...]}`. `kind` is inferred if
  omitted (matches `recommended` -> recommended, in `options` -> option, else free_text).
  `kind="recommended"` with no answer (missing, `None`, `True`, `""`) = the question's recommended text
  (skipped if the question has none)
- A broken custom tool (exception) becomes an error tool result; the turn continues
- Tool return: `str`; `dict`/`list` -> JSON; `None` -> `"ok"`. Sync handlers run in a thread
- Skills in lean setup: names + descriptions go into the prompt; `Read` is added (if not listed) but limited to
  the skill folders. Search: `<cwd>/.claude/skills`, `<cwd>/.cursor/skills`, `~/.claude/skills`, `~/.cursor/skills`
- Infrastructure failures raise `AgentError`; a model run that ends badly (spending cap, max turns, a reply that
  does not match `output_schema`, an API error) returns `Reply(status="error")` so usage is not lost;
  `Reply.error_kind` says which (`budget`, `max_turns`, `output_shape`, `other`). A turn that fails midway (timeout, process died) puts the
  partial turn in `AgentError.reply` (usage summed from the model calls seen; cost unknown -> `cost_usd` 0).
  After a failure the next turn reconnects with resume
- Agent file loaders: `tools:` line absent -> not specified (see above); `model: inherit` -> loader's `model=`
  or engine default; unknown front-matter fields kept in `agent.extra`; `agent.warnings` lists problems
  (e.g. body mentions files but no `Read` tool). Lookup: `<project>/.claude/agents/<name>.md` then `~/.claude/agents/`

## Gotchas
- Custom tools are served from one in-process MCP server named `Agent.tool_server`, default `DEFAULT_SERVER`
  = `"agentlib"` in `agentlib/tools.py`. The model sees `mcp__agentlib__<tool>`, e.g. `mcp__agentlib__run_sql`.
  Events, `Reply.tool_calls`, `PermissionRequest.tool` and `s.info.tools` use the short name; external MCP
  tools keep their full `mcp__<server>__<tool>` name
- The default server name changed on 2026-11-12 (it was the name of the first app that used agentlib).
  Sessions saved before that reference the old `mcp__<old>__...` tool names in their history; resumed, the
  model may call an old name, which no longer exists (unknown-tool error). To resume such a session
  unchanged, pass `Agent(tool_server="<old name>")` for it
- `load_claude_agent(tools=[...])` / `load_cursor_agent(tools=[...])` take Python implementations, not a tool
  list; the list comes from the file
- `ask_sync()` calls `asyncio.run()`: it cannot be used inside a running event loop (use `await agent.ask()`)
- `agent.ask()` starts a new conversation every call; use a session for memory
- `cost_usd` is exact only if you pass `cost_base=` when resuming; on a subscription costs are estimates
- `s.info` is empty until the first turn starts (the Claude CLI reports its init message then)
- Fake engine vs Claude: built-in rules are matched like Claude Code (`agentlib/fake/rules.py`: Bash
  wildcards and compound commands, Read/Edit paths, `WebFetch(domain:...)`, `disallowed_tools` deny) but not
  Claude's built-in read-only Bash commands that need no rule, wrapper stripping, or settings files;
  `setup="project"` with `tools=None` approves every built-in. Scripts may call built-ins the real model
  would not be offered (they go to `on_permission`). No external MCP servers (`CapabilityError`).
  Claude Code runs some read-only shell commands (e.g. `python --version`) with no rule even under
  `never_ask`; the fake denies them. The fake does not enforce `max_turns`
- Spending cap on Claude: the CLI checks its running total between model calls, per opened session (one
  `claude` process); a run may overshoot by one call. After an error result the process is dropped and the
  next turn reconnects with resume (and a fresh cap)

## Engines
- Registry (`agentlib/engines/__init__.py`): `register_engine(name, factory)`; `get_engine(name)` builds and
  caches. `claude` and `cursor` are registered at import (lazily imported); `fake` registers when
  `agentlib.fake` is imported. Unknown name -> `EngineUnavailable`
- Interface (`agentlib/engines/base.py`): `Engine.open(agent, resume, fork, cost_base) -> EngineSession`
  with `start / turn(message) -> async events ending in Done / interrupt / close`; `TurnState` runs custom
  tools + `ask_user` identically for every engine and builds the `Reply`
- `Capabilities` (frozen dataclass): `available, system_prompt, custom_tools, mcp_servers, streaming, resume,
  fork, usage, ends_turn, permission_hook, project_setup, budget, never_ask, structured_output, unsaved,
  list_models`. `Engine.check()` runs in `agent.session()` before
  anything starts: `available` False -> `EngineUnavailable` (message lists what else it would lack); else
  `CapabilityError` naming every needed capability the engine lacks. Needs (`requirements()` in `base.py`):
  `system_prompt` (instructions set, or skills in lean setup), `custom_tools` (any `@tool` or `ask_user`),
  `ends_turn` (`ask_user` or `@tool(ends_turn=True)`), `mcp_servers`, `resume` (`resume=`), `fork`,
  `permission_hook` (`on_permission`), `project_setup`, `budget` (`max_budget_usd`), `never_ask`
  (`permission_mode="never_ask"`), `structured_output` (`output_schema`), `unsaved` (`save_conversation=False`).
  `list_models` is checked by `list_models()` (`Engine.check_list_models()`). `streaming` and `usage` are
  informational only
- Sign-in side (`EngineSetup` in `agentlib/engines/base.py`, registry `register_setup` / `get_setup`): one per
  engine, SDK-free so status works without the engine's package. `resolve(section)` turns the engine's
  `[section]` of `setup/local.toml` into a `Connection(method, summary, env, engine_settings, problems,
  notes)`; also `doc`, `check_model`, `prerequisites()`, `version()`, `fix_for(error)`. Engines call
  `local_setup.require(name)` when they start a process (`SetupError` on problems). Claude: `ClaudeSetup`
  (`engines/claude_setup.py`); fake: `FakeSetup` (only `[fake] auth = "none"`); others get the generic one
  (nothing to set up)

| Engine | File | State | Capabilities that differ from defaults |
|---|---|---|---|
| `claude` | `agentlib/engines/claude.py` | working; the only `claude_agent_sdk` importer | `fork`, `permission_hook`, `budget`, `never_ask`, `structured_output`, `unsaved`, `list_models` all True |
| `cursor` | `agentlib/engines/cursor.py` | stub: `agent.session()` raises `EngineUnavailable` | `available=False`, `system_prompt=False`, `ends_turn=False` (new flags False, unverified) |
| `fake` | `agentlib/fake/engine.py` | working, tests only, zero tokens | same as claude, plus `mcp_servers=False` |

- Cursor plan (stub header): Cursor Python SDK (`cursor-sdk`, beta); no app-set system prompt (AGENTS.md +
  message prefix), no live permission hook, no fork, sync API (wrap in `asyncio.to_thread`), own model names.
  Until then `load_cursor_agent` defaults to the claude engine (`DEFAULT_ENGINE` in `agentlib/loaders/cursor.py`)
- Fake engine: `fake.script(agent_name, turns)`; steps `say, call, ask, rate_limit, fail`; a turn may be
  `fn(message) -> steps`. `call()` runs your real tool through `TurnState`; built-in names go through
  Claude-style rules. No script -> `"(fake) <message>"`. Resume works within one Python process.
  `total_cost_usd` is cumulative per conversation and `cost_usd` honours `cost_base` like the Claude engine.
  `fail()` raises `AgentError` with `.reply`. `s.info` mirrors Claude's. `fake.reset()` between tests
- Fake run controls: `fake.spend(usd)` step adds cost; `max_budget_usd` is checked after every step against the
  opened session's spend -> stops with `error_kind="budget"`. `permission_mode="never_ask"`: built-ins not
  pre-approved are denied. `fake.output(data)` = the model's structured reply (else the turn's text is parsed)
  -> `Reply.data` or `error_kind="output_shape"`. `save_conversation=False`: nothing stored (resume ->
  `ConversationMissing`). `fake.models([...])` scripts `list_models("fake")` (ModelInfo / dict / id string),
  `fake.models(fail="msg")` makes it raise `AgentError`; default `fake.DEFAULT_MODELS` (`fake-large`, `fake-small`)

## Not yet supported
Do not reach for the raw SDK for these; add them via [EXTENDING.md](EXTENDING.md) (or tell the user if they
cannot be made engine-neutral).
- Subagents (`agents=` / `AgentDefinition`, the Task tool); subagent messages are filtered out of events
- User-facing hooks (`hooks=`); hooks are used internally only
- Other `permission_mode` values (acceptEdits, plan, bypassPermissions, auto) and `set_permission_mode()`
  (`default` and `dontAsk` are supported, as `"default"` / `"never_ask"`)
- Limits: `task_budget` (`max_budget_usd` is supported)
- Model controls: `fallback_model`, `set_model()` mid-session, `thinking` / `max_thinking_tokens` (`effort` is supported), `betas`
- Structured output extras: `output_format` types other than `json_schema` (JSON-schema output is supported via
  `output_schema`)
- Non-text input (images, documents); `send()` takes a string only. Streaming input
- Thinking blocks, server tool blocks (web search), task/progress messages, non-init system messages as events
- `ResultMessage` extras: `model_usage` (per-model usage), `permission_denials`, `duration_api_ms`
- Session management: `list_sessions`, `get_session_messages`, rename/tag/delete, `session_store`,
  `continue_conversation`, `resume_session_at`
- File checkpointing / `rewind_files`
- Runtime MCP control: `get_mcp_status`, `toggle_mcp_server`, `reconnect_mcp_server`; `get_context_usage`;
  the rest of `get_server_info` (its model list is `list_models()`; startup info is `s.info`)
- `sandbox`, `plugins`, `settings` (custom settings file; only its sign-in parts are used, via `setup/local.toml`),
  `cli_path`, `user`, `stderr` / `debug_stderr`

## Where to edit
Paths are inside the `agentlib/` package folder unless stated.

| To change | File |
|---|---|
| Agent fields / ask / session entry points | `agent.py` |
| send / stream / answer / interrupt | `session.py` |
| `@tool`, schema from type hints, tool-name resolution, `DEFAULT_SERVER` | `tools.py` |
| Question + answer shape, validation | `questions.py` |
| Wording the model sees (ask_user, answers, skills list) | `prompts/*.md` (loaded by `prompt_files.py`) |
| Live event types | `events.py` |
| Reply / Usage fields | `reply.py` |
| Errors | `errors.py` |
| Sign-in: process env stripping | `auth.py` |
| Sign-in: finding / reading the local setup file | `local_setup.py` |
| Sign-in: what the `[claude]` section means (settings-file keys passed through, fix hints) | `engines/claude_setup.py` (SDK-free) |
| Status, connection check, the `python -m agentlib.check` command | `connection.py`, `check.py` (message text: `prompts/connection_check.md`) |
| Setup guides and the local setup template (repo root) | `setup/<engine>-setup.md`, `setup/local.example.toml` |
| Claude Code / Cursor file parsing | `loaders/claude.py`, `loaders/cursor.py` (shared: `loaders/common.py`, `loaders/frontmatter.py`) |
| Skill lookup (lean setup) | `skills.py` |
| Permission hook shape | `permissions.py` |
| Structured output checking, `ask_structured` | `structured.py` |
| Model list (`ModelInfo`, `list_models`) | `models.py` (Claude parsing: `parse_models` in `engines/claude.py`) |
| Claude SDK options, message mapping | `engines/claude.py` |
| Cursor engine (stub today) | `engines/cursor.py` |
| Engine interface, Capabilities, shared turn bookkeeping | `engines/base.py` |
| Engine registry | `engines/__init__.py` |
| Fake engine (scripted tests) | `fake/engine.py` (permission-rule matching: `fake/rules.py`) |
| Unit tests | `tests/`, `fake/tests/` |
| Runnable samples (repo root) | `examples/` |
| How to add features (repo root) | `EXTENDING.md` |

## Test
- Setup (from this folder): `pip install -e .[dev]`
- Unit (free, from this folder): `python -m pytest` (collects `agentlib/` only)
- Example test (free): `python -m pytest examples/09_test_with_fake_engine.py`
- Live (Haiku, ~$0.01): `python -m agentlib.tests.smoke_claude`
- Live connection check (Haiku, a fraction of a cent): `python -m agentlib.check`
- Tests never read your `setup/local.toml`: `agentlib/conftest.py` points `AGENTLIB_SETUP_FILE` at an empty temp file
- Needs: Claude Code installed and logged in (live test and real use)
