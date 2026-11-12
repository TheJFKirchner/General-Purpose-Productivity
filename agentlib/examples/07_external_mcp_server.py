"""07 - External MCP server.  LIVE: uses your Claude login, costs tokens (haiku, ~$0.01).

Run:  python examples/07_external_mcp_server.py --live
      (without --live it prints this note and shows the fake engine refusing the agent: it cannot start
      external MCP servers, so capabilities.mcp_servers is False and agent.session() raises CapabilityError)

Raw SDK equivalent: ClaudeAgentOptions(mcp_servers={"notes": {...}}, allowed_tools=["mcp__notes__*"]).

Agent.mcp_servers maps a server name to either
  - a path to a Python server file -> run as {"type": "stdio", "command": sys.executable, "args": [path]}
    (a relative path is resolved against Agent.cwd when cwd is set), or
  - a config dict, passed through to the engine as-is, e.g.
      {"type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]}
      {"type": "http", "url": "https://example.com/mcp", "headers": {"Authorization": "Bearer ..."}}
Every tool of a listed server is pre-approved (mcp__<name>__*). The model sees mcp__notes__add_note;
naming them in tools= is optional and just documents intent.
"""
import sys
from pathlib import Path

from agentlib import Agent, CapabilityError

HERE = Path(__file__).resolve().parent
LIVE = "--live" in sys.argv

agent = Agent(
    "notes_keeper",
    instructions="Use the notes tools. Be brief.",
    model="haiku",
    engine="claude" if LIVE else "fake",
    mcp_servers={"notes": str(HERE / "07_notes_server.py")},
    tools=["mcp__notes__add_note", "mcp__notes__list_notes"],
)

if not LIVE:
    from agentlib import fake  # noqa: F401  (registers the fake engine)
    print(__doc__)
    try:
        agent.session()
    except CapabilityError as e:
        print("fake engine:", e.short)
    sys.exit(0)

reply = agent.ask_sync("Save a note 'buy milk', then list all notes.")
for c in reply.tool_calls:
    print(f"  {c.name}({c.input}) -> {c.result!r} error={c.is_error}")   # external tools keep their full name
print("status:", reply.status, "| text:", reply.text)
print(f"cost: ${reply.cost_usd:.6f}")
