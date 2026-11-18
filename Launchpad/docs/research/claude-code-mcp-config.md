# Claude Code MCP config (for "Import from Claude Code") and the `mcp` package

Used by `app/mcpimport.py` (import) and, through agentlib's `agentlib/mcp_check.py`, by every MCP test (`app/mcplib.py`).

## Where Claude Code keeps MCP servers (checked 2026-11-17)
- Local scope (the default for `claude mcp add`): `~/.claude.json` -> `projects["<absolute project path>"].mcpServers`. On Windows the keys use forward slashes (`C:/Users/...`), so paths are compared normalised
- Project scope: `<project>/.mcp.json` -> `mcpServers` (meant to be committed)
- User scope: `~/.claude.json` -> top-level `mcpServers`. The docs page does not print the key; the quickstart and community guides say top level. A GitHub issue (#16728) reports that `--scope user` once wrote under a project entry instead; such a server is found only as the local scope of a connected folder
- Precedence on a name clash: local > project > user (> plugin > claude.ai connectors; managed servers above all). Launchpad keeps the first of a name in that order
- `CLAUDE_CONFIG_DIR` set: `.claude.json` is looked for in that folder first
- Entry shapes: `{type?: "stdio", command, args, env}` (a command without type is stdio); `{type: "http" | "sse" | "streamable-http", url, headers}`; `ws` and helper-based entries (`headersHelper`, `oauth`) are not imported
- `${VAR}` and `${VAR:-default}` expand in command, args, env, url and headers; an unset variable without a default is left as is. Launchpad copies references unexpanded and expands them when it tests or runs a server

## The `mcp` package (MCP protocol library, installed with claude-agent-sdk)
- Installed version here: 2.3.0. 2.x moved things: `mcp.server.mcpserver.MCPServer` (1.x `mcp.server.fastmcp.FastMCP`), `streamable_http_client(url, http_client=create_mcp_http_client(headers=...))` (1.x `streamablehttp_client(url, headers=...)`), pydantic fields in snake_case (`next_cursor`, `server_info`). agentlib's helper handles both
- `stdio_client(params, errlog=...)`: `errlog` must be a real file (it is passed to the subprocess); a temp file captures the server's error output
- An `env` given to `StdioServerParameters` replaces the default (a short safe list), so the helper passes this process's environment plus the server's `env`, like Claude Code does
- Errors arrive wrapped in exception groups (anyio task groups); the helper unwraps to the first real error. `anyio.fail_after` bounds the whole check

## Links
- https://code.claude.com/docs/en/mcp (scopes, file locations, entry shapes, expansion)
- https://code.claude.com/docs/en/mcp-quickstart.md (user scope = top-level `mcpServers`)
- https://github.com/anthropics/claude-code/issues/16728 (user scope written under a project entry)
- https://cursor.com/docs/cli/installation (Cursor CLI: `agent`, older `cursor-agent`; for app/connections/cursor.py)
