"""A tiny stdio MCP server used by 07_external_mcp_server.py. Not run directly.

It uses the `mcp` package, which claude-agent-sdk already installs. agentlib starts it with the same
Python (sys.executable) when an Agent lists it in mcp_servers as a path to a .py file.
"""
try:
    from mcp.server.mcpserver import MCPServer as Server      # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server          # mcp 1.x

server = Server("notes")
NOTES: list[str] = []


@server.tool()
def add_note(text: str) -> str:
    """Save a short note."""
    NOTES.append(text)
    return f"saved note #{len(NOTES)}"


@server.tool()
def list_notes() -> str:
    """List all saved notes."""
    return "\n".join(f"{i}. {n}" for i, n in enumerate(NOTES, 1)) or "(no notes)"


if __name__ == "__main__":
    server.run()          # stdio transport by default
