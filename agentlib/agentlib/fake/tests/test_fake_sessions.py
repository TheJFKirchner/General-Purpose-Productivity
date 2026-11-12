"""Session behaviour on the fake engine: events, ask_user parking, answer/resume, tool errors, permissions."""
import asyncio

import pytest

from agentlib import Agent, AgentError, CapabilityError, ConversationMissing, EngineUnavailable, tool
from agentlib import fake

Q = {"id": "trend_years", "question": "Which years?", "why": "No period given.",
     "options": ["Last 3 years", "Last 5 years"], "recommended": "Last 5 years"}


@tool
def run_sql(query: str) -> str:
    """Run SQL."""
    if query == "bad":
        raise ValueError("syntax error")
    return "1200 rows"


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()


def run(coro):
    return asyncio.run(coro)


def test_event_order_and_reply():
    fake.script("a", [[fake.say("Looking now"), fake.call("run_sql", {"query": "q"}), fake.say("Done.")]])

    async def go():
        async with Agent("a", engine="fake", tools=[run_sql]).session() as s:
            return [ev async for ev in s.stream("go")]
    evs = run(go())
    types = [e.type for e in evs if e.type != "text_delta"]
    assert types == ["text", "tool_call", "tool_result", "text", "done"]
    reply = evs[-1].reply
    assert reply.status == "done" and reply.text == "Looking now\n\nDone."
    assert reply.tool_calls[0].result == "1200 rows"
    assert reply.to_dict()["usage"]["input_tokens"] >= 1


def test_tool_error_keeps_turn_going():
    fake.script("a", [[fake.call("run_sql", {"query": "bad"}), fake.say("Recovered")]])
    r = Agent("a", engine="fake", tools=[run_sql]).ask_sync("go")
    assert r.tool_calls[0].is_error and "syntax error" in r.tool_calls[0].result
    assert r.status == "done" and r.text == "Recovered"


def test_ask_user_parks_then_answer_resumes():
    seen = []
    fake.script("a", [
        [fake.say("Need input"), fake.ask([Q]), fake.say("never reached")],
        lambda msg: seen.append(msg) or [fake.say("Using 3 years")],
    ])

    async def go():
        async with Agent("a", engine="fake").session() as s:
            r1 = await s.send("make the trend report")
            r2 = await s.answer({"trend_years": "Last 3 years"})
            return r1, r2
    r1, r2 = run(go())
    assert r1.status == "needs_input" and r1.questions[0].id == "trend_years"
    assert "never reached" not in r1.text
    assert "trend_years: Last 3 years" in seen[0]
    assert r2.status == "done"


def test_bad_question_shape_goes_back_to_agent():
    fake.script("a", [[fake.ask([{"id": "x", "question": "?"}]), fake.say("fixed it")]])
    r = Agent("a", engine="fake").ask_sync("go")
    assert r.status == "done" and r.tool_calls[0].is_error and "why" in r.tool_calls[0].result


def test_answer_after_restart_with_saved_questions():
    fake.script("a", [[fake.ask([Q])], [fake.say("ok")]])
    agent = Agent("a", engine="fake")
    r1 = agent.ask_sync("go")
    saved = [q.to_dict() for q in r1.questions]           # e.g. stored as JSON by the app

    async def later():
        async with agent.session(resume=r1.session_id) as s:
            return await s.answer({"trend_years": "Last 5 years"}, questions=saved)
    assert run(later()).text == "ok"


def test_resume_unknown_session():
    with pytest.raises(ConversationMissing):
        Agent("a", engine="fake").session(resume="nope")


def test_permissions_default_deny_and_hook():
    fake.script("a", [[fake.call("Bash", {"command": "ls"})]])
    r = Agent("a", engine="fake", tools=["Read"]).ask_sync("go")
    assert r.tool_calls[0].is_error and "not allowed" in r.tool_calls[0].result

    asked = []
    fake.script("b", [[fake.call("Bash", {"command": "ls"})]])
    r = Agent("b", engine="fake", tools=["Read"], on_permission=lambda req: asked.append(req.tool) or "allow")
    out = r.ask_sync("go")
    assert asked == ["Bash"] and not out.tool_calls[0].is_error

    fake.script("c", [[fake.call("Bash", {"command": "ls"})]])
    assert not Agent("c", engine="fake", tools=["Bash(ls:*)"]).ask_sync("go").tool_calls[0].is_error


def test_rate_limit_event_and_failure():
    fake.script("a", [[fake.rate_limit(), fake.say("hi")], [fake.fail("gateway down")]])

    async def go():
        async with Agent("a", engine="fake").session() as s:
            evs = [ev async for ev in s.stream("one")]
            with pytest.raises(AgentError, match="gateway down"):
                await s.send("two")
            return evs
    assert run(go())[0].type == "rate_limit"


def test_cursor_stub_and_capabilities():
    with pytest.raises(EngineUnavailable):
        Agent("a", engine="cursor").session()
    with pytest.raises(EngineUnavailable, match="permission_hook"):    # unavailable first, lacks listed
        Agent("a", engine="cursor", on_permission=lambda r: "allow").session()
    with pytest.raises(CapabilityError, match="mcp_servers"):         # fake has no external MCP servers
        Agent("a", engine="fake", mcp_servers={"db": "db.py"}).session()


# ----------------------------------------------------------------------------- permission rules (4a)

def _bash(rule_tools, command, **kw):
    fake.reset()
    fake.script("p", [[fake.call("Bash", {"command": command})]])
    return Agent("p", engine="fake", tools=rule_tools, **kw).ask_sync("go").tool_calls[0]


@pytest.mark.parametrize("command, ok", [
    ("ls", True), ("ls -la", True), ("lsof", False), ("rm -rf build", False),
    ("ls && rm -rf build", False), ("ls | wc -l", False), ("ls &&", False),
])
def test_bash_prefix_rule_matches_command_not_just_tool(command, ok):
    call = _bash(["Bash(ls:*)"], command)
    assert call.is_error is (not ok), call.result


def test_bash_compound_needs_every_part_allowed():
    assert not _bash(["Bash(ls *)", "Bash(wc *)"], "ls | wc -l").is_error
    assert not _bash(["Bash(npm run build)"], "npm run build").is_error
    assert _bash(["Bash(npm run build)"], "npm run build --watch").is_error
    assert not _bash(["Bash"], "anything at all").is_error


def test_unmatched_command_goes_to_hook_and_always_allow_sticks():
    asked = []
    fake.script("p", [[fake.call("Bash", {"command": "echo hi"}),
                       fake.call("Bash", {"command": "rm x"}),
                       fake.call("Bash", {"command": "rm y"})]])
    agent = Agent("p", engine="fake", tools=["Bash(echo:*)"],
                  on_permission=lambda req: asked.append(req.input["command"]) or "always_allow")
    r = agent.ask_sync("go")
    assert asked == ["rm x"] and not any(c.is_error for c in r.tool_calls)


def test_disallowed_tools_deny_beats_allow_and_hook():
    call = _bash(["Bash"], "git push origin main", disallowed_tools=["Bash(git push *)"],
                 on_permission=lambda req: "allow")
    assert call.is_error and "denied" in call.result
    assert not _bash(["Bash"], "git status", disallowed_tools=["Bash(git push *)"]).is_error


def test_path_and_domain_rules(tmp_path):
    fake.script("p", [[fake.call("Edit", {"file_path": str(tmp_path / "src" / "a.py")}),
                       fake.call("Write", {"file_path": str(tmp_path / "docs" / "b.md")}),
                       fake.call("WebFetch", {"url": "https://docs.python.org/3/"}),
                       fake.call("WebFetch", {"url": "https://evil.example/"})]])
    r = Agent("p", engine="fake", cwd=tmp_path,
              tools=["Edit(src/**)", "WebFetch(domain:*.python.org)"]).ask_sync("go")
    assert [c.is_error for c in r.tool_calls] == [False, True, False, True]


# ----------------------------------------------------------------------------- cost_base (4c)

def test_cost_is_cumulative_per_conversation_and_honours_cost_base():
    fake.script("a", [[fake.say("one two three")], [fake.say("four five")], [fake.say("six")], [fake.say("x")]])
    agent = Agent("a", engine="fake")

    async def go():
        async with agent.session() as s:
            r1 = await s.send("first message")
            r2 = await s.send("second message")
        sid = s.session_id
        async with agent.session(resume=sid, cost_base=r2.total_cost_usd) as s:
            r3 = await s.send("third message")
        async with agent.session(resume=sid) as s:          # no cost_base: cost_usd = whole total
            r4 = await s.send("fourth message")
        return r1, r2, r3, r4
    r1, r2, r3, r4 = run(go())
    assert r2.total_cost_usd == pytest.approx(r1.total_cost_usd + r2.cost_usd)
    assert r3.total_cost_usd > r2.total_cost_usd                          # kept across resume
    assert r3.cost_usd == pytest.approx(r3.total_cost_usd - r2.total_cost_usd)
    assert r4.cost_usd == pytest.approx(r4.total_cost_usd)                # inexact without cost_base


# ----------------------------------------------------------------------------- AgentError.reply (6)

def test_failure_carries_partial_reply():
    fake.script("a", [[fake.say("Starting"), fake.call("run_sql", {"query": "q"}), fake.fail("gateway down")]])
    with pytest.raises(AgentError) as ei:
        Agent("a", engine="fake", tools=[run_sql]).ask_sync("go")
    r = ei.value.reply
    assert r is not None and r.status == "error" and r.error == "gateway down"
    assert r.text == "Starting" and r.tool_calls[0].result == "1200 rows"
    assert r.usage.output_tokens > 0 and r.cost_usd == 0.0


def test_session_info_after_first_turn():
    async def go():
        async with Agent("a", engine="fake", tools=[run_sql, "Read", "ask_user"]).session() as s:
            before = s.info
            await s.send("hi")
            return before, s.info
    before, after = run(go())
    assert before.tools == []
    assert after.tools == ["run_sql", "ask_user", "Read"] and after.mcp_servers == {"agentlib": "connected"}
