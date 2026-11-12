from pathlib import Path

import pytest

from agentlib import AgentFileError, load_claude_agent, load_cursor_agent, tool
from agentlib.skills import find_skill, index_text


@tool
def run_sql(query: str) -> str:
    """Run SQL."""
    return query


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_claude_agent_file(tmp_path):
    _write(tmp_path / ".claude/agents/trend.md", """---
name: trend_reporter
description: Builds trend reports
tools: Read, Grep, run_sql, ask_user
model: sonnet
color: blue
---
You build trend reports. Follow docs/format.md.
""")
    a = load_claude_agent("trend", project=tmp_path, tools=[run_sql])
    assert a.name == "trend_reporter" and a.model == "sonnet" and a.engine == "claude" and a.setup == "lean"
    assert a.cwd == tmp_path.resolve()
    assert a.extra == {"color": "blue"}
    r = a.resolved_tools()
    assert r.builtin_names == ["Read", "Grep"] and [t.name for t in r.custom] == ["run_sql", "ask_user"]
    assert a.warnings == []


def test_claude_agent_inherit_and_overrides(tmp_path):
    p = _write(tmp_path / "x.md", "---\nname: x\nmodel: inherit\n---\nHi")
    a = load_claude_agent(p, model="haiku", setup="project", max_turns=3)
    assert a.model == "haiku" and a.setup == "project" and a.max_turns == 3
    assert a.resolved_tools().all_builtins


def test_claude_agent_missing_tool_function(tmp_path):
    p = _write(tmp_path / "x.md", "---\nname: x\ntools: run_sql\n---\nHi")
    with pytest.raises(AgentFileError):
        load_claude_agent(p)


def test_reference_warning_without_read(tmp_path):
    p = _write(tmp_path / "x.md", "---\nname: x\ntools: ask_user\n---\nUse docs/plan-format.md")
    assert "docs/plan-format.md" in load_claude_agent(p).warnings[0]


def test_cursor_agent_file(tmp_path):
    _write(tmp_path / ".cursor/agents/rev.md", """---
name: reviewer
description: Reviews code
model: gpt-5
readonly: true
is_background: false
---
Review the diff.
""")
    a = load_cursor_agent("rev", project=tmp_path)
    assert a.engine == "claude" and a.model is None
    assert "no Claude equivalent" in a.warnings[0]
    r = a.resolved_tools()
    assert r.builtin_names == ["Read", "Grep", "Glob"] and [t.name for t in r.custom] == ["ask_user"]
    assert a.extra == {"is_background": False}


def test_cursor_agent_no_ask_user(tmp_path):
    p = _write(tmp_path / ".cursor/agents/w.md", "---\nname: w\nmodel: claude-4.5-sonnet\n---\nWork.")
    a = load_cursor_agent(p, ask_user=False, tools=[run_sql])
    assert a.model == "sonnet"
    assert [t.name for t in a.resolved_tools().custom] == ["run_sql"]


def test_agent_not_found(tmp_path):
    with pytest.raises(AgentFileError):
        load_claude_agent("nope", project=tmp_path)


def test_find_skill(tmp_path):
    _write(tmp_path / ".claude/skills/memo/SKILL.md", "---\nname: memo\ndescription: Writes memos\n---\nSteps")
    s = find_skill("memo", tmp_path)
    assert s.description == "Writes memos" and s.file.is_file()
    assert "memo: Writes memos" in index_text([s])
    with pytest.raises(AgentFileError):
        find_skill("missing", tmp_path)
