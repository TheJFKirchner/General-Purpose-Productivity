"""What a finished turn returns.

- Reply.status: done | needs_input (agent called ask_user; see .questions) | error (run ended badly, see .error)
- Usage: per-turn tokens, same field names on every engine; `a + b` adds them up
- cost_usd is this turn only; total_cost_usd is the conversation's running total (an estimate on a subscription)
- error_kind (only when status == "error"): why it ended badly, same values on every engine:
  "budget" (Agent.max_budget_usd reached), "max_turns" (Agent.max_turns reached), "output_shape" (the reply did
  not match Agent.output_schema), "other" (anything else: model/API error, a failed turn in AgentError.reply)
- data: the parsed, schema-checked JSON reply when the agent has output_schema (None otherwise or on error)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

from .questions import Question

Status = Literal["done", "needs_input", "error"]
ErrorKind = Literal["budget", "max_turns", "output_shape", "other"]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(**{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)})

    @property
    def total_input_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens


@dataclass
class ToolCallRecord:
    id: str
    name: str
    input: dict = field(default_factory=dict)
    result: str | None = None
    is_error: bool = False


@dataclass
class Reply:
    status: Status = "done"
    text: str = ""
    questions: list[Question] = field(default_factory=list)
    session_id: str | None = None
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    api_calls: int = 0
    duration_s: float = 0.0
    engine: str = ""
    model: str | None = None
    stop_reason: str | None = None
    error: str | None = None
    error_kind: ErrorKind | None = None      # set only when status == "error" (see module docstring)
    data: Any = None                         # parsed JSON reply when Agent.output_schema is set

    def to_dict(self) -> dict:
        return asdict(self)
