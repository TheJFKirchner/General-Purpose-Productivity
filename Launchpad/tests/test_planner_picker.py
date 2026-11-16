"""The planner's harness-and-model picker (fake engine): options with availability, the remembered choice, a choice
the running session cannot take applied to the next plan, promotion by hand, auto-promote off, harness routing."""
import asyncio

from agentlib import fake

from app.agents.planner import choices
from app.hub import Hub
from app.settings import Settings
from app.store import Store
from conftest import Client

PLANNER = "launchpad-planner"


def _tools(chat) -> list[str]:
    return [getattr(t, "name", t) for t in chat.agent.tools or []]


def test_options_list_availability_and_choice_event(project):
    s = Settings(project=project, engine="fake", planner_start_model="haiku")
    opts = {o["id"]: o for o in choices.options(s)}
    assert opts["claude:sonnet"]["label"] == "Claude · Sonnet" and opts["claude:sonnet"]["available"] is True
    assert opts["claude:opus"]["available"] is True and opts["claude:opus"]["note"] is None
    assert opts["claude:haiku"]["model_label"] == "Haiku"            # a configured start model is always listed
    cursor = [o for o in opts.values() if o["harness"] == "cursor"]
    assert cursor and all(not o["available"] and o["note"] == "not available yet" for o in cursor)   # agentlib stub

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        return c

    ev = asyncio.run(go()).of("planner_choice")[0]
    assert ev["choice"] == {"option_id": "claude:sonnet", "harness": "claude", "model": "sonnet", "label": "Claude · Sonnet"}
    assert ev["auto_promote"] is True and ev["top_model"] == "opus" and ev["top_label"] == "Opus"
    assert "Stay on the cheaper model" in ev["rules"]["markdown"] and ev["rules"]["path"] == "app/agents/planner/promotion.md"
    assert {o["id"] for o in ev["options"]} >= {"claude:sonnet", "claude:opus", "cursor:sonnet"}


def test_choice_before_the_first_message_applies_at_once_and_persists(project, tmp_path):
    store = Store(tmp_path / "settings.json")

    async def go():
        hub = Hub(Settings(project=project, engine="fake"), store=store)
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "planner_choose", "option_id": "claude:opus"})
        return hub, c

    hub, c = asyncio.run(go())
    chat = hub.current.chat
    assert chat.agent.model == "opus" and chat.start_model == chat.top_model == "opus"    # promotion off: one model
    assert "promote_planner" not in _tools(chat)
    pm = c.of("planner_model")[-1]
    assert pm["model"] == "opus" and pm["label"] == "Claude · Opus" and pm["started"] is False
    assert c.of("planner_choice")[-1]["choice"]["option_id"] == "claude:opus"
    again = Store(tmp_path / "settings.json").values()                                     # remembered per user
    assert again["planner_start_model"] == "opus" and again["planner_harness"] == "claude"


def test_a_choice_the_running_session_cannot_take_applies_to_the_next_plan(project, tmp_path):
    fake.script(PLANNER, [[fake.say("hi")], [fake.say("hello again")]])
    store = Store(tmp_path / "settings.json")

    async def go():
        hub = Hub(Settings(project=project, engine="fake"), store=store)
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "planner_choose", "option_id": "claude:opus"})          # before the first message
        await hub.handle({"type": "user_message", "text": "plan something"})
        first = hub.current
        await hub.handle({"type": "planner_choose", "option_id": "claude:sonnet"})        # a step down: next plan
        mid = (first.chat.model, first.chat.agent.model, c.of("planner_model")[-1])
        await hub.handle({"type": "new_session"})
        return hub, c, first, mid

    hub, c, first, (model, agent_model, pm) = asyncio.run(go())
    assert model == agent_model == "opus" and first.chat.session.model == "opus"          # the running one keeps Opus
    assert pm["started"] is True and pm["start_model"] == "opus" and pm["switchable_to"] == []
    choice = c.of("planner_choice")[-1]["choice"]
    assert choice["option_id"] == "claude:sonnet"                     # remembered; the page shows "next new plan"
    assert store.values()["planner_start_model"] == "sonnet"
    nxt = hub.current.chat
    assert hub.current is not first and nxt.agent.model == "sonnet" and nxt.top_model == "opus"
    assert "promote_planner" in _tools(nxt)


def test_top_model_on_a_running_session_is_promotion_by_hand(project, tmp_path):
    fake.script(PLANNER, [[fake.say("hi")]])
    store = Store(tmp_path / "settings.json")

    async def go():
        hub = Hub(Settings(project=project, engine="fake"), store=store)
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "user_message", "text": "hello"})
        await hub.handle({"type": "planner_choose", "option_id": "claude:opus", "session_id": hub.current.id})
        return hub, c

    hub, c = asyncio.run(go())
    pm = c.of("planner_model")[-1]
    assert pm["model"] == "opus" and pm["promoted"] is True and pm["by"] == "user"
    assert hub.current.chat.session.model == "opus"
    assert store.values()["planner_start_model"] == "sonnet"          # promotion is per session: nothing remembered


def test_unavailable_choices_are_refused(project):
    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "planner_choose", "option_id": "cursor:sonnet"})
        await hub.handle({"type": "set_settings", "patch": {"planner_harness": "cursor"}})
        return hub, c

    hub, c = asyncio.run(go())
    texts = [e["text"] for e in c.of("system")]
    assert any("Cursor · Sonnet is not available yet" in t for t in texts)
    assert any(t.startswith("Settings:") and "not available yet" in t for t in texts)
    assert hub.settings.planner_harness == "claude" and hub.current.chat.harness == "claude"


def test_auto_promote_off_means_the_planner_never_promotes_itself(project):
    fake.script(PLANNER, [[fake.call("promote_planner", {"reason": "big"}), fake.say("one")]] * 2)

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        assert "promote_planner" in _tools(hub.current.chat)
        await hub.handle({"type": "set_settings", "patch": {"planner_auto_promote": False}})
        tools_after = _tools(hub.current.chat)
        await hub.handle({"type": "user_message", "text": "a big messy job"})
        return hub, c, tools_after

    hub, c, tools_after = asyncio.run(go())
    assert "promote_planner" not in tools_after                       # unstarted planner reloaded without the tool
    assert hub.current.chat.model == "sonnet" and not hub.current.chat.promoted
    assert not any(e["promoted"] for e in c.of("planner_model"))
    assert c.of("planner_choice")[-1]["auto_promote"] is False
    # promotion by hand still works with auto-promote off
    asyncio.run(hub.handle({"type": "planner_promote", "session_id": hub.current.id}))
    assert hub.current.chat.promoted and hub.current.chat.promoted_by == "user"


def test_auto_promote_switched_off_mid_session_stops_a_planner_that_has_the_tool(project):
    fake.script(PLANNER, [[fake.say("one")], [fake.call("promote_planner", {"reason": "late"}), fake.say("two")]])

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "user_message", "text": "1"})
        assert "promote_planner" in _tools(hub.current.chat)
        await hub.handle({"type": "set_settings", "patch": {"planner_auto_promote": False}})
        await hub.handle({"type": "user_message", "text": "2"})
        return hub

    hub = asyncio.run(go())
    call = hub.current.chat.session.last_reply.tool_calls[0]
    assert call.is_error and "automatic promotion is off" in call.result
    assert not hub.current.chat.promoted


def test_harness_routes_to_its_engine_and_fake_forces_fake(project, monkeypatch):
    s = Settings(project=project, engine="claude", planner_harness="cursor")
    assert choices.planner_engine(s) == "claude"                      # cursor is a stub: never used
    monkeypatch.setattr(choices, "engine_available", lambda e: True)
    assert choices.planner_engine(s) == "cursor"                      # available -> its own engine
    assert choices.planner_engine(Settings(project=project, engine="fake", planner_harness="cursor")) == "fake"
    # a harness whose engine is the fake one: the planner is loaded on that engine although the launch is "claude"
    monkeypatch.setattr(choices, "HARNESSES", choices.HARNESSES + (
        {"harness": "alt", "engine": "fake", "label": "Alt", "models": (("sonnet", "Sonnet"),)},))
    hub = Hub(Settings(project=project, engine="claude", planner_harness="alt"))
    assert hub.current.chat.engine == "fake" and hub.current.chat.agent.engine == "fake"
    assert hub.current.chat.model_event()["label"] == "Alt · Sonnet"
