"""09 - Testing your agent with the fake engine (pytest, zero tokens).

Run:  python -m pytest examples/09_test_with_fake_engine.py -q

Not collected by a plain `python -m pytest` in the agentlib repo (testpaths = agentlib), so pass the path.
In your own project, copy this into tests/test_<agent>.py.

How the fake engine works (agentlib/fake/engine.py):
- `from agentlib import fake` registers engine "fake". Build the agent with engine="fake".
- fake.script(agent_name, turns): one entry per turn; each is a list of steps or fn(message) -> steps.
  Steps: fake.say(text), fake.call(tool, args), fake.ask(questions), fake.rate_limit(), fake.fail(message).
- fake.call() runs YOUR real tool function through the same bookkeeping as the real engine, so tool errors,
  ends_turn and ask_user parking behave the same. Built-in names ("Bash") go through Claude-style permission
  rules ("Bash(ls:*)" approves `ls -la`, not `rm`), then on_permission, and return "(fake) ran <name>".
- No script for an agent -> it replies "(fake) <message>". fake.reset() clears scripts and sessions.
- fake.fail() raises AgentError; its .reply holds the partial turn (text, tool calls, usage so far).
- Limits: no external MCP servers (mcp_servers= raises CapabilityError), no real built-in tools,
  cost/usage are made-up small numbers.
"""
import asyncio

import pytest

from agentlib import Agent, AgentError, CapabilityError, EngineUnavailable, tool
from agentlib import fake


# --- the "agent under test" (in a real project this is imported from your code) --------------------------
@tool
def run_sql(query: str) -> str:
    """Run a read-only SQL query."""
    if "drop" in query.lower():
        raise ValueError("read-only")
    return "3 rows"


def make_agent(engine: str = "claude", **kw) -> Agent:
    # Let tests choose the engine; production code keeps the default.
    kw.setdefault("tools", [run_sql, "ask_user"])
    return Agent("analyst", instructions="Answer with SQL.", engine=engine, **kw)


# --- tests -----------------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_fake():
    fake.reset()                         # scripts and sessions are global; isolate each test
    yield
    fake.reset()


def test_tool_runs_and_reply_is_built():
    fake.script("analyst", [[fake.call("run_sql", {"query": "select 1"}), fake.say("There are 3 rows.")]])
    r = make_agent("fake").ask_sync("How many rows?")
    assert r.status == "done"
    assert r.text == "There are 3 rows."
    assert [(c.name, c.result, c.is_error) for c in r.tool_calls] == [("run_sql", "3 rows", False)]


def test_tool_exception_becomes_error_result():
    fake.script("analyst", [[fake.call("run_sql", {"query": "DROP TABLE x"}), fake.say("Not allowed.")]])
    r = make_agent("fake").ask_sync("Drop the table")
    assert r.tool_calls[0].is_error and "read-only" in r.tool_calls[0].result
    assert r.status == "done"            # the turn carried on


def test_ask_user_parks_and_answer_reaches_the_model():
    received = []
    fake.script("analyst", [
        [fake.ask([{"id": "table", "question": "Which table?", "why": "Not named.",
                    "options": ["sales", "orders"]}])],
        lambda msg: received.append(msg) or [fake.say("Using orders.")],
    ])

    async def go():
        async with make_agent("fake").session() as s:
            r1 = await s.send("Count rows")
            r2 = await s.answer({"table": "orders"})
            return r1, r2

    r1, r2 = asyncio.run(go())
    assert r1.status == "needs_input" and r1.questions[0].id == "table"
    assert "table: orders" in received[0]
    assert r2.text == "Using orders."


def test_message_based_script_and_event_stream():
    fake.script("analyst", [lambda msg: [fake.say(f"echo: {msg}")]])

    async def go():
        async with make_agent("fake").session() as s:
            return [ev.type async for ev in s.stream("hi")]

    types = asyncio.run(go())
    assert types[-1] == "done" and "text" in types and "text_delta" in types


def test_unlisted_builtin_is_denied_without_hook():
    fake.script("analyst", [[fake.call("Bash", {"command": "ls"})]])
    r = make_agent("fake").ask_sync("list files")
    assert r.tool_calls[0].is_error and "not allowed" in r.tool_calls[0].result


def test_listed_rule_approves_only_matching_commands():
    fake.script("analyst", [[fake.call("Bash", {"command": "ls -la"}), fake.call("Bash", {"command": "rm -rf /"})]])
    r = make_agent("fake", tools=[run_sql, "Bash(ls:*)"]).ask_sync("list files")
    assert [c.is_error for c in r.tool_calls] == [False, True]


def test_engine_failure_raises_agent_error():
    fake.script("analyst", [[fake.say("Checking"), fake.fail("gateway down")]])
    with pytest.raises(AgentError, match="gateway down") as ei:
        make_agent("fake").ask_sync("hi")
    assert ei.value.reply.text == "Checking"          # partial turn: text so far, usage, cost_usd 0


def test_capability_checks():
    # Engine.check() runs in agent.session() before anything starts.
    with pytest.raises(CapabilityError):              # the fake engine has no external MCP servers
        make_agent("fake", mcp_servers={"db": "db_server.py"}).session()
    with pytest.raises(EngineUnavailable):            # the cursor engine is a stub (available=False)
        make_agent("cursor").session()
