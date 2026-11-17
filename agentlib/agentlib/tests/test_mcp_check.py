"""check_mcp_server: start a real (tiny, local) MCP server, list its tools, stop it. Zero tokens: no model involved."""
import sys

import pytest

from agentlib.mcp_check import McpCheck, check_mcp_server_sync

SERVER = '''
import os, sys
try:
    from mcp.server.mcpserver import MCPServer as Server      # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server          # mcp 1.x
server = Server("tiny")

@server.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return text

@server.tool()
def secret_seen() -> str:
    """Says whether the env value arrived."""
    return os.environ.get("TINY_TOKEN", "")

if __name__ == "__main__":
    if os.environ.get("TINY_FAIL"):
        sys.stderr.write("cannot start: bad token " + os.environ.get("TINY_TOKEN", "") + "\\n")
        sys.exit(2)
    server.run()
'''


@pytest.fixture
def server_file(tmp_path):
    p = tmp_path / "tiny_server.py"
    p.write_text(SERVER, encoding="utf-8")
    return p


def test_stdio_server_lists_its_tools(server_file):
    r = check_mcp_server_sync({"command": sys.executable, "args": [str(server_file)], "env": {"TINY_TOKEN": "abc123"}})
    assert isinstance(r, McpCheck) and r.ok and r.error is None and r.kind == "stdio"
    assert sorted(t.name for t in r.tools) == ["echo", "secret_seen"] and r.tool_count == 2
    assert next(t for t in r.tools if t.name == "echo").description == "Echo the text back."
    assert r.server_name == "tiny"
    d = r.to_dict()
    assert d["tool_count"] == 2 and d["tools"][0]["name"]


def test_path_config_runs_with_this_python(server_file):
    r = check_mcp_server_sync(server_file.name, cwd=server_file.parent)     # relative path + cwd, like Agent.mcp_servers
    assert r.ok and r.tool_count == 2


def test_program_not_found():
    r = check_mcp_server_sync({"command": "no-such-program-for-agentlib-tests", "args": []})
    assert not r.ok and r.tools == [] and "program not found" in r.error


def test_server_that_exits_hides_secret_values(server_file):
    r = check_mcp_server_sync({"type": "stdio", "command": sys.executable, "args": [str(server_file)],
                               "env": {"TINY_FAIL": "1", "TINY_TOKEN": "s3cr3t-value"}})
    assert not r.ok and r.error
    assert "s3cr3t-value" not in r.error and "s3cr3t-value" not in r.stderr_tail
    assert "cannot start" in r.stderr_tail and "***" in r.stderr_tail


def test_timeout():
    r = check_mcp_server_sync({"command": sys.executable, "args": ["-c", "import time; time.sleep(30)"]}, timeout_s=1)
    assert not r.ok and "no answer within 1 seconds" in r.error


def test_url_server_that_is_not_there():
    r = check_mcp_server_sync({"type": "http", "url": "http://127.0.0.1:9/mcp",
                               "headers": {"Authorization": "Bearer t0k3n-value"}}, timeout_s=10)
    assert not r.ok and r.kind == "http" and r.error and "t0k3n-value" not in r.error


@pytest.mark.parametrize("cfg, words", [
    ({"type": "ws", "url": "ws://x"}, "cannot test type 'ws'"),
    ({}, "neither command nor url"),
    ({"type": "stdio", "command": " "}, "no command"),
    ({"type": "http", "url": ""}, "no url"),
    (42, "must be a dict"),
])
def test_configs_it_cannot_test(cfg, words):
    r = check_mcp_server_sync(cfg)
    assert not r.ok and words in r.error
