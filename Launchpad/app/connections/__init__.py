"""CLI connection tests (Settings > Connections): one small script per tool, each runnable alone from a terminal.

- CONNECTIONS: id, display name (the real tool name: Connections is the one place the UI names a harness), module.
  The page gets [{id, name}] (mcp_library connections) and sends test_connection {id}; adding a tool = one more script
  with ID, NAME and `async def test(engine, *, request=True) -> dict` + one more row here, no page change
- A test returns {installed, version, reachable, usable, detail}; nothing runs until the user clicks Test
- claude_code.py: program + version + one tiny request through agentlib (fake engine in the demo: zero tokens)
- cursor.py: install check only; usable false while agentlib's Cursor engine is a stub
"""
from __future__ import annotations

import importlib

CONNECTIONS: tuple[dict, ...] = (
    {"id": "claude_code", "name": "Claude Code", "module": "claude_code"},
    {"id": "cursor", "name": "Cursor", "module": "cursor"},
)


def listing() -> list[dict]:
    return [{"id": c["id"], "name": c["name"]} for c in CONNECTIONS]


def find(cid: str) -> dict | None:
    return next((c for c in CONNECTIONS if c["id"] == cid), None)


async def run(cid: str, engine: str) -> dict:
    """The connection_test event for one tool (ValueError for an unknown id)."""
    c = find(cid)
    if c is None:
        raise ValueError(f"unknown connection {cid!r}")
    mod = importlib.import_module(f"{__name__}.{c['module']}")
    try:
        r = await mod.test(engine)
    except Exception as e:  # noqa: BLE001 -- a broken test shows as a result, not a crash
        r = {"installed": False, "version": None, "reachable": None, "usable": False,
             "detail": f"The test itself failed: {type(e).__name__}: {e}"}
    return {"type": "connection_test", "id": cid, **{k: r.get(k) for k in ("installed", "version", "reachable",
                                                                         "usable", "detail")}}
