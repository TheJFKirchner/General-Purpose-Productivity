"""A conversation with one agent (any engine).

- async with agent.session() as s:
    reply = await s.send("...")                  # wait for the finished Reply
    async for ev in s.stream("..."): ...         # or watch live events (events.py); last one is Done
    reply = await s.answer({"trend_years": "Last 3 years"})   # after reply.status == "needs_input"
- s.session_id: save it to resume later (agent.session(resume=id))
- s.pending_questions: open ask_user questions; answer() needs them (pass questions= after a restart)
- s.permission_mode / await s.set_permission_mode("accept_edits"): read / change the permission mode live
- s.info: SessionInfo (tools offered, MCP server status, model) as the engine reported it at startup;
  empty until the first turn has started (the Claude CLI reports it at the start of the first turn)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, AsyncIterator

from .errors import AgentError
from .events import Done, Event
from .questions import Question, format_answers, parse_answers, questions_from_dicts
from .reply import Reply


@dataclass
class SessionInfo:
    """What the engine says it set up for this conversation. Same shape on every engine."""
    tools: list[str] = field(default_factory=list)            # offered to the model; custom tools by short name
    mcp_servers: dict[str, str] = field(default_factory=dict)  # server name -> status ("connected", "failed", ...)
    model: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Session:
    def __init__(self, agent, engine_session):
        self.agent = agent
        self._es = engine_session
        self.pending_questions: list[Question] = []
        self.last_reply: Reply | None = None

    @property
    def session_id(self) -> str | None:
        return self._es.session_id

    @property
    def info(self) -> SessionInfo:
        return self._es.info

    @property
    def permission_mode(self) -> str:
        """Current permission mode: "default" | "never_ask" | "accept_edits" | "plan". Follows
        set_permission_mode() and plan approvals (approved -> the mode the app chose)."""
        return self._es.permission_mode or self.agent.permission_mode

    async def set_permission_mode(self, mode: str) -> None:
        """Change the permission mode for the rest of this conversation (also mid-turn; next tool call uses it).
        ValueError for an unknown mode; CapabilityError if the engine cannot switch or cannot run that mode."""
        from .engines import get_engine
        from .engines.base import check_mode_switch
        eng = get_engine(self.agent.engine)
        check_mode_switch(eng.name or self.agent.engine, eng.capabilities, mode)
        await self._es.set_permission_mode(mode)

    @property
    def model(self) -> str | None:
        """The model this conversation uses now (after set_model), else the agent's."""
        return getattr(self._es, "requested_model", None) or self.agent.model

    async def set_model(self, model: str) -> None:
        """Change the model for the rest of this conversation: between turns, or mid-turn (the next model call
        uses it). The conversation carries over; the new model writes it to its own prompt cache once.
        CapabilityError if the engine cannot switch models."""
        from .engines import get_engine
        from .errors import CapabilityError
        eng = get_engine(self.agent.engine)
        if not eng.capabilities.model_switch:
            raise CapabilityError(f"engine '{eng.name}' cannot do: model_switch")
        if not str(model or "").strip():
            raise ValueError("give a model (alias or id)")
        await self._es.set_model(str(model).strip())

    async def __aenter__(self) -> "Session":
        await self._es.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._es.close()

    async def interrupt(self) -> None:
        await self._es.interrupt()

    async def stream(self, message: str) -> AsyncIterator[Event]:
        async for ev in self._es.turn(message):
            if isinstance(ev, Done):
                self.last_reply = ev.reply
                self.pending_questions = list(ev.reply.questions)
            yield ev

    async def send(self, message: str) -> Reply:
        reply = None
        async for ev in self.stream(message):
            if isinstance(ev, Done):
                reply = ev.reply
        if reply is None:
            raise AgentError("turn ended without a reply")
        return reply

    def _answer_message(self, answers: Any, questions: list | None) -> str:
        qs = questions_from_dicts(questions) if questions is not None else self.pending_questions
        if not qs:
            raise AgentError("no open questions to answer (pass questions= when resuming after a restart)")
        return format_answers(parse_answers(answers, qs))

    async def answer(self, answers: Any, *, questions: list | None = None) -> Reply:
        """answers: {id: "text"} | [Answer | {id, answer, kind}] | {"answers": [...]}. Unanswered ids -> skipped."""
        return await self.send(self._answer_message(answers, questions))

    async def answer_stream(self, answers: Any, *, questions: list | None = None) -> AsyncIterator[Event]:
        async for ev in self.stream(self._answer_message(answers, questions)):
            yield ev
