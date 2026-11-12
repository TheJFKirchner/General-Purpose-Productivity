"""Structured (JSON) replies: the caller supplies a JSON Schema, the reply comes back parsed and checked.

- Agent(output_schema={...}) on any engine that has capabilities.structured_output -> Reply.data
- check_schema(schema): raises ValueError at Agent creation if the schema itself is not valid JSON Schema
- check_output(schema, data=, text=): shared by every engine. Uses the engine's native structured value when it
  has one (data), else parses the reply text (first JSON value in it, code fences allowed). Returns
  (data, None) or (None, "reply did not match the output schema: ...") -> Reply.error, error_kind "output_shape"
- ask_structured(message, schema, ...): one-shot call with no tools at all, nothing saved; returns a Reply
  (reply.data on success; reply.status == "error" with error_kind "output_shape" on a malformed reply)
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import jsonschema

_MISSING = object()


def check_schema(schema: dict) -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"output_schema must be a JSON Schema dict, got {type(schema).__name__}")
    try:
        jsonschema.validators.validator_for(schema).check_schema(schema)
    except jsonschema.SchemaError as e:
        raise ValueError(f"output_schema is not a valid JSON Schema: {e.message}") from None


def validate(data: Any, schema: dict) -> str | None:
    """None if data matches schema, else a one-line reason (first problem, with its JSON path)."""
    v = jsonschema.validators.validator_for(schema)(schema)
    errors = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not errors:
        return None
    e = errors[0]
    where = "/".join(str(p) for p in e.absolute_path)
    more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
    return f"{'at ' + where + ': ' if where else ''}{e.message}{more}"


def parse_text(text: str) -> Any:
    """First JSON value in the text (object or array; code fences and surrounding prose tolerated).
    Raises ValueError when there is none."""
    s = (text or "").strip()
    if not s:
        raise ValueError("the reply was empty")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch in "{[":
            try:
                return dec.raw_decode(s, i)[0]
            except json.JSONDecodeError:
                continue
    raise ValueError(f"the reply contained no JSON: {s[:200]!r}")


def check_output(schema: dict, *, data: Any = _MISSING, text: str = "") -> tuple[Any, str | None]:
    """-> (parsed data, None) or (None, error message). data= is the engine's native structured value
    (pass nothing / None if the engine has none); text= is the reply text, parsed when data is absent."""
    if data is _MISSING or data is None:
        try:
            data = parse_text(text)
        except ValueError as e:
            return None, f"reply did not match the output schema: {e}"
    problem = validate(data, schema)
    if problem:
        return None, f"reply did not match the output schema: {problem}"
    return data, None


async def ask_structured(message: str, schema: dict, *, instructions: str = "", model: str | None = None,
                         engine: str = "claude", name: str = "structured", effort: str | None = None,
                         max_budget_usd: float | None = None, timeout_s: float | None = 600,
                         env: dict[str, str] | None = None, cwd=None):
    """One-shot call with no tools, never asks for permission, nothing saved. -> Reply (reply.data)."""
    from .agent import Agent
    agent = Agent(name, instructions=instructions, engine=engine, model=model, tools=[], include_ask_user=False,
                  output_schema=schema, save_conversation=False, permission_mode="never_ask", effort=effort,
                  max_budget_usd=max_budget_usd, timeout_s=timeout_s, env=dict(env or {}), cwd=cwd)
    return await agent.ask(message)


def ask_structured_sync(message: str, schema: dict, **kw):
    """ask_structured() for code with no running event loop (uses asyncio.run)."""
    return asyncio.run(ask_structured(message, schema, **kw))
