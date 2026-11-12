import asyncio
from typing import Literal

import pytest

from agentlib import AgentFileError, tool
from agentlib.tools import base_tool_name, resolve_tools, schema_from_signature


@tool
def run_sql(query: str, limit: int = 100) -> str:
    """Run a read-only SQL query."""
    return f"{query}|{limit}"


@tool(name="boom", ends_turn=True)
async def explode() -> str:
    raise RuntimeError("kaput")


def test_schema_from_type_hints():
    def f(a: str, b: int, c: float = 1.0, d: bool = False, e: list[str] | None = None,
          mode: Literal["x", "y"] = "x"):
        pass
    s = schema_from_signature(f)
    assert s["required"] == ["a", "b"]
    assert s["properties"]["e"] == {"type": "array", "items": {"type": "string"}}
    assert s["properties"]["mode"] == {"enum": ["x", "y"]}
    assert s["properties"]["d"] == {"type": "boolean"}


def test_tool_decorator_and_call():
    assert run_sql.name == "run_sql" and run_sql.description == "Run a read-only SQL query."
    assert asyncio.run(run_sql.call({"query": "q"})) == ("q|100", False)


def test_tool_error_becomes_result():
    text, err = asyncio.run(explode.call({}))
    assert err and "kaput" in text
    assert explode.ends_turn


def test_resolve_mixed_list():
    r = resolve_tools(["Read", "Bash(npm run build:*)", "run_sql", "mcp__agentlib__ask_user", "mcp__db__q"],
                      [run_sql])
    assert [t.name for t in r.custom] == ["run_sql", "ask_user"]
    assert r.builtin_rules == ["Read", "Bash(npm run build:*)"]
    assert r.builtin_names == ["Read", "Bash"]
    assert r.mcp_rules == ["mcp__db__q"]


def test_resolve_unspecified():
    lean = resolve_tools(None, [run_sql], setup="lean")
    assert {t.name for t in lean.custom} == {"run_sql", "ask_user"} and not lean.all_builtins
    assert resolve_tools(None, [], setup="project").all_builtins
    assert [t.name for t in resolve_tools(None, [run_sql], include_ask_user=False).custom] == ["run_sql"]


def test_missing_function_is_an_error():
    with pytest.raises(AgentFileError):
        resolve_tools(["run_sql"], [])


def test_base_tool_name():
    assert base_tool_name("Bash(npm run build:*)") == "Bash"
