"""The CLI chat's CLI-and-model picker (fake engine): options from the planner's table, the remembered choice
(pilot_harness / pilot_model), a chat nobody has written to takes a choice at once, a chat in progress keeps its own
(the choice is for the next new chat), independence from the planner, engine routing, refusals."""
import asyncio

from agentlib import fake

from app.agents.claude_code import choices as cli_choices
from app.agents.planner import choices
from app.hub import Hub
from app.settings import Settings
from app.store import Store
from conftest import Client

PILOT = "launchpad-pilot"


async def _hub(project, store=None, **kw):
    hub = Hub(Settings(project=project, engine="fake", **kw), store=store)
    c = Client(hub)
    await hub.connect(c)
    return hub, c


def test_options_come_from_the_planner_table_and_the_default_is_the_launch_cli(project):
    s = Settings(project=project, engine="fake")
    assert cli_choices.cli_harness(s) == "claude" and cli_choices.cli_model(s) == "sonnet"    # agent file's model
    assert [o["id"] for o in cli_choices.options(s)] == [o["id"] for o in choices.harness_options()]
    cursor = [o for o in cli_choices.options(s) if o["harness"] == "cursor"]
    assert cursor and all(not o["available"] and o["note"] == "not available yet" for o in cursor)
    # --pilot-model haiku: listed for the chosen CLI and chosen
    s2 = Settings(project=project, engine="fake", pilot_model="haiku")
    assert "claude:haiku" in {o["id"] for o in cli_choices.options(s2)}

    async def go():
        hub, c = await _hub(project, pilot_model="haiku")
        hub.overridden.add("pilot_model")
        await hub.handle({"type": "cli_choose", "option_id": "claude:haiku"})
        return c

    c = asyncio.run(go())
    first = c.of("cli_choice")[0]
    assert first["choice"] == {"option_id": "claude:haiku", "harness": "claude", "model": "haiku", "label": "Claude · Haiku"}
    assert c.of("cli_choice")[-1]["overridden"] == []                # picked from the page: no longer a launch override


def test_choice_before_the_first_message_applies_at_once_persists_and_leaves_the_planner_alone(project, tmp_path):
    store = Store(tmp_path / "settings.json")

    async def go():
        hub, c = await _hub(project, store=store)
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "plan"})
        await hub.handle({"type": "cli_choose", "option_id": "claude:opus"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    started = c.of("chat_started")[-1]
    assert started["harness"] == "claude" and started["label"] == "Claude · Sonnet" and started["started"] is False
    chat = hub.chats[cid]
    assert chat.agent.model == "opus" and chat.engine == "fake" and chat.mode == "plan"   # reloaded, mode kept
    cm = c.of("chat_model")[-1]
    assert cm == {"type": "chat_model", "chat_id": cid, "harness": "claude", "model": "opus", "label": "Claude · Opus",
                  "option_id": "claude:opus", "started": False}
    assert c.of("cli_choice")[-1]["choice"]["option_id"] == "claude:opus"
    again = Store(tmp_path / "settings.json").values()                  # remembered per user
    assert again["pilot_model"] == "opus" and again["pilot_harness"] == "claude"
    # independent of the planner: its choice and its unstarted planner did not move
    assert again["planner_start_model"] == "sonnet" and hub.current.chat.agent.model == "sonnet"
    assert c.of("planner_choice")[-1]["choice"]["option_id"] == "claude:sonnet"
    # and the planner's picker does not move the CLI chat
    asyncio.run(hub.handle({"type": "planner_choose", "option_id": "claude:opus"}))
    assert hub.settings.pilot_model == "opus" and chat.agent.model == "opus"


def test_a_choice_during_a_chat_in_progress_applies_to_the_next_new_chat(project, tmp_path):
    fake.script(PILOT, [[fake.say("hi")], [fake.say("again")], [fake.say("new chat")]])
    store = Store(tmp_path / "settings.json")

    async def go():
        hub, c = await _hub(project, store=store)
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        await hub.handle({"type": "cli_choose", "option_id": "claude:opus"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "still there?"})
        await hub.handle({"type": "chat_new"})
        nid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": nid, "text": "fresh"})
        return hub, c, cid, nid

    hub, c, cid, nid = asyncio.run(go())
    old = hub.chats[cid]
    assert old.agent.model == "sonnet" and old.session.model == "sonnet"      # the chat in progress keeps Sonnet
    fixed = [e for e in c.of("chat_model") if e["chat_id"] == cid]
    assert fixed == [{"type": "chat_model", "chat_id": cid, "harness": "claude", "model": "sonnet",
                      "label": "Claude · Sonnet", "option_id": "claude:sonnet", "started": True}]   # sent at the first message
    assert c.of("cli_choice")[-1]["choice"]["option_id"] == "claude:opus"   # the page shows "your next new chat"
    assert store.values()["pilot_model"] == "opus"
    new = hub.chats[nid]
    assert new.agent.model == "opus" and new.session.model == "opus"
    assert c.of("chat_started")[-1]["label"] == "Claude · Opus"
    late = Client(hub)
    asyncio.run(hub.connect(late))
    snap = {x["id"]: x for x in late.events[0]["chats"]}
    assert snap[cid]["label"] == "Claude · Sonnet" and snap[cid]["started"] is True
    assert snap[nid]["option_id"] == "claude:opus"


def test_the_chat_loads_on_the_chosen_cli_engine_and_fake_forces_fake(project, monkeypatch):
    s = Settings(project=project, engine="claude", pilot_harness="cursor")
    assert cli_choices.cli_engine(s) == "claude"                         # cursor is a stub: never used
    monkeypatch.setattr(choices, "engine_available", lambda e: True)
    assert cli_choices.cli_engine(s) == "cursor"                         # available -> its own engine
    assert cli_choices.cli_engine(Settings(project=project, engine="fake", pilot_harness="cursor")) == "fake"
    assert cli_choices.cli_harness(Settings(project=project, engine="claude", pilot_harness="nope")) == "claude"
    monkeypatch.undo()
    # a CLI whose engine is the fake one: the chat is loaded on that engine and model although the launch is "claude"
    monkeypatch.setattr(choices, "HARNESSES", choices.HARNESSES + (
        {"harness": "alt", "engine": "fake", "label": "Alt", "models": (("haiku", "Haiku"),)},))
    hub = Hub(Settings(project=project, engine="claude", pilot_harness="alt", pilot_model="haiku"))
    chat = asyncio.run(hub.chat_new())
    assert chat.engine == "fake" and chat.agent.engine == "fake" and chat.agent.model == "haiku"
    assert chat.started_event()["label"] == "Alt · Haiku" and chat.harness == "alt"
    assert hub.current.chat.engine == "claude"                          # the planner's own choice is untouched


def test_unavailable_cli_choices_are_refused(project):
    async def go():
        hub, c = await _hub(project)
        await hub.handle({"type": "cli_choose", "option_id": "cursor:sonnet"})
        await hub.handle({"type": "set_settings", "patch": {"pilot_harness": "cursor"}})
        await hub.handle({"type": "set_settings", "patch": {"pilot_harness": ""}})      # empty = the launch CLI
        return hub, c

    hub, c = asyncio.run(go())
    texts = [e["text"] for e in c.of("system")]
    assert any(t == "CLI: Cursor · Sonnet is not available yet." for t in texts)
    assert any(t.startswith("Settings:") and "not available yet" in t for t in texts)
    assert hub.settings.pilot_harness is None and cli_choices.cli_harness(hub.settings) == "claude"
