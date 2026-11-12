"""What every engine implements, plus the per-turn bookkeeping they share.

- Engine.open(agent, resume, fork, cost_base) -> EngineSession (start / turn / interrupt / close)
- EngineSession.turn(message) is an async generator of events (events.py) ending with Done(reply)
- Capabilities: what the engine can do; Engine.check() raises EngineUnavailable (engine cannot run at all) or
  CapabilityError (agent needs something the engine lacks) before a run
- TurnState: runs custom tools + ask_user the same way on every engine and builds the Reply
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import reduce
from typing import AsyncIterator

from .. import prompt_files
from ..errors import CapabilityError, EngineUnavailable, QuestionShapeError
from ..events import Event
from ..questions import Question, parse_questions
from ..reply import Reply, Status, ToolCallRecord, Usage
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
    }


class EngineSession(ABC):
    session_id: str | None = None

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


class TurnState:
    """One turn's bookkeeping. Engines call run_tool() for custom tools, record_* for what they observe."""

    def __init__(self, engine: str, tools: list[Tool]):
        self.engine = engine
        self.tools = {t.name: t for t in tools}
        self.t0 = time.monotonic()
        self.texts: list[str] = []
        self.calls: dict[str, ToolCallRecord] = {}
        self.questions: list[Question] = []
        self.stop_requested = False
        self.message_ids: set[str] = set()
        self.usage_by_message: dict[str, Usage] = {}   # latest usage seen per model call (for failure replies)

    def usage_so_far(self) -> Usage:
        """Best-effort usage of the model calls seen this turn (used when a turn fails before its result)."""
        return reduce(lambda a, b: a + b, self.usage_by_message.values(), Usage())

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

    def record_call(self, call_id: str, name: str, inp: dict) -> None:
        self.calls[call_id] = ToolCallRecord(id=call_id, name=name, input=dict(inp or {}))

    def record_result(self, call_id: str, text: str, is_error: bool) -> str:
        rec = self.calls.get(call_id)
        if rec is None:
            return "?"
        rec.result, rec.is_error = text, is_error
        return rec.name

    def reply(self, *, session_id: str | None, usage: Usage, cost_usd: float = 0.0, total_cost_usd: float = 0.0,
              model: str | None = None, stop_reason: str | None = None, error: str | None = None,
              api_calls: int | None = None) -> Reply:
        status: Status = "error" if error else ("needs_input" if self.questions else "done")
        return Reply(status=status, text="\n\n".join(self.texts), questions=list(self.questions),
                     session_id=session_id, usage=usage, cost_usd=round(cost_usd, 6),
                     total_cost_usd=round(total_cost_usd, 6), tool_calls=list(self.calls.values()),
                     api_calls=api_calls if api_calls is not None else len(self.message_ids),
                     duration_s=round(time.monotonic() - self.t0, 2), engine=self.engine, model=model,
                     stop_reason=stop_reason, error=error)
