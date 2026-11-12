"""Fake engine: scripted replies, real tool handlers, zero tokens. For tests and UI work.

- script(agent_name, turns): each turn = list of steps, or fn(message) -> list of steps
- steps: say(text), call(tool, args), ask(questions), rate_limit(status), fail(message), spend(usd), output(data)
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
- spend(usd): the turn costs this much more. Agent.max_budget_usd is checked after every step against what the
  opened session has spent (spend() steps; the automatic token cost is added at the end of the turn, unchecked):
  over the cap -> the turn stops there, Reply.status "error", error_kind "budget" (same message as Claude)
- permission_mode="never_ask": built-ins not pre-approved are denied without asking (on_permission is never
  set: Agent rejects the combination)
- output(data): the model's structured reply (Claude's native structured output). With Agent.output_schema
  the reply is checked like Claude: output() data if given, else the turn's text parsed as JSON ->
  Reply.data, or status "error" / error_kind "output_shape". Without output_schema output() is ignored
- save_conversation=False: nothing is stored; resuming that conversation later raises ConversationMissing
- models(list) scripts list_models() (ModelInfo, dicts, or id strings); models(fail="msg") makes it raise
  AgentError; default: two fake models ("fake-large" default, "fake-small")
- sign-in (FakeSetup): no sign-in needed. Like Claude it reads its own [fake] section of the local setup file
  (only auth = "none" is valid) and opening a session / list_models raises SetupError if the setup has problems,
  so apps can test their "not set up" path for free. check_connection("fake") uses model "fake-small"
"""
from __future__ import annotations

import inspect
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import local_setup, structured
from ..engines.base import Capabilities, Connection, Engine, EngineSession, EngineSetup, TurnState
from ..errors import AgentError, ConversationMissing
from ..events import Done, RateLimit, Text, TextDelta, ToolCall, ToolResult
from ..models import ModelInfo
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


@dataclass
class Spend:
    usd: float


@dataclass
class Output:
    data: Any


def spend(usd: float) -> Spend:
    return Spend(float(usd))


def output(data: Any) -> Output:
    return Output(data)


DEFAULT_MODELS = [
    ModelInfo(id="fake-large", name="Fake Large", description="Most capable (fake)", aliases=["large", "default"],
              is_default=True, effort_levels=["low", "medium", "high"]),
    ModelInfo(id="fake-small", name="Fake Small", description="Fastest (fake)", aliases=["small"],
              effort_levels=["low", "medium", "high"]),
]
_MODELS: dict = {}                    # {"items": [...]} and/or {"fail": "message"}; empty = DEFAULT_MODELS


def models(items: list | None = None, *, fail: str | None = None) -> None:
    """Script list_models(): items = ModelInfo / dict (ModelInfo fields) / id string; fail = raise AgentError."""
    _MODELS.clear()
    if items is not None:
        _MODELS["items"] = [m if isinstance(m, ModelInfo) else ModelInfo(**m) if isinstance(m, dict)
                            else ModelInfo(id=str(m), name=str(m)) for m in items]
    if fail is not None:
        _MODELS["fail"] = fail


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
    _MODELS.clear()


class FakeSetup(EngineSetup):
    """[fake] section: only auth = "none" (the default). Anything else is a setup problem, for testing."""
    section_keys = ("auth",)
    check_model = "fake-small"

    def __init__(self, name: str = "fake"):
        super().__init__(name)

    def resolve(self, section: dict, *, base=None) -> Connection:
        problems = [f"[fake] has unknown setting(s) {', '.join(sorted(set(section) - {'auth'}))}"] \
            if set(section) - {"auth"} else []
        auth = section.get("auth", "none")
        if auth != "none":
            problems.append(f'[fake] auth = {auth!r}: the fake engine only knows "none"')
        return Connection("fake", "none", "fake engine: no sign-in needed", problems=problems)

    def version(self) -> str:
        return "fake engine (zero tokens)"


class FakeEngine(Engine):
    name = "fake"
    capabilities = Capabilities(fork=True, permission_hook=True, mcp_servers=False, budget=True, never_ask=True,
                                structured_output=True, unsaved=True, list_models=True)

    def open(self, agent, *, resume, fork, cost_base) -> "FakeSession":
        local_setup.require("fake")
        return FakeSession(agent, resume=resume, fork=fork, cost_base=cost_base)

    async def list_models(self, *, env: dict[str, str], timeout_s: float | None) -> list[ModelInfo]:
        local_setup.require("fake")
        if "fail" in _MODELS:
            raise AgentError(_MODELS["fail"])
        items = _MODELS.get("items", DEFAULT_MODELS)
        return [ModelInfo(**m.to_dict()) for m in items]        # copies: callers may edit them


def _copy(rec: dict) -> dict:
    return {k: (list(v) if isinstance(v, list) else v) for k, v in rec.items()}


class FakeSession(EngineSession):
    def __init__(self, agent, *, resume: str | None, fork: bool, cost_base: float = 0.0):
        self.agent = agent
        self.resolved = agent.resolved_tools()
        if resume is not None and resume not in _SESSIONS:
            raise ConversationMissing(f"no saved fake conversation {resume}")
        keep = agent.save_conversation               # False: work on a record that is never stored
        if resume is None:
            self.session_id = str(uuid.uuid4())
            self._rec = {"turn": 0, "messages": [], "total_cost": 0.0}
        elif fork:
            self.session_id = str(uuid.uuid4())
            self._rec = _copy(_SESSIONS[resume])
        else:
            self.session_id = resume
            self._rec = _SESSIONS[resume] if keep else _copy(_SESSIONS[resume])
        if keep:
            _SESSIONS[self.session_id] = self._rec
        self._cost_base = float(cost_base or 0.0)
        self._spent = 0.0                            # this opened session's spend (for max_budget_usd)
        self._always_allowed: set[str] = set()       # tools given "always_allow" this session
        self._info = SessionInfo()

    @property
    def total_cost(self) -> float:
        return self._rec.get("total_cost", 0.0)

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
        rec = self._rec
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
            if self.agent.permission_mode == "never_ask":
                return f"{name} is not allowed for this agent (never_ask: not pre-approved).", True
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
        rec = self._rec
        if self._info == SessionInfo():
            self._info = self._startup_info()         # Claude reports init at the start of the first turn
        steps = self._steps(message)
        rec["turn"] += 1
        rec["messages"].append(message)
        state = TurnState("fake", self.resolved.custom)
        model = self.agent.model or "fake"
        cap = self.agent.max_budget_usd
        out_chars = 0
        spent = 0.0                                   # spend() steps this turn
        structured_data = None
        error = kind = None
        for step in steps:
            if isinstance(step, Spend):
                spent += step.usd
                if cap is not None and self._spent + spent > cap:
                    error, kind = f"stopped at the spending cap (max_budget_usd={cap})", "budget"
                    break
                continue
            if isinstance(step, Output):
                structured_data = step.data
                out_chars += len(json.dumps(step.data, default=str))
                continue
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
        turn_cost = (usage.input_tokens + usage.output_tokens) * 1e-6 + spent
        self._spent += turn_cost
        rec["total_cost"] = total = rec.get("total_cost", 0.0) + turn_cost
        cost = total - self._cost_base if total >= self._cost_base else total
        self._cost_base = total
        data = None
        schema = self.agent.output_schema
        if error is None and schema is not None and not state.stop_requested:
            data, problem = structured.check_output(schema, data=structured_data, text="\n\n".join(state.texts))
            if problem:
                error, kind = problem, "output_shape"
        yield Done(state.reply(session_id=self.session_id, usage=usage, cost_usd=cost,
                               total_cost_usd=total, model=model, stop_reason="end_turn", api_calls=1,
                               error=error, error_kind=kind, data=data))
