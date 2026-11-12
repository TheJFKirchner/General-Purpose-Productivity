"""Load standard agent files so the same file works in Claude Code / Cursor and in this library.

- load_claude_agent(): .claude/agents/<name>.md (Claude Code format)
- load_cursor_agent(): .cursor/agents/<name>.md (Cursor format)
"""
from .claude import load_claude_agent
from .cursor import load_cursor_agent

__all__ = ["load_claude_agent", "load_cursor_agent"]
