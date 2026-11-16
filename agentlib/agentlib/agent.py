"""The Agent definition: one plain object, same shape whichever engine runs it.

- Build it in code, Agent(...), or from a standard agent file: load_claude_agent() / load_cursor_agent()
- tools: one mixed list -> built-in names/rules ("Read", "Bash(npm run build:*)"), custom Tool objects,
  custom names ("run_sql", needs the function), "ask_user", external MCP names ("mcp__db__query").
  None = not specified (all given custom tools + ask_user; plus all built-ins in project setup)
- setup: "lean" (default; no folder settings, only listed tools) | "project" (like Claude Code in cwd:
  CLAUDE.md, settings, native skills, all built-ins unless tools narrows them)
- Calls: await agent.ask(msg) / agent.ask_sync(msg) -> Reply;  async with agent.session() as s: ...
- Run limits / modes (each needs the engine capability of the same idea, checked in session()):
  max_budget_usd (budget), permission_mode="never_ask" (never_ask) / "accept_edits" (accept_edits) / "plan"
  (plan_mode), output_schema (structured_output), save_conversation=False (unsaved)
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from .permissions import PERMISSION_MODES, PermissionMode
from .reply import Reply
from .tools import DEFAULT_SERVER, ResolvedTools, Tool, resolve_tools

Setup = Literal["lean", "project"]

REDACTED = "***"
_SECRET_KEY = re.compile(r"token|secret|password|passwd|api[-_]?key|auth|credential|bearer", re.I)
_SECRET_ARG = re.compile(r"^(--?[\w-]*(?:token|secret|password|passwd|key|auth|credential)[\w-]*)=.+$", re.I | re.S)


def _redact_mcp(cfg: Any, key: str = "") -> Any:
    """JSON-safe summary of an MCP server config with secrets hidden: all `env` / `headers` values,
    any value under a secret-looking key, `--flag=value` args with a secret-looking flag, URL
    credentials and query strings. A path (str) config becomes {"type": "stdio", "path": ...}."""
    if isinstance(cfg, str) and not key:
        return {"type": "stdio", "path": cfg}
    if isinstance(cfg, dict):
        out = {}
        for k, v in cfg.items():
            k = str(k)
            if k in ("env", "headers") and isinstance(v, dict):
                out[k] = {str(n): REDACTED for n in v}
            elif _SECRET_KEY.search(k) and isinstance(v, (str, int, float)):
                out[k] = REDACTED
            else:
                out[k] = _redact_mcp(v, k)
        return out
    if isinstance(cfg, (list, tuple)):
        return [_redact_mcp(v, key) for v in cfg]
    if isinstance(cfg, str):
        m = _SECRET_ARG.match(cfg)
        if m:
            return f"{m.group(1)}={REDACTED}"
        if key == "url":
            return re.sub(r"//[^/@]*@", f"//{REDACTED}@", cfg).split("?", 1)[0] + ("?" + REDACTED if "?" in cfg else "")
        return cfg
    if cfg is None or isinstance(cfg, (bool, int, float)):
        return cfg
    return str(cfg)


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
    engine_prompt: bool = False              # lean only: start from the engine's own agent prompt (Claude: the
                                             # claude_code preset) with `instructions` appended; still no folder
                                             # settings, CLAUDE.md, skills or connectors. project setup always has it
    cwd: str | Path | None = None
    add_dirs: list[str | Path] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    skill_dirs: list[str | Path] | None = None    # lean only: folders holding <name>/SKILL.md, searched in order
                                             # (first match wins) INSTEAD of the default search; None = default
                                             # (<cwd>/.claude|.cursor/skills, then the same under the home folder)
    mcp_servers: dict[str, dict | str] = field(default_factory=dict)   # name -> config dict, or path to a .py server
    disallowed_tools: list[str] = field(default_factory=list)
    gated_tools: list[str] = field(default_factory=list)    # built-in names offered but never pre-approved:
                                                            # every call goes to on_permission (denied if none)
    description: str = ""
    max_turns: int | None = None
    max_budget_usd: float | None = None      # spending cap per opened session (one ask() = one run); None = no cap.
                                             # Hitting it -> Reply.status "error", Reply.error_kind "budget"
    permission_mode: PermissionMode = "default"   # starting mode (change it live: Session.set_permission_mode):
                                             # "default" (ask) | "never_ask" (deny, nobody asked) |
                                             # "accept_edits" (edits in the working folders run) | "plan"
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
        if self.permission_mode not in PERMISSION_MODES:
            raise ValueError(f"permission_mode must be one of {', '.join(map(repr, PERMISSION_MODES))}, "
                             f"got {self.permission_mode!r}")
        if self.permission_mode == "never_ask" and self.on_permission is not None:
            raise ValueError("permission_mode='never_ask' cannot be combined with on_permission (nobody is asked)")
        if self.permission_mode == "never_ask" and self.gated_tools:
            raise ValueError("permission_mode='never_ask' cannot be combined with gated_tools (nobody is asked)")
        if self.max_budget_usd is not None and not self.max_budget_usd > 0:
            raise ValueError(f"max_budget_usd must be > 0, got {self.max_budget_usd!r}")
        if self.output_schema is not None:
            from .structured import check_schema
            check_schema(self.output_schema)
        if self.cwd is not None:
            self.cwd = Path(self.cwd)
        if self.skill_dirs is not None:
            self.skill_dirs = [Path(d) for d in self.skill_dirs]

    def resolved_tools(self) -> ResolvedTools:
        return resolve_tools(self.tools, self.available_tools, server=self.tool_server, setup=self.setup,
                             include_ask_user=self.include_ask_user, gated=self.gated_tools)

    def describe(self) -> dict:
        """The agent definition as plain JSON-safe data, for showing it in an app. Starts nothing, spends
        nothing, same on every engine. Keys: name, description, model, engine, source_path, instructions,
        builtin_tools (built-in names/rules + external MCP tool names offered), custom_tools (name,
        description, read_only, ends_turn), mcp_servers (name, config with secrets redacted),
        disallowed_tools, skills, warnings."""
        warnings = list(self.warnings)
        try:
            r = self.resolved_tools()
            builtin, custom = list(r.builtin_rules) + list(r.mcp_rules), r.custom
            if r.all_builtins:
                warnings.append("tools not specified: every built-in tool is offered (setup='project')")
        except Exception as e:  # noqa: BLE001 -- describing must not fail on a half-built agent
            builtin, custom = [], []
            warnings.append(f"tools could not be resolved: {e}")
        out = {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "engine": self.engine,
            "source_path": str(self.source) if self.source else None,
            "instructions": self.instructions,
            "builtin_tools": builtin,
            "custom_tools": [{"name": t.name, "description": t.description,
                              "read_only": bool(t.read_only), "ends_turn": bool(t.ends_turn)} for t in custom],
            "mcp_servers": [{"name": n, "config": _redact_mcp(c)} for n, c in self.mcp_servers.items()],
            "disallowed_tools": list(self.disallowed_tools),
            "skills": list(self.skills),
            "warnings": warnings,
        }
        return json.loads(json.dumps(out, default=str))

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
