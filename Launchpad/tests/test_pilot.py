"""Regular session (Claude Code chat) on the fake engine: streaming, permissions, modes, plans, questions, interrupt, snapshot."""
import asyncio

import pytest

from agentlib import fake

from conftest import Client

PILOT = "launchpad-pilot"


async def _start(h):
    hub, c = await h.start()
    await hub.handle({"type": "chat_new"})
    return hub, c, c.of("chat_started")[-1]["chat_id"]


def _final(c, tool=None):
    return [e for e in c.of("activity") if e["status"] != "started" and (tool is None or e["tool"] == tool)]


def _cards(c, kind="permission"):
    return [e for e in c.of("queue_item") if e["kind"] == kind]


def test_chat_turn_streams_and_tracks_usage(harness, project):
    h = harness()
    fake.script(PILOT, [[fake.say("Hello there."), fake.call("Read", {"file_path": "CLAUDE.md"}),
                         fake.call("Grep", {"pattern": "rules"}), fake.say("Done reading.")]])

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hi"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    started = c.of("chat_started")[0]
    assert started["mode"] == "default" and started["model"] == "sonnet" and started["cwd"] == str(project.resolve())
    assert c.of("chat_delta") and all(e["chat_id"] == cid for e in c.of("chat_delta"))
    assert [e["markdown"] for e in c.of("chat_message")] == ["Hello there.", "Done reading."]
    assert [e["on"] for e in c.of("chat_typing")] == [True, False]
    assert c.of("chat_done")[-1] == {"type": "chat_done", "chat_id": cid, "status": "ok"}
    assert not c.of("queue_item")                                  # Read / Grep never ask (like Claude Code)
    usage = [e for e in c.of("agent_usage") if e["role"] == "pilot"]
    assert usage[-1]["chat_id"] == cid and usage[-1]["session_id"] is None and usage[-1]["tool_calls"] == 2
    acts = _final(c)
    assert {e["tool"] for e in acts} == {"Read", "Grep"} and all(e["chat_id"] == cid for e in acts)
    assert (project / ".launchpad" / cid / "activity.log").is_file()


@pytest.mark.parametrize("decision,status", [("allow", "done"), ("deny", "denied")])
def test_permission_allow_and_deny(harness, decision, status):
    h = harness()
    fake.script(PILOT, [[fake.call("Bash", {"command": "npm test"}), fake.say("ok")]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": decision, "message": "not now"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "test"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    card = _cards(c)[0]
    assert card["chat_id"] == cid and card["session_id"] is None and card["timeout_s"] is None
    assert card["rec"] is None and card["tool"] == "Bash" and card["body"] == "npm test"
    assert {s["remember"] for s in card["suggestions"]} == {"session", "project_local"}
    assert _final(c, "Bash")[0]["status"] == status
    if decision == "deny":
        assert "not now" in hub.chats[cid].last_reply.tool_calls[0].result


def test_always_allow_session_and_project_local(harness, project):
    h = harness()
    fake.script(PILOT, [[fake.call("Bash", {"command": "npm test"}), fake.call("Bash", {"command": "npm run lint"}),
                         fake.call("Write", {"file_path": "a.txt", "content": "x"}),
                         fake.call("Write", {"file_path": "b.txt", "content": "x"})]])
    answers = iter([{"decision": "always", "remember": "project_local"},      # npm test -> Bash(npm:*) saved
                    {"decision": "always", "remember": "session"}])           # Write -> accept edits (Claude Code)
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], **next(answers)}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "go"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    assert [e["tool"] for e in _cards(c)] == ["Bash", "Write"]              # second Bash + second Write unasked
    assert all(e["status"] == "done" for e in _final(c))
    assert any("Bash(npm" in r for r in fake.saved_rules(str(project.resolve())))
    assert c.of("chat_mode")[-1]["mode"] == "accept_edits"


def test_mode_switch_between_turns_and_mid_turn(harness):
    h = harness()
    fake.script(PILOT, [
        [fake.call("Write", {"file_path": "a.txt", "content": "x"})],                     # accept_edits: unasked
        [fake.call("Write", {"file_path": "b.txt", "content": "x"}),                      # default: asks
         fake.call("Edit", {"file_path": "b.txt", "old_string": "x", "new_string": "y"})],   # switched mid-turn
    ])

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "accept_edits"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "one"})
        assert not _cards(c)
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "default"})
        turn = asyncio.create_task(hub.handle({"type": "chat_message", "chat_id": cid, "text": "two"}))
        await h.wait(lambda: _cards(c))
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "accept_edits"})   # mid-turn
        await hub.handle({"type": "queue_response", "id": _cards(c)[0]["id"], "decision": "allow"})
        await turn
        return c

    c = asyncio.run(go())
    assert [e["mode"] for e in c.of("chat_mode")] == ["accept_edits", "default", "accept_edits"]
    assert len(_cards(c)) == 1 and all(e["status"] == "done" for e in _final(c))


def test_plan_approved_into_accept_edits(harness):
    h = harness()
    fake.script(PILOT, [[fake.say("Here is my plan."), fake.plan("1. Write a.txt"),
                         fake.call("Write", {"file_path": "a.txt", "content": "x"}), fake.say("Done.")]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "allow", "mode": "accept_edits"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "plan"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "plan it"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    plan = _cards(c, "plan")
    assert len(plan) == 1 and plan[0]["markdown"] == "1. Write a.txt" and plan[0]["timeout_s"] is None
    assert not _cards(c)                                       # the edit ran unasked after approval
    assert c.of("chat_mode")[-1]["mode"] == "accept_edits" and hub.chats[cid].mode == "accept_edits"
    assert _final(c, "Write")[0]["status"] == "done"


def test_plan_rejected_with_feedback_and_edits_denied_in_plan_mode(harness):
    h = harness()
    fake.script(PILOT, [[fake.plan("1. Write a.txt"), fake.call("Write", {"file_path": "a.txt", "content": "x"}),
                         fake.call("Edit", {"file_path": "a.txt", "old_string": "x", "new_string": "y"})]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "deny", "message": "add tests first"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "plan"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "plan it"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    calls = hub.chats[cid].last_reply.tool_calls
    assert calls[0].is_error and "add tests first" in calls[0].result               # feedback reached the agent
    assert hub.chats[cid].mode == "plan" and len(_cards(c, "plan")) == 1
    assert not _cards(c)                                                            # edits denied without a card
    assert [e["status"] for e in _final(c) if e["tool"] in ("Write", "Edit")] == ["denied", "denied"]


def test_claude_question_tool_becomes_a_question_card(harness):
    h = harness()
    q = {"question": "Which colour?", "header": "Colour", "options": [{"label": "Red"}, {"label": "Blue"}],
         "multiSelect": False}
    fake.script(PILOT, [[fake.call("AskUserQuestion", {"questions": [q]}), fake.say("Blue it is.")]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "answer": "Blue"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "ask me"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    card = _cards(c, "question")[0]
    assert card["title"] == "Colour" and card["body"] == "Which colour?" and card["options"] == ["Red", "Blue"]
    result = hub.chats[cid].last_reply.tool_calls[0].result
    assert '"answers": {"Which colour?": "Blue"}' in result


def test_interrupt_clears_cards_and_stops(harness):
    h = harness()
    fake.script(PILOT, [[fake.call("Bash", {"command": "npm test"}), fake.call("Write", {"file_path": "a", "content": "x"}),
                         fake.say("should not matter")]])

    async def go():
        hub, c, cid = await _start(h)
        turn = asyncio.create_task(hub.handle({"type": "chat_message", "chat_id": cid, "text": "go"}))
        await h.wait(lambda: _cards(c))
        await hub.handle({"type": "chat_stop", "chat_id": cid})
        await turn
        return c

    c = asyncio.run(go())
    assert len(_cards(c)) == 1 and c.of("queue_resolved")[0]["id"] == _cards(c)[0]["id"]
    assert c.of("chat_done")[-1]["status"] == "stopped"
    assert [e["status"] for e in _final(c)] == ["denied", "denied"]


def test_snapshot_restores_chats(harness):
    h = harness()
    fake.script(PILOT, [[fake.say("Hi!")]])

    async def go():
        hub, c, cid = await _start(h)
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "plan"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        late = Client(hub)
        await hub.connect(late)
        return late, cid

    late, cid = asyncio.run(go())
    snap = late.events[0]
    chat = next(x for x in snap["chats"] if x["id"] == cid)
    assert chat["mode"] == "plan" and chat["model"] == "sonnet" and chat["busy"] is False
    assert chat["history"] == [{"role": "user", "markdown": "hello"}, {"role": "assistant", "markdown": "Hi!"}]
    assert late.of("chat_started")[0]["chat_id"] == cid
