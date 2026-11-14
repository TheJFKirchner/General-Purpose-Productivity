"""LIVE planner cost study (planner as Launchpad runs it: Sonnet start, may promote to Opus; Haiku sub-agents). Not collected by pytest.

    python tests/live_planner_study.py --conv A                 # short: request, one round, draft (~3 turns)
    python tests/live_planner_study.py --conv B                 # longer: vague request, typed push-back, 2 lookups,
                                                                #   a visual set + pick, draft, 2 revisions (~8 turns)
    python tests/live_planner_study.py --conv A --turns 2 --effort low     # same, lowest effort, first 2 turns

Per turn: uncached input, cache read, cache write, output (thinking inferred = output minus visible text and tool
inputs at ~3.6 chars/token), planner cost, sub-agent cost; then a breakdown by component at Opus 5.5 prices.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import crew  # noqa: E402
from app.hub import Hub  # noqa: E402
from app.meter import Meter  # noqa: E402
from app.settings import Settings  # noqa: E402

# Published per-token prices: (input, 5m write, 1h write, cache read, output)
PRICES = {"opus": (4e-6, 5e-6, 8e-6, 0.2e-6, 20e-6),        # Opus 5.5: $4 / $5 / $8 / $0.20 / $20 per MTok
          "sonnet": (2e-6, 2.5e-6, 4e-6, 0.1e-6, 10e-6)}      # Sonnet 5.5: $2 / $2.50 / $4 / $0.10 / $10
P_IN, P_W5, P_W1, P_READ, P_OUT = PRICES["opus"]


def price(model_id: str):
    return PRICES["sonnet"] if "sonnet" in (model_id or "") else PRICES["opus"]
CHARS_PER_TOKEN = 3.6

CONV_A = [
    ("say", "I want to add a CSV export button to the orders page of this small Flask app. Ask me what you need "
            "to know before planning."),
    ("answer", {}),
    ("say", "Use explore once to check where the orders page and its query are defined, then draft the plan."),
]

CONV_B = [
    ("say", "I need some kind of dashboard for our clinic managers, something to keep an eye on how things are "
            "going. Not sure exactly what yet."),
    ("answer", {"first": "No, not weekly: they check it every morning, so it has to be daily."}),
    ("say", "Before more questions, check what data files and existing reports the project already has."),
    ("answer", {"first": "Keep it to four KPIs at most; managers look at it on laptops."}),
    ("say", "For the main trend chart, show me some options rather than describing them."),
    ("pick", 2),
    ("say", "I picked one. Now check where the appointment data is loaded, then draft the plan."),
    ("say", "Revise it: drop any export step and add a first step that tests everything with sample data."),
    ("say", "One last change: call the dashboard 'Clinic Pulse' and keep the rest as is."),
]


def make_project(conv: str) -> Path:
    p = Path(tempfile.mkdtemp(prefix=f"launchpad-study{conv}-")) / "proj"
    p.mkdir(parents=True)
    if conv == "A":
        (p / "templates").mkdir()
        (p / "README.md").write_text("# Shop\nSmall Flask app: products, orders, customers.\n", encoding="utf-8")
        (p / "app.py").write_text("from flask import Flask, render_template\nfrom db import fetch_orders\n\n"
                                  "app = Flask(__name__)\n\n\n@app.route('/orders')\ndef orders():\n"
                                  "    return render_template('orders.html', orders=fetch_orders())\n", encoding="utf-8")
        (p / "db.py").write_text("def fetch_orders():\n    return [{'id': 1, 'customer': 'Ana', 'total': 42.0}]\n",
                                 encoding="utf-8")
        (p / "templates" / "orders.html").write_text("<h1>Orders</h1>\n", encoding="utf-8")
    else:
        for d in ("data", "src", "reports"):
            (p / d).mkdir()
        (p / "README.md").write_text("# Clinic ops\nScripts and data for the clinic's operations team.\n",
                                     encoding="utf-8")
        (p / "data" / "appointments.csv").write_text(
            "date,clinic,department,booked,attended,no_show,wait_minutes\n"
            "2026-11-01,North,Cardiology,42,38,4,18\n2026-11-01,South,Pediatrics,51,47,4,12\n", encoding="utf-8")
        (p / "data" / "staff.csv").write_text("date,clinic,doctors_on_shift,nurses_on_shift\n2026-11-01,North,6,14\n",
                                              encoding="utf-8")
        (p / "src" / "load_data.py").write_text(
            "import csv\n\n\ndef load_appointments(path='data/appointments.csv'):\n"
            "    with open(path, newline='') as f:\n        return list(csv.DictReader(f))\n", encoding="utf-8")
        (p / "reports" / "weekly.md").write_text("# Weekly ops report\nAttendance, no-shows and waits per clinic, "
                                                 "built by hand every Monday.\n", encoding="utf-8")
    return p


def visible_tokens(text: str, calls) -> float:
    chars = len(text or "") + sum(len(json.dumps(c.input, ensure_ascii=False)) for c in calls)
    return chars / CHARS_PER_TOKEN


async def main(conv: str, max_turns: int | None, effort: str | None, pin: str | None = None) -> int:
    script = CONV_A if conv == "A" else CONV_B
    project = make_project(conv)
    if effort:
        orig_load = crew.load

        def load(role, **kw):
            if role == "planner":
                kw["effort"] = effort
            return orig_load(role, **kw)
        crew.load = load

    planner_turns: list[dict] = []
    orig_add = Meter.add_reply

    async def add_reply(self, reply, **kw):
        if self.role == "planner" and reply is not None:
            planner_turns.append({"reply": reply})
        return await orig_add(self, reply, **kw)
    Meter.add_reply = add_reply

    hub = Hub(Settings(project=project, engine="claude", planner_model=pin))
    events: list[dict] = []

    async def client(ev):
        events.append(ev)
    await hub.connect(client)
    ls = hub.current
    rows = []

    def sub_cost():
        return {r: sum(m.cost_usd for m in hub.meters if m.role == r) for r in ("astronaut", "visual")}

    try:
        for i, (kind, arg) in enumerate(script, 1):
            if max_turns and len(rows) >= max_turns:
                break
            before_sub, n_before = sub_cost(), len(planner_turns)
            if kind == "pick":
                sets = list(ls.visuals.sets.values())
                if sets and len(sets[-1].options) >= arg:
                    while ls.visuals.tasks:
                        await asyncio.sleep(0.3)
                    vset = sets[-1]
                    opt = vset.options[arg - 1]
                    if opt.status == "ready":
                        await hub.handle({"type": "visual_pick", "session_id": ls.id, "set_id": vset.id,
                                          "option_id": opt.id})
                        print(f"(picked {vset.id}/{opt.id} {opt.label!r})")
                continue
            if kind == "answer":
                rounds = [e for e in events if e["type"] == "question_round"]
                answered = {e.get("roundId") for e in events if e.get("type") == "_answered"}
                if rounds and rounds[-1]["id"] not in answered:
                    r = rounds[-1]
                    answers = {}
                    for j, q in enumerate(r["questions"]):
                        typed = arg.get("first") if j == 0 else None
                        answers[q["id"]] = {"text": typed} if typed else {"accepted": True}
                    events.append({"type": "_answered", "roundId": r["id"]})
                    await hub.handle({"type": "round_answer", "roundId": r["id"], "answers": answers})
                    label = "round answer" + (" (typed push-back)" if arg.get("first") else "")
                else:
                    text = arg.get("first") or "Go with your recommendations."
                    await hub.handle({"type": "user_message", "text": text})
                    label = "typed reply (no open round)"
            else:
                await hub.handle({"type": "user_message", "text": arg})
                label = arg[:48]
            while ls.visuals.tasks:
                await asyncio.sleep(0.3)
            after_sub = sub_cost()
            new = planner_turns[n_before:]
            for t in new:
                r = t["reply"]
                u = r.usage
                vis = visible_tokens(r.text, r.tool_calls)
                rows.append({"by_model": {m: v for m, v in (r.usage_by_model or {}).items()},
                             "turn": len(rows) + 1, "label": label, "tools": [c.name for c in r.tool_calls],
                             "questions": len(r.questions), "in": u.input_tokens, "cr": u.cache_read_tokens,
                             "cw": u.cache_write_tokens, "cw1h": u.cache_write_1h_tokens, "out": u.output_tokens,
                             "visible": round(vis), "think": max(0, round(u.output_tokens - vis)),
                             "cost": r.cost_usd, "astro": after_sub["astronaut"] - before_sub["astronaut"],
                             "visual": after_sub["visual"] - before_sub["visual"], "text": r.text})
    finally:
        await hub.close()

    print(f"\nConversation {conv}  effort={effort or 'default'}  planner start={hub.current.chat.start_model} "
          f"top={hub.current.chat.top_model} now={hub.current.chat.model}")
    print("turn | user | planner tools | in | cache read | cache write (1h) | output (visible / thinking~) | "
          "planner $ | Explorer $ | Visualizer $")
    for r in rows:
        print(f"{r['turn']} | {r['label']} | {','.join(r['tools']) or '-'}{' (' + str(r['questions']) + 'q)' if r['questions'] else ''}"
              f" | {r['in']} | {r['cr']} | {r['cw']} ({r['cw1h']}) | {r['out']} ({r['visible']} / {r['think']}) | "
              f"{r['cost']:.4f} | {r['astro']:.4f} | {r['visual']:.4f}")
        for m, v in r["by_model"].items():
            u = v["usage"]
            print(f"      {m}: in {u.input_tokens} read {u.cache_read_tokens} write {u.cache_write_tokens} "
                  f"out {u.output_tokens} ${v['cost_usd']:.4f}")
    tot = {k: sum(r[k] for r in rows) for k in ("in", "cr", "cw", "cw1h", "out", "visible", "think", "cost", "astro", "visual")}
    comp = {"cache writes": 0.0, "cache reads": 0.0, "uncached input": 0.0, "visible output": 0.0,
            "thinking (inferred)": 0.0, "sub-agents": tot["astro"] + tot["visual"]}
    for r in rows:                                   # each model's tokens at that model's price
        parts = r["by_model"] or {"opus": {"usage": None}}
        out_total = sum(v["usage"].output_tokens for v in r["by_model"].values()) or r["out"] or 1
        for m, v in parts.items():
            pi, p5, p1, pr, po = price(m)
            u = v["usage"]
            if u is None:
                continue
            share = u.output_tokens / out_total
            comp["cache writes"] += u.cache_write_tokens * p1
            comp["cache reads"] += u.cache_read_tokens * pr
            comp["uncached input"] += u.input_tokens * pi
            comp["visible output"] += min(r["visible"], r["out"]) * share * po
            comp["thinking (inferred)"] += r["think"] * share * po
    grand = tot["cost"] + tot["astro"] + tot["visual"]
    print(f"\nplanner reported ${tot['cost']:.4f}; computed from tokens at published prices "
          f"${sum(v for k, v in comp.items() if k != 'sub-agents'):.4f}; sub-agents ${comp['sub-agents']:.4f}; "
          f"conversation total ${grand:.4f}")
    for k, v in comp.items():
        print(f"  {k:<20} ${v:.4f}  {100 * v / grand:5.1f}%")
    for e in events:
        if e["type"] == "planner_model" and e["promoted"]:
            print(f"\nPROMOTED to {e['model']} by {e['by']}: {e['reason']!r} (during turn {len(rows) and next((r['turn'] for r in rows if any('opus' in m for m in r['by_model'])), '?')})")
    for e in events:
        if e["type"] == "question_round":
            print(f"\nquestion round {e['round']}:")
            for q in e["questions"]:
                print(f"  - {q['title']}  [rec: {q.get('rec')}]")
    drafts = [e for e in events if e["type"] == "plan_draft"]
    print("\nplan drafts:", [(d["revision"], len(d["markdown"])) for d in drafts])
    for r in rows:
        print(f"turn {r['turn']} reply ({len(r['text'])} chars): {r['text'][:220]!r}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--conv", choices=["A", "B"], required=True)
    ap.add_argument("--turns", type=int, default=None)
    ap.add_argument("--effort", default=None, help="planner effort override (low|medium|high|xhigh|max)")
    ap.add_argument("--pin", default=None, help="pin the planner to one model (no promotion), e.g. opus")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.conv, a.turns, a.effort, a.pin)))
