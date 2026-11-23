"""Claude engine: pid and kill() against a stub SDK client that owns a REAL stand-in process tree (no tokens,
no `claude` process). The stand-in: a Python parent with a sleeping child, like the CLI running a shell command."""
import asyncio
import subprocess
import sys
import time
from types import SimpleNamespace

import psutil
import pytest

from agentlib import Agent, AgentError
from agentlib import processes
from agentlib.engines import claude as ce
from agentlib.engines.claude import ClaudeSession

PARENT = (
    "import subprocess, sys, time\n"
    "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "print(c.pid, flush=True)\n"
    "time.sleep(120)\n"
)
STARTED: list[subprocess.Popen] = []


@pytest.fixture(autouse=True)
def _cleanup():
    STARTED.clear()
    yield
    for p in STARTED:
        try:
            for c in psutil.Process(p.pid).children(recursive=True):
                c.kill()
        except psutil.Error:
            pass
        if p.poll() is None:
            p.kill()
        try:
            p.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        if p.stdout:
            p.stdout.close()


def _stand_in() -> tuple[subprocess.Popen, int]:
    p = subprocess.Popen([sys.executable, "-c", PARENT], stdout=subprocess.PIPE, text=True)
    STARTED.append(p)
    child = int(p.stdout.readline().strip())
    return p, child


class _ProcClient:
    """Stands in for ClaudeSDKClient: connect() starts the stand-in tree and exposes it like the SDK does
    (client._transport._process.pid); a turn waits until the process dies, then fails (as the SDK would)."""
    with_transport = True
    last: "_ProcClient | None" = None

    def __init__(self, options=None):
        self.proc = None
        self.child = None
        _ProcClient.last = self

    async def connect(self):
        self.proc, self.child = _stand_in()
        if self.with_transport:
            self._transport = SimpleNamespace(_process=SimpleNamespace(pid=self.proc.pid))

    async def query(self, message):
        return None

    async def receive_response(self):
        while self.proc.poll() is None:
            await asyncio.sleep(0.05)
        raise RuntimeError("CLI process exited")
        yield  # pragma: no cover  (makes this an async generator)

    async def interrupt(self):
        return None

    async def disconnect(self):
        return None                      # like a disconnect that leaves the process running


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ce, "ClaudeSDKClient", _ProcClient)
    _ProcClient.with_transport = True
    return _ProcClient


def _gone(*pids, timeout=5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not any(processes.is_running(p) for p in pids):
            return True
        time.sleep(0.05)
    return False


def test_pid_from_the_transport(client):
    async def go():
        s = ClaudeSession(Agent("a", include_ask_user=False), resume=None, fork=False, cost_base=0)
        assert s.pid is None
        await s.start()
        c = client.last
        assert s.pid == c.proc.pid and s.pid_source == "transport"
        res = await s.kill()
        assert res.ok and {c.proc.pid, c.child} <= {i.pid for i in res.ended}
        assert _gone(c.proc.pid, c.child)
        assert s.pid is None
    asyncio.run(go())


def test_process_started_at_is_the_recorded_start_time(client):
    async def go():
        from agentlib.session import Session
        agent = Agent("a", include_ask_user=False)
        s = Session(agent, ClaudeSession(agent, resume=None, fork=False, cost_base=0))
        assert s.process_started_at is None
        async with s:
            pid, started = s.pid, s.process_started_at
            assert isinstance(started, float) and started == processes.process_started_at(pid)
            await s.kill()
            assert s.pid is None and s.process_started_at is None
    asyncio.run(go())


def test_unknown_start_time_records_nothing_and_kills_nothing(client, monkeypatch):
    monkeypatch.setattr(processes, "process_started_at", lambda pid: None)

    async def go():
        s = ClaudeSession(Agent("a", include_ask_user=False), resume=None, fork=False, cost_base=0)
        await s.start()
        c = client.last
        assert s.pid is None and s.process_started_at is None and s.pid_source is None
        res = await s.kill()
        assert res.ok and res.already_gone and not res.ended
        assert processes.is_running(c.proc.pid) and processes.is_running(c.child)   # untouched (fixture ends it)
    asyncio.run(go())


def test_pid_fallback_diffs_children(client):
    client.with_transport = False

    async def go():
        s = ClaudeSession(Agent("a", include_ask_user=False), resume=None, fork=False, cost_base=0)
        await s.start()
        assert s.pid == client.last.proc.pid and s.pid_source == "children"
        await s.kill()
    asyncio.run(go())


def test_kill_mid_turn_ends_tree_fails_turn_and_closes(client):
    async def go():
        from agentlib.session import Session
        agent = Agent("a", include_ask_user=False)
        s = Session(agent, ClaudeSession(agent, resume=None, fork=False, cost_base=0))
        async with s:
            c = client.last
            turn = asyncio.create_task(s.send("work"))
            while not s._es._busy:
                await asyncio.sleep(0.01)
            res = await asyncio.wait_for(s.kill(), 15)
            assert res.ok and c.child in {i.pid for i in res.ended}
            with pytest.raises(AgentError, match="ended") as ei:
                await asyncio.wait_for(turn, 10)
            assert ei.value.reply is not None
            assert _gone(c.proc.pid, c.child)
            again = await s.kill()                              # harmless
            assert again.ok and again.already_gone
            with pytest.raises(AgentError, match="ended"):
                await s.send("more")
    asyncio.run(go())


def test_close_is_unchanged_and_kill_after_close_still_reaches_a_leftover(client):
    async def go():
        s = ClaudeSession(Agent("a", include_ask_user=False), resume=None, fork=False, cost_base=0)
        await s.start()
        c = client.last
        await s.close()                       # disconnect only: the stub leaves the process running
        assert processes.is_running(c.proc.pid) and processes.is_running(c.child)
        assert s.pid is None                  # no live connection
        res = await s.kill()                  # half-closed: the leftover is still ended
        assert res.ok and {c.proc.pid, c.child} <= {i.pid for i in res.ended}
        assert _gone(c.proc.pid, c.child)
    asyncio.run(go())
