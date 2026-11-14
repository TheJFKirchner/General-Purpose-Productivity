"""Shared test setup: fake engine only (zero tokens), a throwaway project folder, a recording UI client."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agentlib import fake  # noqa: E402  (registers the fake engine)

from app import run as run_mod  # noqa: E402
from app.hub import Hub  # noqa: E402
from app.settings import Settings  # noqa: E402

PLAN = {
    "name": "Test plan",
    "goal": "Build two small things.",
    "steps": [
        {"title": "First thing", "details": "Make the first thing.", "done_when": "It exists."},
        {"title": "Second thing", "details": "Make the second thing.", "done_when": "It works.", "after": [1]},
    ],
}


def report(status="done", **kw) -> dict:
    r = {"built": [{"item": "thing.txt", "does": "Holds the thing"}], "assumptions": [], "issues": [],
         "notes_for_orchestrator": "ok", "routing_notes": "", "status": status}
    r.update(kw)
    return r


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    empty = tmp_path / "agentlib-local-setup.toml"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("AGENTLIB_SETUP_FILE", str(empty))       # never read the developer's sign-in setup
    monkeypatch.setenv("LAUNCHPAD_HOME", str(tmp_path / "launchpad-home"))   # settings + backups: never the real home
    fake.reset()
    yield
    fake.reset()


@pytest.fixture
def project(tmp_path) -> Path:
    p = tmp_path / "proj"
    (p / "app").mkdir(parents=True)
    (p / "docs").mkdir()
    (p / "CLAUDE.md").write_text("# Rules\n- be nice\n", encoding="utf-8")
    (p / "docs" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (p / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "outside.md").write_text("# secret\n", encoding="utf-8")
    return p


class Client:
    """Records every event; optional responder(ev) -> UI message to send back (as its own task)."""

    def __init__(self, hub: Hub, responder=None):
        self.hub, self.responder, self.events = hub, responder, []

    async def __call__(self, ev: dict) -> None:
        self.events.append(ev)
        if self.responder is not None:
            msg = self.responder(ev)
            if msg:
                asyncio.get_running_loop().create_task(self.hub.handle(msg))

    def of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e.get("type") == kind]


class Harness:
    def __init__(self, project: Path, monkeypatch, timeout_s: float = 0.3, responder=None,
                 permission_timeout_s: float = 180, autopilot: bool = False):
        self.project = project
        self.settings = Settings(project=project, engine="fake", question_timeout_s=timeout_s,
                                 permission_timeout_s=permission_timeout_s, autopilot_default=autopilot)
        self.responder = responder
        self.replies: list = []                  # every builder/orchestrator Reply, in order
        original = run_mod.Run._turn
        harness = self

        async def recording(self, s, message, meter):
            reply = await original(self, s, message, meter)
            harness.replies.append((meter.role, message, reply))
            return reply

        monkeypatch.setattr(run_mod.Run, "_turn", recording)

    async def start(self) -> tuple[Hub, Client]:
        self.hub = Hub(self.settings)
        self.client = Client(self.hub, self.responder)
        await self.hub.connect(self.client)
        return self.hub, self.client

    async def wait(self, cond, timeout: float = 10.0) -> None:
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while not cond():
            if loop.time() > end:
                raise AssertionError("timed out waiting for condition")
            await asyncio.sleep(0.01)

    def tool_results(self, role: str = "builder") -> list[tuple[str, str, bool]]:
        out = []
        for r, _msg, reply in self.replies:
            if r == role and reply is not None:
                out += [(c.name, c.result or "", c.is_error) for c in reply.tool_calls]
        return out


@pytest.fixture
def harness(project, monkeypatch):
    made: list[Harness] = []

    def make(**kw) -> Harness:
        h = Harness(project, monkeypatch, **kw)
        made.append(h)
        return h
    yield make
    for h in made:                       # the hub turns exceptions into system messages: never let one hide
        client = getattr(h, "client", None)
        errors = [e["text"] for e in (client.of("system") if client else []) if "error" in e["text"].lower()]
        assert not errors, errors


def script_planner_writes_plan(plan: dict = PLAN) -> None:
    fake.script("launchpad-planner", [[fake.call("write_plan", plan), fake.say("Draft saved.")]])


def script_orchestrator_sequential(n_steps: int, seen: list | None = None) -> None:
    """run_builder 1..n, then write_report; records each message it receives in `seen`."""
    import re

    def turn(msg: str):
        if seen is not None:
            seen.append(msg)
        m = re.search(r"Step (\d+) result", msg)
        nxt = int(m.group(1)) + 1 if m else 1
        if nxt <= n_steps:
            return [fake.call("run_builder", {"step": nxt, "brief": f"do step {nxt}"})]
        return [fake.call("write_report", {"summary": "All done.", "built": ["thing"], "issues": []})]

    fake.script("launchpad-orchestrator", [turn] * 20)
