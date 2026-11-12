"""Shared helpers for the agent-file loaders: find the file, default cwd, reference warnings."""
from __future__ import annotations

import re
from pathlib import Path

from ..errors import AgentFileError

_REF = re.compile(r"(?<![\w/])(?:\.{0,2}/)?[\w.-]+(?:/[\w.-]+)*\.(?:md|txt|json|ya?ml|py|sql|csv|toml)\b")


def find_agent_file(name_or_path: str | Path, folder: str, project: str | Path | None) -> Path:
    """folder = '.claude/agents' or '.cursor/agents'. Project folder first, then the user's home (like the IDEs)."""
    p = Path(name_or_path)
    if p.suffix == ".md" or p.parent != Path("."):
        cand = p if p.is_absolute() or project is None else Path(project) / p
        if cand.is_file():
            return cand.resolve()
        if p.is_file():
            return p.resolve()
        raise AgentFileError(f"agent file not found: {name_or_path}")
    roots = [Path(project) if project else Path.cwd(), Path.home()]
    for root in roots:
        cand = root / folder / f"{p.name}.md"
        if cand.is_file():
            return cand.resolve()
    raise AgentFileError(f"agent '{name_or_path}' not found in: " + ", ".join(str(r / folder) for r in roots))


def default_cwd(path: Path) -> Path | None:
    """<project>/.claude/agents/x.md -> <project> (references in the body are relative to it)."""
    if path.parent.name == "agents" and path.parent.parent.name in (".claude", ".cursor"):
        return path.parent.parent.parent
    return None


def reference_warnings(agent) -> list[str]:
    refs = sorted(set(_REF.findall(agent.instructions or "")))
    if not refs:
        return []
    r = agent.resolved_tools()
    if r.all_builtins or "Read" in r.builtin_names:
        return []
    shown = ", ".join(refs[:5]) + (" ..." if len(refs) > 5 else "")
    return [f"agent '{agent.name}' refers to files ({shown}) but has no Read tool to open them"]
