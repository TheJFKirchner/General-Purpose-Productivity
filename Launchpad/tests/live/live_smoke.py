"""LIVE smoke run (spends tokens, roughly $0.50-1.50; takes about 7 minutes). Not collected by pytest.

    python tests/live/live_smoke.py               # from the Launchpad folder
    python tests/live/live_smoke.py --part planner    # only the planner + Explorer part
    python tests/live/live_smoke.py --part run        # only the approved-plan run
    python tests/live/live_smoke.py --part run --quick    # same with 5 s timers (no long-wait check)

What it proves on the real Claude engine, through the real server and websocket:
- planner turn calls explore -> the Explorer (haiku) uses Read/Grep/Glob and returns structured links
- a pre-written 1-step plan is approved; the orchestrator (file says `tools: []`) gets only run_builder/write_report
- the builder's gated Write/Edit reach Launchpad's check: in-project write allowed, outside write refused;
  `git push` raises a permission card (denied by this script)
- a timed question expires at the real 180 s; a blocking question is left unanswered for 130 s, then answered;
  the builder's turn resumes with both answers (not moved to the background, not killed)
- the run ends with report.md + run_finished; agent_usage carries real tokens and cost

Scratch project = a new temp folder (never the Launchpad repo). Prints a summary; full event log goes to
<temp folder>/events.jsonl.
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

from app.agents.explorer import astronaut as astronaut_mod  # noqa: E402
from app.agents.orchestrator import run as run_mod  # noqa: E402
from app.server import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402

PORT, CODE = 8797, "smoke"
BLOCKING_WAIT_S = 130

PLAN = {
    "name": "Live smoke test",
    "goal": "Exercise Launchpad's builder guards and question timers. This is a deliberate test of the app.",
    "steps": [{
        "title": "Guard and timer checks",
        "details": (
            "This step is a deliberate test of the app's guards; follow it exactly, one action at a time:\n"
            "1. Write the file hello.txt in the project folder with the content: hello\n"
            "2. Edit hello.txt so it reads: hello launchpad\n"
            "3. Try to write the file ../outside-smoke.txt (one folder ABOVE the project) with the content: x. "
            "The app is expected to refuse this; do not retry or work around it.\n"
            "4. Run the shell command: git push origin main (expected to need the user's approval; if denied, "
            "do not retry).\n"
            "5. Call ask_question with blocking false: title 'Greeting punctuation?', recommended 'No punctuation'.\n"
            "6. Call ask_question with blocking true: title 'Keep hello.txt?', recommended 'Keep it'.\n"
            "7. Call submit_report, listing what happened for each of 1-6 in issues or built."),
        "done_when": "submit_report called after all six actions."}],
}


def make_project() -> Path:
    p = Path(tempfile.mkdtemp(prefix="launchpad-smoke-")) / "proj"
    (p / "src").mkdir(parents=True)
    (p / "README.md").write_text("# Smoke project\nA tiny app that prints a greeting.\n", encoding="utf-8")
    (p / "src" / "greet.py").write_text('GREETING = "hello"\n\n\ndef greet(name):\n    return f"{GREETING}, {name}"\n',
                                        encoding="utf-8")
    (p / "src" / "main.py").write_text("from greet import greet\n\nprint(greet('world'))\n", encoding="utf-8")
    return p


async def main(part: str, quick: bool = False) -> int:
    project = make_project()
    log_path = project.parent / "events.jsonl"
    settings = Settings(project=project, engine="claude", question_timeout_s=5 if quick else 180)
    blocking_wait = 5 if quick else BLOCKING_WAIT_S
    app = create_app(PORT, CODE, settings)
    hub = app.state.hub
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)

    # record builder/orchestrator replies + session info, and Explorer results (observation only)
    turns: list[dict] = []
    original_turn = run_mod.Run._turn

    async def recording(self, s, message, meter):
        t0 = time.monotonic()
        reply = await original_turn(self, s, message, meter)
        turns.append({"role": meter.role, "secs": round(time.monotonic() - t0), "tools": s.info.tools,
                      "status": getattr(reply, "status", None), "error": getattr(reply, "error", None),
                      "calls": [(c.name, (c.result or "")[:160], c.is_error) for c in (reply.tool_calls if reply else [])]})
        return reply
    run_mod.Run._turn = recording

    explores: list[dict] = []
    original_explore = astronaut_mod.explore

    async def explore_rec(ls, question):
        r = await original_explore(ls, question)
        explores.append({"question": question, **r})
        return r
    astronaut_mod.explore = explore_rec
    import app.agents.planner.planner as planner_mod
    planner_mod.astronaut.explore = explore_rec

    events: list[dict] = []
    t_start = time.monotonic()
    result = 1
    try:
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws?code={CODE}", origin=f"http://127.0.0.1:{PORT}") as ws:
            async def send(o):
                await ws.send(json.dumps(o))

            async def answer_later(item_id, answer, delay):
                await asyncio.sleep(delay)
                await send({"type": "queue_response", "id": item_id, "answer": answer})

            pending: set = set()
            log = log_path.open("w", encoding="utf-8")

            async def pump(until, timeout):
                end = time.monotonic() + timeout
                while not until():
                    left = end - time.monotonic()
                    if left <= 0:
                        raise TimeoutError("smoke run timed out")
                    ev = json.loads(await asyncio.wait_for(ws.recv(), left))
                    ev["_t"] = round(time.monotonic() - t_start, 1)
                    events.append(ev)
                    log.write(json.dumps(ev) + "\n")
                    log.flush()
                    t = ev["type"]
                    if t in ("queue_item", "queue_resolved", "step_update", "run_started", "run_finished",
                             "plan_draft", "planner_message", "system"):
                        short = {k: v for k, v in ev.items() if k not in ("markdown", "type")}
                        print(f"[{ev['_t']:>6}s] {t}: {json.dumps(short)[:220]}", flush=True)
                    if t == "queue_item":
                        if ev["kind"] == "permission":
                            await send({"type": "queue_response", "id": ev["id"], "decision": "deny"})
                        elif ev["blocking"]:
                            pending.add(asyncio.create_task(answer_later(ev["id"], "Keep it", blocking_wait)))
                        # timed questions: left to the server timer (180 s)

            def of(kind):
                return [e for e in events if e["type"] == kind]

            sid = hub.current.id
            if part in ("all", "planner"):
                await send({"type": "user_message", "text": (
                    "Smoke test of the app. Call explore exactly once with the question 'Which file defines the "
                    "greeting text?', then reply with the link in one line. Do not ask me questions and do not "
                    "write a plan.")})
                def planner_done():
                    st = [e["status"] for e in of("agent_usage") if e.get("role") == "planner"]
                    return bool(explores) and "working" in st and st[-1] == "idle"
                await pump(planner_done, 300)
            if part in ("all", "run"):
                await hub.sessions[sid].save_plan(PLAN)                  # pre-written plan -> plan_draft event
                await send({"type": "plan_approve", "session_id": sid})
                await pump(lambda: of("run_finished"), 1200)
            log.close()
            for t in pending:
                t.cancel()

        # ------------------------------------------------------------------ summary
        print("\n================ SUMMARY ================")
        print("project:", project)
        for e in explores:
            print("explore links:", json.dumps(e.get("links"))[:400], "| error:", e.get("error"))
        for t in turns:
            print(f"{t['role']} turn ({t['secs']}s) status={t['status']} tools={t['tools']}")
            for c in t["calls"]:
                print("    ", c)
        final = {}
        for e in of("agent_usage"):
            final[e["agent_id"]] = e
        total = 0.0
        for e in final.values():
            total += e["cost_usd"]
            print(f"usage {e['name']:<26} in={e['input_tokens']} out={e['output_tokens']} cr={e['cache_read_tokens']} "
                  f"cw={e['cache_write_tokens']} tools={e['tool_calls']} ${e['cost_usd']:.4f}")
        print(f"TOTAL COST (all agents): ${total:.4f}")
        fin = of("run_finished")
        if fin:
            print("run_finished:", fin[-1]["status"], fin[-1]["report_path"], "run total", fin[-1]["total_cost_usd"])
            print("report.md exists:", (project / fin[-1]["report_path"]).is_file())
        print("hello.txt:", (project / "hello.txt").read_text(encoding="utf-8") if (project / "hello.txt").exists() else None)
        print("outside file written:", (project.parent / "outside-smoke.txt").exists())
        acts = [e for e in of("activity") if e["status"] != "started"]
        print(f"activity: {len(of('activity'))} events, {len(acts)} finished calls")
        for e in acts:
            print(f"    [{e['role']}] {e['tool']:<18} {e['status']:<7} {e['summary'][:90]}")
        print("queue:", [(e["kind"], e["blocking"], e["timeout_s"]) for e in of("queue_item")])
        print("resolved:", [(e["answer"], e["by"], e["_t"]) for e in of("queue_resolved")])
        result = 0
    finally:
        server.should_exit = True
        await hub.close()
        await server_task
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["all", "planner", "run"], default="all")
    ap.add_argument("--quick", action="store_true", help="5 s timers instead of 180 s / 130 s (skips the long-wait check)")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.part, a.quick)))
