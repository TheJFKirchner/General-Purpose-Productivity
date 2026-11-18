"""The MCP library: the user's MCP servers, their last test result, and which agent gets which server.

- File: <home>/.launchpad/mcp.json, beside settings.json (McpLibrary.beside(store); never in a project, never in
  git); path None = in memory only (a Hub without a user file, most tests). Under --fake the store lives in the
  demo's temp home. Writes: lock file mcp.json.lock, re-read, change, temp file + os.replace (like app/tally.py)
- A server: name (letters, digits, - and _; "agentlib" is taken by Launchpad's own tools), kind command | url,
  config {command, args[], env{}} | {url, headers{}, type?: "http" | "sse"}, status connected | failed | untested
  (+ testing while a test runs, kept in memory only), detail, tool_count, tools (names), tested_at, passed (the last
  FINISHED test passed: what a run uses, also while a re-test is going)
- Secrets: env and header values, secret-looking `--flag=value` / `--flag value` args and URL credentials / query
  strings are MASK in everything sent to the page (a value that is only a ${VAR} reference is shown as is). A save
  that sends MASK back for a value keeps the stored secret (env / headers per key; args / url when the masked form is
  unchanged); a MASK with nothing stored behind it is refused
- Assignments: agent name (crew_list `name`, e.g. launchpad-builder, copy-reviewer) -> [server names]. Nothing by
  default for any agent. Deleting a server removes it from every agent; a rename follows into the assignments
- for_agent(name): what a run gets = assigned servers whose last finished test passed, as agentlib mcp_servers
  configs with ${VAR} / ${VAR:-default} expanded from the environment (like Claude Code does in .mcp.json); every
  other assigned server is skipped with a plain warning (the run goes ahead without it)
- Testing: agentlib.mcp_check (start, list tools, stop; zero tokens), run in a worker thread with its own event loop
  (TESTER; tests replace it)
"""
from __future__ import annotations

import asyncio
import contextlib
import copy
import datetime as dt
import json
import os
import re
import tempfile
import time
from pathlib import Path

FILE_NAME = "mcp.json"
MASK = "********"
KINDS = ("command", "url")
STATUSES = ("connected", "failed", "untested", "testing")
URL_TYPES = ("http", "sse")
RESERVED = {"agentlib"}             # agentlib's DEFAULT_SERVER: Launchpad's own tools are served under this name
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
TEST_TIMEOUT_S = 30.0
LOCK_WAIT_S = 5.0
LOCK_STALE_S = 30.0
_SECRET_FLAG = re.compile(r"^(--?[\w-]*(?:token|secret|password|passwd|key|auth|credential|bearer)[\w-]*)(=)(.+)$",
                          re.I | re.S)
_SECRET_NAME = re.compile(r"token|secret|password|passwd|key|auth|credential|bearer|sig", re.I)
_REF_ONLY = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*(:-[^}]*)?\}$")
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _empty() -> dict:
    return {"version": 1, "servers": [], "assignments": {}}


# --------------------------------------------------------------------------- masking
def _mask_value(v) -> str:
    s = "" if v is None else str(v)
    return s if (not s or _REF_ONLY.match(s)) else MASK


def _mask_args(args: list) -> list:
    out, hide_next = [], False
    for a in args or []:
        a = str(a)
        if hide_next and not a.startswith("-"):
            out.append(_mask_value(a))
            hide_next = False
            continue
        hide_next = False
        m = _SECRET_FLAG.match(a)
        if m:
            out.append(m.group(1) + "=" + _mask_value(m.group(3)))
        else:
            out.append(a)
            hide_next = a.startswith("-") and "=" not in a and bool(_SECRET_NAME.search(a))
    return out


def _mask_url(url: str) -> str:
    u = str(url or "")
    u = re.sub(r"^([a-z][a-z0-9+.-]*://)[^/@]+@", lambda m: m.group(1) + MASK + "@", u, flags=re.I)
    if "?" in u:
        base, query = u.split("?", 1)
        parts = []
        for p in query.split("&"):
            k, eq, v = p.partition("=")
            parts.append(f"{k}={_mask_value(v)}" if eq and _SECRET_NAME.search(k) else p)
        u = base + "?" + "&".join(parts)
    return u


def mask_config(kind: str, cfg: dict) -> dict:
    """The config as the page sees it: secret values replaced by MASK."""
    if kind == "command":
        return {"command": cfg.get("command", ""), "args": _mask_args(cfg.get("args") or []),
                "env": {k: _mask_value(v) for k, v in (cfg.get("env") or {}).items()}}
    out = {"url": _mask_url(cfg.get("url", "")),
           "headers": {k: _mask_value(v) for k, v in (cfg.get("headers") or {}).items()}}
    if cfg.get("type") == "sse":
        out["type"] = "sse"
    return out


def _unmask_map(new: dict, old: dict, what: str) -> dict:
    out = {}
    for k, v in new.items():
        if str(v) == MASK or MASK in str(v):
            if k not in old:
                raise ValueError(f"{what} {k} shows a hidden value but none is stored; type the value again")
            out[k] = old[k]
        else:
            out[k] = v
    return out


def _unmask_args(new: list, old: list) -> list:
    masked_old = _mask_args(old)
    out = []
    for i, a in enumerate(new):
        if MASK in a:
            if a in masked_old:                     # the same masked arg as before (same place preferred)
                j = i if i < len(masked_old) and masked_old[i] == a else masked_old.index(a)
                out.append(str(old[j]))
                continue
            raise ValueError(f"argument {a!r} shows a hidden value that is not stored; type it again")
        out.append(a)
    return out


# --------------------------------------------------------------------------- validation, run-time config
def _str_map(value, what: str) -> dict:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be name: value pairs")
    out = {}
    for k, v in value.items():
        k = str(k).strip()
        if not k:
            raise ValueError(f"{what}: a name is empty")
        out[k] = "" if v is None else str(v)
    return out


def clean_server(server: dict, old: dict | None) -> dict:
    """A server from the page (or an import) -> {name, kind, config} with masked values put back from `old`.
    ValueError with a plain message when it cannot be saved."""
    if not isinstance(server, dict):
        raise ValueError("send the server as an object")
    name = str(server.get("name") or "").strip()
    if not NAME.match(name):
        raise ValueError("a server name uses letters, digits, - and _ only (up to 64), starting with a letter or digit")
    if name.lower() in RESERVED:
        raise ValueError(f"'{name}' is taken by Launchpad's own tools; choose another name")
    cfg_in = server.get("config") if isinstance(server.get("config"), dict) else {}
    kind = str(server.get("kind") or ("url" if cfg_in.get("url") else "command")).strip()
    if kind not in KINDS:
        raise ValueError("kind must be command or url")
    old_cfg = (old or {}).get("config") or {} if (old or {}).get("kind") == kind else {}
    if kind == "command":
        command = str(cfg_in.get("command") or "").strip()
        if not command:
            raise ValueError("give the command that starts the server")
        args = cfg_in.get("args") or []
        if isinstance(args, str):
            args = args.split()
        if not isinstance(args, list):
            raise ValueError("arguments must be a list")
        args = [str(a) for a in args if str(a) != ""]
        env = _str_map(cfg_in.get("env"), "environment variables")
        args = _unmask_args(args, [str(a) for a in old_cfg.get("args") or []])
        env = _unmask_map(env, old_cfg.get("env") or {}, "environment variable")
        return {"name": name, "kind": kind, "config": {"command": command, "args": args, "env": env}}
    url = str(cfg_in.get("url") or "").strip()
    if MASK in url:
        if not old_cfg.get("url") or _mask_url(old_cfg["url"]) != url:
            raise ValueError("the URL shows a hidden value that is not stored; type the full URL again")
        url = old_cfg["url"]
    if not re.match(r"^https?://[^\s/]+", url, re.I):
        raise ValueError("give the server's URL (http:// or https://)")
    headers = _unmask_map(_str_map(cfg_in.get("headers"), "headers"), old_cfg.get("headers") or {}, "header")
    typ = str(cfg_in.get("type") or "").strip().lower()
    if typ in ("streamable-http", "streamable_http"):
        typ = "http"
    if typ not in URL_TYPES:            # the page's form has no type: keep the stored one, else guess from the path
        typ = old_cfg.get("type") or ("sse" if url.split("?", 1)[0].rstrip("/").endswith("/sse") else "http")
    cfg = {"url": url, "headers": headers}
    if typ == "sse":
        cfg["type"] = "sse"
    return {"name": name, "kind": kind, "config": cfg}


def _expand(value: str) -> str:
    return _REF.sub(lambda m: os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else m.group(0)),
                    str(value))


def agent_config(server: dict) -> dict:
    """A stored server -> an agentlib mcp_servers config (also what the test starts), ${VAR} expanded."""
    cfg = server.get("config") or {}
    if server.get("kind") == "command":
        return {"type": "stdio", "command": _expand(cfg.get("command", "")),
                "args": [_expand(a) for a in cfg.get("args") or []],
                "env": {k: _expand(v) for k, v in (cfg.get("env") or {}).items()}}
    return {"type": cfg.get("type") or "http", "url": _expand(cfg.get("url", "")),
            "headers": {k: _expand(v) for k, v in (cfg.get("headers") or {}).items()}}


def summary(kind: str, cfg: dict) -> str:
    """One line for import lists: the command and its arguments (masked), or the URL (masked)."""
    if kind == "command":
        return " ".join([str(cfg.get("command") or "")] + _mask_args(cfg.get("args") or [])).strip()
    t = "SSE " if cfg.get("type") == "sse" else ""
    return f"{t}{_mask_url(cfg.get('url') or '')}"


async def run_check(config: dict) -> dict:
    """Default TESTER: agentlib's MCP check in a worker thread (its own event loop) -> {ok, error, tools}."""
    from agentlib.mcp_check import check_mcp_server_sync
    r = await asyncio.to_thread(check_mcp_server_sync, config, timeout_s=TEST_TIMEOUT_S)
    detail = r.error or ""
    if r.error and r.stderr_tail:
        detail += " | server said: " + " ".join(r.stderr_tail.split())[-200:]
    return {"ok": r.ok, "error": detail or None, "tools": [t.name for t in r.tools]}


TESTER = run_check                  # async (config) -> {ok, error, tools}; tests replace it


# --------------------------------------------------------------------------- the store
class McpLibrary:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._mem = _empty()
        self.testing: set[str] = set()              # servers whose test is running now (never saved)

    @classmethod
    def beside(cls, store) -> "McpLibrary":
        p = getattr(store, "path", None)
        return cls(Path(p).parent / FILE_NAME if p else None)

    # ---------------------------------------------------------------- file access
    def _read(self) -> dict:
        if self.path is None:
            return self._mem
        for _ in range(50):
            try:
                text = self.path.read_text(encoding="utf-8")
                break
            except FileNotFoundError:
                return _empty()
            except PermissionError:                    # Windows: the file is being replaced right now
                time.sleep(0.02)
        else:
            raise OSError(f"cannot read {self.path.name}")
        try:
            data = json.loads(text)
        except ValueError:
            return _empty()
        if not isinstance(data, dict):
            return _empty()
        if not isinstance(data.get("servers"), list):
            data["servers"] = []
        if not isinstance(data.get("assignments"), dict):
            data["assignments"] = {}
        data["servers"] = [s for s in data["servers"] if isinstance(s, dict) and s.get("name")]
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix="mcp-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        for _ in range(50):
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:
                time.sleep(0.02)
        os.replace(tmp, self.path)

    @contextlib.contextmanager
    def _locked(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except (FileExistsError, PermissionError):
                try:
                    stale = time.time() - lock.stat().st_mtime > LOCK_STALE_S
                except OSError:
                    stale = False
                if stale or time.monotonic() > deadline:
                    with contextlib.suppress(OSError):
                        lock.unlink()
                    deadline = time.monotonic() + LOCK_WAIT_S
                    continue
                time.sleep(0.005)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                lock.unlink()

    def _update(self, change):
        if self.path is None:
            return change(self._mem)
        with self._locked():
            data = self._read()
            out = change(data)
            self._write(data)
            return out

    # ---------------------------------------------------------------- reads
    def data(self) -> dict:
        return copy.deepcopy(self._read())

    def get(self, name: str) -> dict | None:
        return next((s for s in self._read()["servers"] if s.get("name") == name), None)

    def names(self) -> list[str]:
        return [s["name"] for s in self._read()["servers"]]

    def assignments(self) -> dict[str, list[str]]:
        known = set(self.names())
        return {a: [n for n in ns if n in known] for a, ns in self._read()["assignments"].items()
                if isinstance(ns, list)}

    def view(self, server: dict) -> dict:
        """One server as the page sees it (secrets masked)."""
        status = "testing" if server["name"] in self.testing else server.get("status") or "untested"
        if status not in STATUSES:
            status = "untested"
        return {"name": server["name"], "kind": server.get("kind", "command"),
                "config": mask_config(server.get("kind", "command"), server.get("config") or {}),
                "status": status, "detail": server.get("detail") or None,
                "tool_count": server.get("tool_count") if status != "untested" else None,
                "tools": list(server.get("tools") or []), "tested_at": server.get("tested_at")}

    def event(self, **extra) -> dict:
        d = self._read()
        return {"type": "mcp_library", "servers": [self.view(s) for s in d["servers"]],
                "assignments": self.assignments(), **extra}

    # ---------------------------------------------------------------- changes
    def save(self, server: dict, original_name: str | None = None) -> str:
        """Add (no original_name) or edit a server -> its name. The stored status becomes untested (the hub tests
        it next). A rename follows into every assignment."""
        orig = str(original_name or "").strip() or None

        def change(d):
            servers = d["servers"]
            old = next((s for s in servers if s["name"] == orig), None) if orig else None
            if orig and old is None:
                raise ValueError(f"there is no server named '{orig}' to edit")
            clean = clean_server(server, old)
            name = clean["name"]
            if name != orig and any(s["name"] == name for s in servers):
                raise ValueError(f"a server named '{name}' is already in the library")
            entry = {**clean, "status": "untested", "detail": None, "tool_count": None, "tools": [],
                     "tested_at": None, "passed": False, "added_at": (old or {}).get("added_at") or now_iso()}
            if old is not None:
                servers[servers.index(old)] = entry
                if name != orig:
                    for a, ns in d["assignments"].items():
                        d["assignments"][a] = [name if n == orig else n for n in ns]
            else:
                servers.append(entry)
            return name
        return self._update(change)

    def remove(self, name: str) -> None:
        def change(d):
            if not any(s["name"] == name for s in d["servers"]):
                raise ValueError(f"there is no server named '{name}'")
            d["servers"] = [s for s in d["servers"] if s["name"] != name]
            d["assignments"] = {a: [n for n in ns if n != name] for a, ns in d["assignments"].items()}
            d["assignments"] = {a: ns for a, ns in d["assignments"].items() if ns}
        self._update(change)
        self.testing.discard(name)

    def set_agent(self, agent: str, servers) -> list[str]:
        agent = str(agent or "").strip()
        if not agent:
            raise ValueError("give the agent name")
        if not isinstance(servers, list) or not all(isinstance(x, str) for x in servers):
            raise ValueError("servers must be a list of server names")

        def change(d):
            known = {s["name"] for s in d["servers"]}
            unknown = [n for n in servers if n not in known]
            if unknown:
                raise ValueError(f"not in the library: {', '.join(unknown)}")
            names = list(dict.fromkeys(servers))
            if names:
                d["assignments"][agent] = names
            else:
                d["assignments"].pop(agent, None)
            return names
        return self._update(change)

    def set_result(self, name: str, result: dict) -> None:
        """A finished test: connected (passed) or failed, with the tool count / names or the error."""
        def change(d):
            s = next((x for x in d["servers"] if x["name"] == name), None)
            if s is None:                               # deleted while it was being tested
                return
            ok = bool(result.get("ok"))
            tools = [str(t) for t in result.get("tools") or []]
            s.update(status="connected" if ok else "failed", passed=ok, tools=tools if ok else [],
                     tool_count=len(tools) if ok else None, tested_at=now_iso(),
                     detail=(f"{len(tools)} tool{'s' if len(tools) != 1 else ''}" if ok
                             else str(result.get("error") or "the test failed")))
        self._update(change)

    # ---------------------------------------------------------------- what a run gets
    def for_agent(self, agent: str) -> tuple[dict, list[dict]]:
        """-> (agentlib mcp_servers for the agent's assigned servers whose last finished test passed, skipped:
        [{server, reason}] for every other assigned one)."""
        d = self._read()
        by_name = {s["name"]: s for s in d["servers"]}
        servers, skipped = {}, []
        for n in d["assignments"].get(agent) or []:
            s = by_name.get(n)
            if s is None:
                skipped.append({"server": n, "reason": "it is no longer in the MCP library"})
            elif s.get("passed"):
                servers[n] = agent_config(s)
            elif s.get("status") == "failed":
                skipped.append({"server": n, "reason": f"its last test failed ({s.get('detail') or 'no detail'})"})
            else:
                skipped.append({"server": n, "reason": "it has not passed a test yet"})
        return servers, skipped
