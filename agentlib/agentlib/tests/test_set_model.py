"""Session.set_model: switch a live conversation to another model (between turns and mid-turn)."""
import asyncio

import pytest

from agentlib import Agent, CapabilityError, fake, tool
from agentlib.engines import get_engine


@pytest.fixture(autouse=True)
def _clean():
    fake.reset()
    yield
    fake.reset()


def test_fake_switch_between_turns_and_mid_turn_keeps_the_conversation():
    seen = []
    holder = {}

    @tool
    async def promote() -> str:
        """Switch to the bigger model."""
        await holder["s"].set_model("fake-large")
        return "promoted"

    fake.script("m", [
        [fake.say("one")],
        lambda msg: seen.append(msg) or [fake.call("promote"), fake.say("two")],
        [fake.say("three")],
    ])

    async def go():
        a = Agent("m", instructions="x", engine="fake", model="fake-small", tools=[promote])
        async with a.session() as s:
            holder["s"] = s
            r1 = await s.send("hi")
            r2 = await s.send("again")
            assert s.model == "fake-large"
            r3 = await s.send("more")
            return r1, r2, r3, s.session_id

    r1, r2, r3, sid = asyncio.run(go())
    assert r1.model == "fake-small" and r2.model == "fake-large" and r3.model == "fake-large"
    assert set(r2.usage_by_model) == {"fake-large"} and r2.usage_by_model["fake-large"]["cost_usd"] == r2.cost_usd
    assert r1.session_id == r3.session_id == sid and seen == ["again"]        # same conversation throughout


def test_claude_session_records_model_for_restarts_and_capability():
    a = Agent("m", instructions="x", tools=[], model="sonnet")
    es = get_engine("claude").open(a, resume=None, fork=False, cost_base=0)
    asyncio.run(es.set_model("opus"))                       # no live process yet: the next one starts on opus
    assert es.requested_model == "opus" and es.options(resume=None).model == "opus"
    assert get_engine("claude").capabilities.model_switch and not get_engine("cursor").capabilities.model_switch


def test_claude_model_usage_becomes_per_turn_per_model():
    from types import SimpleNamespace
    es = get_engine("claude").open(Agent("m", instructions="x", tools=[]), resume=None, fork=False, cost_base=0)
    t1 = SimpleNamespace(model_usage={"s": {"inputTokens": 5, "outputTokens": 10, "cacheReadInputTokens": 100,
                                            "cacheCreationInputTokens": 50, "costUSD": 0.01}})
    t2 = SimpleNamespace(model_usage={"s": {"inputTokens": 5, "outputTokens": 10, "cacheReadInputTokens": 100,
                                            "cacheCreationInputTokens": 50, "costUSD": 0.01},
                                      "o": {"inputTokens": 2, "outputTokens": 7, "cacheReadInputTokens": 0,
                                            "cacheCreationInputTokens": 900, "costUSD": 0.02}})
    assert es._turn_usage_by_model(t1)["s"]["cost_usd"] == 0.01
    second = es._turn_usage_by_model(t2)
    assert list(second) == ["o"] and second["o"]["usage"].cache_write_tokens == 900


def test_unsupported_engine_raises():
    with pytest.raises(CapabilityError):
        from agentlib.session import Session
        s = Session.__new__(Session)
        s.agent = Agent("x", instructions="x", engine="cursor")
        asyncio.run(s.set_model("opus"))
