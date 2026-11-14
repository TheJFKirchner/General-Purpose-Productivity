"""UI-review fix round: agent_id on cards, plain names, Explorer trips, snapshot, favicon, one session total, no rec."""
import asyncio

from fastapi.testclient import TestClient

from agentlib import fake

from app.server import create_app
from app.settings import Settings
from conftest import PLAN, Client, report, script_orchestrator_sequential

ONE = {**PLAN, "steps": PLAN["steps"][:1]}


def _script(builder_steps):
    fake.script("launchpad-planner", [[fake.call("explore", {"question": "q1"}), fake.call("explore", {"question": "q2"}),
                                       fake.call("write_plan", ONE)]])
    fake.script("launchpad-astronaut", [[fake.call("Glob", {"pattern": "*.md"}), fake.spend(0.003),
                                         fake.output({"links": [{"path": "CLAUDE.md", "answer": "rules"}]})]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [builder_steps])


def test_cards_names_astronaut_totals_and_snapshot(harness):
    h = harness(timeout_s=5)
    _script([fake.call("Bash", {"command": "git push"}),
             fake.call("ask_question", {"title": "Q?", "body": "b", "recommended": "A"}),
             fake.spend(0.02), fake.call("submit_report", report())])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "deny", "answer": "B"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "report_to_planner", "session_id": hub.current.id})
        late = Client(hub)
        await hub.connect(late)
        return hub, c, late

    hub, c, late = asyncio.run(go())
    usage = c.of("agent_usage")
    builder_id = next(e["agent_id"] for e in usage if e["role"] == "builder")
    perm, question = c.of("queue_item")
    # 1 + 2: cards carry agent_id; names are plain display names
    assert perm["agent_id"] == builder_id and question["agent_id"] == builder_id
    assert perm["agent"] == "Builder" and perm["step"] == 1
    assert all("step" not in e["name"] for e in usage + c.of("activity"))
    # 7: permission cards carry no recommendation; questions still do
    assert perm["kind"] == "permission" and perm["rec"] is None and question["rec"] == "A"
    # 3: one Explorer per session, working -> idle around each trip
    astro = [e for e in usage if e["role"] == "astronaut"]
    assert len({e["agent_id"] for e in astro}) == 1
    statuses = [e["status"] for e in astro]
    flips = [s for i, s in enumerate(statuses) if i == 0 or s != statuses[i - 1]]
    assert flips.count("working") == 2 and flips[-1] == "idle" and "done" not in statuses
    crew_astro = [a for ev in c.of("crew") for a in ev["agents"] if a["role"] == "astronaut"]
    assert {a["status"] for a in crew_astro} >= {"working", "idle"}
    # 6: one definition of the session total everywhere
    final = {}
    for e in usage:
        final[e["agent_id"]] = e
    sid = hub.current.id
    total = sum(e["cost_usd"] for e in final.values() if e["session_id"] == sid and e["role"] != "planner")
    fin = c.of("run_finished")[0]
    assert abs(fin["total_cost_usd"] - total) < 1e-5 and "planner_cost_usd" in fin
    assert f"**${fin['total_cost_usd']:.4f}**" in fin["markdown"]
    assert "Planner (separate, not in the session total)" in fin["markdown"]
    # 4: snapshot restores the current session, its chat and report_sent
    snap = late.events[0]
    assert snap["type"] == "snapshot" and snap["current_session_id"] == sid
    s = next(x for x in snap["sessions"] if x["session_id"] == sid)
    assert s["report_sent"] is True and s["chat"][0] == {"role": "user", "text": "go"}
    assert {"role": "system", "text": "Run report sent to the planner."} in s["chat"]
    assert abs(s["total_cost_usd"] - fin["total_cost_usd"]) < 1e-5     # astronaut cost after the run: none


def test_favicon_served(project):
    app = create_app(1234, "x", Settings(project=project, engine="fake"))
    r = TestClient(app).get("/favicon.ico")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg")


def test_echarts_served_locally_and_page_locks_frames(project):
    app = create_app(1234, "x", Settings(project=project, engine="fake"))
    client = TestClient(app)
    js = client.get("/vendor/echarts.min.js")
    assert js.status_code == 200 and js.headers["content-type"].startswith("application/javascript")
    assert len(js.content) > 500_000 and b"echarts" in js.content[:2000]
    csp = client.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in csp and "connect-src 'self' ws://127.0.0.1:1234" in csp
    assert "http" not in csp.replace("ws://127.0.0.1", "").replace("ws://localhost", "")    # no outside hosts
