"""Tool-run permissions (Bash, Edit, ...), permission modes and plan approval. Separate from ask_user.

- Agent(on_permission=fn): fn(PermissionRequest) -> "allow" | "deny" | "always_allow" (or True/False) or a
  PermissionDecision (remember where, rules, switch mode, deny message), sync or async
- Called only for tools that are NOT pre-approved; pre-approved tools never ask (Agent(tools=) rules, and in
  setup="project" the user's / project's settings rules too)
- No hook set -> anything not pre-approved is denied (same as headless Claude Code)
- Permission modes (Agent(permission_mode=), Session.set_permission_mode()): "default" (ask), "never_ask"
  (deny instead of asking), "accept_edits" (file edits + filesystem commands inside the working folders run
  without asking), "plan" (the agent explores and proposes a plan; edits are never pre-approved)
- Plan approval: in plan mode the agent proposes its plan through on_permission: PermissionRequest.kind ==
  "plan", .plan = the plan text. Allow -> the session leaves plan mode (PermissionDecision.mode picks the next
  mode, default "default"); deny -> it stays in plan mode (PermissionDecision.message = feedback to the agent)
- "always_allow" remembers for this session (default) or in the project's local settings
  (PermissionDecision(remember="project_local"); Claude: <cwd>/.claude/settings.local.json, read back by later
  sessions with setup="project", like Claude Code's own "always allow")
- Claude and fake engines (engine.capabilities.permission_hook); others raise CapabilityError at session()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["allow", "deny", "always_allow"]
PermissionMode = Literal["default", "never_ask", "accept_edits", "plan"]
Remember = Literal["session", "project_local"]
Where = Literal["session", "project_local", "project_shared", "user"]
RequestKind = Literal["tool", "plan"]
SuggestionKind = Literal["add_rules", "replace_rules", "remove_rules", "set_mode", "add_dirs", "remove_dirs"]

PERMISSION_MODES: tuple[str, ...] = ("default", "never_ask", "accept_edits", "plan")
DECISIONS: tuple[str, ...] = ("allow", "deny", "always_allow")
REMEMBER: tuple[str, ...] = ("session", "project_local")
PLAN_APPROVED_MODE = "default"       # mode after a plan is approved with a plain "allow"


def check_mode(mode: str) -> str:
    if mode not in PERMISSION_MODES:
        raise ValueError(f"permission_mode must be one of {', '.join(map(repr, PERMISSION_MODES))}, got {mode!r}")
    return mode


@dataclass
class PermissionSuggestion:
    """An engine's ready-made "always allow" option for one request (Claude: ToolPermissionContext.suggestions).

    kind: add_rules | replace_rules | remove_rules | set_mode | add_dirs | remove_dirs
    rules: permission rules in the Agent(tools=) syntax ("Bash(npm test:*)", "Read"); custom tools by short name
    behavior: "allow" | "deny" | "ask" (rule kinds); mode: a permission mode (set_mode); dirs: folders (*_dirs)
    where: "session" | "project_local" (this project, this person) | "project_shared" (checked-in project
    settings) | "user" (all projects)
    """
    kind: str
    rules: list[str] = field(default_factory=list)
    behavior: str | None = None
    mode: str | None = None
    dirs: list[str] = field(default_factory=list)
    where: str = "session"

    def to_dict(self) -> dict:
        return {"kind": self.kind, "rules": list(self.rules), "behavior": self.behavior, "mode": self.mode,
                "dirs": list(self.dirs), "where": self.where}


@dataclass
class PermissionRequest:
    agent: str
    tool: str
    input: dict = field(default_factory=dict)
    reason: str | None = None
    kind: RequestKind = "tool"           # "plan": the agent proposes a plan and asks to proceed (see .plan)
    plan: str | None = None              # the plan text (kind == "plan")
    suggestions: list[PermissionSuggestion] = field(default_factory=list)   # engine's "always allow" options
    mode: str | None = None              # the session's permission mode when it asked
    call_id: str | None = None           # matches ToolCall.id / ToolCallRecord.id of this call, when known
    title: str | None = None             # engine's prompt sentence ("Claude wants to read foo.txt"), if any

    def to_dict(self) -> dict:
        return {"agent": self.agent, "tool": self.tool, "input": dict(self.input), "reason": self.reason,
                "kind": self.kind, "plan": self.plan, "suggestions": [s.to_dict() for s in self.suggestions],
                "mode": self.mode, "call_id": self.call_id, "title": self.title}


@dataclass
class PermissionDecision:
    """A full answer from on_permission (a plain "allow" / "deny" / "always_allow" string still works).

    decision: "allow" | "deny" | "always_allow"
    remember: where "always_allow" is kept: "session" (default) or "project_local" (persists for this project)
    rules: rules "always_allow" remembers (Agent(tools=) syntax). None = engine default: session -> the whole
      tool (as a plain "always_allow"); project_local -> the engine's suggested rules for this call (e.g.
      "Bash(npm test:*)"), else the whole tool
    mode: on allow, switch the session to this permission mode (e.g. "accept_edits" = allow all edits from now
      on). For a plan approval it picks the mode to continue in (None -> "default")
    message: on deny, told to the agent (for a plan: what to change; it keeps planning)
    input: on allow, run the tool with this input instead of the agent's (e.g. the user's answers for the
      engine's own question tool: Claude AskUserQuestion -> {"questions": [...], "answers": {question: label}})
    """
    decision: Decision = "allow"
    remember: Remember = "session"
    rules: list[str] | None = None
    mode: PermissionMode | None = None
    message: str | None = None
    input: dict | None = None

    def __post_init__(self):
        if self.decision not in DECISIONS:
            raise ValueError(f"decision must be one of {', '.join(map(repr, DECISIONS))}, got {self.decision!r}")
        if self.remember not in REMEMBER:
            raise ValueError(f"remember must be one of {', '.join(map(repr, REMEMBER))}, got {self.remember!r}")
        if self.mode is not None:
            check_mode(self.mode)
        if self.rules is not None:
            self.rules = [str(r).strip() for r in self.rules if str(r).strip()]
        if self.input is not None and not isinstance(self.input, dict):
            raise ValueError("input must be a dict (the tool input to run with)")

    @property
    def allowed(self) -> bool:
        return self.decision != "deny"


def normalize(decision) -> Decision:
    if isinstance(decision, PermissionDecision):
        return decision.decision
    if decision is True:
        return "allow"
    if decision in ("allow", "always_allow"):
        return decision
    return "deny"


def resolve(decision) -> PermissionDecision:
    """Whatever on_permission returned -> PermissionDecision (unknown values deny, as before)."""
    if isinstance(decision, PermissionDecision):
        return decision
    return PermissionDecision(normalize(decision))
