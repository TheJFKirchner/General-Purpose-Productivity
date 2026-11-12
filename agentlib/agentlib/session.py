"""A conversation with one agent (any engine).

- async with agent.session() as s:
    reply = await s.send("...")                  # wait for the finished Reply
    async for ev in s.stream("..."): ...         # or watch live events (events.py); last one is Done
    reply = await s.answer({"trend_years": "Last 3 years"})   # after reply.status == "needs_input"
- s.session_id: save it to resume later (agent.session(resume=id))
- s.pending_questions: open ask_user questions; answer() needs them (pass questions= after a restart)
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
