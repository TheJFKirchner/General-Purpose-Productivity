"""Claude Code permission-rule matching, approximated for the fake engine (test-only; the core never uses it).

Mirrors https://code.claude.com/docs/en/permissions as far as is practical without a shell parser:
- "Tool" or "Tool(*)" matches every use of the tool
- Bash / PowerShell: "Bash(npm run build)" exact; "*" matches any text (spaces too); a trailing " *" (or the
  legacy ":*") as the only wildcard also matches the bare command ("Bash(ls *)" matches "ls", not "lsof").
  Compound commands are split on && || ; | |& & and newlines: allow needs EVERY part allowed (by any rule),
  deny needs ANY part matched. A dangling && / || is unparseable -> never allowed by a rule
- Read / Edit path rules (gitignore style): "//abs", "~/home", "/cwd-anchored", "rel" or "./rel" from cwd;
  "*" within a segment, "**" across. A rule with no "/" (".env", "*.py") matches at any depth; deny rules with
  one directory segment ("secrets/**") match at any depth too. Edit rules cover Edit/Write/MultiEdit/
  NotebookEdit; Read rules cover Read/Grep/Glob (and, for deny, Edit/Write on the same path).
  Path rules written as Write(...), Grep(...), Glob(...) never match (as in Claude Code)
- WebFetch(domain:host): case-insensitive hostname; "*.example.com" = subdomains only; "*" = any host
- mcp__server, mcp__server__*, mcp__server__tool, mcp__server__get_* (no parentheses)
- deny rules only: "Tool(param:value)" on a top-level input field ("*" wildcard)
Not modelled: Claude's built-in read-only Bash commands that need no rule, wrapper stripping (timeout, xargs),
quoting / subshells inside commands, settings-file rules.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

SHELL_TOOLS = {"Bash", "PowerShell"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}
PATH_KEYS = ("file_path", "notebook_path", "path")
_SPLIT = re.compile(r"&&|\|\||\|&|[;|&\n]")
_FLAGS = re.IGNORECASE if sys.platform == "win32" else 0


def parse(rule: str) -> tuple[str, str | None]:
    """'Bash(npm run *)' -> ('Bash', 'npm run *'); 'Read' / 'Read(*)' -> ('Read', None)."""
    rule = rule.strip()
    m = re.fullmatch(r"([^()\s]+)\s*\((.*)\)", rule, re.S)
    if not m:
        return rule, None
    spec = m.group(2).strip()
    return m.group(1), (None if spec in ("", "*") else spec)


# --------------------------------------------------------------------------- shell commands

def _subcommands(command: str) -> list[str] | None:
    """Split a compound command; None if unparseable (dangling && or ||)."""
    if re.search(r"(&&|\|\|)\s*$", command):
        return None
    parts = [p.strip() for p in _SPLIT.split(command)]
    return [p for p in parts if p] or [""]


def command_matches(pattern: str, command: str) -> bool:
    """One simple command against one Bash rule specifier."""
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    command = command.strip()
    if "*" not in pattern:
        return command == pattern
    rx = ".*".join(re.escape(p) for p in pattern.split("*"))
    if re.fullmatch(rx, command, re.S):
        return True
    return pattern.endswith(" *") and pattern.count("*") == 1 and command == pattern[:-2].rstrip()


# --------------------------------------------------------------------------- paths

def _posix(p: Path) -> str:
    s = p.as_posix()
    if re.match(r"^[A-Za-z]:/", s):                 # C:/Users/x -> /c/Users/x (as Claude Code does on Windows)
        s = "/" + s[0].lower() + s[2:]
    return s.rstrip("/") or "/"


def _glob_rx(pat: str) -> str:
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pat.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pat[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pat[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pat[i]), i + 1
    return out


def path_matches(pattern: str, target: str, cwd: Path, *, deny: bool = False) -> bool:
    if pattern.startswith("//"):
        base, pat = "/", pattern[2:]
    elif pattern.startswith("~/"):
        base, pat = _posix(Path.home().resolve()), pattern[2:]
    elif pattern.startswith("/"):
        base, pat = _posix(cwd), pattern[1:]
    else:
        base, pat = _posix(cwd), pattern[2:] if pattern.startswith("./") else pattern
    pat = pat.rstrip("/")
    if not pat:
        return False
    p = Path(target).expanduser()
    full = _posix((p if p.is_absolute() else cwd / p).resolve())
    fold = (lambda s: s.lower()) if _FLAGS else (lambda s: s)
    if base == "/":
        rel = full.lstrip("/")
    elif fold(full) == fold(base):
        rel = ""
    elif fold(full).startswith(fold(base) + "/"):
        rel = full[len(base) + 1:]
    else:
        return False                                 # a rule only matches under its anchor
    any_depth = "/" not in pat or (deny and not pattern.startswith(("/", "./", "~/"))
                                   and re.fullmatch(r"[^/*]+/\*\*", pat) is not None)
    body = _glob_rx(pat[:-3]) + "(?:/.*)?" if pat.endswith("/**") else _glob_rx(pat)   # dir/** covers dir too
    rx = ("(?:.*/)?" if any_depth else "") + body
    # gitignore: a pattern that matches a directory also covers everything under it
    segs = rel.split("/") if rel else []
    return any(re.fullmatch(rx, "/".join(segs[:n]), _FLAGS) for n in range(len(segs), 0, -1))


# --------------------------------------------------------------------------- web / mcp

def domain_matches(spec: str, url: str) -> bool:
    if not spec.startswith("domain:"):
        return False
    want = spec[len("domain:"):].strip().lower().rstrip(".")
    host = (urlparse(str(url)).hostname or "").lower().rstrip(".")
    if not host:
        return False
    if want == "*":
        return True
    if want.startswith("*."):
        return host.endswith(want[1:]) and host != want[2:]
    return re.fullmatch("[^.]*".join(re.escape(p) for p in want.split("*")), host) is not None


def _mcp_matches(name: str, tool: str) -> bool:
    if name == tool:
        return True
    parts = tool.split("__", 2)                      # mcp, server, tool
    if len(parts) < 3:
        return False
    server_prefix = f"mcp__{parts[1]}"
    if name == server_prefix:
        return True
    if name.startswith(server_prefix + "__") and "*" in name:
        rx = ".*".join(re.escape(p) for p in name[len(server_prefix) + 2:].split("*"))
        return re.fullmatch(rx, parts[2]) is not None
    return False


# --------------------------------------------------------------------------- rule sets

def _covers(rule_name: str, tool: str, has_spec: bool, deny: bool) -> bool:
    if rule_name == tool:
        return True
    if not has_spec:
        return False
    if rule_name == "Edit":
        return tool in EDIT_TOOLS
    if rule_name == "Read":
        return tool in READ_TOOLS or (deny and tool in ("Edit", "Write", "MultiEdit"))
    return False


def _scalar(v) -> str:
    return v if isinstance(v, str) else json.dumps(v)   # True -> "true", as in the model's JSON input


def _target_path(inp: dict, cwd: Path) -> str:
    for k in PATH_KEYS:
        if inp.get(k):
            return str(inp[k])
    return str(cwd)                                  # Grep / Glob default to the working directory


def _rule_matches(rule: str, tool: str, inp: dict, cwd: Path, *, deny: bool) -> bool:
    """One rule against one call. Shell commands are handled per subcommand by the callers."""
    name, spec = parse(rule)
    if tool.startswith("mcp__"):
        return "(" not in rule and _mcp_matches(name, tool)
    if not _covers(name, tool, spec is not None, deny):
        return False
    if spec is None:
        return True
    if deny:
        m = re.fullmatch(r"(\w+)\s*:\s*(.*)", spec, re.S)
        if m and m.group(1) not in ("domain",) and m.group(1) in inp:
            rx = ".*".join(re.escape(p) for p in m.group(2).split("*"))
            return re.fullmatch(rx, _scalar(inp[m.group(1)]), re.S) is not None
    if tool in SHELL_TOOLS:
        return command_matches(spec, str(inp.get("command", "")))
    if name in ("Read", "Edit"):
        return path_matches(spec, _target_path(inp, cwd), cwd, deny=deny)
    if name in READ_TOOLS | EDIT_TOOLS:
        return False                                 # Write(path) / Grep(path) / Glob(path) never match
    if tool == "WebFetch":
        return domain_matches(spec, inp.get("url", ""))
    return False                                     # unknown specifier: does not pre-approve


def allowed(rules: list[str], tool: str, inp: dict, cwd: str | Path | None = None) -> bool:
    """True if the allow rules pre-approve this call (shell: every subcommand must be covered)."""
    cwd = Path(cwd or os.getcwd()).resolve()
    if tool in SHELL_TOOLS:
        whole = [r for r in rules if parse(r)[0] == tool and parse(r)[1] is None]
        if whole:
            return True
        parts = _subcommands(str(inp.get("command", "")))
        if parts is None:
            return False
        specs = [s for n, s in map(parse, rules) if n == tool and s is not None]
        return all(any(command_matches(s, part) for s in specs) for part in parts)
    return any(_rule_matches(r, tool, inp, cwd, deny=False) for r in rules)


def denied(rules: list[str], tool: str, inp: dict, cwd: str | Path | None = None) -> bool:
    """True if any deny rule matches this call (shell: any subcommand)."""
    cwd = Path(cwd or os.getcwd()).resolve()
    if tool in SHELL_TOOLS:
        cmd = str(inp.get("command", ""))
        parts = [p for p in _SPLIT.split(cmd) if p.strip()] or [cmd]
        for r in rules:
            name, spec = parse(r)
            if name != tool:
                continue
            if spec is None:
                return True
            m = re.fullmatch(r"(\w+)\s*:\s*(.*)", spec, re.S)
            if m and m.group(1) != "command" and m.group(1) in inp:
                if _rule_matches(r, tool, inp, cwd, deny=True):
                    return True
                continue
            if any(command_matches(spec, p) for p in parts):
                return True
        return False
    return any(_rule_matches(r, tool, inp, cwd, deny=True) for r in rules)
