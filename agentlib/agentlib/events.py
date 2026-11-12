"""The six live events every engine emits while a turn runs (session.stream()).

- text_delta  live text as it is typed (top-level agent only)
- text        a finished block of text
- tool_call   the agent called a tool (short name: "ask_user", not "mcp__agentlib__ask_user")
- tool_result what the tool returned
- rate_limit  usage-limit status (status, resets_at, utilization, limit_type)
- done        the turn is over; carries the final Reply
Each event has `.type` (the string above) so a UI can switch on it or send it as JSON (to_dict()).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar, Union

from .reply import Reply


@dataclass
class _Event:
    type: ClassVar[str] = ""

    def to_dict(self) -> dict:
        return {"type": self.type, **asdict(self)}


@dataclass
class TextDelta(_Event):
    type: ClassVar[str] = "text_delta"
    text: str


@dataclass
class Text(_Event):
    type: ClassVar[str] = "text"
    text: str


@dataclass
class ToolCall(_Event):
    type: ClassVar[str] = "tool_call"
    id: str
    name: str
    input: dict = field(default_factory=dict)


@dataclass
class ToolResult(_Event):
    type: ClassVar[str] = "tool_result"
    id: str
    name: str
    text: str
    is_error: bool = False


@dataclass
class RateLimit(_Event):
    type: ClassVar[str] = "rate_limit"
    status: str                       # allowed | allowed_warning | rejected
    resets_at: Any = None
    utilization: float | None = None
    limit_type: str | None = None     # five_hour | seven_day | ...


@dataclass
class Done(_Event):
    type: ClassVar[str] = "done"
    reply: Reply

    def to_dict(self) -> dict:
        return {"type": self.type, "reply": self.reply.to_dict()}


Event = Union[TextDelta, Text, ToolCall, ToolResult, RateLimit, Done]
