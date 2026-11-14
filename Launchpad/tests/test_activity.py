"""Activity feed: one started + one final event per tool call, short summaries, activity.log, reconnect replay."""
import asyncio

from agentlib import fake

from app.activity import SUMMARY_MAX, summarize
from conftest import PLAN, Client, report, script_orchestrator_sequential, script_planner_writes_plan


def test_summaries_are_short_and_never_contents(project):
    assert summarize("Bash", {"command": "git status"}) == "git status"
    assert summarize("Write", {"file_path": str(project / "a" / "b.txt"), "content": "SECRET"}, project) == "a/b.txt"
    assert summarize("Grep", {"pattern": "def x", "path": "src"}) == "def x in src"
    assert summarize("run_builder", {"step": 2, "brief": "long brief"}) == "start step 2"
    assert len(summarize("Bash", {"command": "x" * 1000})) <= SUMMARY_MAX
    assert "SECRET" not in summarize("Edit", {"file_path": "f.py", "old_string": "SECRET", "new_string": "SECRET"})


def test_activity_events_log_and_snapshot(harness):
    h = harness(responder=lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "deny"}
                                      if ev.get("type") == "queue_item" else None))
    script_planner_writes_plan({**PLAN, "steps": PLAN["steps"][:1]})
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[
        fake.call("Read", {"file_path": "CLAUDE.md"}),
        fake.call("Bash", {"command": "python -m pytest -q"}),
        fake.call("Write", {"file_path": "../escape.txt", "content": "TOPSECRET"}),
        fake.call("add_to_flight_log", {"path": "nope", "why": "x"}),
        fake.call("submit_report", report())]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        late = Client(hub)                                   # a UI that connects after the run
        await hub.connect(late)
        return hub, c, late

    hub, c, late = asyncio.run(go())
    acts = c.of("activity")
    by_id = {}
    for e in acts:
        by_id.setdefault(e["id"], []).append(e["status"])
    assert all(s[0] == "started" and len(s) == 2 for s in by_id.values())      # every call closed exactly once
    keys = {"id", "session_id", "agent_id", "role", "name", "step", "tool", "summary", "status", "ts"}
    assert all(keys <= set(e) for e in acts)
    final = {(e["role"], e["tool"]): e for e in acts if e["status"] != "started"}
    assert final[("planner", "write_plan")]["status"] == "done"
    assert final[("orchestrator", "run_builder")]["summary"] == "start step 1"
    assert final[("builder", "Bash")]["summary"] == "python -m pytest -q" and final[("builder", "Bash")]["step"] == 1
    assert final[("builder", "Write")]["status"] == "denied"
    assert final[("builder", "submit_report")]["status"] == "done"
    assert "TOPSECRET" not in str(acts)
    log = hub.current.folder.read(hub.current.folder.activity).splitlines()
    assert len(log) == len(by_id) and any("| denied  |" in ln and "../escape.txt" in ln for ln in log)
    assert "TOPSECRET" not in "\n".join(log)
    assert len(late.of("activity")) == len(acts)                               # replayed on reconnect
