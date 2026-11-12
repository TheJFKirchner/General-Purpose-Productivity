# Extending agentlib

How to add something agentlib does not expose yet, so it stays engine-neutral. Read the README's
"Not yet supported" list first; it names the raw SDK features known to be missing.

## The rules
1. `claude_agent_sdk` is imported only in `agentlib/engines/claude.py`. Never in agent code, never in other
   library modules, never in a project that uses agentlib.
2. The public surface (`Agent`, `Session`, `Reply`, events, `@tool`, ...) uses engine-neutral names and
   shapes. No SDK types cross it (convert SDK objects to agentlib dataclasses inside the engine).
3. Every feature is declared in `Capabilities`, so an engine that cannot do it raises `CapabilityError`
   before a run instead of silently ignoring it.
4. The fake engine mirrors every behaviour, so projects can test it at zero cost.
5. Model-facing text the library adds goes in `agentlib/prompts/<name>.md`, loaded with
   `prompt_files.load(name)` / `prompt_files.fill(name, key=value)` (placeholders `{key}`).
6. If something truly cannot be expressed engine-neutrally (it only makes sense as a Claude SDK object, or
   the neutral version would mislead), **stop and tell the user**. Do not add an escape hatch to the raw SDK.

## The engine interface (`agentlib/engines/base.py`)

```
Engine                                   # one instance per engine name (cached by get_engine)
  name: str
  capabilities: Capabilities
  open(agent, *, resume, fork, cost_base) -> EngineSession     # abstract
  check(agent, *, fork=False, resume=False)  # EngineUnavailable / CapabilityError; Agent.session() calls it before open()

EngineSession                            # one conversation
  session_id: str | None
  info -> SessionInfo                    # property; default empty. tools offered (custom: short names), mcp_servers, model
  async start()                          # abstract; connect (Session.__aenter__)
  turn(message) -> AsyncIterator[Event]  # abstract; async generator, MUST end with Done(reply)
  async interrupt()                      # default: no-op
  async close()                          # abstract (Session.__aexit__)

TurnState(engine_name, tools)            # per-turn bookkeeping shared by all engines
  await run_tool(name, args) -> (text, is_error)   # runs a custom Tool or validates ask_user; sets stop_requested
  record_text(text) / record_call(id, name, input) / record_result(id, text, is_error) -> name
  message_ids: set[str]                  # distinct model calls (-> Reply.api_calls)
  usage_by_message: dict[str, Usage]     # latest usage per model call; usage_so_far() sums it
  stop_requested: bool                   # True after ask_user or an ends_turn tool: end the turn now
  reply(session_id=, usage=, cost_usd=, total_cost_usd=, model=, stop_reason=, error=, api_calls=) -> Reply
```

When a turn fails midway, raise `AgentError(msg, reply=state.reply(..., usage=state.usage_so_far(),
cost_usd=0.0, error=msg))` so callers keep the partial turn (`ClaudeSession._failed_reply()` does this).

How a turn flows: `Session.stream()` -> `EngineSession.turn()`. The engine creates a `TurnState` with
`agent.resolved_tools().custom`, maps whatever its SDK emits to agentlib events (`agentlib/events.py`),
routes custom tool calls through `state.run_tool()`, records text/calls/results, and finishes with
`Done(state.reply(...))`. `Reply.status` is derived there: `error` if `error=` is set, `needs_input` if
`ask_user` produced questions, else `done`.

`Capabilities` (frozen dataclass, same file): `available, system_prompt, custom_tools, mcp_servers, streaming,
resume, fork, usage, ends_turn, permission_hook, project_setup`. `requirements(agent, fork=, resume=)` (same
file) maps capability name -> "does this agent/call need it"; `Engine.check()` enforces every name in it:
`system_prompt, custom_tools, ends_turn, mcp_servers, resume, fork, permission_hook, project_setup`.
`available=False` raises `EngineUnavailable` first (listing what else is missing). `streaming` and `usage`
are informational (no request can require them).

Registry (`agentlib/engines/__init__.py`): `register_engine(name, factory)`, `get_engine(name)`. Built-in
engines are registered with lazy factories so their SDKs import only when used.

## Recipe: add an Agent option (example: a spend cap, `max_budget_usd`)

1. **Agent field** - `agentlib/agent.py`: add `max_budget_usd: float | None = None` with a short comment.
   Neutral name and units (no SDK wording). Default must mean "off" so existing agents are unchanged.
2. **Capability** - `agentlib/engines/base.py`: add `budget: bool = False` to `Capabilities` (default False:
   an engine only claims it explicitly). Add `"budget": agent.max_budget_usd is not None` to the dict
   returned by `requirements()` (enforced by `Engine.check()`).
3. **Claude engine** - `agentlib/engines/claude.py`:
   - `ClaudeEngine.capabilities = Capabilities(fork=True, permission_hook=True, budget=True)`
   - map it in `ClaudeSession.options()`: `if a.max_budget_usd is not None: kw["max_budget_usd"] = a.max_budget_usd`
   - if it changes results, map them in `_turn()` / `_map()` (e.g. a budget stop arrives as
     `ResultMessage.is_error` -> already becomes `Reply.status == "error"`)
4. **Other engines** - `agentlib/engines/cursor.py`: add `budget=False` (or True if Cursor can) to the
   explicit `Capabilities(...)` list, so the stub documents it. Cursor agents asking for it now raise
   `CapabilityError`.
5. **Fake engine** - `agentlib/fake/engine.py`: `FakeEngine.capabilities` gets `budget=True` and
   `FakeSession.turn()` imitates the behaviour (e.g. stop with `error="budget exceeded"` when
   `self.total_cost > agent.max_budget_usd`). If it is a new kind of scripted event, add a step dataclass +
   helper (like `rate_limit()`) and export it from `agentlib/fake/__init__.py`.
6. **Loaders** (only if agent files have a standard field for it) - `agentlib/loaders/claude.py` /
   `cursor.py`: map the front-matter key and add it to `KNOWN`. Library-only settings stay out of files;
   users pass them as loader keyword overrides.
7. **Tests** (all zero-token):
   - option mapping: `agentlib/tests/test_claude_options.py` style,
     `ClaudeSession(agent, resume=None, fork=False, cost_base=0).options(resume=None)` builds the SDK options
     without starting a process
   - behaviour: `agentlib/fake/tests/test_fake_sessions.py` style, scripted fake turns
   - capability: an engine without it raises `CapabilityError` from `agent.session()` (add a row to
     `CASES` in `agentlib/tests/test_capabilities.py`)
   - optional live check: extend `agentlib/tests/smoke_claude.py` (run by hand, costs ~1 cent)
8. **Docs** - `README.md`: the lookup table row (raw SDK thing -> agentlib -> file), the `Agent` field table,
   the "I want to" table, remove it from "Not yet supported", and the public exports table if you exported
   anything from `agentlib/__init__.py` (add to `__all__` too). Add or extend an example in `examples/`
   that runs on the fake engine, and its row in `examples/README.md`.

## Other kinds of addition

| Adding | Touch |
|---|---|
| A new live event (e.g. thinking text) | `agentlib/events.py` (dataclass with `type: ClassVar[str]`, add to `Event` union, export in `__init__.py`); emit in `ClaudeSession._map()`; fake step; `Capabilities` flag if not every engine can produce it; README events rows; `examples/03_streaming_events.py` |
| A new `Reply` / `Usage` field | `agentlib/reply.py` (with a default); fill it via `TurnState.reply(...)` (add a keyword) from each engine; fake gives a plausible value; README `Reply` row |
| A new session operation (e.g. change model mid-session) | `EngineSession` in `base.py`: a method with a safe default (raise `CapabilityError` naming the engine); implement in `ClaudeSession` (must run on the worker task that owns the client: send it through `self._ops`); fake version; `Session` wrapper in `agentlib/session.py`; capability flag |
| A new tool flag | `Tool` + `tool()` in `agentlib/tools.py`; engine mapping in `ClaudeSession._build_server()`; shared behaviour in `TurnState.run_tool()` so every engine gets it |
| Model-facing wording | `agentlib/prompts/<name>.md`; `prompt_files.fill()`; never inline strings |
| A new error | subclass `AgentError` in `agentlib/errors.py`; raise it from the engine when the SDK error is recognised; export it |

Claude engine notes that bite: one `ClaudeSDKClient` per session, owned by a single worker task
(`_run()`); anything touching the client goes through `self._ops`. Long system prompts (>30K chars) go
through a temp file because of the Windows command-line limit. Lean setup must stay lean: any new option
that loads folder state belongs only in the project branch of `options()`.

## Adding the Cursor engine later
From the header of `agentlib/engines/cursor.py`:
- Use the Cursor Python SDK (`cursor-sdk`, beta): `Agent.create` / `send` / `on_delta`, `custom_tools`
- Only `engines/cursor.py` may import it; register stays lazy (already `register_engine("cursor", _cursor)`)
- Known gaps to handle: no app-set system prompt (write instructions to AGENTS.md in cwd + a message
  prefix), no live permission hook, no fork, synchronous API (wrap calls in `asyncio.to_thread`), its own
  model names (map aliases)
- `ends_turn` is unverified: `ask_user` parking may need a tool result telling the agent to stop
- Steps: implement `CursorSession(EngineSession)` using `TurnState` for custom tools and `ask_user`; map its
  stream to the six events; build `Usage` with the same field names; set `available=True` and correct the
  other flags in `CursorEngine.capabilities` (`system_prompt` / `ends_turn` are enforced: if the engine
  emulates them via AGENTS.md or a "stop now" tool result, set them True, otherwise every agent with
  instructions / `ask_user` raises `CapabilityError`); add `requirements()` entries for any new capability
  agents can request; override `info` from Cursor's startup data if it has any; switch `DEFAULT_ENGINE` in `agentlib/loaders/cursor.py` to `"cursor"`;
  add a hand-run smoke test like `agentlib/tests/smoke_claude.py`; update the README engines table
- The examples should then run with `engine="cursor"` unchanged, except for features the capabilities
  table says Cursor lacks (those must raise `CapabilityError`, not misbehave)

## Checklist
- [ ] No `claude_agent_sdk` import outside `agentlib/engines/claude.py`
- [ ] Agent field / API name is engine-neutral; default keeps old behaviour
- [ ] `Capabilities` flag added, set on claude, cursor and fake engines, listed in `requirements()`
- [ ] Fake engine mirrors it
- [ ] Zero-token tests added; `python -m pytest` passes
- [ ] README tables updated (lookup, fields, exports, I want to, Not yet supported); example added
- [ ] If it could not be made engine-neutral: stopped and told the user
