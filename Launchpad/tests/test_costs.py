"""Cost totals are summed in one place (app/costs.py) and sent by the server: per session, the planner's share, per CLI
chat and app-wide, live and again on connect (fake engine)."""
import asyncio

from agentlib import fake

from app import costs
from conftest import PLAN, Client, report, script_orchestrator_sequential

ONE = {**PLAN, "steps": PLAN["steps"][:1]}


def _last(c, scope, **where):
    found = [e for e in c.of("usage") if e.get("scope") == scope and all(e.get(k) == v for k, v in where.items())]
    return found[-1]


def test_formatting_helper_keeps_four_decimals():
    assert costs.usd(0.5) == "$0.5000" and costs.usd(0.12345, symbol=False) == "0.1235" and costs.usd(None) == "$0.0000"
    assert costs.wire(0.1234567891) == 0.123457


def test_server_totals_equal_the_sum_of_the_meters_for_session_planner_chat_and_app(harness):
    h = harness(timeout_s=5)
    fake.script("launchpad-planner", [[fake.spend(0.011), fake.call("write_plan", ONE)]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.spend(0.02), fake.call("submit_report", report())]])
    fake.script("launchpad-pilot", [[fake.spend(0.005), fake.say("hi")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        late = Client(hub)
        await hub.connect(late)
        return hub, c, late, cid

    hub, c, late, cid = asyncio.run(go())
    sid = hub.current.id
    ms = hub.meters
    run_sum = sum(m.cost_usd for m in ms if m.session_id == sid and m.role != "planner")
    planner_sum = sum(m.cost_usd for m in ms if m.session_id == sid and m.role == "planner")
    chat_sum = sum(m.cost_usd for m in ms if m.chat_id == cid)
    assert run_sum > 0 and planner_sum > 0 and chat_sum > 0
    for src in (c, late):                                                        # live, and replayed on connect
        s = _last(src, "session", session_id=sid)
        assert abs(s["cost"] - run_sum) < 1e-5 and abs(s["planner_cost"] - planner_sum) < 1e-5
        ch = _last(src, "chat", chat_id=cid)
        assert abs(ch["cost"] - chat_sum) < 1e-5 and ch["agents"] == 1
        app = _last(src, "app")
        assert abs(app["cost"] - sum(m.cost_usd for m in ms)) < 1e-5
        assert abs(sum(app["by_role"].values()) - app["cost"]) < 1e-5
        assert abs(app["by_role"]["planner"] - planner_sum) < 1e-5 and "builder" in app["by_role"]
    fin = c.of("run_finished")[0]                                                # the same figures everywhere
    assert abs(fin["total_cost_usd"] - run_sum) < 1e-5 and abs(fin["planner_cost_usd"] - planner_sum) < 1e-5
    snap = next(x for x in late.of("snapshot")[0]["sessions"] if x["session_id"] == sid)
    assert abs(snap["total_cost_usd"] - run_sum) < 1e-5 and abs(snap["planner_cost_usd"] - planner_sum) < 1e-5
    assert f"**{costs.usd(fin['total_cost_usd'])}**" in fin["markdown"]


def test_a_chat_cost_never_lands_in_a_session_total(harness):
    h = harness()
    fake.script("launchpad-pilot", [[fake.spend(0.007), fake.say("hi")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        return hub, c

    hub, c = asyncio.run(go())
    assert all(e["cost"] == 0 and e["planner_cost"] == 0 for e in c.of("usage") if e.get("scope") == "session")
    assert _last(c, "app")["cost"] > 0
