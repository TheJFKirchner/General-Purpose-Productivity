"""agentlib: define an agent once, run it on Claude (Agent SDK) now and Cursor later. See README.md.

    from agentlib import Agent, tool, load_claude_agent

    @tool
    def run_sql(query: str) -> str:
        "Run a read-only SQL query."
        ...

    agent = load_claude_agent("trend_reporter", tools=[run_sql])   # .claude/agents/trend_reporter.md
    reply = agent.ask_sync("Build the trend report")
    if reply.status == "needs_input": ...                          # reply.questions
"""
from .agent import Agent
from .auth import use_login_only
from .engines import get_engine, register_engine
from .errors import (AgentError, AgentFileError, CapabilityError, ConversationMissing, EngineUnavailable,
                     QuestionShapeError)
from .events import Done, Event, RateLimit, Text, TextDelta, ToolCall, ToolResult
from .loaders import load_claude_agent, load_cursor_agent
from .permissions import PermissionRequest
from .questions import Answer, Question
from .reply import Reply, ToolCallRecord, Usage
from .session import Session, SessionInfo
from .tools import Tool, tool

__all__ = [
    "Agent", "Session", "SessionInfo", "Reply", "Usage", "ToolCallRecord", "Tool", "tool",
    "load_claude_agent", "load_cursor_agent", "Question", "Answer", "PermissionRequest",
    "Event", "TextDelta", "Text", "ToolCall", "ToolResult", "RateLimit", "Done",
    "AgentError", "AgentFileError", "CapabilityError", "ConversationMissing", "EngineUnavailable",
    "QuestionShapeError", "get_engine", "register_engine", "use_login_only",
]
