"""Fake engine: permission modes, live mode switch, plan approval, suggestions, where always_allow is kept."""
import asyncio

import pytest

from agentlib import Agent, CapabilityError, PermissionDecision, PermissionRequest, PermissionSuggestion
from agentlib import fake


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()
    yield
    fake.reset()


def run(coro):
    return asyncio.run(coro)


class Recorder:
    """on_permission that records every request and answers from a queue (default: deny)."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.seen: list[PermissionRequest] = []

    def __call__(self, req):
        self.seen.append(req)
        return self.answers.pop(0) if self.answers else "deny"


def write(path="notes.txt"):
    return fake.call("Write", {"file_path": path, "content": "x"})


# --- modes on Agent ----------------------------------------------------------------------------------
def test_four_modes_validate():
    for m in ("default", "never_ask", "accept_edits", "plan"):
        assert Agent("a", engine="fake", permission_mode=m).permission_mode == m
    for bad in ("acceptEdits", "bypassPermissions", "auto", "dontAsk"):
        with pytest.raises(ValueError, match="permission_mode"):
            Agent("a", engine="fake", permission_mode=bad)


def test_accept_edits_runs_edits_inside_cwd_without_asking(tmp_path):
    rec = Recorder("deny", "deny")
    fake.script("a", [[write("notes.txt"), fake.call("Bash", {"command": "mkdir build && touch build/x"}),
                       write(str(tmp_path.parent / "outside.txt")), fake.call("Bash", {"command": "curl x"})]])
    r = Agent("a", engine="fake", cwd=tmp_path, tools=["Write", "Bash(echo:*)"], gated_tools=["Write"],
              permission_mode="accept_edits", on_permission=rec).ask_sync("go")
    assert [c.is_error for c in r.tool_calls] == [False, False, True, True]
    assert [q.tool for q in rec.seen] == ["Write", "Bash"]        # outside cwd and non-filesystem command asked
    assert all(q.mode == "accept_edits" for q in rec.seen)


def test_default_mode_asks_for_the_same_edit(tmp_path):
    rec = Recorder()
    fake.script("a", [[write()]])
    r = Agent("a", engine="fake", cwd=tmp_path, tools=[], on_permission=rec).ask_sync("go")
    assert r.tool_calls[0].is_error and rec.seen[0].tool == "Write" and rec.seen[0].mode == "default"


def test_plan_mode_never_preapproves_edits(tmp_path):
    rec = Recorder("deny")
    fake.script("a", [[fake.call("Read", {"file_path": "a.txt"}), write()]])
    r = Agent("a", engine="fake", cwd=tmp_path, tools=["Read", "Write"], permission_mode="plan",
              on_permission=rec).ask_sync("go")
    assert [c.is_error for c in r.tool_calls] == [False, True]   # Write listed, still asked (and denied here)
    assert [q.tool for q in rec.seen] == ["Write"] and rec.seen[0].mode == "plan"
    fake.script("b", [[write()]])
    r = Agent("b", engine="fake", cwd=tmp_path, tools=["Write"], permission_mode="plan").ask_sync("go")
    assert r.tool_calls[0].is_error                               # no hook: blocked


# --- live switch ---------------------------------------------------------------------------------------
def test_set_permission_mode_between_turns(tmp_path):
    rec = Recorder()
    fake.script("a", [[write()], [write()], [write()]])

    async def go():
        async with Agent("a", engine="fake", cwd=tmp_path, tools=[], on_permission=rec).session() as s:
            r1 = await s.send("1")
            await s.set_permission_mode("accept_edits")
            m = s.permission_mode
            r2 = await s.send("2")
            await s.set_permission_mode("default")
            r3 = await s.send("3")
            return r1, m, r2, r3, s.permission_mode
    r1, m, r2, r3, last = run(go())
    assert r1.tool_calls[0].is_error and m == "accept_edits" and not r2.tool_calls[0].is_error
    assert r3.tool_calls[0].is_error and last == "default" and len(rec.seen) == 2


def test_set_permission_mode_rejects_bad_mode():
    async def go():
        async with Agent("a", engine="fake").session() as s:
            with pytest.raises(ValueError):
                await s.set_permission_mode("bypassPermissions")
            assert s.permission_mode == "default"
    run(go())


def test_decision_mode_switches_mid_turn(tmp_path):
    rec = Recorder(PermissionDecision("allow", mode="accept_edits"))
    fake.script("a", [[write("a.txt"), write("b.txt")]])

    async def go():
        async with Agent("a", engine="fake", cwd=tmp_path, tools=[], on_permission=rec).session() as s:
            return await s.send("go"), s.permission_mode
    r, mode = run(go())
    assert [c.is_error for c in r.tool_calls] == [False, False] and len(rec.seen) == 1 and mode == "accept_edits"


# --- plan approval -------------------------------------------------------------------------------------
PLAN = "1. Add notes.txt\n2. Fill it in"


def test_plan_approved_continues_in_chosen_mode(tmp_path):
    rec = Recorder(PermissionDecision("allow", mode="accept_edits"))
    fake.script("a", [[fake.say("Here is my plan."), fake.plan(PLAN), write()]])

    async def go():
        async with Agent("a", engine="fake", cwd=tmp_path, tools=[], permission_mode="plan",
                         on_permission=rec).session() as s:
            return await s.send("plan it"), s.permission_mode
    r, mode = run(go())
    req = rec.seen[0]
    assert (req.kind, req.plan, req.tool, req.mode) == ("plan", PLAN, fake.PLAN_TOOL, "plan")
    assert req.call_id == r.tool_calls[0].id
    assert mode == "accept_edits" and len(rec.seen) == 1          # the edit after approval was not asked
    assert [c.is_error for c in r.tool_calls] == [False, False]


def test_plan_plain_allow_goes_to_default_mode(tmp_path):
    rec = Recorder(True, "deny")
    fake.script("a", [[fake.plan(PLAN), write()]])

    async def go():
        async with Agent("a", engine="fake", cwd=tmp_path, tools=[], permission_mode="plan",
                         on_permission=rec).session() as s:
            return await s.send("go"), s.permission_mode
    r, mode = run(go())
    assert mode == "default" and [q.kind for q in rec.seen] == ["plan", "tool"]   # default: the edit asks


def test_plan_rejected_stays_in_plan_mode_then_approved(tmp_path):
    rec = Recorder(PermissionDecision("deny", message="Also cover the tests."), PermissionDecision(mode="default"))
    fake.script("a", [[fake.plan(PLAN)], [fake.plan(PLAN + "\n3. Tests")]])

    async def go():
        async with Agent("a", engine="fake", cwd=tmp_path, tools=[], permission_mode="plan",
                         on_permission=rec).session() as s:
            r1 = await s.send("plan")
            m1 = s.permission_mode
            r2 = await s.send("revise")
            return r1, m1, r2, s.permission_mode
    r1, m1, r2, m2 = run(go())
    c = r1.tool_calls[0]
    assert c.is_error and "Also cover the tests." in c.result and "plan mode" in c.result and m1 == "plan"
    assert not r2.tool_calls[0].is_error and m2 == "default" and rec.seen[1].plan.endswith("3. Tests")


def test_plan_outside_plan_mode_or_without_hook_is_an_error(tmp_path):
    fake.script("a", [[fake.plan(PLAN)]])
    rec = Recorder("allow")
    r = Agent("a", engine="fake", tools=[], on_permission=rec).ask_sync("go")
    assert r.tool_calls[0].is_error and rec.seen == []
    r = Agent("a", engine="fake", tools=[], permission_mode="plan").ask_sync("go")
    assert r.tool_calls[0].is_error


# --- suggestions + always allow ------------------------------------------------------------------------
def test_requests_carry_suggestions():
    rec = Recorder()
    custom = PermissionSuggestion("add_rules", ["Bash(npm test:*)"], "allow", where="project_local")
    fake.script("a", [[fake.call("Bash", {"command": "npm run build"}), write(),
                       fake.call("Bash", {"command": "npm test"}, suggestions=[custom]),
                       fake.call("WebFetch", {"url": "https://x.org"},
                                 suggestions=[{"kind": "add_rules", "rules": ["WebFetch(domain:x.org)"]}])]])
    Agent("a", engine="fake", tools=[], on_permission=rec).ask_sync("go")
    s = [q.suggestions for q in rec.seen]
    assert s[0][0].rules == ["Bash(npm:*)"] and s[0][0].where == "project_local"
    assert (s[1][0].kind, s[1][0].mode, s[1][0].where) == ("set_mode", "accept_edits", "session")
    assert s[2] == [custom] and s[3][0].rules == ["WebFetch(domain:x.org)"] and s[3][0].where == "session"
    assert s[0][0].to_dict()["kind"] == "add_rules" and rec.seen[0].to_dict()["suggestions"][0]["rules"]


def test_always_allow_session_only_by_default(tmp_path):
    rec = Recorder("always_allow")
    fake.script("a", [[fake.call("Bash", {"command": "npm run x"}), fake.call("Bash", {"command": "git log"})],
                      [fake.call("Bash", {"command": "git log"})]])
    agent = Agent("a", engine="fake", cwd=tmp_path, setup="project", tools=[], on_permission=rec)
    r = agent.ask_sync("go")
    assert [c.is_error for c in r.tool_calls] == [False, False] and len(rec.seen) == 1   # whole tool, this session
    assert fake.saved_rules(tmp_path) == []
    fake.script("a", [[fake.call("Bash", {"command": "git log"})]])
    agent.ask_sync("new session")
    assert len(rec.seen) == 2                                     # a new session asks again


def test_always_allow_project_local_persists_for_project_sessions(tmp_path):
    rec = Recorder(PermissionDecision("always_allow", remember="project_local"))
    fake.script("a", [[fake.call("Bash", {"command": "npm run build"}), fake.call("Bash", {"command": "npm test"}),
                       fake.call("Bash", {"command": "git push"})]])
    agent = Agent("a", engine="fake", cwd=tmp_path, setup="project", tools=[], on_permission=rec)
    r = agent.ask_sync("go")
    assert fake.saved_rules(tmp_path) == ["Bash(npm:*)"]          # the suggested rule, not the whole tool
    assert [c.is_error for c in r.tool_calls] == [False, False, True]   # npm test: remembered; git push: asked
    fake.script("a", [[fake.call("Bash", {"command": "npm ci"})]])
    assert not agent.ask_sync("later").tool_calls[0].is_error and len(rec.seen) == 2   # new session: not asked
    fake.script("lean", [[fake.call("Bash", {"command": "npm ci"})]])
    lean = Agent("lean", engine="fake", cwd=tmp_path, tools=[], on_permission=Recorder())
    assert lean.ask_sync("go").tool_calls[0].is_error            # lean setup does not read project settings
    assert fake.saved_rules(tmp_path.parent) == []


def test_always_allow_with_explicit_rules(tmp_path):
    rec = Recorder(PermissionDecision("always_allow", rules=["Bash(git status)"], remember="project_local"))
    fake.script("a", [[fake.call("Bash", {"command": "git status"}), fake.call("Bash", {"command": "git status"}),
                       fake.call("Bash", {"command": "git push"})]])
    Agent("a", engine="fake", cwd=tmp_path, setup="project", tools=[], on_permission=rec).ask_sync("go")
    assert fake.saved_rules(tmp_path) == ["Bash(git status)"] and len(rec.seen) == 2


def test_deny_message_reaches_the_tool_result():
    fake.script("a", [[fake.call("Bash", {"command": "rm -rf x"})]])
    r = Agent("a", engine="fake", tools=[],
              on_permission=lambda req: PermissionDecision("deny", message="Archive it instead.")).ask_sync("go")
    assert r.tool_calls[0].result == "The user denied Bash. The user's feedback: Archive it instead."


def test_bad_decisions_rejected():
    with pytest.raises(ValueError):
        PermissionDecision("maybe")
    with pytest.raises(ValueError):
        PermissionDecision("always_allow", remember="user")
    with pytest.raises(ValueError):
        PermissionDecision(mode="acceptEdits")


def test_mode_switch_needs_capability():
    from agentlib.engines.base import check_mode_switch
    from agentlib.engines import Capabilities
    with pytest.raises(CapabilityError, match="mode_switch"):
        check_mode_switch("x", Capabilities(), "default")
    with pytest.raises(CapabilityError, match="plan_mode"):
        check_mode_switch("x", Capabilities(mode_switch=True), "plan")
    check_mode_switch("x", Capabilities(mode_switch=True, accept_edits=True), "accept_edits")
