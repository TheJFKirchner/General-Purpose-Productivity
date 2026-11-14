"""The whole loop on the fake engine: planner -> draft -> approve -> orchestrator -> builders -> report."""
import asyncio
import json
import re

from agentlib import fake

from app import plan as plan_mod
from conftest import PLAN, Client, report, script_orchestrator_sequential, script_planner_writes_plan


def test_full_loop_writes_session_files_and_events(harness, project):
    h = harness()
    seen = []
    fake.script("launchpad-planner", [[
        fake.call("explore", {"question": "where are the rules?"}),
        fake.call("write_plan", PLAN), fake.say("Draft saved.")]])
    fake.script("launchpad-astronaut", [[fake.call("Grep", {"pattern": "rules"}), fake.output({
        "links": [{"path": "CLAUDE.md", "line": 1, "answer": "Project rules."},
                  {"path": "../outside.md", "answer": "dropped"}, {"path": "nope.py", "answer": "dropped"}],
        "routing_notes": "Grepped the whole tree first."})]])
    script_orchestrator_sequential(2, seen)

    def builder(msg):
        n = int(re.search(r"Build step (\d+)", msg).group(1))
        return [fake.call("Read", {"file_path": "CLAUDE.md"}),
                fake.call("Write", {"file_path": f"out/step{n}.txt", "content": "x"}),
                fake.call("add_to_flight_log", {"path": "app/main.py", "why": "Entry point."}),
                fake.spend(0.01),
                fake.call("submit_report", report(assumptions=[f"assumed thing {n}"],
                                                  routing_notes=f"step {n} read too much"))]

    fake.script("launchpad-builder", [builder])

    async def go():
        hub, c = await h.start()
        ls = hub.current
        await hub.handle({"type": "user_message", "text": "Build two things"})
        assert c.of("plan_draft") and c.of("plan_draft")[-1]["steps"] == [
            {"n": 1, "title": "First thing", "agent": None, "agent_display": "Builder", "agent_purpose": "building"},
            {"n": 2, "title": "Second thing", "agent": None, "agent_display": "Builder", "agent_purpose": "building"}]
        assert not c.of("run_started")                         # a draft never starts a run by itself
        await hub.handle({"type": "plan_approve", "session_id": ls.id})
        await h.wait(lambda: c.of("run_finished"))
        return hub, c, ls

    hub, c, ls = asyncio.run(go())
    f = ls.folder
    fin = c.of("run_finished")[-1]
    assert fin["status"] == "done" and fin["report_path"] == f".launchpad/{ls.id}/report.md"
    assert fin["total_cost_usd"] > 0 and "## Costs per agent" in fin["markdown"]
    assert c.of("session_started")[0]["folder"] == f".launchpad/{ls.id}"
    # files
    saved = plan_mod.parse(f.read(f.plan))
    assert saved["status"] == "approved" and [s["status"] for s in saved["steps"]] == ["done", "done"]
    for n in (1, 2):
        step = f.read(f.step_path(n))
        assert "Status: **done**" in step and "thing.txt" in step
    log = f.read(f.flight_log)
    assert "CLAUDE.md:1" in log and "_(Explorer)_" in log and "app/main.py" in log and "outside" not in log
    assert "assumed thing 1" in f.read(f.assumptions) and "assumed thing 2" in f.read(f.assumptions)
    ops = f.read(f.ops_manual)
    assert "Grepped the whole tree first." in ops and "step 2 read too much" in ops and "tool calls:" in ops
    rep = f.read(f.report)
    assert "All done." in rep and "assumed thing 2" in rep and "Planner (separate, not in the session total)" in rep
    # events
    statuses = [(e["n"], e["status"]) for e in c.of("step_update")]
    assert (1, "in_progress") in statuses and (1, "done") in statuses and statuses[-1] == (2, "done")
    done_update = [e for e in c.of("step_update") if e["status"] == "done"][0]
    assert done_update["report_path"].endswith("steps/step-01.md") and done_update["built"]
    usage = c.of("agent_usage")
    roles = {e["role"] for e in usage}
    assert roles == {"planner", "astronaut", "orchestrator", "builder"}
    builders = [e for e in usage if e["role"] == "builder" and e["status"] == "done"]
    assert builders and all(e["cost_usd"] > 0 and e["tool_calls"] >= 4 for e in builders)
    for key in ("session_id", "agent_id", "name", "step", "input_tokens", "output_tokens", "cache_read_tokens",
                "cache_write_tokens", "cost_usd", "tool_calls"):
        assert key in usage[-1]
    # the orchestrator started with light context: plan + flight log + paths
    assert seen[0].startswith('Run the approved plan "Test plan"') and "flight log" in seen[0]


def test_orchestrator_receives_only_capped_return(harness):
    h = harness()
    seen = []
    script_planner_writes_plan({**PLAN, "steps": PLAN["steps"][:1]})
    script_orchestrator_sequential(1, seen)
    long = "x" * 5000
    fake.script("launchpad-builder", [[fake.call("submit_report", report(
        built=[{"item": f"file{i}.py " + long, "does": long} for i in range(20)],
        assumptions=[long] * 12, issues=[long] * 9, notes_for_orchestrator=long, routing_notes=long))]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        return hub

    hub = asyncio.run(go())
    result_msg = seen[1]
    assert result_msg.startswith("Step 1 result:") and len(result_msg) < 4000
    data = json.loads(result_msg.split("\n", 1)[1].rsplit("\nNext:", 1)[0])
    assert set(data) == {"step", "status", "agent", "report_path", "built", "assumptions", "issues", "notes"}
    assert data["agent"] == "Builder"
    assert data["report_path"].endswith("steps/step-01.md")
    assert len(data["built"]) == 9 and data["built"][-1] == "(+12 more in the report)"
    assert all(len(x) <= 160 for x in data["built"] + data["assumptions"] + data["issues"])
    assert len(data["notes"]) <= 300 and long not in result_msg
    # the full text is still in the step report
    step = hub.current.folder.read(hub.current.folder.step_path(1))
    assert "file19.py" in step


def test_builder_without_submit_report_is_nudged_then_failed(harness):
    h = harness()
    script_planner_writes_plan({**PLAN, "steps": PLAN["steps"][:1]})
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.say("I did stuff")], [fake.say("still no report")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    assert [m for r, m, _ in h.replies if r == "builder"][1].startswith("You have not called submit_report")
    assert [e for e in c.of("step_update") if e["status"] == "failed"]
    assert "without submit_report" in c.of("run_finished")[-1]["markdown"]


def test_run_stop_and_parallel_sessions(harness):
    """Session A waits on a blocking question; a new session B plans and runs meanwhile; A is then stopped."""
    h = harness()
    script_planner_writes_plan({**PLAN, "steps": PLAN["steps"][:1]})
    script_orchestrator_sequential(1)

    def builder(msg):
        if "block me" in msg:
            return [fake.call("ask_question", {"title": "Which?", "body": "b", "recommended": "A",
                                               "blocking": True}),
                    fake.call("submit_report", report())]
        return [fake.call("submit_report", report())]

    fake.script("launchpad-builder", [builder])

    async def go():
        hub, c = await h.start()
        a = hub.current
        await hub.handle({"type": "user_message", "text": "go"})
        a.plan_text = a.plan_text.replace("Make the first thing.", "Make the first thing. block me")
        a.folder.write_plan(a.plan_text)
        await hub.handle({"type": "plan_approve", "session_id": a.id})
        await h.wait(lambda: [e for e in c.of("queue_item") if e["session_id"] == a.id])
        b = await hub.new_session()
        assert b.id != a.id and hub.current is b
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": b.id})
        await h.wait(lambda: [e for e in c.of("run_finished") if e["session_id"] == b.id])
        assert a.running                                         # A still waiting on the user
        await hub.handle({"type": "run_stop", "session_id": a.id})
        await h.wait(lambda: [e for e in c.of("run_finished") if e["session_id"] == a.id])
        return c, a, b

    c, a, b = asyncio.run(go())
    fin = {e["session_id"]: e for e in c.of("run_finished")}
    assert fin[b.id]["status"] == "done" and fin[a.id]["status"] == "stopped"
    assert c.of("queue_resolved") and a.folder.report.is_file() and b.folder.report.is_file()
    assert a.folder.path != b.folder.path


def test_report_to_planner_feeds_the_report(harness):
    h = harness()
    got = []
    fake.script("launchpad-planner", [[fake.call("write_plan", {**PLAN, "steps": PLAN["steps"][:1]})],
                                      lambda m: got.append(m) or [fake.say("Here is what happened.")]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "report_to_planner", "session_id": hub.current.id})
        return c

    c = asyncio.run(go())
    assert got and got[0].startswith("[Launchpad] The run finished (done)") and "# Report: Test plan" in got[0]
    assert c.of("planner_message")[-1]["text"] == "Here is what happened."


def _send_back_script(seen_plans=None):
    one = {**PLAN, "steps": PLAN["steps"][:1]}
    fake.script("launchpad-planner", [
        [fake.call("write_plan", one)],
        [fake.call("write_plan", {**one, "name": "Revised plan"}), fake.say("Revised.")],
        [fake.say("ok")]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])


def test_send_back_then_approve_starts_a_second_run(harness):
    """Run -> report to planner -> revised draft -> Approve: plan_draft revision 2, run 2, old run archived."""
    h = harness()
    _send_back_script()

    async def go():
        hub, c = await h.start()
        sid = hub.current.id
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": sid})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "plan_approve", "session_id": sid})            # nothing new to approve
        await hub.handle({"type": "report_to_planner", "session_id": sid})
        late = Client(hub)                                                       # a reload after the revision
        await hub.connect(late)
        await hub.handle({"type": "plan_approve", "session_id": sid})
        await h.wait(lambda: len(c.of("run_finished")) == 2)
        return hub, c, late

    hub, c, late = asyncio.run(go())
    drafts = c.of("plan_draft")
    assert [(d["revision"], d["previous_runs"]) for d in drafts] == [(1, 0), (2, 1)]
    assert any("no new draft to approve" in e["text"] for e in c.of("system"))
    runs = c.of("run_started")
    assert [(r["run"], r["revision"], r["name"]) for r in runs] == [(1, 1, "Test plan"), (2, 2, "Revised plan")]
    assert [e["status"] for e in c.of("run_finished")] == ["done", "done"]
    f = hub.current.folder
    assert (f.path / "run-1" / "report.md").is_file() and f.report.is_file()
    # the reloaded page got the finished run AND the pending revised draft, in that order
    kinds = [e["type"] for e in late.events if e["type"] in ("run_started", "run_finished", "plan_draft")]
    assert kinds[:3] == ["run_started", "run_finished", "plan_draft"]          # the replay (run 2 follows live)
    s = next(x for x in late.events[0]["sessions"] if x["session_id"] == hub.current.id)
    assert s["draft_pending"] is True and s["plan_revision"] == 2 and s["runs"] == 1


def test_revised_draft_before_any_run_can_be_approved(harness):
    h = harness()
    _send_back_script()

    async def go():
        hub, c = await h.start()
        sid = hub.current.id
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "user_message", "text": "make it better"})
        await hub.handle({"type": "plan_approve", "session_id": sid})
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    assert [d["revision"] for d in c.of("plan_draft")] == [1, 2]
    run = c.of("run_started")[0]
    assert run["name"] == "Revised plan" and run["revision"] == 2 and run["run"] == 1
