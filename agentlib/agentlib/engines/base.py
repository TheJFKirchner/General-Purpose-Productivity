"""What every engine implements, plus the per-turn bookkeeping they share.

- Engine.open(agent, resume, fork, cost_base) -> EngineSession (start / turn / interrupt / close)
- EngineSession.turn(message) is an async generator of events (events.py) ending with Done(reply)
- EngineSession.set_permission_mode(mode) (capability mode_switch; default raises CapabilityError) and
  .permission_mode (current mode); Session checks check_mode_switch() first
- Capabilities: what the engine can do; Engine.check() raises EngineUnavailable (engine cannot run at all) or
  CapabilityError (agent needs something the engine lacks) before a run
- TurnState: runs custom tools + ask_user the same way on every engine and builds the Reply
- Engine.list_models(env=, timeout_s=) -> list[ModelInfo] (no request sent); default raises CapabilityError
- EngineSession.pid (OS process, default None) and kill(timeout_s=) -> KillResult (end the process tree, then
  closed; default raises CapabilityError): capability process_control, checked by Session.kill()
- EngineSetup: how a user connects an engine (sign-in), read from that engine's section of the local setup file
  (local_setup.py). SDK-free, so status works even when the engine's package is missing. -> Connection
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path
from typing import AsyncIterator

from .. import prompt_files
from ..errors import CapabilityError, EngineUnavailable, QuestionShapeError
from ..events import Event
from ..questions import Question, parse_questions
from ..reply import Reply, Status, ToolCallRecord, TurnUsage, Usage
from ..session import SessionInfo
from ..tools import Tool


@dataclass(frozen=True)
class Capabilities:
    available: bool = True        # False = stub, cannot run yet (check() raises EngineUnavailable)
    system_prompt: bool = True    # app-set instructions (Cursor: no, uses AGENTS.md)
    custom_tools: bool = True     # library-served tools (@tool functions, ask_user)
    mcp_servers: bool = True      # Agent.mcp_servers (external servers)
    streaming: bool = True        # informational: TextDelta events (not enforced; events still arrive)
    resume: bool = True
    fork: bool = False
    usage: bool = True            # informational: real token counts in Reply.usage (not enforced)
    ends_turn: bool = True        # stop right after a tool (needed for ask_user parking)
    permission_hook: bool = False # live Allow/Deny for tools not pre-approved
    project_setup: bool = True    # setup="project"
    budget: bool = False          # Agent.max_budget_usd: stop a run at a spending cap (Reply.error_kind "budget")
    never_ask: bool = False       # Agent.permission_mode="never_ask": deny anything not pre-approved, never ask
    structured_output: bool = False   # Agent.output_schema: JSON reply checked against a schema -> Reply.data
    unsaved: bool = False         # Agent.save_conversation=False: the conversation is not stored (cannot resume)
    list_models: bool = False     # Engine.list_models(): models on offer, without a request
    accept_edits: bool = False    # permission mode "accept_edits": edits inside the working folders run unasked
    plan_mode: bool = False       # permission mode "plan": explore + propose a plan (on_permission kind "plan")
    mode_switch: bool = False     # Session.set_permission_mode(): change the permission mode on a live session
    engine_prompt: bool = False   # Agent.engine_prompt: the engine's own agent prompt + instructions, in lean setup
    project_rules: bool = False   # Agent.project_rules: caller-supplied project rules text given to a lean agent
    model_switch: bool = False    # Session.set_model(): change the model on a live session (between turns or mid-turn)
    model_turns: bool = False     # informational: Text / ToolCall / ToolResult carry model_turn (else None; not enforced)
    turn_usage: bool = False      # informational: Reply.turn_usage has tokens per model reply (else empty; not enforced)
    process_control: bool = False # Session.pid (the OS process the session runs in) + Session.kill() (end it and
                                  # everything it started); checked by Session.kill(), not per agent


def requirements(agent, *, fork: bool = False, resume: bool = False) -> dict[str, bool]:
    """Capability name -> does this agent / session request need it. Engine.check() enforces these."""
    custom = agent.resolved_tools().custom
    return {
        "system_prompt": bool(agent.instructions.strip()) or (agent.setup == "lean" and bool(agent.skills)),
        "custom_tools": bool(custom),
        "ends_turn": any(t.ends_turn for t in custom),          # ask_user and @tool(ends_turn=True)
        "mcp_servers": bool(agent.mcp_servers),
        "resume": resume,
        "fork": fork,
        "permission_hook": agent.on_permission is not None,
        "project_setup": agent.setup == "project",
        "budget": agent.max_budget_usd is not None,
        "never_ask": agent.permission_mode == "never_ask",
        "accept_edits": agent.permission_mode == "accept_edits",
        "plan_mode": agent.permission_mode == "plan",
        "structured_output": agent.output_schema is not None,
        "unsaved": not agent.save_conversation,
        "engine_prompt": bool(getattr(agent, "engine_prompt", False)) and agent.setup == "lean",
        "project_rules": agent.rules_text() is not None,         # lean + non-blank text (project setup ignores it)
    }


MODE_CAPABILITY = {"never_ask": "never_ask", "accept_edits": "accept_edits", "plan": "plan_mode"}


def check_mode_switch(engine_name: str, caps: Capabilities, mode: str) -> None:
    """Session.set_permission_mode(mode) guard: valid mode, engine can switch and can run that mode."""
    from ..permissions import check_mode
    check_mode(mode)
    missing = [] if caps.mode_switch else ["mode_switch"]
    need = MODE_CAPABILITY.get(mode)
    if need and not getattr(caps, need):
        missing.append(need)
    if missing:
        raise CapabilityError(f"engine '{engine_name}' cannot do: {', '.join(missing)} (set_permission_mode({mode!r}))")


class EngineSession(ABC):
    session_id: str | None = None
    permission_mode: str | None = None     # current permission mode (engines that track it set this)

    @property
    def info(self) -> SessionInfo:
        """Startup info (tools offered, MCP servers, model). Engines that report it override this."""
        return SessionInfo()

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    def turn(self, message: str) -> AsyncIterator[Event]: ...

    async def interrupt(self) -> None:
        return None

    async def set_permission_mode(self, mode: str) -> None:
        """Change the permission mode for the rest of this conversation (capability mode_switch)."""
        raise CapabilityError(f"engine session {type(self).__name__} cannot do: mode_switch")

    async def set_model(self, model: str) -> None:
        """Change the model for the rest of this conversation (capability model_switch)."""
        raise CapabilityError(f"engine session {type(self).__name__} cannot do: model_switch")

    @property
    def pid(self) -> int | None:
        """The OS process this session runs in, while it runs (capability process_control); None = no process
        (not connected yet, closed) or the engine cannot tell."""
        return None

    @property
    def process_started_at(self) -> float | None:
        """Start time of `pid` as recorded when the process started (seconds since the epoch); None whenever
        pid is None. Engines with process_control record it together with the pid."""
        return None

    async def kill(self, *, timeout_s: float = 3.0):
        """End this session's process and everything it started, then close the session (capability
        process_control). Must work mid-turn and half-closed, and be safe to call twice. -> processes.KillResult"""
        raise CapabilityError(f"engine session {type(self).__name__} cannot do: process_control")

    @abstractmethod
    async def close(self) -> None: ...


class Engine(ABC):
    name: str = ""
    capabilities: Capabilities = Capabilities()

    @abstractmethod
    def open(self, agent, *, resume: str | None, fork: bool, cost_base: float) -> EngineSession: ...

    def check(self, agent, *, fork: bool = False, resume: bool = False) -> None:
        """Called by Agent.session() before open(). EngineUnavailable if the engine cannot run at all
        (capabilities.available False); else CapabilityError naming every capability the agent needs and lacks."""
        c = self.capabilities
        need = requirements(agent, fork=fork, resume=resume)
        missing = [k for k, wanted in need.items() if wanted and not getattr(c, k)]
        if not c.available:
            also = f"; it would also lack: {', '.join(missing)}" if missing else ""
            raise EngineUnavailable(f"engine '{self.name}' cannot run yet (capabilities.available is False; "
                                    f"agent '{agent.name}'){also}")
        if missing:
            raise CapabilityError(f"engine '{self.name}' cannot do: {', '.join(missing)} (agent '{agent.name}')")

    def check_list_models(self) -> None:
        """Called by agentlib.list_models() before list_models()."""
        if not self.capabilities.available:
            raise EngineUnavailable(f"engine '{self.name}' cannot run yet (capabilities.available is False)")
        if not self.capabilities.list_models:
            raise CapabilityError(f"engine '{self.name}' cannot do: list_models")

    async def list_models(self, *, env: dict[str, str], timeout_s: float | None) -> list:
        """-> list[agentlib.models.ModelInfo]. Engines with capabilities.list_models override this."""
        raise CapabilityError(f"engine '{self.name}' cannot do: list_models")


@dataclass
class Connection:
    """How this user connects an engine, resolved from the local setup file. Secret values live only in `env` /
    `engine_settings` (kept out of repr); everything else is safe to show."""
    engine: str
    method: str                       # engine-defined short name, e.g. "login", "settings-file", "env"
    summary: str                      # plain language, names only, never values
    env: dict[str, str] = field(default_factory=dict, repr=False)            # added to the engine process env
    engine_settings: dict = field(default_factory=dict, repr=False)          # engine-specific (Claude: --settings)
    problems: list[str] = field(default_factory=list)                        # each says what to fix
    notes: list[str] = field(default_factory=list)                           # hints, not errors


class EngineSetup:
    """Sign-in side of an engine. One per engine name (engines.register_setup). Must not import the engine SDK.

    - doc: setup guide, relative to the agentlib folder (e.g. "setup/claude-setup.md")
    - section_keys: keys allowed in the engine's [section] of the local setup file (others -> problem)
    - check_model: cheapest model, used by check_connection()
    - resolve(section, base=) -> Connection (problems listed, not raised)
    - prerequisites() -> problems with the installation (package / program missing)
    - version() -> one line for the check command; fix_for(error) -> plain-language fix for a failed check
    """
    doc: str | None = None
    section_keys: tuple[str, ...] = ()
    check_model: str | None = None

    def __init__(self, name: str):
        self.name = name

    def resolve(self, section: dict, *, base: Path | None = None) -> Connection:
        unknown = sorted(set(section) - set(self.section_keys))
        problems = [f"[{self.name}] has unknown setting(s) {', '.join(unknown)}; this engine has nothing to set up"] \
            if unknown else []
        return Connection(self.name, "default", "nothing to set up", problems=problems)

    def prerequisites(self) -> list[str]:
        return []

    def version(self) -> str:
        return ""

    def fix_for(self, error: str) -> str | None:
        return None


class TurnState:
    """One turn's bookkeeping. Engines call run_tool() for custom tools, record_* for what they observe."""

    def __init__(self, engine: str, tools: list[Tool], model_turn: int = 0):
        self.engine = engine
        self.tools = {t.name: t for t in tools}
        self.t0 = time.monotonic()
        self.texts: list[str] = []
        self.calls: dict[str, ToolCallRecord] = {}
        self.questions: list[Question] = []
        self.stop_requested = False
        self.message_ids: set[str] = set()
        self.usage_by_message: dict[str, Usage] = {}   # usage per model call, largest seen (record_usage())
        self._model_by_message: dict[str, str] = {}
        self._turn_usage: dict[int, TurnUsage] = {}    # set_turn_usage(): engines without per-reply keys
        # model_turn: number of the latest model reply in the session (0 = none yet). The engine session passes
        # the count it reached last turn and reads state.model_turn back afterwards, so numbers run on.
        self.model_turn = model_turn
        self._turn_base = model_turn
        self._turn_by_key: dict[str, int] = {}
        self._results_since_reply = False

    def next_model_turn(self) -> int:
        """A new model reply starts: returns its number (1, 2, 3, ... over the session)."""
        self.model_turn += 1
        self._results_since_reply = False
        return self.model_turn

    def model_turn_for(self, key: str | None) -> int:
        """The model reply an engine message belongs to. key = the engine's id for one model reply (Claude:
        AssistantMessage.message_id, shared by every block of that reply): same key -> same number, a new key ->
        the next number. No key: a new reply only if tool results arrived since the last one (best effort)."""
        if key is not None:
            if key not in self._turn_by_key:
                self._turn_by_key[key] = self.next_model_turn()
            return self._turn_by_key[key]
        if self.model_turn == self._turn_base or self._results_since_reply:
            return self.next_model_turn()
        return self.model_turn

    def call_turn(self, call_id: str) -> int | None:
        """model_turn of a recorded call (for its ToolResult), None if unknown."""
        rec = self.calls.get(call_id)
        return rec.model_turn if rec else None

    def usage_so_far(self) -> Usage:
        """Best-effort usage of the model calls seen this turn (used when a turn fails before its result)."""
        return reduce(lambda a, b: a + b, self.usage_by_message.values(), Usage())

    def record_usage(self, key: str, usage: Usage, model: str | None = None) -> None:
        """Usage reported for one model call (key = the same per-reply id given to model_turn_for()). The same
        call may be reported several times (once per content block, or while it streams): counts only grow, so
        each field keeps the largest figure seen and repeats are never added together."""
        old = self.usage_by_message.get(key)
        self.usage_by_message[key] = usage if old is None else \
            Usage(**{f: max(getattr(old, f), getattr(usage, f)) for f in vars(usage)})
        if model:
            self._model_by_message[key] = model

    def set_turn_usage(self, model_turn: int, usage: Usage, model: str | None = None) -> None:
        """Usage of one model reply by its number (engines that number replies themselves, e.g. the fake)."""
        self._turn_usage[model_turn] = TurnUsage(model_turn, usage, model)

    def turn_usage(self) -> list[TurnUsage]:
        """Tokens per model reply this turn, in model_turn order: set_turn_usage() entries, plus record_usage()
        calls whose key was numbered by model_turn_for(). Calls never numbered (no event seen) are left out."""
        out = dict(self._turn_usage)
        for key, u in self.usage_by_message.items():
            n = self._turn_by_key.get(key)
            if n is None:
                continue
            prev = out.get(n)
            out[n] = TurnUsage(n, u if prev is None else prev.usage + u,
                               self._model_by_message.get(key) or (prev.model if prev else None))
        return [out[n] for n in sorted(out)]

    async def run_tool(self, name: str, args: dict) -> tuple[str, bool]:
        t = self.tools.get(name)
        if t is None:
            return f"error: unknown tool '{name}'", True
        if t.builtin == "ask_user":
            try:
                qs = parse_questions(args)
            except QuestionShapeError as e:
                return f"error: {e}. Fix the call and try again.", True
            self.questions.extend(qs)
            self.stop_requested = True
            return prompt_files.fill("ask_user_parked", count=str(len(qs))), False
        text, err = await t.call(args)
        if t.ends_turn and not err:
            self.stop_requested = True
        return text, err

    def record_text(self, text: str) -> None:
        if text.strip():
            self.texts.append(text.strip())

    def record_call(self, call_id: str, name: str, inp: dict, model_turn: int | None = None) -> None:
        self.calls[call_id] = ToolCallRecord(id=call_id, name=name, input=dict(inp or {}), model_turn=model_turn)

    def record_result(self, call_id: str, text: str, is_error: bool) -> str:
        self._results_since_reply = True
        rec = self.calls.get(call_id)
        if rec is None:
            return "?"
        rec.result, rec.is_error = text, is_error
        return rec.name

    def reply(self, *, session_id: str | None, usage: Usage, cost_usd: float = 0.0, total_cost_usd: float = 0.0,
              model: str | None = None, stop_reason: str | None = None, error: str | None = None,
              api_calls: int | None = None, error_kind: str | None = None, data=None,
              usage_by_model: dict | None = None, turn_usage: list[TurnUsage] | None = None) -> Reply:
        """turn_usage None -> self.turn_usage() (what record_usage / set_turn_usage collected); [] = cannot tell."""
        status: Status = "error" if error else ("needs_input" if self.questions else "done")
        kind = (error_kind or "other") if error else None
        return Reply(status=status, text="\n\n".join(self.texts), questions=list(self.questions),
                     session_id=session_id, usage=usage, cost_usd=round(cost_usd, 6),
                     total_cost_usd=round(total_cost_usd, 6), tool_calls=list(self.calls.values()),
                     api_calls=api_calls if api_calls is not None else len(self.message_ids),
                     duration_s=round(time.monotonic() - self.t0, 2), engine=self.engine, model=model,
                     stop_reason=stop_reason, error=error, error_kind=kind, data=None if error else data,
                     usage_by_model=dict(usage_by_model or ({model: {"usage": usage, "cost_usd": round(cost_usd, 6)}}
                                                            if model else {})),
                     turn_usage=list(self.turn_usage() if turn_usage is None else turn_usage))
