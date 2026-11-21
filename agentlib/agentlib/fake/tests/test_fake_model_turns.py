"""model_turn on the fake engine: which model reply each text / tool call / tool result belongs to."""
import asyncio

import pytest

from agentlib import Agent
from agentlib import fake


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()


def _read(path):
    return fake.call("Read", {"file_path": path})


def _agent():
    return Agent("a", engine="fake", tools=["Read", "ask_user"])


def _events(agent, *messages):
    async def go():
        out = []
        async with agent.session() as s:
            for m in messages:
                out.append([ev async for ev in s.stream(m) if ev.type != "text_delta"])
        return out
    return asyncio.run(go())


def test_calls_in_separate_replies_get_increasing_numbers():
    fake.script("a", [[fake.say("Looking"), _read("a.md"), _read("b.md"), _read("c.md"), fake.say("Done.")]])
    [evs] = _events(_agent(), "go")
    assert [(e.type, e.model_turn) for e in evs[:-1]] == [
        ("text", 1), ("tool_call", 1), ("tool_result", 1),     # text before a call is part of that reply
        ("tool_call", 2), ("tool_result", 2),
        ("tool_call", 3), ("tool_result", 3),
        ("text", 4)]
    reply = evs[-1].reply
    assert [c.model_turn for c in reply.tool_calls] == [1, 2, 3]
    assert reply.api_calls == 4


def test_parallel_calls_share_one_reply():
    fake.script("a", [[fake.parallel(fake.say("Reading all three"), _read("a.md"), _read("b.md"), _read("c.md")),
                       fake.say("Done.")]])
    [evs] = _events(_agent(), "go")
    assert [e.type for e in evs[:-1]] == ["text"] + ["tool_call"] * 3 + ["tool_result"] * 3 + ["text"]
    assert [e.model_turn for e in evs[:-2]] == [1] * 7
    assert evs[-2].model_turn == 2
    calls = [e for e in evs if e.type == "tool_call"]
    results = [e for e in evs if e.type == "tool_result"]
    assert [r.id for r in results] == [c.id for c in calls] and not any(r.is_error for r in results)
    assert {c.model_turn for c in evs[-1].reply.tool_calls} == {1} and evs[-1].reply.api_calls == 2


def test_eighteen_reads_one_reply_vs_eighteen_replies():
    reads = [_read(f"f{i}.md") for i in range(18)]
    fake.script("a", [[fake.parallel(*reads)], reads])
    one, many = _events(_agent(), "one reply", "many replies")
    assert {e.model_turn for e in one if e.type == "tool_call"} == {1}
    assert [e.model_turn for e in many if e.type == "tool_call"] == list(range(2, 20))   # numbers run on


def test_numbers_run_on_across_answer_and_restart_on_a_new_session():
    q = {"id": "x", "question": "Which?", "why": "Unclear.", "options": ["A", "B"], "recommended": "A"}
    fake.script("a", [[_read("a.md"), fake.ask([q])], [fake.say("Using A")]])
    agent = _agent()

    async def go():
        async with agent.session() as s:
            first = [ev async for ev in s.stream("go") if ev.type != "text_delta"]
            second = [ev async for ev in s.answer_stream({"x": "A"}) if ev.type != "text_delta"]
            return first, second, s.session_id
    first, second, sid = asyncio.run(go())
    assert [e.model_turn for e in first[:-1]] == [1, 1, 2, 2]
    assert second[0].type == "text" and second[0].model_turn == 3

    fake.script("a", [[fake.say("again")]])

    async def again():
        async with agent.session(resume=sid) as s:
            return [ev async for ev in s.stream("more") if ev.type == "text"]
    assert asyncio.run(again())[0].model_turn == 1          # a resumed session counts from 1 again


def test_model_turn_in_to_dict_and_default_none():
    from agentlib import ToolCall, ToolResult
    fake.script("a", [[_read("a.md")]])
    [evs] = _events(_agent(), "go")
    assert evs[0].to_dict()["model_turn"] == 1
    assert evs[-1].reply.to_dict()["tool_calls"][0]["model_turn"] == 1
    assert ToolCall("i", "Read").model_turn is None and ToolResult("i", "Read", "x").model_turn is None


def test_parallel_takes_only_say_and_call_steps():
    with pytest.raises(TypeError, match="parallel"):
        fake.parallel(fake.spend(0.1))


def test_capability_flag():
    from agentlib import get_engine
    assert get_engine("fake").capabilities.model_turns and get_engine("claude").capabilities.model_turns
    assert not get_engine("cursor").capabilities.model_turns
