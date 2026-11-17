"""Cost totals: the ONE place that adds per-agent costs up and formats them (a leaf module: imports nothing of the app).

- Where a cost comes from is unchanged: the engine's per-turn cost -> agentlib Reply -> Meter.cost_usd (app/meter.py)
- Which roles count: a session's total = every agent of the session except the planner; the planner is its own share
  (never inside the total). Role ids keep the old words (astronaut = Explorer, visual = Visualizer, pilot = CLI)
- The server sends every total the page shows (hub.emit_totals: usage scope app / session / chat); the page only displays
- meter_usage(m): one agent run's own figures, sent with a role review's case and a drafting call (no session, so they
  count in the app-wide total only: role "reviewer" / "drafter", session_id None)
- Python-side text: usd(x) = "$0.1234" (four decimals; symbol=False for a table cell); wire(x) = the figure sent to the page
"""
from __future__ import annotations

PLANNER_ROLE = "planner"
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")


def usd(value: float, *, symbol: bool = True) -> str:
    return f"{'$' if symbol else ''}{float(value or 0.0):.4f}"


def wire(value: float) -> float:
    """A cost as sent to the page (six decimals)."""
    return round(float(value or 0.0), 6)


def session_split(meters, session_id: str) -> tuple[float, float]:
    """(total = every agent of the session but the planner, planner) in dollars."""
    ms = [m for m in meters if m.session_id == session_id]
    return (sum(m.cost_usd for m in ms if m.role != PLANNER_ROLE),
            sum(m.cost_usd for m in ms if m.role == PLANNER_ROLE))


def _tokens(ms) -> dict:
    return {k: sum(getattr(m.usage, k) for m in ms) for k in TOKEN_FIELDS}


def app_usage(meters) -> dict:
    """The app-wide usage event: every meter, plus the cost per role (the Whole-app tooltip)."""
    ms = list(meters)
    u = _tokens(ms)
    by_role: dict[str, float] = {}
    for m in ms:
        by_role[m.role] = by_role.get(m.role, 0.0) + m.cost_usd
    return {"type": "usage", "scope": "app", "tokens": sum(u.values()), "cost": wire(sum(m.cost_usd for m in ms)),
            "by_role": {r: wire(v) for r, v in by_role.items()}, **u}


def session_usage(meters, session_id: str) -> dict:
    """A session's totals: cost = every agent but the planner (agents / token counts are those same agents'),
    planner_cost = the planner's own share."""
    total, planner = session_split(meters, session_id)
    crew = [m for m in meters if m.session_id == session_id and m.role != PLANNER_ROLE]
    steps: dict[str, dict] = {}
    for n in sorted({m.step for m in crew if m.role == "builder" and m.step is not None}):
        ms = [m for m in crew if m.role == "builder" and m.step == n]
        steps[str(n)] = {"cost": wire(sum(m.cost_usd for m in ms)), "tool_calls": sum(m.tool_calls for m in ms),
                         "agents": len(ms), **_tokens(ms)}
    return {"type": "usage", "scope": "session", "session_id": session_id, "cost": wire(total),
            "planner_cost": wire(planner), "agents": len(crew), **_tokens(crew), "steps": steps}


def meter_usage(meter) -> dict:
    """One agent run's own figures (a role review, a drafting call): {tokens, cost, input_tokens, output_tokens,
    cache_read_tokens, cache_write_tokens}; tokens = the four counts, as in the app-wide usage."""
    u = _tokens([meter])
    return {"tokens": sum(u.values()), "cost": wire(meter.cost_usd), **u}


def chat_usage(meters, chat_id: str) -> dict:
    ms = [m for m in meters if m.chat_id == chat_id]
    u = _tokens(ms)
    return {"type": "usage", "scope": "chat", "chat_id": chat_id, "cost": wire(sum(m.cost_usd for m in ms)),
            "tokens": sum(u.values()), "tool_calls": sum(m.tool_calls for m in ms), "agents": len(ms), **u}
