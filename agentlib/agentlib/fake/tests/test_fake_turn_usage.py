"""Reply.turn_usage on the fake engine: tokens per model reply, scripted or default (zero tokens)."""
import asyncio
from functools import reduce

import pytest

from agentlib import Agent, AgentError, TurnUsage, Usage
from agentlib import fake


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()


def _read(path, **kw):
    return fake.call("Read", {"file_path": path}, **kw)


def _agent(**kw):
    return Agent("a", engine="fake", tools=["Read", "ask_user"], **kw)


def _replies(agent, *messages):
    async def go():
        out = []
        async with agent.session() as s:
            for m in messages:
                out.append(await s.send(m))
        return out
    return asyncio.run(go())


def _sum(turns):
    return reduce(lambda a, b: a + b, (t.usage for t in turns), Usage())


def test_default_split_adds_up_and_leaves_reply_usage_unchanged():
    fake.script("a", [[fake.say("Looking at the files now"), _read("a.md"), _read("b.md"), fake.say("All done here.")]])
    [r] = _replies(_agent(), "please read two files")
    assert [t.model_turn for t in r.turn_usage] == [1, 2, 3]
    assert _sum(r.turn_usage) == r.usage
    assert r.usage == Usage(input_tokens=len("please read two files") // 4,
                            output_tokens=len("Looking at the files now" "All done here.") // 4)   # old formula
    assert r.turn_usage[0].usage.input_tokens == r.usage.input_tokens          # input on the first reply
    assert r.turn_usage[1].usage == Usage()                                    # a bare call writes no text
    assert all(t.model == "fake" for t in r.turn_usage)


def test_scripted_usage_per_separate_reply_and_reply_total_is_their_sum():
    fake.script("a", [[_read("a.md", usage=Usage(input_tokens=100, output_tokens=20, cache_read_tokens=5)),
                       _read("b.md", usage={"input_tokens": 300, "output_tokens": 40, "cache_write_tokens": 7}),
                       fake.say("Done.", usage=Usage(input_tokens=10, output_tokens=2))]])
    [r] = _replies(_agent(model="fake-small"), "go")
    assert r.turn_usage == [
        TurnUsage(1, Usage(input_tokens=100, output_tokens=20, cache_read_tokens=5), "fake-small"),
        TurnUsage(2, Usage(input_tokens=300, output_tokens=40, cache_write_tokens=7), "fake-small"),
        TurnUsage(3, Usage(input_tokens=10, output_tokens=2), "fake-small")]
    assert r.usage == _sum(r.turn_usage) == Usage(410, 62, 5, 7)


def test_parallel_calls_are_one_reply_with_one_usage():
    fake.script("a", [[fake.parallel(fake.say("Reading both", usage=Usage(output_tokens=3)),
                                     _read("a.md"), _read("b.md", usage=Usage(output_tokens=4)),
                                     usage=Usage(input_tokens=500)),
                       fake.say("Done.", usage=Usage(input_tokens=600, output_tokens=5))]])
    [r] = _replies(_agent(), "go")
    assert {c.model_turn for c in r.tool_calls} == {1}
    assert [(t.model_turn, t.usage) for t in r.turn_usage] == [(1, Usage(input_tokens=500, output_tokens=7)),
                                                                (2, Usage(input_tokens=600, output_tokens=5))]
    assert r.usage == _sum(r.turn_usage)


def test_numbers_run_on_across_send_and_answer():
    q = {"id": "x", "question": "Which?", "why": "Unclear.", "options": ["A", "B"], "recommended": "A"}
    fake.script("a", [[_read("a.md", usage=Usage(1, 1)), fake.ask([q], usage=Usage(2, 2))],
                      [fake.say("Using A", usage=Usage(3, 3))],
                      [_read("b.md"), fake.say("ok")]])
    agent = _agent()

    async def go():
        async with agent.session() as s:
            r1 = await s.send("go")
            r2 = await s.answer({"x": "A"})
            r3 = await s.send("more")
            return r1, r2, r3
    r1, r2, r3 = asyncio.run(go())
    assert [t.model_turn for t in r1.turn_usage] == [1, 2] and r1.status == "needs_input"
    assert [(t.model_turn, t.usage) for t in r2.turn_usage] == [(3, Usage(3, 3))]
    assert [t.model_turn for t in r3.turn_usage] == [4, 5]            # default split, numbers run on
    assert _sum(r3.turn_usage) == r3.usage
    # the turn_usage numbers are the events' numbers
    assert {c.model_turn for c in r3.tool_calls} <= {t.model_turn for t in r3.turn_usage}


def test_unscripted_replies_keep_their_default_share_when_others_are_scripted():
    fake.script("a", [[_read("a.md", usage=Usage(input_tokens=1000)), fake.say("The answer is here.")]])
    [r] = _replies(_agent(), "go")
    assert r.turn_usage[0].usage == Usage(input_tokens=1000)
    assert r.turn_usage[1].usage.output_tokens == len("The answer is here.") // 4
    assert r.usage == _sum(r.turn_usage)


def test_set_model_counts_from_the_next_reply():
    agent = _agent(model="fake-large")

    async def go():
        async with agent.session() as s:
            fake.script("a", [[_read("a.md"), fake.say("done")]])
            await s.set_model("fake-small")
            return await s.send("go")
    r = asyncio.run(go())
    assert {t.model for t in r.turn_usage} == {"fake-small"}


def test_failed_turn_keeps_turn_usage_in_the_error_reply():
    fake.script("a", [[_read("a.md", usage=Usage(input_tokens=50, output_tokens=5)), fake.fail("boom")]])

    async def go():
        async with _agent().session() as s:
            await s.send("go")
    with pytest.raises(AgentError) as ei:
        asyncio.run(go())
    rep = ei.value.reply
    assert [(t.model_turn, t.usage) for t in rep.turn_usage] == [(1, Usage(input_tokens=50, output_tokens=5))]
    assert rep.usage == Usage(input_tokens=50, output_tokens=5)


def test_bad_usage_value_and_to_dict():
    with pytest.raises(TypeError, match="usage"):
        fake.say("x", usage=5)
    fake.script("a", [[fake.say("hi", usage=Usage(2, 1))]])
    [r] = _replies(_agent(), "go")
    assert r.to_dict()["turn_usage"] == [{"model_turn": 1, "model": "fake",
                                          "usage": {**Usage(2, 1).__dict__}}]


def test_capability_flag():
    from agentlib import get_engine
    assert get_engine("fake").capabilities.turn_usage
    assert not get_engine("cursor").capabilities.turn_usage
