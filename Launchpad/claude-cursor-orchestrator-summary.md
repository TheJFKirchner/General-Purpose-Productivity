# Claude + Cursor Orchestrator: Design Summary

Goal: one Python orchestrator where the user picks Claude or Cursor per role (planner, worker), and each worker uses that harness's built-in capabilities.

## Core model
- Python only **launches** workers. Each worker is a full top-level session opened in a target folder (`cwd`). It uses that harness's own file and shell tools, so workers can write SQL, Python or JS, run `npm`, and so on.
- Each worker loads its folder's setup: `CLAUDE.md` / `AGENTS.md`, `.claude/skills`, `.cursor/rules`, hooks.
- The orchestrator plays the "parent agent" role in code: it plans, dispatches, checks the output, then moves to the next task.
- Harnesses never share a conversation. The handoff is files on disk (a plan file plus each task's output).

## Worker vs. subagent (latest decision)
| | Claude subagent | SDK worker (recommended) |
|---|---|---|
| Who starts it | A Claude session, mid-task | Your orchestrator |
| System prompt | Only its own prompt plus environment details; already lean | Whatever you pass |
| Trimming | `omitClaudeMd: true`, short `tools:` list | `system_prompt="..."`, `setting_sources=[]`, short `allowed_tools` |
| Reports to | Parent session | Your Python code |
| Works for Cursor too | No | Yes |

- Prefer the SDK over calling `claude -p`: same engine, typed results, no output parsing.
- Claude SDK: leaving `system_prompt` out gives a **minimal** prompt, not the full Claude Code one. Use the `claude_code` preset to match the command-line tool.
- Cursor: a custom system prompt is allowed, but tool schemas, rules and skills still load. To keep it lean, use a clean folder and few tools.

## Capability comparison
| | Claude Agent SDK | Cursor SDK (beta) |
|---|---|---|
| Custom tools in code | `@tool` + `create_sdk_mcp_server` | `CustomTool` in `custom_tools` (local only) |
| Whole MCP server | `mcp_servers` + `allowed_tools=["mcp__name__*"]` | `mcp_servers`; no allow list needed |
| Multi-turn | `ClaudeSDKClient` (`query` again in the same client) | Same `Agent` object, call `send()` again |
| Resume later | `resume=session_id` (can fork) | `Agent.resume(agent_id)` (no fork) |
| Shell limits | Per command: `Bash(npm run build:*)` | All-or-nothing; per-command needs a `.cursor/hooks.json` hook |
| Hooks / approval callback | Yes, in code | Hook files only; no approval callback |
| Structured output | `output_format` JSON schema | None; use a `submit_result` tool and validate it yourself |
| Calls | async | sync (wrap in `asyncio.to_thread`) |
| Sign-in | Company login through the gateway | `CURSOR_API_KEY` (user or service account) |

## Shared library shape (`agentkit`)
```python
worker = Agent(harness="claude" | "cursor", cwd="target/folder",
               role="sql_builder" | "dashboard_builder",
               system="lean task prompt",
               tools=[ask_user_important_question],
               mcp_servers={"databricks": "mcp_servers/databricks_server.py"})
async with worker.conversation() as c:
    reply = await c.send("Do T1 and T2 in plan/tasks.md")
```
The library translates per harness:
- roles into tool rules (`Bash` vs. `Shell`)
- Python functions into `@tool` or `CustomTool`
- MCP wildcards (added for Claude only)
- sync vs. async calls
- result shapes
- resume

## Design rules
1. Put tools in a standalone MCP server. Both SDKs and both IDEs can use it.
2. Put guardrails (read-only SQL, row limits) **inside the tools**, not in hooks. Cursor hooks are file-only and unreliable.
3. Keep shared content in `.claude/skills`, `.claude/agents` and `AGENTS.md`. Cursor reads these too.
4. The orchestrator owns task status. A task is done only if the agent says DONE **and** its output file exists.
5. Use roles instead of per-app permissions, e.g. `sql_builder` = `run_sql.py` only, `dashboard_builder` = `npm install` / `npm run build`. Don't let workers run `npm run dev`.

## Watch-outs
- **Data path:** Cursor inference goes through Cursor's servers; Claude goes through the company LiteLLM gateway to Bedrock. Get sign-off before running unattended work on claims data.
- **Long-waiting tools** (e.g. texting the user): raise `MCP_TOOL_TIMEOUT` for Claude. For long waits, prefer send-then-resume: save the session ID, end the turn, resume when the reply arrives.
- **Beta churn:** Cursor's Python SDK names may change. Pin versions and keep a small test that runs both adapters.
- **Cursor custom tools are local only.** They aren't available to Cursor cloud agents.
