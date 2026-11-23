"""Fake engine: Session.pid and Session.kill() (capability process_control), zero tokens."""
import asyncio
import subprocess
import sys
from dataclasses import replace

import pytest

from agentlib import Agent, AgentError, CapabilityError, get_engine, register_engine
from agentlib import fake
from agentlib.processes import is_running


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()
    yield
    fake.reset()


def run(coro):
    return asyncio.run(coro)


def test_capability_claimed_by_claude_and_fake_not_cursor():
    assert get_engine("fake").capabilities.process_control
    assert get_engine("claude").capabilities.process_control
    assert not get_engine("cursor").capabilities.process_control


def test_unscripted_pid_is_none_and_kill_is_recorded():
    async def go():
        async with Agent("a", engine="fake").session() as s:
            assert s.pid is None
            res = await s.kill()
            assert res.ok and res.already_gone and res.pid is None
            return s.session_id
    sid = run(go())
    assert fake.kills() == [{"agent": "a", "session_id": sid, "pid": None, "mid_turn": False, "real": False}]


def test_scripted_pid_kill_closes_the_session_and_twice_is_harmless():
    fake.process("a", 424242)

    async def go():
        s = Agent("a", engine="fake").session()
        assert s.pid is None                                  # not connected yet
        async with s:
            assert s.pid == 424242
            first = await s.kill()
            assert first.ok and first.pid == 424242 and not first.ended    # recorded only (not real)
            assert s.pid is None
            second = await s.kill()
            assert second.ok and second.already_gone
            with pytest.raises(AgentError, match="ended"):
                await s.send("more")
    run(go())
    assert [k["pid"] for k in fake.kills()] == [424242, None]


def test_pid_function_per_session_and_close_clears_pid():
    n = iter([111, 222])
    fake.process("a", lambda: next(n))

    async def go():
        pids = []
        for _ in range(2):
            async with Agent("a", engine="fake").session() as s:
                await s.send("hi")
                pids.append(s.pid)
            assert s.pid is None                              # closed
        return pids
    assert run(go()) == [111, 222]


def test_kill_mid_turn_fails_the_turn_with_partial_reply():
    fake.process("a", 7)
    fake.script("a", [[fake.say("one"), fake.say("two"), fake.say("three")]])

    async def go():
        async with Agent("a", engine="fake").session() as s:
            seen = []
            with pytest.raises(AgentError, match="ended") as ei:
                async for ev in s.stream("go"):
                    seen.append(ev.type)
                    if ev.type == "text":
                        await s.kill()
            assert "one" in ei.value.reply.text and "three" not in ei.value.reply.text
    run(go())
    assert fake.kills()[0]["mid_turn"] is True


def test_real_stand_in_process_is_ended():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        fake.process("a", p.pid, real=True)

        async def go():
            async with Agent("a", engine="fake").session() as s:
                assert s.pid == p.pid
                return await s.kill()
        res = run(go())
        assert res.ok and p.pid in {i.pid for i in res.ended}
        p.wait(timeout=10)
        assert not is_running(p.pid)
        assert fake.kills()[0]["real"] is True
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=10)


def test_process_started_at_on_the_fake():
    from agentlib.fake.engine import FAKE_STARTED_AT
    from agentlib.processes import end_process_tree
    fake.process("a", 4242)

    async def go():
        s = Agent("a", engine="fake").session()
        assert s.process_started_at is None
        async with s:
            assert s.process_started_at == FAKE_STARTED_AT
            # a scripted pid with its made-up start time can never end a real process that has that pid
            res = end_process_tree(s.pid, started_at=s.process_started_at)
            assert not res.ended
            await s.kill()
            assert s.process_started_at is None
    run(go())


def test_real_process_start_time_and_unknown_start_time():
    from agentlib.processes import process_started_at
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        fake.process("a", p.pid, real=True)

        async def go():
            async with Agent("a", engine="fake").session() as s:
                assert s.process_started_at == process_started_at(p.pid)
                await s.kill()
        run(go())
        p.wait(timeout=10)
        fake.process("b", p.pid, real=True)              # gone now: start time unknown -> nothing recorded

        async def gone():
            async with Agent("b", engine="fake").session() as s:
                assert s.pid is None and s.process_started_at is None
                assert (await s.kill()).already_gone
        run(gone())
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=10)


def test_session_kill_needs_the_capability():
    caps = replace(get_engine("fake").capabilities, process_control=False)

    class NoProc(fake.FakeEngine):
        capabilities = caps
    register_engine("fake-noproc", NoProc)

    async def go():
        async with Agent("a", engine="fake-noproc").session() as s:
            with pytest.raises(CapabilityError, match="process_control"):
                await s.kill()
    run(go())
