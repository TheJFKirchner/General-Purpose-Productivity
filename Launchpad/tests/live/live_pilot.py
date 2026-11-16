"""LIVE check of the regular session (Claude Code chat) on real Claude. Spends tokens (haiku, a few cents). Not collected by pytest.

    python tests/live/live_pilot.py                 # from the Launchpad folder
    python tests/live/live_pilot.py --model sonnet  # the production default model (costs more)
    python tests/live/live_pilot.py --turns 5       # only some turns (1-5)

Scratch project in a new temp folder: .claude/settings.json denies editing blocked.txt; .claude/settings.local.json
allows `mkdir` (checked-in allow rules need Claude Code's folder trust, which a temp folder never has).
Five short turns through the real server and websocket:
1. default mode: Write hello.txt -> a real permission card reaches the script -> Allow -> file written
2. default mode: a python command -> card -> "always" saved to project-local settings -> settings.local.json written
3. accept_edits: Edit hello.txt -> no card, edit goes through
4. plan mode: plan proposal card -> approved into accept_edits -> file created without a card
5. default mode: the project's own settings rules: `mkdir` runs unasked, writing blocked.txt is denied, no cards
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # the Launchpad folder
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402
import websockets  # noqa: E402

from app.server import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

PORT, CODE = 8796, "pilot"

TURNS = [
    ("default", "Use the Write tool to create hello.txt containing exactly: hi. Nothing else."),
    ("default", 'Run exactly this shell command with Bash: python -c "print(42)". Nothing else.'),
    ("accept_edits", "Use the Edit tool to change hello.txt so it contains exactly: hello. Nothing else."),
    ("plan", "Task: create plan.txt containing exactly: planned. Do not explore. Propose a one-line plan with "
             "ExitPlanMode now; once approved, create the file with Write."),
    ("default", "Run `mkdir made_by_rule` with Bash, then use Write to create blocked.txt containing x. "
                "If anything is denied, do not retry; just say what happened."),
]


def make_project() -> Path:
    p = Path(tempfile.mkdtemp(prefix="launchpad-pilot-")) / "proj"
    (p / ".claude").mkdir(parents=True)
    (p / "README.md").write_text("# Pilot scratch project\n", encoding="utf-8")
    # Checked-in project settings: the deny rule applies at once. (Allow rules here are ignored until the folder
    # is trusted in Claude Code, Claude Code's own rule; a temp folder never is.) Edit(...) rules cover Write too.
    (p / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"deny": ["Edit(blocked.txt)"]}},
                                                            indent=1), encoding="utf-8")
    # Personal project-local settings (where "always allow, this project" saves): honoured without trust
    (p / ".claude" / "settings.local.json").write_text(json.dumps({"permissions": {"allow": ["Bash(mkdir:*)"]}},
                                                                  indent=1), encoding="utf-8")
    return p


async def main(model: str, only: set[int] | None = None) -> int:
    project = make_project()
    app = create_app(PORT, CODE, Settings(project=project, engine="claude", pilot_model=model))
    hub = app.state.hub
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    events: list[dict] = []
    t0 = time.monotonic()
    try:
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws?code={CODE}", origin=f"http://127.0.0.1:{PORT}") as ws:
            async def send(o):
                await ws.send(json.dumps(o))

            async def pump(until, timeout=240):
                end = time.monotonic() + timeout
                while not until():
                    ev = json.loads(await asyncio.wait_for(ws.recv(), max(0.1, end - time.monotonic())))
                    ev["_t"] = round(time.monotonic() - t0, 1)
                    events.append(ev)
                    t = ev["type"]
                    if t in ("queue_item", "chat_mode", "chat_done", "chat_message", "system"):
                        short = {k: v for k, v in ev.items() if k not in ("type",)}
                        print(f"[{ev['_t']:>6}s] {t}: {json.dumps(short)[:230]}", flush=True)
                    if t == "queue_item" and ev.get("chat_id"):
                        if ev["kind"] == "plan":
                            await send({"type": "queue_response", "id": ev["id"], "decision": "allow", "mode": "accept_edits"})
                        elif ev["kind"] == "question":
                            await send({"type": "queue_response", "id": ev["id"], "answer": (ev.get("options") or ["ok"])[0]})
                        elif "print(42)" in ev.get("body", ""):
                            await send({"type": "queue_response", "id": ev["id"], "decision": "always",
                                        "remember": "project_local"})
                        else:
                            await send({"type": "queue_response", "id": ev["id"], "decision": "allow"})

            def of(kind):
                return [e for e in events if e["type"] == kind]

            await send({"type": "chat_new"})
            await pump(lambda: of("chat_started"))
            cid = of("chat_started")[-1]["chat_id"]
            for i, (mode, text) in enumerate(TURNS, 1):
                if only and i not in only:
                    continue
                if hub.chats[cid].mode != mode:
                    await send({"type": "chat_set_mode", "chat_id": cid, "mode": mode})
                    await pump(lambda m=mode: of("chat_mode") and of("chat_mode")[-1]["mode"] == m)
                before = len(of("queue_item"))
                print(f"\n--- turn {i} ({mode}) ---", flush=True)
                n_done = len(of("chat_done"))
                await send({"type": "chat_message", "chat_id": cid, "text": text})
                await pump(lambda n=n_done: len(of("chat_done")) > n)
                cards = [(e["kind"], e.get("tool"), e["body"][:60]) for e in of("queue_item")[before:]]
                print(f"turn {i} cards: {cards}")

        print("\n================ SUMMARY ================")
        print("project:", project)
        for name in ("hello.txt", "plan.txt", "blocked.txt"):
            f = project / name
            print(f"{name}: {f.read_text(encoding='utf-8').strip() if f.exists() else None}")
        print("made_by_rule dir:", (project / "made_by_rule").is_dir())
        local = project / ".claude" / "settings.local.json"
        print("settings.local.json:", local.read_text(encoding="utf-8") if local.exists() else None)
        print("modes:", [e["mode"] for e in of("chat_mode")])
        print("chat_done:", [e["status"] for e in of("chat_done")])
        acts = [e for e in of("activity") if e["status"] != "started"]
        for e in acts:
            print(f"    {e['tool']:<16} {e['status']:<7} {e['summary'][:80]}")
        final = {}
        for e in of("agent_usage"):
            final[e["agent_id"]] = e
        total = sum(e["cost_usd"] for e in final.values())
        for e in final.values():
            print(f"usage {e['name']} in={e['input_tokens']} out={e['output_tokens']} cr={e['cache_read_tokens']} "
                  f"cw={e['cache_write_tokens']} tools={e['tool_calls']} ${e['cost_usd']:.4f}")
        print(f"TOTAL COST: ${total:.4f}")
        return 0
    finally:
        server.should_exit = True
        await hub.close()
        await server_task


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--turns", default="", help="comma-separated turn numbers to run (default: all)")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.model, {int(x) for x in a.turns.split(",") if x.strip()} or None)))
