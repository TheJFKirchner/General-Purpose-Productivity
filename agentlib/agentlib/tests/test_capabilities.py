"""Engine.check(): availability and every capability an Agent / session request can need (no tokens)."""
from dataclasses import replace

import pytest

from agentlib import Agent, CapabilityError, EngineUnavailable, get_engine, register_engine, tool
from agentlib.engines import Capabilities, Engine

FULL = Capabilities(fork=True, permission_hook=True)


@tool(ends_turn=True)
def finish(note: str) -> str:
    """Finish."""
    return note


@tool
def plain(x: str) -> str:
    """Plain."""
    return x


class _Probe(Engine):
    name = "probe"

    def __init__(self, caps: Capabilities):
        self.capabilities = caps

    def open(self, agent, *, resume, fork, cost_base):
        raise AssertionError("check() should have stopped this")


def _engine(**off) -> Engine:
    eng = _Probe(replace(FULL, **off))
    register_engine("probe", lambda: eng)
    return get_engine("probe")


BARE = dict(engine="probe", include_ask_user=False)     # needs nothing at all


# (capability turned off, agent kwargs that need it, session kwargs that need it)
CASES = [
    ("system_prompt", {"instructions": "Be brief."}, {}),
    ("custom_tools", {"tools": [plain]}, {}),
    ("ends_turn", {"tools": [finish]}, {}),
    ("ends_turn", {"tools": ["ask_user"]}, {}),
    ("mcp_servers", {"mcp_servers": {"db": "db.py"}}, {}),
    ("resume", {}, {"resume": "abc"}),
    ("fork", {}, {"resume": "abc", "fork": True}),
    ("permission_hook", {"on_permission": lambda req: "allow"}, {}),
    ("project_setup", {"setup": "project"}, {}),
]


@pytest.mark.parametrize("flag, agent_kw, session_kw", CASES)
def test_each_needed_capability_is_enforced(flag, agent_kw, session_kw):
    _engine(**{flag: False})
    with pytest.raises(CapabilityError, match=flag):
        Agent("a", **{**BARE, **agent_kw}).session(**session_kw)


@pytest.mark.parametrize("flag, agent_kw, session_kw", CASES)
def test_capability_not_needed_is_not_enforced(flag, agent_kw, session_kw):
    eng = _engine(**{flag: False})
    eng.check(Agent("a", **BARE))                      # bare agent passes even with the flag off


def test_lean_skills_need_system_prompt():
    eng = _engine(system_prompt=False)
    with pytest.raises(CapabilityError, match="system_prompt"):
        eng.check(Agent("a", skills=["memo"], **BARE))
    eng.check(Agent("a", skills=["memo"], setup="project", **BARE))   # project: native skills, no prompt


def test_informational_flags_are_not_enforced():
    eng = _engine(streaming=False, usage=False)
    eng.check(Agent("a", instructions="x", tools=[plain, "ask_user"], **BARE))


def test_unavailable_engine_raises_engine_unavailable_at_check():
    eng = _engine(available=False)
    with pytest.raises(EngineUnavailable, match="cannot run yet"):
        eng.check(Agent("a", **BARE))
    with pytest.raises(EngineUnavailable, match="fork"):          # lists what it would also lack
        _engine(available=False, fork=False).check(Agent("a", **BARE), fork=True)


def test_cursor_stub_fails_at_check_time():
    with pytest.raises(EngineUnavailable) as ei:
        get_engine("cursor").check(Agent("a", engine="cursor", instructions="hi"))
    assert "cursor" in ei.value.short and "system_prompt" in ei.value.short
    assert not isinstance(ei.value, CapabilityError)


def test_missing_list_names_all_gaps():
    _engine(fork=False, permission_hook=False)
    with pytest.raises(CapabilityError, match="fork, permission_hook"):
        Agent("a", on_permission=lambda r: True, **BARE).session(resume="abc", fork=True)
