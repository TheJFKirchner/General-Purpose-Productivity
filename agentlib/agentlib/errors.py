"""Errors the library raises.

- AgentError: base; `.short` = one line for the UI
- `.reply`: when a turn fails midway (timeout, process died, stream cut), the partial Reply for that turn:
  status "error", text and tool calls seen so far, usage summed (best effort) from the model calls seen,
  cost_usd 0.0 (cost only arrives with the final result), total_cost_usd = last known total.
  None when nothing ran (start-up failures, resume misses, capability checks)
- Raised for infrastructure failures (process died, timeout, no sign-in). A model run that ends badly
  (max turns, budget) comes back as Reply(status="error") instead, so usage is not lost.
"""
from __future__ import annotations


class AgentError(RuntimeError):
    def __init__(self, message: str, detail: str = "", reply=None):
        super().__init__(f"{message}\n{detail}".strip())
        self.short = message
        self.reply = reply


class ConversationMissing(AgentError):
    """resume=<id> found no saved conversation (wrong id, or a different cwd)."""


class EngineUnavailable(AgentError):
    """The engine exists in name only (e.g. cursor) or its package is not installed."""


class CapabilityError(AgentError):
    """The agent needs something its engine cannot do (see engine.capabilities)."""


class SetupError(AgentError):
    """The local setup file (setup/local.toml) is broken or points at something missing. The message says what
    to fix; nothing was sent."""


class AgentFileError(AgentError):
    """An agent .md file is missing, unreadable, or lists a tool with no implementation."""


class QuestionShapeError(ValueError):
    """ask_user questions or answers don't match the shared shape (questions.py)."""
