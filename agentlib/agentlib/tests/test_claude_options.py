"""Claude engine option building and message mapping (no process started, no tokens)."""
import asyncio
from pathlib import Path

import pytest

from agentlib import Agent, AgentError, tool
from agentlib.engines import TurnState
from agentlib.engines import claude as ce          # SDK types via the engine module (no direct SDK import)
from agentlib.engines.claude import ClaudeSession


@tool
def run_sql(query: str) -> str:
    """Run SQL."""
    return query


def _opts(agent, resume=None):
    return ClaudeSession(agent, resume=resume, fork=False, cost_base=0).options(resume=resume)


def test_lean_options():
    o = _opts(Agent("a", instructions="Be brief.", tools=["Read", "Bash(npm run build:*)", run_sql, "ask_user"]))
    assert o.setting_sources == [] and o.strict_mcp_config is True
    assert o.tools == ["Read", "Bash"]
    assert set(o.allowed_tools) == {"Read", "Bash(npm run build:*)", "mcp__agentlib__run_sql",
                                    "mcp__agentlib__ask_user"}
    assert set(o.mcp_servers) == {"agentlib"}
    assert o.system_prompt == "Be brief."
    assert o.env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"
    assert "PostToolUse" in o.hooks                      # ask_user ends the turn
    assert "disable-slash-commands" in o.extra_args
    assert o.session_id and not o.resume


def test_lean_no_tools_means_no_builtins():
    o = _opts(Agent("a", include_ask_user=False))
    assert o.tools == [] and o.allowed_tools == [] and not o.mcp_servers


def test_project_options():
    o = _opts(Agent("a", instructions="Extra rule.", setup="project", cwd="."))
    assert o.setting_sources == ["user", "project", "local"]
    assert o.tools == {"type": "preset", "preset": "claude_code"}
    assert o.system_prompt == {"type": "preset", "preset": "claude_code", "append": "Extra rule."}


def test_long_prompt_goes_to_file():
    s = ClaudeSession(Agent("a", instructions="x" * 40_000), resume=None, fork=False, cost_base=0)
    sp = s.options(resume=None).system_prompt
    assert sp["type"] == "file" and Path(sp["path"]).read_text(encoding="utf-8") == "x" * 40_000
    Path(sp["path"]).unlink()


def test_lean_skills_add_read_with_guard(tmp_path):
    skill = tmp_path / ".claude/skills/memo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: memo\ndescription: Writes memos\n---\nSteps", encoding="utf-8")
    o = _opts(Agent("a", cwd=tmp_path, skills=["memo"], include_ask_user=False))
    assert o.tools == ["Read"] and "Read" not in o.allowed_tools
    assert "PreToolUse" in o.hooks and str(skill.resolve()) in o.add_dirs
    assert "memo: Writes memos" in o.system_prompt


class _StubClient:
    """Stands in for ClaudeSDKClient: one assistant message (text + usage), then the process 'dies'."""

    def __init__(self, messages, exc):
        self.messages, self.exc = messages, exc

    async def query(self, message):
        return None

    async def receive_response(self):
        for m in self.messages:
            yield m
        raise self.exc

    async def disconnect(self):
        return None

    async def interrupt(self):
        return None


def _assistant(text, mid, usage):
    return ce.AssistantMessage(content=[ce.TextBlock(text)], model="claude-haiku", message_id=mid, usage=usage)


def test_failed_turn_attaches_partial_reply():
    s = ClaudeSession(Agent("a", include_ask_user=False), resume=None, fork=False, cost_base=0.25)
    u1 = {"input_tokens": 10, "output_tokens": 2}
    u1b = {"input_tokens": 10, "output_tokens": 7, "cache_read_input_tokens": 100}   # same message, later block
    s._client = _StubClient([_assistant("Working", "m1", u1), _assistant("on it", "m1", u1b),
                             _assistant("more", "m2", {"input_tokens": 1, "output_tokens": 1})],
                            RuntimeError("process exited 1"))

    async def go():
        q = asyncio.Queue()
        with pytest.raises(AgentError) as ei:
            await s._turn("hi", q)
        return ei.value
    err = asyncio.run(go())
    r = err.reply
    assert "process exited" in err.short and r is not None and r.status == "error"
    assert r.text == "Working\n\non it\n\nmore" and r.api_calls == 2
    assert (r.usage.input_tokens, r.usage.output_tokens, r.usage.cache_read_tokens) == (11, 8, 100)
    assert r.cost_usd == 0.0 and r.total_cost_usd == 0.25


def test_session_info_from_init_message():
    s = ClaudeSession(Agent("a", tools=[run_sql, "Read"]), resume=None, fork=False, cost_base=0)
    assert s.info.tools == []
    init = ce.SystemMessage(subtype="init", data={
        "tools": ["Read", "mcp__agentlib__run_sql", "mcp__agentlib__ask_user"], "model": "claude-haiku",
        "mcp_servers": [{"name": "agentlib", "status": "connected"}], "session_id": "sid-1"})
    s._map(init, TurnState("claude", []))
    assert s.info.tools == ["Read", "run_sql", "ask_user"]
    assert s.info.mcp_servers == {"agentlib": "connected"} and s.info.model == "claude-haiku"
    assert s.session_id == "sid-1"


def test_resume_and_external_mcp():
    o = _opts(Agent("a", mcp_servers={"db": "servers/db.py"}, include_ask_user=False), resume="abc")
    assert o.resume == "abc" and "mcp__db__*" in o.allowed_tools
    assert o.mcp_servers["db"]["args"][0].endswith("db.py")
