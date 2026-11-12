"""Engine-neutral custom tools.

- @tool turns a plain Python function into a Tool: inputs from type hints, description from the docstring
- sync or async handlers; return str (dict/list -> JSON, None -> "ok"); an exception -> error result, turn goes on
- flags: ends_turn=True (agent stops right after a successful call), read_only=True (safe to run in parallel)
- ASK_USER: the library's built-in material-question tool (handled by the engine, see questions.py)
- resolve_tools(): splits an agent's mixed `tools:` list into custom Tools vs built-in rules ("Read",
  "Bash(npm run build:*)") vs external MCP names ("mcp__db__run_sql")
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
import types
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, get_args, get_origin

from . import prompt_files
from .errors import AgentFileError
from .questions import ASK_USER_SCHEMA

ASK_USER_NAME = "ask_user"
DEFAULT_SERVER = "agentlib"          # custom tools appear to the model as mcp__agentlib__<name>


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    handler: Callable[..., Any] | None = None
    ends_turn: bool = False
    read_only: bool = False
    builtin: str | None = None          # "ask_user" for the library's own tool

    async def call(self, args: dict) -> tuple[str, bool]:
        """Run the handler -> (text, is_error). Never raises."""
        if self.handler is None:
            return f"error: tool '{self.name}' has no handler", True
        try:
            if inspect.iscoroutinefunction(self.handler):
                out = await self.handler(**args)
            else:
                out = await asyncio.to_thread(self.handler, **args)
        except Exception as e:  # noqa: BLE001 -- a broken tool must not kill the turn
            return f"error: {type(e).__name__}: {e}", True
        return to_text(out), False


def to_text(out: Any) -> str:
    if out is None:
        return "ok"
    if isinstance(out, str):
        return out
    try:
        return json.dumps(out, ensure_ascii=False, default=str)
    except TypeError:
        return str(out)


# --------------------------------------------------------------------------- schema from type hints

def _json_type(tp: Any) -> dict:
    origin = get_origin(tp)
    if tp is inspect.Parameter.empty or tp is Any:
        return {}
    if origin is Literal:
        return {"enum": list(get_args(tp))}
    if origin in (typing.Union, types.UnionType):
        args = [a for a in get_args(tp) if a is not type(None)]
        return _json_type(args[0]) if len(args) == 1 else {"anyOf": [_json_type(a) for a in args]}
    if tp is str:
        return {"type": "string"}
    if tp is bool:
        return {"type": "boolean"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if tp in (list, tuple) or origin in (list, tuple):
        args = get_args(tp)
        return {"type": "array", **({"items": _json_type(args[0])} if args else {})}
    if tp is dict or origin is dict:
        return {"type": "object"}
    return {"type": "string"}


def schema_from_signature(fn: Callable) -> dict:
    hints = typing.get_type_hints(fn)
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        props[name] = _json_type(hints.get(name, p.annotation))
        if p.default is p.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def tool(fn: Callable | None = None, *, name: str | None = None, description: str | None = None,
         schema: dict | None = None, ends_turn: bool = False, read_only: bool = False):
    """Use as @tool or @tool(name=..., ends_turn=True)."""
    def wrap(f: Callable) -> Tool:
        return Tool(name=name or f.__name__,
                    description=(description or inspect.getdoc(f) or f.__name__).strip(),
                    schema=schema or schema_from_signature(f),
                    handler=f, ends_turn=ends_turn, read_only=read_only)
    return wrap(fn) if fn is not None else wrap


def ask_user_tool() -> Tool:
    return Tool(name=ASK_USER_NAME, description=prompt_files.load("ask_user_tool"),
                schema=ASK_USER_SCHEMA, ends_turn=True, builtin="ask_user")


# --------------------------------------------------------------------------- name helpers

def full_name(name: str, server: str = DEFAULT_SERVER) -> str:
    return f"mcp__{server}__{name}"


def short_name(name: str, server: str = DEFAULT_SERVER) -> str:
    prefix = f"mcp__{server}__"
    return name[len(prefix):] if name.startswith(prefix) else name


def base_tool_name(rule: str) -> str:
    """'Bash(npm run build:*)' -> 'Bash'."""
    return re.split(r"[(\s]", rule.strip(), maxsplit=1)[0]


@dataclass
class ResolvedTools:
    custom: list[Tool] = field(default_factory=list)       # served by the library (incl. ask_user)
    builtin_rules: list[str] = field(default_factory=list)  # "Read", "Bash(npm run build:*)"
    mcp_rules: list[str] = field(default_factory=list)      # external MCP names, passed through
    all_builtins: bool = False                              # tools unspecified -> engine default set

    @property
    def builtin_names(self) -> list[str]:
        return list(dict.fromkeys(base_tool_name(r) for r in self.builtin_rules))


def resolve_tools(specs: list[str | Tool] | None, available: list[Tool] = (), *,
                  server: str = DEFAULT_SERVER, setup: str = "lean",
                  include_ask_user: bool = True) -> ResolvedTools:
    """specs=None means 'not specified' (like a Claude Code agent file with no tools: line):
    all given custom tools + ask_user (unless include_ask_user=False), plus all built-ins in project
    mode / none in lean mode."""
    pool = {t.name: t for t in available}
    pool.setdefault(ASK_USER_NAME, ask_user_tool())
    out = ResolvedTools()
    if specs is None:
        out.custom = [t for t in pool.values() if include_ask_user or t.builtin != "ask_user"]
        out.all_builtins = setup == "project"
        return out
    for spec in specs:
        if isinstance(spec, Tool):
            pool[spec.name] = spec
            out.custom.append(spec)
            continue
        s = str(spec).strip()
        if not s:
            continue
        short = short_name(s, server)
        if short in pool:
            out.custom.append(pool[short])
        elif s.startswith("mcp__"):
            out.mcp_rules.append(s)
        elif s[:1].islower():
            raise AgentFileError(f"tool '{s}' is listed but no function was given for it "
                                 f"(pass it in tools=[...] when loading)")
        else:
            out.builtin_rules.append(s)
    seen: set[str] = set()
    out.custom = [t for t in out.custom if not (t.name in seen or seen.add(t.name))]
    return out
