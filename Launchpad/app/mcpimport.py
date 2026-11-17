"""Import MCP servers into the MCP library from another tool's own setup. A list of sources; each finds candidates.

- SOURCES: id, name (shown on the button: "Import from <name>"), find(folders) -> candidates. A new source (Cursor:
  ~/.cursor/mcp.json and <folder>/.cursor/mcp.json) = one more function + one more row; nothing else changes
- A candidate: name, kind (command | url), config (Launchpad's shape, app/mcplib.py; secrets intact, never sent),
  scope (one word: local / project / user), where (file it came from). The page gets name, kind, summary (one line,
  masked) and exists (a server of that name is already in the library)
- Same name found twice: the first one wins, in the tool's own order of precedence
- Claude Code (checked against https://code.claude.com/docs/en/mcp, 2026-11-17; see docs/research/claude-code-mcp-config.md):
  local scope  = ~/.claude.json  projects["<absolute folder path>"].mcpServers  (keys use / on Windows too)
  project      = <folder>/.mcp.json  mcpServers
  user scope   = ~/.claude.json  mcpServers (top level)
  precedence local > project > user; with CLAUDE_CONFIG_DIR set, .claude.json lives in that folder.
  Entries: {type?: stdio, command, args, env} (a command without type = stdio) or {type: http | sse |
  streamable-http, url, headers}; other types (ws, managed, plugin, claude.ai connectors) are not imported.
  ${VAR} references are copied as they are (expanded when the server is tested or run)
- CLAUDE_HOME: where .claude.json is looked for (None = CLAUDE_CONFIG_DIR, else the home folder); the fake demo points
  it at a sample in its temp folder so it never reads the real home
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import mcplib

CLAUDE_HOME: Path | None = None


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _claude_files() -> list[Path]:
    if CLAUDE_HOME is not None:
        return [Path(CLAUDE_HOME) / ".claude.json"]
    out = []
    named = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if named:
        out.append(Path(os.path.expanduser(named)) / ".claude.json")
    out += [Path.home() / ".claude.json", Path.home() / ".claude" / ".claude.json"]
    return out


def from_claude_entry(entry) -> tuple[str, dict] | None:
    """A Claude Code mcpServers entry -> (kind, config) in Launchpad's shape, or None when it cannot be imported."""
    if not isinstance(entry, dict):
        return None
    typ = str(entry.get("type") or "").strip().lower()
    if entry.get("command") and typ in ("", "stdio"):
        args = entry.get("args") if isinstance(entry.get("args"), list) else []
        env = entry.get("env") if isinstance(entry.get("env"), dict) else {}
        return "command", {"command": str(entry["command"]), "args": [str(a) for a in args],
                           "env": {str(k): str(v) for k, v in env.items()}}
    if entry.get("url") and typ in ("http", "sse", "streamable-http", "streamable_http"):
        headers = entry.get("headers") if isinstance(entry.get("headers"), dict) else {}
        cfg = {"url": str(entry["url"]), "headers": {str(k): str(v) for k, v in headers.items()}}
        if typ == "sse":
            cfg["type"] = "sse"
        return "url", cfg
    return None


def _path_key(p) -> str:
    return os.path.normcase(os.path.normpath(str(p))).rstrip("\\/")


def claude_code(folders: list[Path]) -> list[dict]:
    """Candidates from Claude Code: each connected folder's local scope then its .mcp.json, then user scope."""
    found: list[dict] = []
    config_file = next((f for f in _claude_files() if f.is_file()), None)
    cfg = _read_json(config_file) if config_file else {}
    projects = cfg.get("projects") if isinstance(cfg.get("projects"), dict) else {}
    by_key = {_path_key(k): v for k, v in projects.items() if isinstance(v, dict)}

    def add(servers, scope: str, where: str) -> None:
        if not isinstance(servers, dict):
            return
        for name, entry in servers.items():
            conv = from_claude_entry(entry)
            if conv is None or any(c["name"] == str(name) for c in found):
                continue
            found.append({"name": str(name), "kind": conv[0], "config": conv[1], "scope": scope, "where": where})

    for folder in folders:
        folder = Path(folder)
        local = by_key.get(_path_key(folder.resolve())) or by_key.get(_path_key(folder)) or {}
        add(local.get("mcpServers"), "local", f"{folder.name} (local)")
        add(_read_json(folder / ".mcp.json").get("mcpServers"), "project", f"{folder.name}/.mcp.json")
    add(cfg.get("mcpServers"), "user", "user")
    return found


SOURCES: tuple[dict, ...] = (
    {"id": "claude_code", "name": "Claude Code", "find": claude_code},
)


def listing() -> list[dict]:
    """[{id, name}] for the page (mcp_library import_sources)."""
    return [{"id": s["id"], "name": s["name"]} for s in SOURCES]


def source(sid: str) -> dict:
    s = next((x for x in SOURCES if x["id"] == sid), None)
    if s is None:
        raise ValueError(f"unknown import source {sid!r}")
    return s


def candidates(sid: str, folders: list[Path]) -> list[dict]:
    return source(sid)["find"](list(folders))


def page_view(cands: list[dict], existing: set[str]) -> list[dict]:
    """What mcp_imports sends: name, kind, summary (masked, + where it came from), exists."""
    return [{"name": c["name"], "kind": c["kind"],
             "summary": f"{mcplib.summary(c['kind'], c['config'])} · {c['where']}",
             "scope": c["scope"], "exists": c["name"] in existing} for c in cands]
