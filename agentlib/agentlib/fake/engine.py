"""Fake engine: scripted replies, real tool handlers, zero tokens. For tests and UI work.

- script(agent_name, turns): each turn = list of steps, or fn(message) -> list of steps
- steps: say(text), call(tool, args), ask(questions), rate_limit(status), fail(message)
- call() runs the agent's real custom tool (or ask_user validation) through the shared TurnState, so
  tool errors, ends_turn and needs_input behave exactly like the real engine
- calling a built-in name (e.g. "Bash") checks permissions like Claude (rules matched as in rules.py):
  disallowed_tools match -> denied; tools= rule matches (e.g. "Bash(ls:*)" vs the command) -> runs (fake
  result); else agent.on_permission ("always_allow" remembers the tool for the session), else denied.
  setup="project" with tools=None approves every built-in (the fake cannot read your settings files)
- no external MCP servers: capabilities.mcp_servers is False, so Agent(mcp_servers=...) raises CapabilityError
- cost: total_cost_usd is cumulative per conversation (kept across resume / copied on fork); cost_usd is the
  delta from cost_base, exactly like the Claude engine (resume without cost_base -> cost_usd = whole total)
- fail(message) raises AgentError whose .reply is the partial turn (usage so far, cost_usd 0)
- no script -> one reply: "(fake) <message>"; resume works within the same Python process
"""
from __future__ import annotations

import inspect
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from ..engines.base import Capabilities, Engine, EngineSession, TurnState
from ..errors import AgentError, ConversationMissing
from ..events import Done, RateLimit, Text, TextDelta, ToolCall, ToolResult
from ..permissions import PermissionRequest, normalize
from ..reply import Usage
from ..session import SessionInfo
from . import rules


@dataclass
class Say:
    text: str


@dataclass
class Call:
    tool: str
    args: dict = field(default_factory=dict)


@dataclass
class RateLimitStep:
    status: str = "allowed_warning"
    utilization: float | None = 0.9


@dataclass
class Fail:
    message: str


def say(text: str) -> Say:
    return Say(text)


def call(tool: str, args: dict | None = None) -> Call:
    return Call(tool, dict(args or {}))


def ask(questions: list[dict]) -> Call:
    return Call("ask_user", {"questions": questions})


def rate_limit(status: str = "allowed_warning", utilization: float | None = 0.9) -> RateLimitStep:
    return RateLimitStep(status, utilization)


def fail(message: str) -> Fail:
    return Fail(message)


_SCRIPTS: dict[str, list] = {}
_SESSIONS: dict[str, dict] = {}       # session_id -> {"turn": n, "messages": [...], "total_cost": float}


def script(agent_name: str, turns: list[list | Callable[[str], list]]) -> None:
    _SCRIPTS[agent_name] = list(turns)


def reset() -> None:
    _SCRIPTS.clear()
    _SESSIONS.clear()


class FakeEngine(Engine):
    name = "fake"
    capabilities = Capabilities(fork=True, permission_hook=True, mcp_servers=False)

    def open(self, agent, *, resume, fork, cost_base) -> "FakeSession":
        return FakeSession(agent, resume=resume, fork=fork, cost_base=cost_base)


class FakeSession(EngineSession):
    def __init__(self, agent, *, resume: str | None, fork: bool, cost_base: float = 0.0):
        self.agent = agent
        self.resolved = agent.resolved_tools()
        if resume is not None and resume not in _SESSIONS:
            raise ConversationMissing(f"no saved fake conversation {resume}")
        if resume is None:
            self.session_id = str(uuid.uuid4())
            _SESSIONS[self.session_id] = {"turn": 0, "messages": [], "total_cost": 0.0}
        elif fork:
            self.session_id = str(uuid.uuid4())
            _SESSIONS[self.session_id] = {k: (list(v) if isinstance(v, list) else v)
                                          for k, v in _SESSIONS[resume].items()}
        else:
            self.session_id = resume
        self._cost_base = float(cost_base or 0.0)
        self._always_allowed: set[str] = set()       # tools given "always_allow" this session
        self._info = SessionInfo()

    @property
    def total_cost(self) -> float:
        return _SESSIONS[self.session_id].get("total_cost", 0.0)

    @property
    def info(self) -> SessionInfo:
        return self._info

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def _startup_info(self) -> SessionInfo:
        """What the Claude engine would report: offered tools (custom by short name) and the tool server."""
        r = self.resolved
        tools = [t.name for t in r.custom] + list(r.builtin_names) + list(r.mcp_rules)
        if self.agent.skills and self.agent.setup == "lean" and not r.all_builtins and "Read" not in tools:
            tools.append("Read")
        servers = {self.agent.tool_server: "connected"} if r.custom else {}
        return SessionInfo(tools=list(dict.fromkeys(tools)), mcp_servers=servers, model=self.agent.model or "fake")

    def _steps(self, message: str) -> list:
        rec = _SESSIONS[self.session_id]
        turns = _SCRIPTS.get(self.agent.name)
        if turns is None:
            return [Say(f"(fake) {message}")]
        if rec["turn"] >= len(turns):
            return [Say("(fake) script finished")]
        t = turns[rec["turn"]]
        return t(message) if callable(t) else list(t)

    async def _builtin(self, name: str, args: dict) -> tuple[str, bool]:
        cwd = self.agent.cwd or os.getcwd()
        if rules.denied(list(self.agent.disallowed_tools), name, args, cwd):
            return f"{name} is denied for this agent.", True
        allowed = (self.resolved.all_builtins or name in self._always_allowed
                   or rules.allowed(self.resolved.builtin_rules, name, args, cwd))
        if not allowed:
            hook = self.agent.on_permission
            if hook is None:
                return f"{name} is not allowed for this agent.", True
            d = hook(PermissionRequest(agent=self.agent.name, tool=name, input=dict(args)))
            if inspect.isawaitable(d):
                d = await d
            d = normalize(d)
            if d == "deny":
                return f"The user denied {name}.", True
            if d == "always_allow":
                self._always_allowed.add(name)
        return f"(fake) ran {name}", False

    @staticmethod
    def _usage(message: str, out_chars: int) -> Usage:
        return Usage(input_tokens=max(1, len(message) // 4), output_tokens=out_chars // 4)

    async def turn(self, message: str):
        rec = _SESSIONS[self.session_id]
        if self._info == SessionInfo():
            self._info = self._startup_info()         # Claude reports init at the start of the first turn
        steps = self._steps(message)
        rec["turn"] += 1
        rec["messages"].append(message)
        state = TurnState("fake", self.resolved.custom)
        model = self.agent.model or "fake"
        out_chars = 0
        for step in steps:
            if isinstance(step, Fail):
                partial = state.reply(session_id=self.session_id, usage=self._usage(message, out_chars),
                                      cost_usd=0.0, total_cost_usd=self._cost_base, model=model,
                                      error=step.message, api_calls=1)
                raise AgentError(step.message, reply=partial)
            if isinstance(step, Say):
                for word in step.text.split(" "):
                    yield TextDelta(word + " ")
                state.record_text(step.text)
                out_chars += len(step.text)
                yield Text(step.text)
            elif isinstance(step, RateLimitStep):
                yield RateLimit(status=step.status, utilization=step.utilization, limit_type="five_hour")
            elif isinstance(step, Call):
                cid = f"fake-{uuid.uuid4().hex[:8]}"
                state.record_call(cid, step.tool, step.args)
                yield ToolCall(cid, step.tool, dict(step.args))
                if step.tool in state.tools:
                    text, err = await state.run_tool(step.tool, step.args)
                elif step.tool[:1].isupper():
                    text, err = await self._builtin(step.tool, step.args)
                else:
                    text, err = f"error: unknown tool '{step.tool}'", True
                state.record_result(cid, text, err)
                yield ToolResult(cid, step.tool, text, err)
                if state.stop_requested:
                    break
        usage = self._usage(message, out_chars)
        # Like Claude's ResultMessage.total_cost_usd: cumulative for the conversation; per-turn cost is the
        # delta from cost_base (the caller's last known total), the same formula as ClaudeSession._turn()
        rec["total_cost"] = total = rec.get("total_cost", 0.0) + (usage.input_tokens + usage.output_tokens) * 1e-6
        cost = total - self._cost_base if total >= self._cost_base else total
        self._cost_base = total
        yield Done(state.reply(session_id=self.session_id, usage=usage, cost_usd=cost,
                               total_cost_usd=total, model=model, stop_reason="end_turn", api_calls=1))
