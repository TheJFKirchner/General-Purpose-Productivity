"""Test an external MCP server without any agent or model: start it (or connect to it), list its tools, stop it.
Engine-neutral and free (no tokens: nothing is sent to a model). For settings screens with a "Test" button next to
an MCP server, and for checking a server before handing it to an Agent.

- await check_mcp_server(config, *, timeout_s=30, cwd=None) -> McpCheck
- check_mcp_server_sync(config, **kw) -> McpCheck   (asyncio.run; not inside a running event loop)
- config: the same shapes as an Agent.mcp_servers value
    {"command": "npx", "args": [...], "env": {...}}            stdio (type "stdio", or no type with a command)
    {"type": "http", "url": "https://...", "headers": {...}}    streamable HTTP ("streamable-http" is an alias)
    {"type": "sse", "url": "https://...", "headers": {...}}     server-sent events (older servers)
    "path/to/server.py"                                         run with this Python (relative to cwd)
  stdio servers get this process's environment plus `env` (like the engine would start them); a config `cwd`
  (stdio) or the `cwd` argument sets their working folder
- Never raises for a server that fails: McpCheck.ok is False and .error says why in one line (env / header values
  are blanked out of it); the end of the server's own error output is in .stderr_tail
- Uses the `mcp` package (the MCP protocol library, installed with the Claude Agent SDK); works with mcp 1.x and 2.x
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HTTP_TYPES = ("http", "streamable-http", "streamable_http")
MAX_PAGES = 20               # tools/list pages read at most
STDERR_TAIL = 400            # characters of the server's own error output kept


@dataclass
class McpTool:
    name: str
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class McpCheck:
    ok: bool                              # started, answered the handshake and listed its tools
    kind: str                             # "stdio" | "http" | "sse" | "" (config not understood)
    tools: list[McpTool] = field(default_factory=list)
    error: str | None = None              # one line, no secret values
    duration_s: float = 0.0
    server_name: str | None = None        # what the server calls itself (handshake), if it said
    server_version: str | None = None
    stderr_tail: str = ""                 # end of a stdio server's error output (secrets blanked)

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tool_count"] = self.tool_count
        return d


def _kind(cfg: dict) -> str:
    t = str(cfg.get("type") or "").strip().lower()
    if not t:
        return "stdio" if cfg.get("command") else ("http" if cfg.get("url") else "")
    if t in HTTP_TYPES:
        return "http"
    return t


def _normalise(config: dict | str, cwd: str | Path | None) -> dict:
    if isinstance(config, (str, Path)):
        p = Path(config)
        if not p.is_absolute() and cwd:
            p = Path(cwd) / p
        return {"type": "stdio", "command": sys.executable, "args": [str(p)]}
    if not isinstance(config, dict):
        raise ValueError("an MCP server config must be a dict or a path to a .py server")
    return dict(config)


def _secrets(cfg: dict) -> list[str]:
    vals = [str(v) for k in ("env", "headers") for v in (cfg.get(k) or {}).values() if v is not None]
    return sorted({v for v in vals if len(v) >= 4}, key=len, reverse=True)


def _blank(text: str, secrets: list[str]) -> str:
    for s in secrets:
        text = text.replace(s, "***")
    return text


def _leaf(e: BaseException) -> BaseException:
    """The first real error inside (nested) exception groups."""
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return e


def _message(e: BaseException, cfg: dict, kind: str, timeout_s: float | None) -> str:
    e = _leaf(e)
    if isinstance(e, (TimeoutError, asyncio.TimeoutError)):
        return f"no answer within {timeout_s:g} seconds"
    if isinstance(e, FileNotFoundError) and kind == "stdio":
        return f"could not start '{cfg.get('command')}': program not found"
    if isinstance(e, PermissionError) and kind == "stdio":
        return f"could not start '{cfg.get('command')}': permission denied"
    text = " ".join(str(e).split()) or type(e).__name__
    name = type(e).__name__
    if (name in ("ClosedResourceError", "EndOfStream", "BrokenResourceError", "BrokenPipeError")
            or text.lower() == "connection closed"):
        text = "the server closed the connection before answering"
    elif name in ("ConnectError", "ConnectTimeout", "ConnectionRefusedError"):
        text = f"could not connect to the server ({text})"
    elif name not in text and not text.lower().startswith(("could not", "connection", "the server")):
        text = f"{name}: {text}"
    return text[:300]


async def _list_tools(session) -> list[McpTool]:
    out: list[McpTool] = []
    cursor = None
    for _ in range(MAX_PAGES):
        if cursor is None:
            res = await session.list_tools()
        else:
            try:                                        # mcp 2.x
                from mcp.types import PaginatedRequestParams
                res = await session.list_tools(params=PaginatedRequestParams(cursor=cursor))
            except TypeError:                           # mcp 1.x
                res = await session.list_tools(cursor=cursor)
        out += [McpTool(str(t.name), " ".join(str(getattr(t, "description", "") or "").split()))
                for t in res.tools]
        cursor = getattr(res, "next_cursor", None) or getattr(res, "nextCursor", None)
        if not cursor:
            break
    return out


async def _talk(cfg: dict, kind: str, cwd, errlog) -> tuple[list[McpTool], Any]:
    from mcp import ClientSession
    async with contextlib.AsyncExitStack() as stack:
        if kind == "stdio":
            from mcp.client.stdio import StdioServerParameters, stdio_client
            env = {**os.environ, **{str(k): str(v) for k, v in (cfg.get("env") or {}).items()}}
            params = StdioServerParameters(command=str(cfg["command"]), args=[str(a) for a in cfg.get("args") or []],
                                           env=env, cwd=cfg.get("cwd") or (str(cwd) if cwd else None))
            streams = await stack.enter_async_context(stdio_client(params, errlog=errlog))
        elif kind == "http":
            from mcp.client import streamable_http as sh
            headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()}
            if hasattr(sh, "streamable_http_client"):   # mcp 2.x: headers ride on the HTTP client
                client = await stack.enter_async_context(sh.create_mcp_http_client(headers=headers or None))
                streams = await stack.enter_async_context(sh.streamable_http_client(str(cfg["url"]), http_client=client))
            else:                                       # mcp 1.x
                streams = await stack.enter_async_context(sh.streamablehttp_client(str(cfg["url"]), headers=headers or None))
        else:
            from mcp.client.sse import sse_client
            headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()}
            streams = await stack.enter_async_context(sse_client(str(cfg["url"]), headers=headers or None))
        read, write = streams[0], streams[1]
        session = await stack.enter_async_context(ClientSession(read, write))
        init = await session.initialize()
        tools = await _list_tools(session)
        return tools, init


async def check_mcp_server(config: dict | str, *, timeout_s: float | None = 30,
                           cwd: str | Path | None = None) -> McpCheck:
    """Start / connect to one MCP server, list its tools, stop it. Free; never raises for a failing server."""
    t0 = time.monotonic()
    try:
        cfg = _normalise(config, cwd)
    except ValueError as e:
        return McpCheck(ok=False, kind="", error=str(e))
    kind = _kind(cfg)
    if kind not in ("stdio", "http", "sse"):
        what = f"type '{cfg.get('type')}'" if cfg.get("type") else "a config with neither command nor url"
        return McpCheck(ok=False, kind=kind, error=f"cannot test {what} (stdio, http and sse servers can be tested)")
    if kind == "stdio" and not str(cfg.get("command") or "").strip():
        return McpCheck(ok=False, kind=kind, error="no command given")
    if kind != "stdio" and not str(cfg.get("url") or "").strip():
        return McpCheck(ok=False, kind=kind, error="no url given")
    try:
        import mcp  # noqa: F401
    except ImportError:
        return McpCheck(ok=False, kind=kind, error="the Python package 'mcp' is not installed (pip install mcp)")
    secrets = _secrets(cfg)
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as errlog:
        try:
            import anyio
            with anyio.fail_after(timeout_s) if timeout_s else contextlib.nullcontext():
                tools, init = await _talk(cfg, kind, cwd, errlog)
            error = None
        except Exception as e:  # noqa: BLE001 -- any failure is the result, never raised
            tools, init, error = [], None, _blank(_message(e, cfg, kind, timeout_s), secrets)
        tail = ""
        with contextlib.suppress(Exception):
            errlog.flush()
            errlog.seek(0)
            tail = _blank(errlog.read()[-STDERR_TAIL:].strip(), secrets)
    info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
    return McpCheck(ok=error is None, kind=kind, tools=tools, error=error, duration_s=round(time.monotonic() - t0, 2),
                    server_name=getattr(info, "name", None), server_version=getattr(info, "version", None),
                    stderr_tail=tail if error else "")


def check_mcp_server_sync(config: dict | str, **kw) -> McpCheck:
    """check_mcp_server() for code with no running event loop (uses asyncio.run)."""
    return asyncio.run(check_mcp_server(config, **kw))
