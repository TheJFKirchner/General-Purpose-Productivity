# Research: Cursor vs Claude Agent SDK (for Mission Control / `agentlib`)

Answers the brief in `v1plan.md` section 9. Researched 2026-11-04.

**Scope change during research:** V1 now signs in with the user's own Claude subscription (the Claude Code login), not the LiteLLM gateway. So extra question (d), about LiteLLM caching, is dropped. The gateway part of Q8 is kept short. Subscription sign-in gets its own section (§2) because it turned out to matter.

---

## 1. Headline findings

1. **Anthropic's docs say an Agent SDK app should not use claude.ai subscription login unless Anthropic has approved it.** This affects the scope change directly (§2). Check it before building on subscription sign-in.
2. **The Agent SDK loads CLAUDE.md, skills and settings.json by default.** The app has to pass `setting_sources=[]` and a few env flags to stop this. The full recipe is in §5(b). It is all doable.
3. **Cursor now has an official Python SDK (`cursor-sdk`, beta, proprietary licence).** It fits this app much better than either the CLI print mode or ACP:
   - it can switch off every built-in tool
   - it takes Python functions as custom tools inside the app's own process
   - it reports input, output, cache-read and cache-write tokens for each turn
4. **Cursor cannot take app-set instructions today.** The CLI has no system-prompt flag. The SDK's `systemPrompt` option is "still unavailable for external accounts" (Cursor staff, 2026-10-22). The workaround is an `AGENTS.md` or rules file in a folder the app controls, plus repeating key instructions at the start of the message.
5. **Every Cursor request goes through Cursor's servers.** There is no documented way to point the Cursor agent at a company gateway. Whether that counts as an approved channel for claims data is a compliance question, not a technical one.

---

## 2. Subscription sign-in (the scope change)

| Question | Verdict | Evidence | Source |
|---|---|---|---|
| Does Anthropic allow an Agent SDK app to use claude.ai login? | **No for products given to other people. Unclear for a personal or internal tool.** | The SDK overview says: *"Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK."* The Legal page says developers building products "including those using the Agent SDK, should use API key authentication". It also says Anthropic does not permit routing requests "through Free, Pro, Max, or Ultra plan credentials on behalf of their users". The same page says Pro/Max/Ultra usage limits "assume ordinary, individual usage of Claude Code **and the Agent SDK**", so personal SDK use on a subscription is expected. Nothing on the page covers an internal tool where each employee uses their own Team or Enterprise seat. The page says to "contact sales" about permitted sign-in methods. | [SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) and [Legal and compliance → Authentication and credential use](https://code.claude.com/docs/en/legal-and-compliance). Both undated, fetched and quoted 2026-11-04. |
| Does the SDK use the stored Claude Code login? | **Yes** | The SDK starts the bundled CLI. If no other credential is set, the CLI falls back to the `/login` OAuth credentials, which is step 7 of 7 in its order. Where they are stored: on Windows `%USERPROFILE%\.claude\.credentials.json`; on macOS the Keychain. Moving `CLAUDE_CONFIG_DIR` moves where the CLI looks, so the existing login is lost. The order is: cloud provider variables → `ANTHROPIC_AUTH_TOKEN` → `ANTHROPIC_API_KEY` → `apiKeyHelper` → `CLAUDE_CODE_OAUTH_TOKEN` → profiles → `/login`. **Trap:** an `ANTHROPIC_API_KEY` in the environment always wins in non-interactive mode, and the SDK's `env` option is merged over the parent environment. So remove those variables from `os.environ` before starting the SDK. `claude setup-token` makes a one-year OAuth token for `CLAUDE_CODE_OAUTH_TOKEN`. | [Authentication](https://code.claude.com/docs/en/authentication) and [Env vars](https://code.claude.com/docs/en/env-vars). Undated, fetched 2026-11-04. |
| Do usage and limits still show up with a subscription? | **Partly** | Token counts come from the API response, so they appear the same way. `total_cost_usd` is a local estimate; for subscribers the docs call it "not relevant for billing". `RateLimitEvent` carries `status` (`allowed` / `allowed_warning` / `rejected`), `resets_at`, `utilization`, and a type such as `five_hour`, `seven_day` or `seven_day_opus`. That suits a "limit nearly reached" banner. A claude.ai login also loads the user's claude.ai MCP connectors. Block them with `strict_mcp_config=True` or `ENABLE_CLAUDEAI_MCP_SERVERS=false`. | [Python reference](https://code.claude.com/docs/en/agent-sdk/python), [Cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking), [Claude Code features](https://code.claude.com/docs/en/agent-sdk/claude-code-features) |
| How is data handled? | **Depends on plan** | **Team, Enterprise and API (commercial):** no training on Claude Code prompts; 30-day retention; zero data retention only as a per-organisation add-on for Claude for Enterprise. **Free, Pro, Max and Ultra (consumer):** used for training if the user's setting is on; 5-year retention if opted in, otherwise 30 days. **Claims data should only ever go through a commercial (Team or Enterprise) seat.** | [Data usage](https://code.claude.com/docs/en/data-usage), undated, fetched 2026-11-04 |

**What this means for V1:** subscription sign-in works technically. Policy allows it most clearly when the user runs the tool themself, on their own seat, interactively. Before giving Mission Control to colleagues, get written confirmation from the Anthropic account team, or keep an API-key or gateway path in `agentlib` as the fallback. That is cheap to do, because the engine adapter only changes environment variables.

---

## 3. Sources and versions

| Source | Version / date |
|---|---|
| `claude-agent-sdk` (Python) on [PyPI](https://pypi.org/project/claude-agent-sdk/) | **0.2.178**, released 2026-11-04. Bundles Claude Code CLI **2.1.318** (per the research pass, not re-checked). The [CHANGELOG](https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md) has no dates. |
| Agent SDK and Claude Code docs, `code.claude.com/docs/en/...` (agent-sdk/python, overview, quickstart, claude-code-features, custom-tools, mcp, tool-search, modifying-system-prompts, sessions, cost-tracking, agent-loop, hosting, env-vars, authentication, data-usage, legal-and-compliance, errors, setup, cli-reference, costs) | Undated. Fetched 2026-11-04. |
| [Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms) | Effective 2025-10-08 |
| `cursor-sdk` (Python) on [PyPI](https://pypi.org/project/cursor-sdk/) and [docs](https://cursor.com/docs/sdk/python.md) | **1.3.1**, uploaded 2026-11-04. "Development Status :: 4 - Beta", licence Proprietary. The [SDK release notes](https://cursor.com/docs/release-notes/sdk.md) only go up to 1.0.40. |
| Cursor CLI docs: [overview, headless, parameters, output-format, permissions, configuration, mcp](https://cursor.com/docs/cli/reference/parameters.md), [ACP](https://cursor.com/docs/cli/acp.md), [installation](https://cursor.com/docs/cli/installation.md) | Undated. Fetched 2026-11-04. |
| [Cursor CLI changelog](https://cursor.com/docs/cli/changelog.md) | Latest entry **v2026.10.22**. Cursor CLI versions are dates. |
| Cursor privacy: [data-use](https://cursor.com/data-use) and [enterprise privacy & data governance](https://cursor.com/docs/enterprise/privacy-and-data-governance.md) | data-use last updated 2026-09-03. The governance page is undated. |
| [Agent Client Protocol](https://agentclientprotocol.com/protocol/v1/overview.md) | v1 stable (`protocolVersion: 1`). v2 is a **draft**, announced 2026-07-20. The TS and Rust SDKs reached 1.0 on 2026-06-25. |
| Cursor forum staff posts | Each one is dated inline below |

Everything the research pass found was taken from these pages. I re-checked the highest-stakes claims myself on 2026-11-04:
- Anthropic's claude.ai-login wording
- the Agent SDK `settingSources` default
- Cursor SDK `tools` and `custom_tools`
- Cursor's `systemPrompt` forum thread

---

## 4. The 15 questions

Verdicts are **Yes / Partly / No / Not documented**. "Cursor" means the CLI (print mode and ACP), as the brief asks. A **Cursor SDK** note is added wherever the new Python SDK changes the answer.

### Q1. Programmatic control
- **Agent SDK: Yes.**
  - The official Python package is `claude-agent-sdk` (Python 3.10 or later). It has two entry points:
    - `query()`: one-off; each call starts a new session.
    - `ClaudeSDKClient`: keeps one session open, supports interrupts, and is the one meant for chat UIs.
  - Each session runs the CLI as a subprocess ("One agent session maps to one subprocess"). The CLI binary comes bundled, and Node is not needed.
  - Sources: [python](https://code.claude.com/docs/en/agent-sdk/python), [hosting](https://code.claude.com/docs/en/agent-sdk/hosting), [quickstart](https://code.claude.com/docs/en/agent-sdk/quickstart).
- **Cursor CLI: Yes (CLI plus ACP).**
  - **ACP** is JSON-RPC 2.0 over stdio, started with `agent acp`. Sign in with `authenticate` (`methodId: "cursor_login"`) after `agent login`, `--api-key` or `--auth-token`.
  - **Methods Cursor supports:** `initialize`, `session/new`, `session/load`, `session/prompt`, `session/cancel`, and `session/request_permission` with `allow-once` / `allow-always` / `reject-once`.
  - **Modes:** agent / plan / ask.
  - **Cursor's own extensions:** `cursor/ask_question`, `cursor/create_plan`, `cursor/update_todos`, `cursor/task`, `cursor/generate_image`.
  - **ACP v1 `session/update` kinds:** `agent_message_chunk`, `agent_thought_chunk`, `tool_call`, `tool_call_update`, `plan`, `usage_update`, `current_mode_update`, among others.
  - **Python client library:** `pip install agent-client-protocol`.
  - **Stability:** the ACP v1 spec is stable. Cursor's ACP mode has had recent bugs (see Q6).
  - Sources: [cursor ACP](https://cursor.com/docs/cli/acp.md), [ACP v1](https://agentclientprotocol.com/protocol/v1/overview.md), [ACP Python](https://agentclientprotocol.com/libraries/python.md).
  - **Cursor SDK: Yes, beta.** `pip install cursor-sdk`. It runs locally ("against local files on disk") through a bundled `cursor-sdk-bridge` binary and does not need the `agent` CLI. There is also a cloud mode. Source: [sdk/python](https://cursor.com/docs/sdk/python.md).

### Q2. Non-interactive runs and streaming
- **Agent SDK: Yes.**
  - **Message types:** `UserMessage`, `AssistantMessage`, `SystemMessage` (subtypes include `init`, plus Task*, `HookEventMessage`, `MirrorErrorMessage`), `ResultMessage`, `StreamEvent`, `RateLimitEvent`, `ConversationResetMessage`.
  - **Content blocks:** `TextBlock`, `ThinkingBlock`, `ToolUseBlock`, `ToolResultBlock`, `ServerToolUseBlock`, `ServerToolResultBlock`.
  - **Live partial text:** set `include_partial_messages=True`. `StreamEvent.event` then carries the raw API stream events (text deltas).
  - **`ResultMessage.subtype` values:** `success`, `error_during_execution`, `error_max_turns`, `error_max_budget_usd`, `error_max_structured_output_retries`.
  - Source: [python](https://code.claude.com/docs/en/agent-sdk/python).
- **Cursor CLI: Yes.**
  - **Flags:**
    - `-p/--print`
    - `--output-format text|json|stream-json`
    - `--stream-partial-output` (stream-json only)
    - `-f/--force` (alias `--yolo`)
    - `--model`, `--mode plan|ask`
    - `--resume [chatId]`, `--continue`
    - `--workspace`, `--trust`, `--approve-mcps`
    - `--sandbox enabled|disabled`
    - `--api-key`, `-H/--header`
  - **stream-json events:**
    - `system`/`init`: `apiKeySource`, `cwd`, `session_id`, `model`, `permissionMode`
    - `user`
    - `assistant`: `message.content[].text`
    - `tool_call`/`started` and `tool_call`/`completed`: `call_id`, `tool_call.{readToolCall|writeToolCall|function}`
    - `result`/`success`: `duration_ms`, `duration_api_ms`, `is_error`, `result`, `session_id`, `request_id`
  - Thinking events are dropped in print mode.
  - **Live text:** yes, with `--stream-partial-output`. Use only the `assistant` events that have `timestamp_ms` and no `model_call_id`; the others are duplicate flushes.
  - Sources: [parameters](https://cursor.com/docs/cli/reference/parameters.md), [output-format](https://cursor.com/docs/cli/reference/output-format.md).
  - **Cursor SDK:** `run.messages()` yields `system`, `user`, `assistant`, `thinking`, `tool_call` (running / completed / error), `status`, `task`, `request`, `summary`, `usage`. The `on_delta` callback gives token-by-token text. The docs warn that the shape of tool-call args and results is unstable.

### Q3. Multi-turn sessions
- **Agent SDK: Yes.**
  - With `ClaudeSDKClient`, one process keeps the session, and each `client.query()` continues it.
  - **Session options:** `session_id` (on `ResultMessage`), `resume`, `continue_conversation`, `fork_session`, `resume_session_at` (added 0.2.137).
  - **History:** plaintext JSONL files under `~/.claude/projects/<encoded-cwd>/`, kept **30 days** by default (`cleanupPeriodDays`).
  - **To stop saving history:** set `CLAUDE_CODE_SKIP_PROMPT_HISTORY=1`. (`persistSession:false` exists only in the TypeScript SDK.)
  - Sources: [sessions](https://code.claude.com/docs/en/agent-sdk/sessions), [data-usage](https://code.claude.com/docs/en/data-usage).
- **Cursor CLI: Partly.**
  - **Print mode:** one process per turn, continued with `--resume <chatId>`. `agent create-chat`, `agent ls` and `agent resume` also exist. No streaming-input-over-stdin mode is documented.
  - **ACP:** one process can hold several sessions and messages. Loading old sessions with `session/load` had a "Session not found" bug, closed in May 2026 without a confirmed fix; the v2026.09.15 changelog suggests it now works.
  - **Not documented:** where chat history is stored locally, and how long it is kept.
  - Sources: [parameters](https://cursor.com/docs/cli/reference/parameters.md), [forum thread](https://forum.cursor.com/t/cursor-acp-session-load-fails-with-session-id-not-found-breaking-persistent-sessions-acpx-openclaw-acp-runtime/155516).
  - **Cursor SDK:** yes. Each `agent.send()` on one `Agent` keeps the conversation. `Agent.resume(id)` survives a restart, and state is kept by the bridge in a "per-workspace state root".

### Q4. Instructions
- **Agent SDK: Yes, but you must opt out of filesystem settings yourself.**
  - **System prompt options:** omit it (a minimal default); a string (sent exactly as given); the preset `{"type":"preset","preset":"claude_code","append":...}`; or `{"type":"file","path":...}`.
  - **The default changed.** Current docs say: *"When you omit settingSources, query() reads the same filesystem settings as the Claude Code CLI: user, project, and local settings, CLAUDE.md files, and .claude/ skills, agents, and commands."* Earlier changelogs said the opposite.
  - `setting_sources=[]` turns those off. It was ignored up to 0.1.59 and fixed in 0.1.60.
  - **Still read regardless:** managed policy, `~/.claude.json`, and auto memory. Turn auto memory off with `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. Also set `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` as a second guard.
  - Sources: [system prompts](https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts), [claude-code-features](https://code.claude.com/docs/en/agent-sdk/claude-code-features) (both checked 2026-11-04).
- **Cursor CLI: No.**
  - There is no system-prompt flag. Instructions come from `.cursor/rules`, plus `AGENTS.md` and `CLAUDE.md` at the project root, "applied as rules".
  - Rule layers are Team → Project → User. Team rules that an admin enforces cannot be turned off.
  - A feature request for `--append-system-prompt` (2026-08-27) is open.
  - Sources: [cli/using](https://cursor.com/docs/cli/using.md), [rules](https://cursor.com/docs/rules.md), [forum request](https://forum.cursor.com/t/cursor-cli-launch-time-instruction-injection-append-system-prompt-flag-or-env-var/169757).
  - **Cursor SDK: documented, but not usable.**
    - The TypeScript `systemPrompt` option exists (local runs only). Even with it, tool schemas, rules and skills still load. The Python docs have no `system_prompt` option.
    - Cursor staff, 2026-10-22: *"It's still unavailable for external accounts."* Their suggested workaround is `AGENTS.md` or `.cursor/rules/*.mdc` in the agent's `cwd`, plus key instructions at the start of `agent.send()`.
    - `local.setting_sources` controls which settings layers load (project / user / team / mdm / plugins). Rules and `AGENTS.md` in `cwd` and `dirs` still load ("rules, skills, and workspace context load from every path").
    - Sources: [forum thread (staff)](https://forum.cursor.com/t/cursor-sdk-1-0-31-systemprompt-fails-in-local-agent-with-unknown-option-system-prompt/170614) (checked 2026-11-04), [sdk/python](https://cursor.com/docs/sdk/python.md).

### Q5. Restricting tools
- **Agent SDK: Yes.**
  - `tools=[]` removes every built-in tool: "Claude can only use your MCP tools."
  - `allowed_tools` only skips the approval step; it does **not** remove tools.
  - A bare tool name in `disallowed_tools` removes that tool.
  - **`permission_mode` values:** `default`, `acceptEdits`, `plan`, `dontAsk`, `bypassPermissions`, `auto`. `dontAsk` denies anything that is not pre-approved.
  - `can_use_tool` is skipped for pre-approved tools, so use a `PreToolUse` hook as the final guard.
  - Tool search is on by default and adds a built-in `ToolSearch` tool. Turn it off with `ENABLE_TOOL_SEARCH=false`.
  - Check at runtime that the `init` message's `tools` list holds only `mcp__planner__*`.
  - Sources: [custom-tools](https://code.claude.com/docs/en/agent-sdk/custom-tools), [tool-search](https://code.claude.com/docs/en/agent-sdk/tool-search), [agent-loop](https://code.claude.com/docs/en/agent-sdk/agent-loop).
- **Cursor CLI: Partly.**
  - `cli-config.json` and `.cursor/cli.json` take `permissions.allow` / `deny` rules: `Shell(cmd)`, `Read(glob)`, `Write(glob)`, `WebFetch(domain)`, `Mcp(server:tool)`. These **reject calls**, but the tools are still offered to the model.
  - `--mode ask` and `--mode plan` are read-only, but they still have read and search tools.
  - **Approvals in print mode are documented inconsistently.** The headless page says that without `--force`, changes "are only proposed". The using page says it has "full write access in non-interactive mode".
  - Untrusted workspaces fail in headless mode unless you pass `--trust` or `--force`.
  - Admins can turn headless mode off for the whole organisation (since 2026-05-20).
  - In ACP, every tool call that needs approval comes to the app as `session/request_permission`, so the app can reject all non-MCP tools.
  - Sources: [permissions](https://cursor.com/docs/cli/reference/permissions.md), [headless](https://cursor.com/docs/cli/headless.md), [using](https://cursor.com/docs/cli/using.md).
  - **Cursor SDK: Yes, local runs only.**
    - `tools` is an allowlist of built-in tools: "tools=[] offers no built-in tools, so the model can only respond with text."
    - Valid names include `"read"`, `"edit"`, `"task"` and `"webSearch"`, plus the groups `"shell"` and `"mcp"`. A deny always wins. Disallowing `"mcp"` also removes custom tools.
    - The restriction does **not** carry over on resume, so pass it again each time.
    - **Not documented:** whether `tools=[]` also hides `custom_tools`. The wording suggests `tools=["mcp"]` is the safe setting. Test it (§9).

### Q6. Custom tools via MCP
- **Agent SDK: Yes.**
  - Define tools with `@tool(...)` and `create_sdk_mcp_server(...)`. The server runs **in-process, not as a separate process**.
  - `mcp_servers` takes a dict or a config file path. Server types: stdio, `sse`, `http`, `sdk`.
  - Tools are named `mcp__<server>__<tool>`.
  - `strict_mcp_config=True` (added 0.1.74) ignores `.mcp.json`, user settings, plugins and claude.ai connectors.
  - **Limits:**
    - Tool results over 25k tokens or 50k characters are saved to a file. With no Read tool, the agent can't open that file, so keep results small.
    - The Python `@tool` decorator only forwards `content` and `is_error`.
    - Startup waits up to `MCP_TIMEOUT` (30 s) for the server to connect.
  - Sources: [custom-tools](https://code.claude.com/docs/en/agent-sdk/custom-tools), [mcp](https://code.claude.com/docs/en/agent-sdk/mcp).
- **Cursor CLI: Partly.**
  - **Print mode:** MCP servers come only from `.cursor/mcp.json` or `~/.cursor/mcp.json`. There is no per-run flag. Commands: `agent mcp list|list-tools|enable|disable|login`, and `--approve-mcps` to skip approvals.
  - **Stdio servers in headless runs:** the CLI waits for them to start before running (since 2026-05).
  - **Approvals:** global servers are approved automatically; project servers need approval (since 2026-04).
  - **ACP:** servers can be passed per session in `session/new` `mcpServers`.
    - That was broken: "accepted silently, but no connection happens" (staff, 2026-03-05). It was marked fixed on 2026-04-12.
    - Staff, 2026-10-04: servers passed in `session/new` "can connect without pre-seeding mcp-approvals.json".
    - The ACP doc page still says servers come from `mcp.json`. **Treat this as recently fixed and test it.**
  - **Tool count:** no limit is documented. Staff said on 2026-09-09 that the CLI now loads tool definitions only when needed.
  - **Enterprise:** an admin **MCP allowlist** can block the app's server.
  - Sources: [cli/mcp](https://cursor.com/docs/cli/mcp.md), [forum 153623](https://forum.cursor.com/t/acp-agent-silently-ignores-mcpservers-in-session-new/153623), [forum 153823](https://forum.cursor.com/t/mcp-servers-passed-via-session-new-dont-work-in-acp-mode/153823), [forum 165642](https://forum.cursor.com/t/cli-mcp-tool-limits/165642), [mcp](https://cursor.com/docs/mcp.md).
  - **Cursor SDK: Yes.**
    - Inline `mcp_servers` (stdio or http) can be set on `Agent.create()` or on each `send()`. A per-send value *replaces* the creation-time servers rather than adding to them.
    - "Without `local.setting_sources`, only inline servers are loaded."
    - `LocalAgentOptions.custom_tools` exposes plain Python functions "without standing up a separate MCP server". `output_schema` is advertised to the model but results are not checked against it.
    - Inline servers are not saved across resume.

### Q7. Sub-agents and parallel runs
- **Agent SDK: Yes.**
  - Define sub-agents with `agents={name: AgentDefinition(...)}`. The keys are camelCase, such as `disallowedTools`.
  - Parallel runs: each session is its own subprocess. The hosting docs mention running several SDK processes per container.
  - **Not documented:** any official limit on concurrent clients in one Python process.
  - The app's design (D26) runs the reader as a separate session, not a built-in sub-agent, so this works either way.
  - Sources: [python](https://code.claude.com/docs/en/agent-sdk/python), [hosting](https://code.claude.com/docs/en/agent-sdk/hosting).
- **Cursor CLI: Yes for sub-agents; Not documented for parallel processes.**
  - Sub-agents run "in the editor, CLI, and Cloud Agents" (CLI since 2026-03). They inherit rules and approvals.
  - Nothing documents locking or safety when several CLI processes run at once.
  - SDK 1.0.35 fixed ID collisions between agents restored from the same snapshot.
  - Sources: [subagents](https://cursor.com/docs/subagents.md), [CLI changelog](https://cursor.com/docs/cli/changelog.md).

### Q8. Model choice
- **Agent SDK: Yes.**
  - Options: `model`, plus `fallback_model` (comma-separated).
  - All Claude models available to the signed-in account can be used.
  - Gateway, briefly: `ANTHROPIC_BASE_URL` with `ANTHROPIC_AUTH_TOKEN` points it at a gateway. Bedrock, Vertex and Foundry are set with `CLAUDE_CODE_USE_*`. Under subscription sign-in, leave all of these unset.
  - Sources: [python](https://code.claude.com/docs/en/agent-sdk/python), [authentication](https://code.claude.com/docs/en/authentication).
- **Cursor CLI: Partly.**
  - **Choosing a model: Yes.** Use `--model`, `agent models` or `--list-models`. Admins can limit models per team or group.
  - **Anthropic models listed:** Claude Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.1. Note that **Fable stores inputs and outputs at Anthropic** and needs admin approval.
  - **Custom base URL or company gateway: No.**
    - With your own API key, "all requests are routed through Cursor's servers for final prompt building", and Cursor's zero-data-retention policy no longer applies.
    - The only own-key route the CLI documents is `agent bedrock`.
    - The editor's OpenAI base-URL override is not documented for the CLI, agent mode or the SDK.
  - **Recent bugs:** several 2026 forum threads report that named non-Composer models (Opus, Sonnet) fail in SDK *local* runs with an empty error.
  - Sources: [models-and-pricing](https://cursor.com/docs/models-and-pricing.md), [model management](https://cursor.com/docs/enterprise/model-and-integration-management.md), [api-keys](https://cursor.com/help/models-and-usage/api-keys.md), [privacy & governance](https://cursor.com/docs/enterprise/privacy-and-data-governance.md).

### Q9. Token usage
- **Agent SDK: Yes, with caveats.**
  - **`ResultMessage.usage`** has `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. It covers **this turn**, main loop only.
  - **`model_usage`** has the same counts per model, including sub-agents, in camelCase keys.
  - With `ClaudeSDKClient`, `model_usage` and `total_cost_usd` are **running totals**.
  - **Per-step usage:** `AssistantMessage.usage` exists. Remove duplicates by `message_id`, and don't trust per-step `output_tokens`.
  - `total_cost_usd` is an estimate from a local price table. Under a subscription it is notional.
  - Source: [cost-tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking).
- **Cursor CLI: Yes, but only in print mode, and the reference page doesn't show it.**
  - The 2026-02 changelog says: "Per-turn input/output/cache token totals… in stream-json output".
  - Cursor staff (2026-06-30) confirmed the field: `"usage": {"inputTokens","outputTokens","cacheReadTokens","cacheWriteTokens"}`. `inputTokens` counts **uncached** input only.
  - The output-format reference page does not show it yet.
  - **ACP: Not documented for Cursor.** ACP v1's `usage_update` carries only `used`, `size` and an optional `cost`. Per-turn token usage in ACP is still a draft proposal.
  - **Other ways to get usage:** the Admin API `POST /teams/filtered-usage-events` returns per-event `tokenUsage`, but it needs an admin key.
  - Sources: [forum 164471](https://forum.cursor.com/t/discrepancies-between-cursor-cli-usage-and-billing/164471), [admin-api](https://cursor.com/docs/account/teams/admin-api.md).
  - **Cursor SDK: Yes, documented.**
    - `TokenUsage` has `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `total_tokens`, `reasoning_tokens`.
    - It arrives per turn as a `usage` message. `run.usage` and `result.usage` give the totals.
    - Billed cost via `agent.get_usage()` is "rolling out gradually" for local agents.

### Q10. Prompt caching
- **Agent SDK: Yes (automatic). Ordering control: Partly.**
  - "You do not need to configure caching yourself."
  - Turn it off with `DISABLE_PROMPT_CACHING` (per-model variants exist).
  - **Cache lifetime:** subscribers within their included usage get a 1-hour cache automatically; otherwise use `ENABLE_PROMPT_CACHING_1H` or `CLAUDE_CODE_PROMPT_CACHE_TTL`.
  - **Ordering control:**
    - A string system prompt is sent exactly as given, so the app controls its order. That fits D48: core rules → playbook → wiki page.
    - Tool definitions come from the MCP server.
    - The Python SDK cannot split the prompt into a static part and a changing part; that is TypeScript only.
    - On a resumed session, a changed system prompt only takes effect after compaction.
  - Sources: [cost-tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking), [env-vars](https://code.claude.com/docs/en/env-vars), [system prompts](https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts).
- **Cursor CLI: Not documented.**
  - Pricing lists cache-read and cache-write prices, and usage reports cache tokens, so caching happens.
  - No controls are documented. The app can't control prompt order beyond the order of rules files and the message itself.

### Q11. Sandbox and security
- **Agent SDK: Partly.**
  - `sandbox=SandboxSettings(...)` is off by default, covers **Bash only**, and is "Not supported" on native Windows. With `tools=[]` there is no Bash, so this doesn't matter here.
  - **Where data goes:** prompts go to Anthropic over TLS. On a commercial seat there is no training and 30-day retention (§2).
  - **Telemetry switches:** `DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`. Error reporting is on by default for Pro, Max and Ultra sign-ins (v2.1.198 and later).
  - **Settings the SDK can't turn off:** if the organisation pushes managed settings to the login, they apply ("you can't disable them from the SDK").
  - Sources: [python](https://code.claude.com/docs/en/agent-sdk/python), [data-usage](https://code.claude.com/docs/en/data-usage), [claude-code-features](https://code.claude.com/docs/en/agent-sdk/claude-code-features).
- **Cursor CLI: Partly.**
  - **Sandbox:** macOS uses Seatbelt; Linux uses Landlock and seccomp, with network "Blocked by default". **No Windows sandbox is documented.** SDK local agents run with the sandbox off by default.
  - **Data path:** prompts and context go through **Cursor's backend** to the model providers.
  - **Privacy Mode:** on by default for Enterprise and can be enforced. Under it, "most models" have zero data retention; the exceptions are Fable and own-key requests.
  - **Code storage:** only Cloud Agents store code.
  - **Not found:** specific retention periods, and codebase-indexing details for the CLI.
  - **For claims data:** compliance must approve Cursor as a data processor. The team needs Privacy Mode enforced and Fable blocked.
  - Sources: [run-modes](https://cursor.com/docs/agent/security/run-modes.md), [privacy & governance](https://cursor.com/docs/enterprise/privacy-and-data-governance.md), [data-use](https://cursor.com/data-use) (2026-09-03).

### Q12. Working directory and file access
- **Agent SDK: Yes.**
  - `cwd` sets the working folder, and `add_dirs` adds extra folders (passed as `--add-dir`). With `tools=[]` the planner can't read files at all.
  - The Haiku reader (D26, D30b) does need Read, Grep and Glob, limited to `cwd` plus `add_dirs`. Use a `PreToolUse` hook to enforce the path boundary strictly.
  - Source: [python](https://code.claude.com/docs/en/agent-sdk/python).
- **Cursor CLI: Yes.**
  - `--workspace` sets the folder; the default is the current directory.
  - `sandbox.readBoundary: "workspace"` plus `Read(...)` allow rules limit reads (Cursor 3.23, 2026-10-01).
  - In the SDK, set `local.cwd` plus `dirs`.
  - Source: [configuration](https://cursor.com/docs/cli/reference/configuration.md).

### Q13. Errors
- **Agent SDK: Yes.**
  - **Exceptions:** `ClaudeSDKError` → `CLIConnectionError` / `CLINotFoundError`, `ProcessError` → `ResultError` (0.2.140), and `CLIJSONDecodeError`.
  - **`AssistantMessage.error`:** `authentication_failed`, `billing_error`, `rate_limit`, `invalid_request`, `server_error`, `unknown`.
  - **`ResultMessage` fields:** `is_error`, `errors`, `api_error_status`, `terminal_reason`.
  - Error text looks like "API Error: <status> <message>".
  - A one-shot `query()` raises after yielding the error result. A `ClaudeSDKClient` session stays alive.
  - There is no session timeout. Use `max_turns`, `API_TIMEOUT_MS`, and the app's own watchdog.
  - Sources: [python](https://code.claude.com/docs/en/agent-sdk/python), [errors](https://code.claude.com/docs/en/errors).
- **Cursor CLI: Partly.**
  - The process exits non-zero and writes the error to stderr.
  - `json` output prints no object on failure. `stream-json` may end without a `result` event.
  - No exit-code table, error subtypes or rate-limit event are documented.
  - **Cursor SDK:** has `RateLimitError` (`is_retryable`, `retry_after`), `AuthenticationError`, `APITimeoutError` and `NetworkError`. Run status is `finished|error|cancelled|expired`. `RunResult.error_code` and `error_message` exist since 1.0.39.

### Q14. Authentication in scripts
- **Agent SDK: Yes.**
  - Options: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `apiKeyHelper`, `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`), or the stored `/login` credentials.
  - Policy limits on subscription login are in §2.
  - Enterprise admins can enforce `forceLoginMethod`, `forceLoginOrgUUID` and `allowedProviders` through managed settings. The init message's `apiKeySource` shows which credential was used.
  - Source: [authentication](https://code.claude.com/docs/en/authentication).
- **Cursor CLI: Yes.**
  - Options: `CURSOR_API_KEY` or `--api-key`, `--auth-token` (ACP), or browser `agent login`.
  - Keys come from the user dashboard or from **service accounts**, which Cursor recommends for headless use.
  - The SDK accepts user and service-account keys. "Team Admin API keys are not yet supported."
  - Source: [service accounts](https://cursor.com/docs/account/enterprise/service-accounts.md).

### Q15. Windows and Mac
- **Agent SDK: Yes.**
  - **Wheels:** macOS 11+ (arm64 and x64) and Windows x64. The CLI itself needs macOS 13+ and Windows 10 1809+.
  - **Windows on ARM:** no bundled binary, so Claude Code must be installed separately.
  - No Node is needed. Git Bash is only needed for the Bash tool.
  - **Windows command-line limit:** a string `system_prompt` is passed on the command line, and Windows caps that at about 32 KB. Use `{"type":"file","path":...}` for long prompts such as playbook plus wiki page.
  - Sources: [PyPI](https://pypi.org/project/claude-agent-sdk/), [setup](https://code.claude.com/docs/en/setup).
- **Cursor CLI: Yes.**
  - **Install on Windows (native, no WSL):** `irm 'https://cursor.com/install?win32=true' | iex`
  - **Install on Mac:** `curl https://cursor.com/install -fsS | bash`
  - On Windows the agent runs shell commands in PowerShell (UTF-8 fix in v2026.10.22). **No Windows sandbox.**
  - The SDK has `win_amd64` and macOS wheels. Its bridge is "Windows x64 only".
  - Sources: [installation](https://cursor.com/docs/cli/installation.md), [sdk/bridge](https://cursor.com/docs/sdk/bridge.md).

---

## 5. Extra questions from the plan review

**(a) In-process MCP server?**
- **Agent SDK: Yes.** `create_sdk_mcp_server(name=..., tools=[...])` runs inside the Python process with no separate process. Plain `query(prompt=str)` works with it; streaming input is no longer required. Startup waits up to `MCP_TIMEOUT` for the server to connect. Mark read-only tools with `readOnlyHint` if they should run in parallel.
- **Cursor CLI: no in-process option.** It needs a server it can reach from config: either a stdio command, which Cursor starts as a separate process, or an **HTTP/URL MCP server**. The app can host the HTTP version on localhost inside its own process, which avoids a second process, keeps state in one place, and reuses the D11–D13 security checks. Print mode would otherwise start a stdio server again on every turn.
- **Cursor SDK:** `custom_tools` are plain Python functions, so they also run in-process.

**(b) Turn off all built-in tools and filesystem settings (Agent SDK 0.2.178)**

The core settings are `tools=[]`, `setting_sources=[]` and `strict_mcp_config=True`. The rest is extra protection.

```python
import os
from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, HookMatcher

for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
    os.environ.pop(k, None)            # otherwise they override the subscription login

planner = create_sdk_mcp_server(name="planner", version="1.0.0",
                                tools=[ask_user, explore, save_note, write_plan])
options = ClaudeAgentOptions(
    tools=[],                          # remove every built-in tool
    mcp_servers={"planner": planner},
    allowed_tools=["mcp__planner__*"], # pre-approve only ours
    permission_mode="dontAsk",         # anything not pre-approved is denied
    strict_mcp_config=True,            # ignore .mcp.json, user/plugin MCP, claude.ai connectors
    setting_sources=[],                # no user/project/local settings, CLAUDE.md, skills, agents, commands
    system_prompt={"type": "file", "path": prompt_path},  # avoids the Windows ~32 KB limit
    hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[deny_unless_planner_tool])]},
    env={
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
        "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
        "ENABLE_TOOL_SEARCH": "false",              # 4 tools: load them all up front
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_MAX_RETRIES": "1",             # see (c)
        # "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1",   # optional: no transcript in ~/.claude/projects
    },
)
```

Caveats:
- Managed and server-pushed policy settings, and `~/.claude.json`, are always read.
- Don't set `CLAUDE_CONFIG_DIR` if you want to reuse the user's login, because it moves where the CLI looks for credentials.
- I'm inferring that plugins enabled in user settings stay off once `setting_sources=[]`; the docs don't say it directly.
- At startup, assert that the `init` message's `tools` list holds only `mcp__planner__*`.

**(c) Built-in retry behaviour (Agent SDK and CLI)**
- The CLI "retries transient failures up to 10 times with exponential backoff". This covers 429, 5xx, overloaded (529) and connection errors that happen before any output has streamed.
- Set the count with `CLAUDE_CODE_MAX_RETRIES`. The default is 10, capped at 15 since v2.1.186.
- **Setting it to 1** is documented as a valid value. **Setting it to 0** is not explicitly documented (test it, §9).
- Other settings:
  - Overloaded backoff: `CLAUDE_CODE_OVERLOADED_RETRY_BASE_DELAY_MS` (default 500) and `..._MAX_DELAY_MS` (default 32000).
  - `API_TIMEOUT_MS`: default 600000; `0` means no limit on v2.1.305+.
  - Stalled streams: `CLAUDE_STREAM_IDLE_TIMEOUT_MS` (minimum 300000).
  - Don't set `CLAUDE_CODE_RETRY_WATCHDOG`. With it on, a session that hits a usage limit waits out the remaining window.
- **For D50a:** set `CLAUDE_CODE_MAX_RETRIES=1` and **don't** add an app-level retry on top, or the "exactly one retry" rule becomes two. Alternatively, set it to `0` (if accepted) and let the app do the single retry, so it can show progress in the chat.
- Sources: [errors](https://code.claude.com/docs/en/errors), [env-vars](https://code.claude.com/docs/en/env-vars).
- **Cursor:** CLI retry behaviour is not documented. The SDK's `RateLimitError` exposes `is_retryable` and `retry_after`, which suggests the app is expected to handle retries.

**(d) LiteLLM prompt-caching passthrough:** dropped after the scope change to subscription sign-in. Revisit if the gateway comes back.

---

## 6. Side-by-side table

| # | Capability | Agent SDK (Python) | Cursor CLI (print / ACP) | Cursor Python SDK (beta), for reference |
|---|---|---|---|---|
| 1 | Programmatic control | **Yes**: official library | **Yes**: CLI plus ACP (JSON-RPC, stdio) | **Yes**: official, beta, proprietary |
| 2 | Non-interactive runs and live streaming | **Yes**: `include_partial_messages` | **Yes**: `--stream-partial-output` / ACP chunks | **Yes**: `on_delta` |
| 3 | Multi-turn in one session | **Yes**: `ClaudeSDKClient` | **Partly**: print = one process per turn plus `--resume`; ACP = one process | **Yes**: `Agent.send()` |
| 4 | App-set instructions; rules files off | **Yes**: string prompt plus `setting_sources=[]` | **No**: rules files only | **No (today)**: `systemPrompt` gated per account |
| 5 | Only custom tools, no built-ins | **Yes**: `tools=[]` | **Partly**: deny rules or ACP rejection; tools still offered to model | **Yes**: `tools` allowlist (check `custom_tools`) |
| 6 | Custom tools via MCP, set per run | **Yes**: in-process SDK server | **Partly**: print = `mcp.json` only; ACP `session/new` (recently fixed) | **Yes**: inline `mcp_servers` / `custom_tools` |
| 7 | Sub-agents / parallel | **Yes** / **Yes** (one process per session) | **Yes** / **Not documented** | **Yes** / **Partly** |
| 8 | Model choice; company gateway | **Yes** / **Yes** (`ANTHROPIC_BASE_URL`) | **Yes** / **No**: always via Cursor's servers | **Yes** / **No** |
| 9 | Token usage incl. cache | **Yes** | **Partly**: print-mode `usage` (staff-confirmed, not on the reference page); ACP not documented | **Yes**: documented |
| 10 | Prompt caching and order control | **Yes** / **Partly** | **Not documented** | **Not documented** |
| 11 | Sandbox / privacy | **Partly**: Bash-only sandbox, none on Windows; commercial plan: no training, 30 days | **Partly**: no Windows sandbox; data goes via Cursor; Privacy Mode / ZDR (not Fable) | Same as CLI; sandbox off by default |
| 12 | Working directory and extra folders | **Yes**: `cwd`, `add_dirs` | **Yes**: `--workspace`, `readBoundary` | **Yes**: `cwd`, `dirs` |
| 13 | Error reporting | **Yes**: typed exceptions and fields | **Partly**: exit code and stderr; no error event | **Yes**: typed errors |
| 14 | Script authentication | **Yes**: API key / token / login (policy caveat) | **Yes**: API key / service account | **Yes**: no team-admin keys |
| 15 | Windows and Mac | **Yes**: watch the ~32 KB command-line limit | **Yes**: native Windows; no sandbox there | **Yes**: Windows x64 only |

---

## 7. Top 3 risks of using Cursor as an engine, with workarounds

1. **The app can't control the instructions.** No system-prompt option works for external accounts. Team rules always load, and Cursor's built-in prompt stays in place. Our core rules, playbook and pushback style would sit *underneath* Cursor's agent prompt, so behaviour may drift and caching order can't be controlled (D48).
   - **Workaround:** run every Cursor agent in an **app-owned empty working folder** containing a generated `AGENTS.md` (core rules plus playbook).
   - Repeat the key rules at the start of each `send()`.
   - Leave `setting_sources` unset (SDK) so user and project settings don't load.
   - Give the reader the real project folders only through `dirs`, after testing which rules load from them.
   - Watch the forum thread for `systemPrompt` access, or ask the Cursor account team to enable it.
2. **Data and channel compliance.** All Cursor traffic goes through Cursor's servers to model providers. It can't use a company gateway. Own-key requests lose zero data retention, and Fable models store data at Anthropic. Our MCP server must also be on the enterprise MCP allowlist.
   - **Workaround:** get Cursor approved as a processor before any claims data goes through it.
   - Require the team to enforce Privacy Mode and block Fable.
   - Get the app's MCP server allowlisted.
   - Until then, mark Cursor in settings as "not for sensitive data" and keep the reader, and anything touching data, on Claude.
3. **Unstable surfaces.** The SDK is beta, proprietary and moving fast (1.0.x to 1.3.1 within months). ACP's MCP support and `session/load` were fixed only in April to October 2026. Print-mode `usage` isn't on the reference page. Forum threads report local SDK runs failing with Anthropic models. Tool-call event shapes are "explicitly unstable".
   - **Workaround:** pin exact versions (`cursor-sdk==1.3.1`, a fixed CLI version).
   - Keep all Cursor-specific code inside `agentlib/engines/cursor.py`, behind tests that replay recorded event streams.
   - Run the §9 experiments as a smoke test on every upgrade.
   - Fall back to Claude for any role where the Cursor smoke test fails.

---

## 8. Recommendations

### CLI print mode vs ACP
**Short answer: neither, if the beta Cursor Python SDK is acceptable. If the choice has to be CLI print mode or ACP, use ACP, provided experiment C3 shows it reports token usage. Otherwise use print mode.**

- **The Cursor Python SDK** is the only Cursor option that cleanly does all four of these:
  - removes built-in tools
  - takes in-process custom tools
  - documents per-turn cache token usage
  - keeps a long-lived session in Python
  
  It is the closest match to the Claude adapter. The costs are beta status, a proprietary licence and a bundled bridge binary. Pin the version.
- **ACP over print mode, for an interactive planner:**
  - One long-lived process instead of a fresh process (and MCP server start-up) every turn.
  - MCP servers can be passed per session instead of writing `mcp.json`.
  - Every tool approval comes back to the app as `session/request_permission`, so the app can reject every built-in tool. That is the strongest "custom tools only" guarantee the CLI offers.
  - `session/cancel` matches the chat's stop button.
  - It's an open spec with a Python client library.
  - **The catch:** token usage over ACP isn't documented, and the cost counter (D8, D17) depends on it.
- **Print mode's advantages:**
  - Simplest to build.
  - Per-turn `usage` with cache counts (confirmed by staff).
- **Print mode's disadvantages:**
  - MCP only from config files.
  - A process (and stdio MCP server) per turn.
  - Built-in tools can only be denied, not removed.
  - Inconsistent docs on approvals in print mode.

### Can the `agentlib` interface be supported on both engines?

| Operation | Claude (Agent SDK) | Cursor (SDK, else ACP / print) | Engine-specific part |
|---|---|---|---|
| start session | `ClaudeSDKClient(options).connect()` | `Agent.create(...)` / `session/new` / `create-chat` | Session ID format; resume semantics (Cursor SDK drops tool restrictions and inline MCP on resume, so pass them again) |
| send message | `client.query(text)` | `agent.send(text)` / `session/prompt` / `-p --resume` | Cursor: put key instructions at the start of the message |
| stream reply | `StreamEvent` text deltas, `AssistantMessage`, `ResultMessage` | `on_delta` / `agent_message_chunk` / partial `assistant` events | Map each engine's events to one `agentlib` event type (text delta, tool call, tool result, turn done, error, rate limit) |
| use tools | In-process `create_sdk_mcp_server` | `custom_tools` (in-process) / localhost HTTP MCP | Define tools once, engine-neutral (name, description, JSON schema, Python handler). Each adapter wraps them. Tool names differ (`mcp__planner__ask_user` vs plain names), so normalise them |
| count tokens | `ResultMessage.usage` (per turn) | `usage` message / stream-json `usage` / ACP: unknown | Both give new input, output, cache read and cache write. Normalise field names. Cursor's ACP may not report usage |

**Verdict: fully supported on Claude. Supported on Cursor through the Python SDK, with one real gap: instructions.** With ACP the gap is instructions plus possibly token counts; with print mode it is instructions plus per-run MCP. Keep these engine-specific in the interface:
- how instructions are delivered: system prompt vs `AGENTS.md` file plus message prefix
- prompt-cache ordering (Claude only)
- model names
- rate-limit events (Claude's `RateLimitEvent` vs Cursor's `RateLimitError`)
- authentication

Add a `capabilities` field on each engine (for example `system_prompt: bool`, `usage: bool`, `sandbox_windows: bool`). The app can then warn or refuse when a role needs something the engine lacks.

---

## 9. Quick experiments

All commands work in PowerShell on Windows unless marked otherwise. Use a throwaway folder.

**Claude Agent SDK**

| ID | Check | How |
|---|---|---|
| A1 | Only our tools are offered | Start a client with the §5(b) options. Print `SystemMessage(subtype="init").data["tools"]` and `data["apiKeySource"]`. Expect only `mcp__planner__*` and a non-API-key source. |
| A2 | `CLAUDE_CODE_MAX_RETRIES=0` accepted | `$env:CLAUDE_CODE_MAX_RETRIES="0"; $env:ANTHROPIC_BASE_URL="http://127.0.0.1:9"; claude -p "hi" --output-format stream-json --verbose`, then count the retry lines. Repeat with `1`. Afterwards `Remove-Item Env:ANTHROPIC_BASE_URL`. |
| A3 | Filesystem settings really off | Put a `CLAUDE.md` saying "always answer in French" and a `.claude/skills/x/SKILL.md` in `cwd`. Run with `setting_sources=[]`. Expect English and no skill in the init message. |
| A4 | Usage and rate-limit events on subscription | Run 3 turns with `ClaudeSDKClient`. Log each `ResultMessage.usage` (expect `cache_read_input_tokens` > 0 from turn 2) and any `RateLimitEvent`. |
| A5 | Windows long prompt | 50 KB system prompt as a string (expect failure) vs `{"type":"file"}` (expect success). |

**Cursor**

| ID | Check | How |
|---|---|---|
| C1 | Print-mode usage and stream events | `agent -p "Reply with OK" --output-format stream-json --stream-partial-output --model <model> > out.jsonl`, then look for `"usage"` and list the distinct `type`/`subtype` values. Run it twice with `--resume <session_id>` and check `cacheReadTokens`. |
| C2 | Built-in tools in print mode | In an empty folder with `.cursor/cli.json` = `{"permissions":{"deny":["Shell(*)","Read(**)","Write(**)","WebFetch(*)"]}}`, run `agent -p "List the files here and run 'whoami'" --output-format stream-json`. Note which `tool_call` events appear and whether they were rejected. Repeat without `--force`, then with it. |
| C3 | ACP: MCP per session, usage, load | Python with `agent-client-protocol`: `initialize` → `authenticate cursor_login` → `session/new` with `mcpServers` = our localhost HTTP server → `session/prompt` asking it to call `save_note`. Log every `session/update` kind, especially `usage_update` and any `_meta` usage. Reject every `session/request_permission` that isn't ours. Then restart and `session/load` the same ID. |
| C4 | SDK: only custom tools | `cursor-sdk==1.3.1`, `Agent.create(model=..., tools=[], local=LocalAgentOptions(cwd=empty_dir, custom_tools={...}))`. Ask it to call the tool and to read a file. Repeat with `tools=["mcp"]`. This shows whether `tools=[]` also hides custom tools. |
| C5 | SDK: which rules load | `cwd` containing `AGENTS.md` ("always answer in French"), and `setting_sources` unset. Then add a user rule in the Cursor app and check whether it leaks in. Repeat with `setting_sources=["project"]`. |
| C6 | SDK: Anthropic models locally on Windows | Same as C4 with each Claude model from `agent models`, on Windows and Mac. Several forum threads report empty-error failures. |
| C7 | Parallel processes | Start two `agent -p ... --output-format json` runs in different folders at the same moment, 10 times. Check for lock errors or mixed-up session IDs. |
| C8 | Error shape | `$env:CURSOR_API_KEY="invalid"; agent -p "hi" --output-format stream-json; $LASTEXITCODE`. Record stderr, the exit code, and whether a `result` event appears. Repeat with an invalid `--model`. |
| C9 | `systemPrompt` access | TS SDK `systemPrompt: "Reply exactly X"` on a local agent. The expected error now names the account gate. Re-run after asking Cursor to enable it. |
