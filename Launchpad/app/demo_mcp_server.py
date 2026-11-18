"""A tiny local MCP server for the zero-token demo (`python -m app.launch --fake`): the demo's MCP library lists it, so
its background test really starts it, lists its tools and stops it (no network, no model, no tokens).

    python app/demo_mcp_server.py --set notes       # add_note, list_notes, search_notes
    python app/demo_mcp_server.py --set glossary    # define_term, list_terms

Uses the `mcp` package (installed with the Claude Agent SDK). Made-up data; nothing is saved.
"""
from __future__ import annotations

import sys

try:
    from mcp.server.mcpserver import MCPServer as Server      # mcp 2.x
except ImportError:                                           # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server

which = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv[:-1] else "notes"
server = Server(f"demo-{which}")
NOTES: list[str] = []
TERMS = {"SKU": "Stock keeping unit: one sellable item.", "AOV": "Average order value."}

if which == "glossary":
    @server.tool()
    def define_term(term: str) -> str:
        """Look up a term in the shop's glossary (made up)."""
        return TERMS.get(term.upper(), "not in the glossary")

    @server.tool()
    def list_terms() -> str:
        """List every glossary term."""
        return ", ".join(sorted(TERMS))
else:
    @server.tool()
    def add_note(text: str) -> str:
        """Save a short note."""
        NOTES.append(text)
        return f"saved note #{len(NOTES)}"

    @server.tool()
    def list_notes() -> str:
        """List the saved notes."""
        return "\n".join(NOTES) or "(no notes)"

    @server.tool()
    def search_notes(word: str) -> str:
        """Find notes containing a word."""
        return "\n".join(n for n in NOTES if word.lower() in n.lower()) or "(none)"

if __name__ == "__main__":
    server.run()
