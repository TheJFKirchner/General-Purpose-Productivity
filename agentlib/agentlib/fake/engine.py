"""Fake engine: scripted replies, real tool handlers, zero tokens. For tests and UI work.

- script(agent_name, turns): each turn = list of steps, or fn(message) -> list of steps
- steps: say(text), call(tool, args), ask(questions), rate_limit(status), fail(message), spend(usd), output(data),
  plan(text), parallel(*steps)
- model replies (events' model_turn, numbered over the opened session like Claude): a say() or call() starts a
  new model reply unless one is already open; a reply ends with its tool call. So say("Looking") + call(A) is
  one reply, a following call(B) is the next reply, and a final say("Done") another. parallel(say(..),
  call(A), call(B)) is ONE reply issuing both calls (same model_turn). Reply.api_calls = replies in the turn
  (at least 1). rate_limit / spend / output / fail neither start nor end a reply
- tokens per model reply (Reply.turn_usage, one TurnUsage per reply): say / call / ask / plan / parallel take
  usage= (a Usage or a dict of Usage fields) = tokens of the model reply that step belongs to (several on one
  reply are added together). Default (no usage= in the turn): the turn's estimated usage is split over its
  replies (all input on the first, each reply's text chars // 4 as output, the rest of the output on the last),
  so the replies add up to Reply.usage, which is unchanged. Once any reply in a turn has usage=, unscripted
  replies keep their default share and Reply.usage becomes the sum of the replies (so scripted figures add up).
  TurnUsage.model = the model when the reply opened (set_model counts from the next reply)
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
- permission modes like Claude: "accept_edits" runs edit tools and mkdir/touch/rm/rmdir/mv/cp/sed on paths
  inside cwd / add_dirs without asking (rules.accept_edits_allows); "plan" never pre-approves edit tools (they
  go to on_permission, denied if none). s.set_permission_mode(mode) switches live; a decision's mode= too
- plan(text) step = the model calls ExitPlanMode: in plan mode it goes to on_permission as
  PermissionRequest(kind="plan", plan=text); allow -> mode becomes decision.mode or "default"; deny -> stays
  in plan mode (error tool result with prompts/plan_rejected.md). Outside plan mode -> error result
- permission requests carry suggestions (default: "Bash(<first word>:*)" project_local for shell tools,
  set_mode accept_edits for edit tools, the whole tool otherwise; call(..., suggestions=[...]) overrides),
  mode and call_id. always_allow remembers rules for the session, or with remember="project_local" in an
  in-memory per-cwd store (saved_rules(cwd)) that later setup="project" sessions in that cwd honour
- output(data): the model's structured reply (Claude's native structured output). With Agent.output_schema
  the reply is checked like Claude: output() data if given, else the turn's text parsed as JSON ->
  Reply.data, or status "error" / error_kind "output_shape". Without output_schema output() is ignored
- save_conversation=False: nothing is stored; resuming that conversation later raises ConversationMissing
- models(list) scripts list_models() (ModelInfo, dicts, or id strings); models(fail="msg") makes it raise
  AgentError; default: two fake models ("fake-large" default, "fake-small")
- sign-in (FakeSetup): no sign-in needed. Like Claude it reads its own [fake] section of the local setup file
  (only auth = "none" is valid) and opening a session / list_models raises SetupError if the setup has problems,
  so apps can test their "not set up" path for free. check_connection("fake") uses model "fake-small"
- process control (capability process_control, like Claude): Session.pid = the pid scripted with
  process(agent_name, pid) (None if unscripted), from start / first turn until close or kill. Session.kill()
  records the call (kills()), closes the session (later turns raise AgentError), makes a running turn raise
  AgentError at its next step, and returns a KillResult; with process(..., real=True) it really ends that
  process tree (for tests with stand-in processes)
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import uuid
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path
from typing import Any, Callable

from .. import local_setup, prompt_files, structured
from ..engines.base import Capabilities, Connection, Engine, EngineSession, EngineSetup, TurnState
from ..errors import AgentError, ConversationMissing
from ..events import Done, RateLimit, Text, TextDelta, ToolCall, ToolResult
from ..models import ModelInfo
from ..permissions import PLAN_APPROVED_MODE, PermissionRequest, PermissionSuggestion, check_mode, resolve
from ..processes import KillResult, end_process_tree, process_started_at
from ..reply import TurnUsage, Usage
from ..session import SessionInfo
from . import rules

PLAN_TOOL = "ExitPlanMode"            # same name as Claude's plan-proposal tool (events show it the same way)


@dataclass
class Say:
    text: str
    usage: Usage | None = None        # tokens of the model reply this step is part of (added to its other steps')


@dataclass
class Call:
    tool: str
    args: dict = field(default_factory=dict)
    suggestions: list | None = None   # PermissionSuggestion / dict overrides for this call's permission request
    usage: Usage | None = None        # tokens of the model reply this step is part of (added to its other steps')


@dataclass
class Parallel:
    steps: list                       # Say / Call steps that make up ONE model reply
    usage: Usage | None = None        # tokens of this reply (added to usage= given on its steps)


def _tokens(usage) -> Usage | None:
    """usage= on a step: a Usage, a dict of Usage field names, or None."""
    if usage is None or isinstance(usage, Usage):
        return usage
    if isinstance(usage, dict):
        return Usage(**usage)
    raise TypeError(f"usage= takes a Usage or a dict of Usage fields, not {type(usage).__name__}")


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


def say(text: str, *, usage: Usage | dict | None = None) -> Say:
    """Model text. usage= = tokens of the model reply it is part of (see the module docstring)."""
    return Say(text, _tokens(usage))


def call(tool: str, args: dict | None = None, *, suggestions: list | None = None,
         usage: Usage | dict | None = None) -> Call:
    """A tool call. suggestions= replaces the fake's default "always allow" suggestions if it asks. usage= =
    tokens of the model reply that issues it."""
    return Call(tool, dict(args or {}),
                None if suggestions is None else [s if isinstance(s, PermissionSuggestion) else PermissionSuggestion(**s)
                                                  for s in suggestions], _tokens(usage))


def parallel(*steps, usage: Usage | dict | None = None) -> Parallel:
    """One model reply that issues several tool calls at once (they share one model_turn). Takes say() and
    call() / ask() / plan() steps: its text comes first, then every call's ToolCall event, then the calls run
    in order and their ToolResult events follow (like parallel calls whose results come back after all were
    issued). usage= = tokens of this one reply."""
    for s in steps:
        if not isinstance(s, (Say, Call)):
            raise TypeError(f"parallel() takes say() and call() steps, not {type(s).__name__}")
    return Parallel(list(steps), _tokens(usage))


def plan(text: str, *, usage: Usage | dict | None = None) -> Call:
    """The model proposes a plan and asks to proceed (Claude: ExitPlanMode). Only works in plan mode."""
    return Call(PLAN_TOOL, {"plan": text}, usage=_tokens(usage))


def ask(questions: list[dict], *, usage: Usage | dict | None = None) -> Call:
    return Call("ask_user", {"questions": questions}, usage=_tokens(usage))


def rate_limit(status: str = "allowed_warning", utilization: float | None = 0.9) -> RateLimitStep:
    return RateLimitStep(status, utilization)


def fail(message: str) -> Fail:
    return Fail(message)


_SCRIPTS: dict[str, list] = {}
_SESSIONS: dict[str, dict] = {}       # session_id -> {"turn": n, "messages": [...], "total_cost": float}
_LOCAL_RULES: dict[str, list[str]] = {}   # resolved cwd -> allow rules "remembered" in project local settings


def script(agent_name: str, turns: list[list | Callable[[str], list]]) -> None:
    _SCRIPTS[agent_name] = list(turns)


def _cwd_key(cwd) -> str:
    return str(Path(cwd or os.getcwd()).resolve())


def saved_rules(cwd=None) -> list[str]:
    """Allow rules that always_allow with remember="project_local" saved for this folder (Claude:
    <cwd>/.claude/settings.local.json). In memory only; later setup="project" sessions in that cwd honour them."""
    return list(_LOCAL_RULES.get(_cwd_key(cwd), []))


_PROCESSES: dict[str, tuple[Any, bool]] = {}   # agent name -> (pid or fn() -> pid, real)
_KILLS: list[dict] = []
KILLED = "the session was ended (kill)"       # same words as the Claude engine
# Session.process_started_at for a scripted (not real) pid: a fixed time long past, so passing it to the real
# end_process_tree with that pid is refused (start time differs) instead of ending an unrelated process
FAKE_STARTED_AT = 1_000_000_000.0


def process(agent_name: str, pid: int | Callable[[], int | None] | None, *, real: bool = False) -> None:
    """Script the OS process this agent's fake sessions report as Session.pid (an int, None = cannot tell, or a
    function called once per session). real=True: Session.kill() really ends that process tree with
    processes.end_process_tree (give the pid of a stand-in process your test started); default: kill() only
    records the call (kills()). Unscripted agents report pid None (a made-up number could be a real process)."""
    _PROCESSES[agent_name] = (pid, real)


def kills() -> list[dict]:
    """Every Session.kill() on the fake engine, in order: {agent, session_id, pid, mid_turn, real}."""
    return [dict(k) for k in _KILLS]


def reset() -> None:
    _SCRIPTS.clear()
    _SESSIONS.clear()
    _MODELS.clear()
    _LOCAL_RULES.clear()
    _PROCESSES.clear()
    _KILLS.clear()


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
                                structured_output=True, unsaved=True, list_models=True,
                                accept_edits=True, plan_mode=True, mode_switch=True, engine_prompt=True,
                                model_switch=True, model_turns=True, turn_usage=True, process_control=True)

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
        self._session_rules: list[str] = []          # allow rules from "always_allow" (remember="session")
        self._info = SessionInfo()
        self.requested_model: str | None = None      # set by set_model()
        self.permission_mode: str = agent.permission_mode
        self._model_turns = 0                        # model replies since open (events' model_turn runs on)
        self._proc: tuple[int, float | None] | None = None   # scripted process (pid, start time if real)
        self._connected = False
        self._killed = False
        self._busy = False

    @property
    def total_cost(self) -> float:
        return self._rec.get("total_cost", 0.0)

    @property
    def info(self) -> SessionInfo:
        return self._info

    def _connect(self) -> None:
        """Like the Claude engine starting its process: pick up the scripted pid (process())."""
        if self._connected:
            return
        self._connected = True
        spec, real = _PROCESSES.get(self.agent.name, (None, False))
        pid = spec() if callable(spec) else spec
        if pid is None:
            self._proc = None
            return
        started = process_started_at(int(pid)) if real else None
        # like Claude: a real process whose start time cannot be read is not recorded (never kill by pid alone)
        self._proc = None if real and started is None else (int(pid), started)

    @property
    def pid(self) -> int | None:
        return self._proc[0] if self._connected and self._proc else None

    @property
    def process_started_at(self) -> float | None:
        """real=True: the stand-in's start time read at connect; else a fixed made-up time (never used to kill)."""
        if not (self._connected and self._proc):
            return None
        return self._proc[1] if self._proc[1] is not None else FAKE_STARTED_AT

    async def start(self) -> None:
        if self._killed:
            raise AgentError(f"{KILLED}; open a new session")
        self._connect()

    async def close(self) -> None:
        self._connected = False                      # pid reads None until a later turn "reconnects"

    async def kill(self, *, timeout_s: float = 3.0) -> KillResult:
        _, real = _PROCESSES.get(self.agent.name, (None, False))
        proc = self._proc if self._connected else None
        _KILLS.append({"agent": self.agent.name, "session_id": self.session_id,
                       "pid": proc[0] if proc else None, "mid_turn": self._busy, "real": bool(real and proc)})
        self._killed, self._connected, self._proc = True, False, None
        if proc is None:
            return KillResult(pid=None, ok=True, already_gone=True)
        if real:
            return await asyncio.to_thread(end_process_tree, proc[0], started_at=proc[1], timeout_s=timeout_s)
        return KillResult(pid=proc[0], ok=True)

    async def set_permission_mode(self, mode: str) -> None:
        self.permission_mode = check_mode(mode)

    async def set_model(self, model: str) -> None:
        self.requested_model = model                 # the rest of the turn (and later turns) report this model

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

    def _remembered(self) -> list[str]:
        """Allow rules from always_allow: this session's, plus project-local ones (read back in project setup,
        like Claude loading .claude/settings.local.json)."""
        local = _LOCAL_RULES.get(_cwd_key(self.agent.cwd), []) if self.agent.setup == "project" else []
        return self._session_rules + local

    @staticmethod
    def _default_suggestions(name: str, args: dict) -> list[PermissionSuggestion]:
        """What Claude typically offers: a command-prefix rule for shell tools (project local), "allow all edits
        this session" (set_mode accept_edits) for edit tools, else the whole tool (project local)."""
        if name in rules.SHELL_TOOLS:
            first = str(args.get("command", "")).strip().split(" ")[0]
            return [PermissionSuggestion("add_rules", [f"{name}({first}:*)" if first else name], "allow",
                                         where="project_local")]
        if name in rules.EDIT_TOOLS:
            return [PermissionSuggestion("set_mode", mode="accept_edits", where="session")]
        return [PermissionSuggestion("add_rules", [name], "allow", where="project_local")]

    async def _ask(self, req: PermissionRequest):
        d = self.agent.on_permission(req)
        if inspect.isawaitable(d):
            d = await d
        return resolve(d)

    async def _plan(self, args: dict, cid: str | None) -> tuple[str, bool]:
        """ExitPlanMode: the plan goes to on_permission (kind "plan"); allow leaves plan mode, deny keeps it."""
        if self.permission_mode != "plan":
            return "(fake) not in plan mode: there is no plan to approve.", True
        if self.agent.on_permission is None:
            return f"{PLAN_TOOL} is not allowed for this agent.", True
        d = await self._ask(PermissionRequest(agent=self.agent.name, tool=PLAN_TOOL, input=dict(args), kind="plan",
                                              plan=str(args.get("plan") or ""), mode=self.permission_mode,
                                              call_id=cid))
        if d.decision == "deny":
            fb = " " + prompt_files.fill("plan_feedback", feedback=d.message) if d.message else ""
            return prompt_files.fill("plan_rejected", feedback=fb), True
        self.permission_mode = d.mode or PLAN_APPROVED_MODE
        return f"(fake) the user approved the plan; permission mode is now {self.permission_mode}", False

    async def _builtin(self, name: str, args: dict, cid: str | None = None,
                       suggestions: list | None = None) -> tuple[str, bool]:
        if name == PLAN_TOOL:
            return await self._plan(args, cid)
        a, cwd = self.agent, self.agent.cwd or os.getcwd()
        mode = self.permission_mode
        if rules.denied(list(a.disallowed_tools), name, args, cwd):
            return f"{name} is denied for this agent.", True
        gated = name in self.resolved.gated            # gated_tools: offered, never pre-approved
        plan_edit = mode == "plan" and name in rules.EDIT_TOOLS    # plan: edits always go to on_permission
        allowed = not plan_edit and (
            (mode == "accept_edits" and rules.accept_edits_allows(name, args, cwd, a.add_dirs))
            or rules.allowed(self._remembered(), name, args, cwd)
            or (not gated and (self.resolved.all_builtins
                               or rules.allowed(self.resolved.approved_rules, name, args, cwd))))
        if not allowed:
            if mode == "never_ask":
                return f"{name} is not allowed for this agent (never_ask: not pre-approved).", True
            if a.on_permission is None:
                return f"{name} is not allowed for this agent.", True
            offered = self._default_suggestions(name, args) if suggestions is None else list(suggestions)
            d = await self._ask(PermissionRequest(agent=a.name, tool=name, input=dict(args), suggestions=offered,
                                                  mode=mode, call_id=cid))
            if d.decision == "deny":
                fb = " " + prompt_files.fill("plan_feedback", feedback=d.message) if d.message else ""
                return prompt_files.fill("permission_denied", tool=name, feedback=fb), True
            if d.decision == "always_allow":
                self._remember(name, d, offered)
            if d.mode is not None:
                self.permission_mode = d.mode
            if d.input is not None:                   # allowed with a changed input: show what ran
                return f"(fake) ran {name} with {json.dumps(d.input, ensure_ascii=False, default=str)}", False
        return f"(fake) ran {name}", False

    def _remember(self, name: str, d, offered: list[PermissionSuggestion]) -> None:
        """Same choice as the Claude engine: rules given, else (project_local) the suggested allow rules, else
        the whole tool. Session rules apply to this session; project-local ones also to later project sessions."""
        if d.rules is not None:
            new = list(d.rules)
        elif d.remember == "project_local":
            new = [r for s in offered if s.kind == "add_rules" and (s.behavior or "allow") == "allow" for r in s.rules]
        else:
            new = []
        new = new or [name]
        if d.remember == "project_local":
            saved = _LOCAL_RULES.setdefault(_cwd_key(self.agent.cwd), [])
            saved.extend(r for r in new if r not in saved)
        self._session_rules.extend(r for r in new if r not in self._session_rules)

    @staticmethod
    def _usage(message: str, out_chars: int) -> Usage:
        return Usage(input_tokens=max(1, len(message) // 4), output_tokens=out_chars // 4)

    async def turn(self, message: str):
        if self._killed:
            raise AgentError(f"{KILLED}; open a new session")
        self._connect()
        self._busy = True
        try:
            async for ev in self._turn(message):
                yield ev
        finally:
            self._busy = False

    async def _turn(self, message: str):
        rec = self._rec
        if self._info == SessionInfo():
            self._info = self._startup_info()         # Claude reports init at the start of the first turn
        steps = self._steps(message)
        rec["turn"] += 1
        rec["messages"].append(message)
        state = TurnState("fake", self.resolved.custom, model_turn=self._model_turns)
        base_turn = self._model_turns
        model = self.requested_model or self.agent.model or "fake"
        cap = self.agent.max_budget_usd
        out_chars = 0
        spent = 0.0                                   # spend() steps this turn
        structured_data = None
        error = kind = None
        open_turn: int | None = None                  # model reply in progress; None = next say/call opens one
        replies: list[dict] = []                      # per model reply: n, model, chars, scripted usage

        def open_reply() -> int:
            n = state.next_model_turn()
            self._model_turns = n                     # kept even if the turn fails or is abandoned midway
            replies.append({"n": n, "model": self.requested_model or self.agent.model or "fake", "chars": 0,
                            "usage": None})
            return n

        def add_tokens(u: Usage | None) -> None:
            if u is not None:
                r = replies[-1]
                r["usage"] = u if r["usage"] is None else r["usage"] + u

        def split() -> tuple[Usage, list[TurnUsage]]:
            """(Reply.usage, Reply.turn_usage). Default: the turn's estimate split over its replies (input on the
            first, each reply's text chars // 4 as output, the rest of the output on the last), so they add up.
            Once any reply has scripted usage=, those replies use it and Reply.usage is the sum of all replies."""
            total = self._usage(message, out_chars)
            per = []
            for i, r in enumerate(replies):
                per.append(Usage(input_tokens=total.input_tokens if i == 0 else 0, output_tokens=r["chars"] // 4))
            if per:
                per[-1].output_tokens += total.output_tokens - sum(u.output_tokens for u in per)
            if any(r["usage"] is not None for r in replies):
                per = [r["usage"] if r["usage"] is not None else u for r, u in zip(replies, per)]
                total = reduce(lambda a, b: a + b, per, Usage())
            return total, [TurnUsage(r["n"], Usage(**vars(u)), r["model"]) for r, u in zip(replies, per)]

        for step in steps:
            if self._killed:                          # kill() between steps: the turn fails like Claude's
                so_far, per_turn = split()
                raise AgentError(KILLED, reply=state.reply(
                    session_id=self.session_id, usage=so_far, turn_usage=per_turn, cost_usd=0.0,
                    total_cost_usd=self._cost_base, model=model, error=KILLED,
                    api_calls=max(1, state.model_turn - base_turn)))
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
                so_far, per_turn = split()
                partial = state.reply(session_id=self.session_id, usage=so_far, turn_usage=per_turn,
                                      cost_usd=0.0, total_cost_usd=self._cost_base, model=model,
                                      error=step.message, api_calls=max(1, state.model_turn - base_turn))
                raise AgentError(step.message, reply=partial)
            if isinstance(step, RateLimitStep):
                yield RateLimit(status=step.status, utilization=step.utilization, limit_type="five_hour")
                continue
            if not isinstance(step, (Say, Call, Parallel)):
                continue
            if open_turn is None:
                open_turn = open_reply()
            group = step.steps if isinstance(step, Parallel) else [step]
            if isinstance(step, Parallel):
                add_tokens(step.usage)
            for s in group:
                add_tokens(s.usage)
                if isinstance(s, Say):
                    for word in s.text.split(" "):
                        yield TextDelta(word + " ")
                    state.record_text(s.text)
                    out_chars += len(s.text)
                    replies[-1]["chars"] += len(s.text)
                    yield Text(s.text, model_turn=open_turn)
            calls = [(f"fake-{uuid.uuid4().hex[:8]}", s) for s in group if isinstance(s, Call)]
            for cid, c in calls:                      # every call of the reply is issued before any runs
                state.record_call(cid, c.tool, c.args, model_turn=open_turn)
                yield ToolCall(cid, c.tool, dict(c.args), model_turn=open_turn)
            for cid, c in calls:
                text, err = await self._run_call(state, c, cid)
                state.record_result(cid, text, err)
                yield ToolResult(cid, c.tool, text, err, model_turn=open_turn)
            if calls:
                open_turn = None                      # tool results go back: the next say/call is a new reply
                if state.stop_requested:
                    break
        model = self.requested_model or self.agent.model or "fake"   # a mid-turn set_model counts
        usage, per_turn = split()
        if self._killed:
            raise AgentError(KILLED, reply=state.reply(
                session_id=self.session_id, usage=usage, turn_usage=per_turn, cost_usd=0.0,
                total_cost_usd=self._cost_base, model=model, error=KILLED,
                api_calls=max(1, state.model_turn - base_turn)))
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
        yield Done(state.reply(session_id=self.session_id, usage=usage, turn_usage=per_turn, cost_usd=cost,
                               total_cost_usd=total, model=model, stop_reason="end_turn",
                               api_calls=max(1, state.model_turn - base_turn),
                               error=error, error_kind=kind, data=data))

    async def _run_call(self, state: TurnState, c: Call, cid: str) -> tuple[str, bool]:
        """Run one scripted call: a custom tool / ask_user through TurnState, a built-in through the rules."""
        if c.tool in state.tools:
            return await state.run_tool(c.tool, c.args)
        if c.tool[:1].isupper():
            return await self._builtin(c.tool, c.args, cid, c.suggestions)
        return f"error: unknown tool '{c.tool}'", True
