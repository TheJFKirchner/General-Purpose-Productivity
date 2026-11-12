"""Optional hook for tool-run permissions (Bash, Edit, ...). Separate from ask_user (material questions).

- Agent(on_permission=fn): fn(PermissionRequest) -> "allow" | "deny" | "always_allow" (or True/False), sync or async
- Called only for tools that are NOT pre-approved; pre-approved tools never ask
- No hook set -> anything not pre-approved is denied (same as headless Claude Code)
- Claude and fake engines (engine.capabilities.permission_hook); others raise CapabilityError at session()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["allow", "deny", "always_allow"]


@dataclass
class PermissionRequest:
    agent: str
    tool: str
    input: dict = field(default_factory=dict)
    reason: str | None = None


def normalize(decision) -> Decision:
    if decision is True:
        return "allow"
    if decision in ("allow", "always_allow"):
        return decision
    return "deny"
