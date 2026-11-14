"""LIVE cost of the Opus planner with vs without the Claude Code preset (a few tens of cents). Not collected by pytest.

    python tests/live_planner_cost.py --variant lean      # as Launchpad runs it: its own prompt only
    python tests/live_planner_cost.py --variant preset    # hypothetical: Claude Code preset + its prompt appended

Same three-turn exchange each time in a scratch Flask project: a planning request (expects an ask_user round),
the round answered with the recommendations, then "explore once and draft the plan" (explore + write_plan).
Prints per-turn usage and cost, the first model call's prompt size, and what the planner did.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentlib.engines import base  # noqa: E402

from app import crew  # noqa: E402
from app.hub import Hub  # noqa: E402
from app.meter import Meter  # noqa: E402
from app.settings import Settings  # noqa: E402

TURNS = [
    ("user_message", "I want to add a CSV export button to the orders page of this small Flask app. Ask me what you "
                     "need to know before planning."),
    ("round_answer", None),
    ("user_message", "Use explore once to check where the orders page and its query are defined, then draft the plan."),
]


def make_project() -> Path:
    p = Path(tempfile.mkdtemp(prefix="launchpad-plannercost-")) / "shop"
    (p / "templates").mkdir(parents=True)
    (p / "README.md").write_text("# Shop\nSmall Flask app: products, orders, customers.\n", encoding="utf-8")
    (p / "app.py").write_text(
        "from flask import Flask, render_template\nfrom db import fetch_orders\n\napp = Flask(__name__)\n\n\n"
        "@app.route('/orders')\ndef orders():\n    return render_template('orders.html', orders=fetch_orders())\n",
        encoding="utf-8")
    (p / "db.py").write_text("def fetch_orders():\n    return [{'id': 1, 'customer': 'Ana', 'total': 42.0}]\n",
                             encoding="utf-8")
    (p / "templates" / "orders.html").write_text("<h1>Orders</h1>\n<table>{% for o in orders %}<tr><td>{{o.id}}</td>"
                                                 "</tr>{% endfor %}</table>\n", encoding="utf-8")
    return p


async def main(variant: str) -> int:
    project = make_project()
    first_calls: list = []
    orig_reply = base.TurnState.reply

    def reply(self, **kw):
        calls = list(self.usage_by_message.values())
        first_calls.append(calls[0] if calls else None)
        return orig_reply(self, **kw)
    base.TurnState.reply = reply

    if variant == "preset":                      # the planner as if it ran with the Claude Code preset
        orig_load = crew.load

        def load(role, **kw):
            if role == "planner":
                kw["setup"] = "project"
            return orig_load(role, **kw)
        crew.load = load

    turns: list[dict] = []
    orig_add = Meter.add_reply

    async def add_reply(self, reply, **kw):
        if self.role == "planner" and reply is not None:
            turns.append({"usage": reply.usage, "cost": reply.cost_usd, "tools": [c.name for c in reply.tool_calls],
                          "status": reply.status, "text": reply.text, "questions": len(reply.questions),
                          "first_call": first_calls[-1] if first_calls else None})
        return await orig_add(self, reply, **kw)
    Meter.add_reply = add_reply

    hub = Hub(Settings(project=project, engine="claude"))
    events: list[dict] = []

    async def client(ev):
        events.append(ev)
    await hub.connect(client)
    print(f"variant={variant}  planner setup={hub.current.chat.agent.setup}  model={hub.current.chat.agent.model}")
    try:
        for kind, text in TURNS:
            if kind == "round_answer":
                rounds = [e for e in events if e["type"] == "question_round"]
                if not rounds:
                    print("(no question round to answer; sending a plain reply instead)")
                    await hub.handle({"type": "user_message", "text": "Use your recommended answers."})
                    continue
                r = rounds[-1]
                await hub.handle({"type": "round_answer", "roundId": r["id"],
                                  "answers": {q["id"]: {"accepted": True} for q in r["questions"]}})
            else:
                await hub.handle({"type": "user_message", "text": text})
            await asyncio.sleep(0.5)
            while hub.current.visuals.tasks:
                await asyncio.sleep(0.5)
    finally:
        await hub.close()

    print("\nturn | tools | questions | input | output | cache read | cache write (1h) | cost | first call prompt")
    total = 0.0
    for i, t in enumerate(turns, 1):
        u, fc = t["usage"], t["first_call"]
        prefix = (fc.input_tokens + fc.cache_read_tokens + fc.cache_write_tokens) if fc else None
        total += t["cost"]
        print(f"{i} | {','.join(t['tools']) or '-'} | {t['questions']} | {u.input_tokens} | {u.output_tokens} | "
              f"{u.cache_read_tokens} | {u.cache_write_tokens} ({u.cache_write_1h_tokens}) | ${t['cost']:.4f} | "
              f"{prefix} (cr {fc.cache_read_tokens if fc else '-'}, cw {fc.cache_write_tokens if fc else '-'})")
    print(f"PLANNER TOTAL: ${total:.4f}")
    other = sum(m.cost_usd for m in hub.meters if m.role != "planner")
    print(f"other agents (Explorer etc.): ${other:.4f}")
    for i, t in enumerate(turns, 1):
        txt = t["text"]
        fmt = {"headings": bool(re.search(r"(?m)^#", txt)), "tables": "|" in txt,
               "bullets": bool(re.search(r"(?m)^\s*[-*] ", txt)), "chars": len(txt)}
        print(f"turn {i} reply {fmt}: {txt[:300]!r}")
    drafts = [e for e in events if e["type"] == "plan_draft"]
    if drafts:
        print("\nplan draft steps:", [s["title"] for s in drafts[-1]["steps"]])
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["lean", "preset"], required=True)
    sys.exit(asyncio.run(main(ap.parse_args().variant)))
