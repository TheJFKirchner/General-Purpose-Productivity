"""The Agent definition: one plain object, same shape whichever engine runs it.

- Build it in code, Agent(...), or from a standard agent file: load_claude_agent() / load_cursor_agent()
- tools: one mixed list -> built-in names/rules ("Read", "Bash(npm run build:*)"), custom Tool objects,
  custom names ("run_sql", needs the function), "ask_user", external MCP names ("mcp__db__query").
  None = not specified (all given custom tools + ask_user; plus all built-ins in project setup)
- setup: "lean" (default; no folder settings, only listed tools) | "project" (like Claude Code in cwd:
  CLAUDE.md, settings, native skills, all built-ins unless tools narrows them)
- Calls: await agent.ask(msg) / agent.ask_sync(msg) -> Reply;  async with agent.session() as s: ...
- Run limits / modes (each needs the engine capability of the same idea, checked in session()):
  max_budget_usd (budget), permission_mode="never_ask" (never_ask), output_schema (structured_output),
  save_conversation=False (unsaved)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from .reply import Reply
from .tools import DEFAULT_SERVER, ResolvedTools, Tool, resolve_tools

Setup = Literal["lean", "project"]
PermissionMode = Literal["default", "never_ask"]


@dataclass
class Agent:
    name: str
    instructions: str = ""
    engine: str = "claude"
    model: str | None = None                 # alias (opus / sonnet / haiku) or full id; None = engine default
    tools: list[str | Tool] | None = None
    available_tools: list[Tool] = field(default_factory=list)   # implementations for names in `tools`
    include_ask_user: bool = True            # only when tools is None: give ask_user automatically
    setup: Setup = "lean"
    cwd: str | Path | None = None
    add_dirs: list[str | Path] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    mcp_servers: dict[str, dict | str] = field(default_factory=dict)   # name -> config dict, or path to a .py server
    disallowed_tools: list[str] = field(default_factory=list)
    description: str = ""
    max_turns: int | None = None
    max_budget_usd: float | None = None      # spending cap per opened session (one ask() = one run); None = no cap.
                                             # Hitting it -> Reply.status "error", Reply.error_kind "budget"
    permission_mode: PermissionMode = "default"   # "never_ask": tools not pre-approved are denied, nobody is asked
    output_schema: dict | None = None        # JSON Schema: reply comes back parsed + checked in Reply.data
    save_conversation: bool = True           # False: the engine stores nothing (no resume, not in session lists)
    timeout_s: float | None = 600            # per turn; None = no limit
    effort: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    on_permission: Callable[..., Any] | None = None
    tool_server: str = DEFAULT_SERVER        # custom tools appear as mcp__<tool_server>__<name>
    source: Path | None = None               # agent file it came from, if any
    extra: dict = field(default_factory=dict)        # front-matter fields the library doesn't use (kept)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.setup not in ("lean", "project"):
            raise ValueError(f"setup must be 'lean' or 'project', got {self.setup!r}")
        if self.permission_mode not in ("default", "never_ask"):
            raise ValueError(f"permission_mode must be 'default' or 'never_ask', got {self.permission_mode!r}")
        if self.permission_mode == "never_ask" and self.on_permission is not None:
            raise ValueError("permission_mode='never_ask' cannot be combined with on_permission (nobody is asked)")
        if self.max_budget_usd is not None and not self.max_budget_usd > 0:
            raise ValueError(f"max_budget_usd must be > 0, got {self.max_budget_usd!r}")
        if self.output_schema is not None:
            from .structured import check_schema
            check_schema(self.output_schema)
        if self.cwd is not None:
            self.cwd = Path(self.cwd)

    def resolved_tools(self) -> ResolvedTools:
        return resolve_tools(self.tools, self.available_tools, server=self.tool_server, setup=self.setup,
                             include_ask_user=self.include_ask_user)

    # ------------------------------------------------------------------ running
    def session(self, *, resume: str | None = None, fork: bool = False, cost_base: float = 0.0):
        """Multi-turn conversation. resume=<session id> continues a saved one (same cwd);
        fork=True branches it (engines with capabilities.fork). Raises EngineUnavailable / CapabilityError
        before anything starts if the engine cannot run this agent (Engine.check). cost_base = total_cost_usd already spent, for exact per-turn cost."""
        from .engines import get_engine
        from .session import Session
        engine = get_engine(self.engine)
        engine.check(self, fork=fork, resume=resume is not None)
        return Session(self, engine.open(self, resume=resume, fork=fork, cost_base=cost_base))

    async def ask(self, message: str) -> Reply:
        """One-shot run. If the reply is needs_input, answer later with
        agent.session(resume=reply.session_id) -> s.answer(answers, questions=reply.questions)."""
        async with self.session() as s:
            return await s.send(message)

    def ask_sync(self, message: str) -> Reply:
        return asyncio.run(self.ask(message))
