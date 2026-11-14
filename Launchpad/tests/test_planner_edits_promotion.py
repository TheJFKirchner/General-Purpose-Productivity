"""Planner: edit-based revisions and Sonnet -> Opus promotion (fake engine)."""
import asyncio

from agentlib import fake

from app import crew
from app import plan as plan_mod
from app.settings import Settings
from conftest import PLAN, Client

PLANNER = "launchpad-planner"


def _usage(c, role="planner"):
    return [e for e in c.of("agent_usage") if e["role"] == role]


def test_edit_plan_applies_local_edits_and_rejects_invalid_ones(harness):
    h = harness()
    fake.script(PLANNER, [
        [fake.call("write_plan", PLAN)],
        [fake.call("edit_plan", {"edits": [{"op": "rename", "name": "Better plan"},
                                           {"op": "replace", "find": "Make the second thing.",
                                            "replace": "Make the second thing, with tests."},
                                           {"op": "add_step", "title": "Third thing", "details": "Wrap up.",
                                            "after": [2]}]}),
         fake.say("Renamed it and added a wrap-up step.")],
        [fake.call("edit_plan", {"edits": [{"op": "move_step", "n": 3, "to": 1}]})],     # would break dependencies
        [fake.call("edit_plan", {"edits": [{"op": "remove_step", "n": 1}]})],             # step 2 depends on it
    ])

    async def go():
        hub, c = await h.start()
        for text in ("plan it", "tweak it", "move it", "drop step 1"):
            await hub.handle({"type": "user_message", "text": text})
        return hub, c

    hub, c = asyncio.run(go())
    drafts = c.of("plan_draft")
    assert [d["revision"] for d in drafts] == [1, 2]                     # the two refused edits saved nothing
    p = plan_mod.parse(drafts[-1]["markdown"])
    assert p["name"] == "Better plan" and [s["title"] for s in p["steps"]] == ["First thing", "Second thing", "Third thing"]
    assert p["steps"][2]["after"] == [2] and "with tests." in drafts[-1]["markdown"]
    replies = hub.current.chat.session.last_reply
    assert replies.tool_calls[0].is_error and "depend on step 1" in replies.tool_calls[0].result
    assert hub.current.plan_text == drafts[-1]["markdown"]


def test_starts_on_sonnet_and_promotes_by_criteria_in_the_window(harness):
    h = harness()
    seen = []
    fake.script(PLANNER, [
        [fake.call("promote_planner", {"reason": "Multi-part dashboard with unclear goals."}),
         fake.ask([{"id": "q1", "question": "Who uses it?", "why": "Sets the scope.", "recommended": "Managers"}])],
        lambda m: seen.append(m) or [fake.say("Thanks, carrying on.")],
    ])

    async def go():
        hub, c = await h.start()
        assert hub.current.chat.agent.model == "sonnet"
        await hub.handle({"type": "user_message", "text": "a big messy dashboard"})
        rnd = c.of("question_round")[-1]
        await hub.handle({"type": "round_answer", "roundId": rnd["id"], "answers": {"q1": {"accepted": True}}})
        return hub, c

    hub, c = asyncio.run(go())
    events = c.of("planner_model")
    assert events[0]["model"] == "sonnet" and events[0]["promoted"] is False
    assert events[-1] == {"type": "planner_model", "session_id": hub.current.id, "model": "opus", "promoted": True,
                          "reason": "Multi-part dashboard with unclear goals.", "by": "criteria"}
    chat = hub.current.chat
    assert chat.session.model == "opus" and chat.session.last_reply.model == "opus"
    assert seen and "q1: " in seen[0]                                     # same conversation: the answer arrived
    assert chat.session.session_id == chat.session.last_reply.session_id
    by_model = _usage(c)[-1]["by_model"]
    assert {b["model"] for b in by_model} == {"opus"} and by_model[0]["cost_usd"] > 0


def test_no_promotion_after_the_window_and_never_twice(harness):
    h = harness()
    fake.script(PLANNER, [[fake.say("one")], [fake.say("two")],
                          [fake.call("promote_planner", {"reason": "late"}), fake.say("three")]])

    async def go():
        hub, c = await h.start()
        for t in ("1", "2", "3"):
            await hub.handle({"type": "user_message", "text": t})
        late = hub.current.chat.session.last_reply.tool_calls[0]
        await hub.handle({"type": "planner_promote", "session_id": hub.current.id})      # by hand: any time
        await hub.handle({"type": "planner_promote", "session_id": hub.current.id})      # never twice
        return hub, c, late

    hub, c, late = asyncio.run(go())
    assert late.is_error and "window" in late.result
    ev = c.of("planner_model")[-1]
    assert ev["promoted"] is True and ev["by"] == "user" and ev["reason"] is None and ev["model"] == "opus"
    assert len([e for e in c.of("planner_model") if e["promoted"]]) == 1
    assert any("already promoted" in e["text"] for e in c.of("system"))


def test_manual_promotion_before_the_first_turn_and_settings_override(harness, project):
    h = harness()
    fake.script(PLANNER, [[fake.say("hi")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "planner_promote", "session_id": hub.current.id})
        await hub.handle({"type": "user_message", "text": "hello"})
        return hub, c

    hub, c = asyncio.run(go())
    assert hub.current.chat.session.last_reply.model == "opus"
    # "always start on the top model": promotion off, no promote tool offered
    s = Settings(project=project, engine="fake", planner_start_model="opus", planner_top_model="opus")
    ev = crew.crew_list("fake", project, s)
    planner = next(a for a in ev["agents"] if a["role"] == "planner")
    assert planner["model"] == "opus" and planner["promotion"]["window_turns"] == 0
    assert "promote_planner" not in [t["name"] for t in planner["custom_tools"]]
    pinned = Settings(project=project, engine="fake", planner_model="haiku")
    p2 = next(a for a in crew.crew_list("fake", project, pinned)["agents"] if a["role"] == "planner")
    assert p2["promotion"]["start_model"] == p2["promotion"]["target_model"] == "haiku"


def test_crew_list_shows_criteria_and_snapshot_restores_model(harness):
    h = harness()
    fake.script(PLANNER, [[fake.call("promote_planner", {"reason": "conflicting goals"}), fake.say("ok")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "get_crew"})
        late = Client(hub)
        await hub.connect(late)
        return hub, c, late

    hub, c, late = asyncio.run(go())
    planner = next(a for a in c.of("crew_list")[-1]["agents"] if a["role"] == "planner")
    promo = planner["promotion"]
    assert promo["start_model"] == "sonnet" and promo["target_model"] == "opus" and promo["window_turns"] == 2
    assert "Stay on the cheaper model" in promo["criteria"] and promo["criteria_path"] == "app/planner-promotion.md"
    s = next(x for x in late.events[0]["sessions"] if x["session_id"] == hub.current.id)
    assert (s["model"], s["promoted"], s["reason"], s["by"]) == ("opus", True, "conflicting goals", "criteria")
    assert late.of("planner_model")[0]["model"] == "opus"


def test_crew_list_paths_are_relative_inside_launchpad_and_absolute_outside(project):
    ev = crew.crew_list("fake", project)
    for a in ev["agents"]:
        assert a["source_path"] == ".claude/agents/" + crew.ROLES[a["role"]]["file"]
    own = project / "my-criteria.md"
    own.write_text("Promote for anything big.", encoding="utf-8")
    s = Settings(project=project, engine="fake", promotion_criteria_path=str(own))
    promo = next(a for a in crew.crew_list("fake", project, s)["agents"] if a["role"] == "planner")["promotion"]
    assert promo["criteria_path"] == str(own.resolve()) and promo["criteria"] == "Promote for anything big."
