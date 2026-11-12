# agentlib examples

One task per script, heavily commented. Run from the repo root (agentlib installed: `pip install -e .`).

**Cost rule: nothing spends tokens unless you pass `--live`.** Without it every script runs on the fake
engine (zero tokens, no login). With `--live` it runs on Claude with `model="haiku"` using your Claude Code
login, or whatever sign-in your `setup/local.toml` says (LIVE: costs tokens, roughly a cent per script). The agent code is identical on both engines; only
`engine=` and the fake script differ.

| # | File | Shows | Free run |
|---|---|---|---|
| 01 | `01_one_shot.py` | Smallest agent: `Agent(...)`, `ask_sync`, reading `Reply` (status, text, usage, cost, session id) | yes |
| 02 | `02_multi_turn_session.py` | `agent.session()`, `send`, resume by id with `cost_base`, `fork=True` | yes |
| 03 | `03_streaming_events.py` | `s.stream()`: `TextDelta`, `Text`, `ToolCall`, `ToolResult`, `RateLimit`, `Done`; `to_dict()` | yes |
| 04 | `04_custom_tools.py` | `@tool` (type hints -> schema), `read_only`, `ends_turn`, async tools, exceptions -> error results | yes |
| 05 | `05_ask_user.py` | `ask_user` parks (`needs_input`), save questions, resume and `answer(..., questions=)` | yes |
| 06 | `06_permissions.py` | `on_permission` allow/deny for tools that are not pre-approved; `Bash(echo:*)` rules | yes |
| 07 | `07_external_mcp_server.py` | `mcp_servers=` with a Python stdio server (`07_notes_server.py`) | **LIVE only** (`--live`); free run shows the fake engine's `CapabilityError` (no external MCP) |
| 08 | `08_agent_file.py` | `load_claude_agent` from `.claude/agents/word_counter.md`; `load_cursor_agent` from `.cursor/agents/reviewer.md` | yes |
| 09 | `09_test_with_fake_engine.py` | pytest tests for an agent using `agentlib.fake` (tools, ask_user, rules, `AgentError.reply`, capability checks) | `python -m pytest examples/09_test_with_fake_engine.py` |
| 10 | `10_spending_cap.py` | `Agent(max_budget_usd=)`; a cap stop is `status == "error"`, `error_kind == "budget"`; `fake.spend()` | yes |
| 11 | `11_never_ask.py` | `Agent(permission_mode="never_ask")`: unlisted tools denied, nobody asked | yes |
| 12 | `12_list_models.py` | `list_models_sync(engine)` -> `ModelInfo` list for a model menu; `fake.models()` | yes (`--live` starts Claude Code but spends no tokens) |
| 13 | `13_structured_output.py` | `ask_structured_sync(msg, schema)` -> `reply.data`; malformed -> `error_kind == "output_shape"`; `fake.output()` | yes |
| 14 | `14_connection_check.py` | `connection_status(engine)` for a settings screen; `check_connection_sync(engine)` for a "Test connection" button (`.ok`, `.error`, `.fix`, `.report()`); `--fail` scripts a failure | yes (`--live` sends one tiny Haiku message) |

```
python examples/01_one_shot.py          # fake, free
python examples/01_one_shot.py --live   # LIVE: Claude haiku, costs tokens
```

Supporting files:
- `07_notes_server.py`: tiny MCP server (uses the `mcp` package that claude-agent-sdk installs; mcp 1.x and 2.x)
- `.claude/agents/word_counter.md`: sample Claude Code agent file (with a custom tool and `ask_user`)
- `.cursor/agents/reviewer.md`: sample Cursor agent file (`readonly: true`, non-Claude model -> warning)

Notes:
- 06 uses the same `tools=["Bash(echo:*)"]` on both engines: the fake engine matches permission rules like
  Claude Code (`agentlib/fake/rules.py`), so only `echo ...` is pre-approved and other commands ask.
- 09 is not collected by a plain `python -m pytest` at the repo root (`testpaths = agentlib`); pass its path.
