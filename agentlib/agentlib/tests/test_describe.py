import json

from agentlib import Agent, fake, load_claude_agent, tool

KEYS = {"name", "description", "model", "engine", "source_path", "instructions", "builtin_tools",
        "custom_tools", "mcp_servers", "disallowed_tools", "skills", "warnings"}


@tool(read_only=True)
def run_sql(query: str) -> str:
    """Run a read-only SQL query."""
    return "3 rows"


def test_describe_built_in_code():
    a = Agent("analyst", instructions="Answer with SQL.", description="SQL helper", model="haiku",
              tools=[run_sql, "Read", "Bash(git status:*)", "ask_user", "mcp__db__query"],
              mcp_servers={
                  "db": {"type": "stdio", "command": "db-server", "args": ["--port=1", "--token=hunter2"],
                         "env": {"DB_PASSWORD": "hunter2"}},
                  "web": {"type": "http", "url": "https://u:pw@example.com/mcp?key=hunter2",
                          "headers": {"Authorization": "Bearer hunter2"}},
                  "local": "servers/notes.py"},
              disallowed_tools=["WebFetch"], skills=["sql-style"], engine="fake")
    d = a.describe()
    assert set(d) == KEYS
    assert d["name"] == "analyst" and d["description"] == "SQL helper" and d["model"] == "haiku"
    assert d["engine"] == "fake" and d["source_path"] is None and d["instructions"] == "Answer with SQL."
    assert d["builtin_tools"] == ["Read", "Bash(git status:*)", "mcp__db__query"]
    by_name = {t["name"]: t for t in d["custom_tools"]}
    assert by_name["run_sql"] == {"name": "run_sql", "description": "Run a read-only SQL query.",
                                  "read_only": True, "ends_turn": False}
    assert by_name["ask_user"]["ends_turn"] is True
    servers = {s["name"]: s["config"] for s in d["mcp_servers"]}
    assert servers["local"] == {"type": "stdio", "path": "servers/notes.py"}
    assert servers["db"]["command"] == "db-server" and servers["db"]["env"] == {"DB_PASSWORD": "***"}
    assert servers["db"]["args"] == ["--port=1", "--token=***"]
    assert servers["web"]["headers"] == {"Authorization": "***"}
    assert "hunter2" not in json.dumps(d) and "u:pw" not in json.dumps(d)
    assert d["disallowed_tools"] == ["WebFetch"] and d["skills"] == ["sql-style"] and d["warnings"] == []
    json.dumps(d)


def test_describe_works_on_claude_engine_and_starts_nothing():
    d = Agent("x", instructions="hi", tools=["Read"]).describe()     # default engine = claude, no process
    assert d["engine"] == "claude" and d["builtin_tools"] == ["Read"] and d["model"] is None


def test_describe_unspecified_tools_and_unresolvable_tools():
    d = Agent("p", setup="project").describe()
    assert d["builtin_tools"] == [] and any("every built-in" in w for w in d["warnings"])
    bad = Agent("b", tools=["run_sql"]).describe()          # name listed, no function: reported, not raised
    assert any("could not be resolved" in w for w in bad["warnings"])


def test_describe_from_agent_file(tmp_path):
    p = tmp_path / ".claude" / "agents" / "trend.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nname: trend_reporter\ndescription: Builds trend reports\n"
                 "tools: Read, run_sql\nmodel: sonnet\n---\nYou build trend reports. Follow docs/format.md.\n",
                 encoding="utf-8")
    a = load_claude_agent("trend", project=tmp_path, tools=[run_sql], engine="fake")
    d = a.describe()
    assert set(d) == KEYS
    assert d["name"] == "trend_reporter" and d["description"] == "Builds trend reports"
    assert d["model"] == "sonnet" and d["engine"] == "fake"
    assert d["source_path"] == str(a.source) and d["source_path"].endswith("trend.md")
    assert d["instructions"].startswith("You build trend reports.")
    assert d["builtin_tools"] == ["Read"] and [t["name"] for t in d["custom_tools"]] == ["run_sql"]
    assert d["warnings"] == a.warnings
    json.dumps(d)
    fake.reset()
