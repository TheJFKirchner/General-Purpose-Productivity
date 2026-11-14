"""LIVE check of the visual sidecar on real Claude (planner opus turn + visual agent haiku; a few cents). Not collected by pytest.

    python tests/live_visuals.py [--out <folder>]     # from the Launchpad folder

A real planner turn calls show_visuals; the visual agent renders three ECharts options that must pass
validation; one tweak ("same but horizontal") revises option 1. Prints per-option timings and cost and copies
the HTML files to --out (default: a new temp folder). Scratch project in a temp folder.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402
import websockets  # noqa: E402

from app.server import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

PORT, CODE = 8795, "visuals"
ASK = ("Planning a sales dashboard. Design question: the chart for monthly revenue over the last 12 months, split "
       "by three product lines. I want to see options rather than decide in words: show me exactly three options "
       "now (bar, stacked bar, line). Do not ask me questions first.")


async def main(out: Path) -> int:
    project = Path(tempfile.mkdtemp(prefix="launchpad-visuals-")) / "proj"
    project.mkdir(parents=True)
    (project / "README.md").write_text("# Sales dashboard (scratch)\n", encoding="utf-8")
    app = create_app(PORT, CODE, Settings(project=project, engine="claude"))
    hub = app.state.hub
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    events: list[dict] = []
    t0 = time.monotonic()
    try:
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws?code={CODE}", origin=f"http://127.0.0.1:{PORT}") as ws:
            async def pump(until, timeout=300):
                end = time.monotonic() + timeout
                while not until():
                    ev = json.loads(await asyncio.wait_for(ws.recv(), max(0.1, end - time.monotonic())))
                    ev["_t"] = round(time.monotonic() - t0, 1)
                    events.append(ev)
                    if ev["type"] == "visual_set":
                        print(f"[{ev['_t']:>6}s] visual_set {ev['set_id']}: "
                              + ", ".join(f"{o['label']}={o['status']}" for o in ev["options"]), flush=True)
                    elif ev["type"] in ("planner_message", "system"):
                        print(f"[{ev['_t']:>6}s] {ev['type']}: {ev['text'][:200]}", flush=True)

            def of(kind):
                return [e for e in events if e["type"] == kind]

            def settled():
                s = of("visual_set")
                return bool(s) and all(o["status"] != "rendering" for o in s[-1]["options"])

            def planner_idle():
                st = [e["status"] for e in of("agent_usage") if e.get("role") == "planner"]
                return "working" in st and st[-1] == "idle"

            sid = hub.current.id
            await ws.send(json.dumps({"type": "user_message", "text": ASK}))
            await pump(lambda: planner_idle() and settled())
            board = hub.sessions[sid].visuals
            vset = list(board.sets.values())[-1]
            print("\nbrief:", vset.brief)
            for o in vset.options:
                print(f"  {o.id} {o.label!r}: {o.status} in {o.secs}s, {len(o.html or '')} chars, error={o.error}")
            first = vset.options[0]
            await ws.send(json.dumps({"type": "visual_tweak", "session_id": sid, "set_id": vset.id,
                                      "option_id": first.id, "text": "same but horizontal"}))
            await pump(lambda: first.revision >= 2 or (first.status == "failed" and first.error), timeout=180)
            print(f"  tweak {first.id}: {first.status} in {first.secs}s, path={first.path}, error={first.error}")

        out.mkdir(parents=True, exist_ok=True)
        vis = project / ".launchpad" / sid / "visuals"
        for f in sorted(vis.glob("*.html")):
            shutil.copy2(f, out / f.name)
        print("\nsaved in session:", vis)
        print("copied to:", out, [f.name for f in sorted(out.glob("*.html"))])
        final = {}
        for e in of("agent_usage"):
            final[e["agent_id"]] = e
        total = 0.0
        for e in final.values():
            total += e["cost_usd"]
            print(f"usage {e['name']:<14} in={e['input_tokens']} out={e['output_tokens']} cr={e['cache_read_tokens']} "
                  f"cw={e['cache_write_tokens']} ${e['cost_usd']:.4f}")
        print(f"TOTAL COST: ${total:.4f}")
        tools = [(e["tool"], e["status"]) for e in of("activity") if e["status"] != "started"]
        print("activity:", tools)
        return 0
    finally:
        server.should_exit = True
        await hub.close()
        await server_task


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="launchpad-visuals-out-")))))
