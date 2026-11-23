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
from .connection import CheckResult, ConnectionStatus, check_connection, check_connection_sync, connection_status
from .engines import get_engine, register_engine
from .errors import (AgentError, AgentFileError, CapabilityError, ConversationMissing, EngineUnavailable,
                     QuestionShapeError, SetupError)
from .events import Done, Event, RateLimit, Text, TextDelta, ToolCall, ToolResult
from .loaders import load_claude_agent, load_cursor_agent
from .models import ModelInfo, list_models, list_models_sync
from .permissions import PERMISSION_MODES, PermissionDecision, PermissionRequest, PermissionSuggestion
from .processes import (KillResult, ProcessInfo, describe_process, end_process_tree, list_descendants,
                        process_started_at)
from .questions import Answer, Question
from .reply import Reply, ToolCallRecord, TurnUsage, Usage
from .session import Session, SessionInfo
from .structured import ask_structured, ask_structured_sync
from .tools import Tool, tool

__all__ = [
    "Agent", "Session", "SessionInfo", "Reply", "Usage", "TurnUsage", "ToolCallRecord", "Tool", "tool",
    "load_claude_agent", "load_cursor_agent", "Question", "Answer", "PermissionRequest",
    "PermissionDecision", "PermissionSuggestion", "PERMISSION_MODES",
    "Event", "TextDelta", "Text", "ToolCall", "ToolResult", "RateLimit", "Done",
    "AgentError", "AgentFileError", "CapabilityError", "ConversationMissing", "EngineUnavailable",
    "QuestionShapeError", "get_engine", "register_engine", "use_login_only",
    "ModelInfo", "list_models", "list_models_sync", "ask_structured", "ask_structured_sync",
    "SetupError", "ConnectionStatus", "CheckResult", "connection_status", "check_connection", "check_connection_sync",
    "ProcessInfo", "KillResult", "end_process_tree", "list_descendants", "describe_process", "process_started_at",
]
