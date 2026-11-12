"""load_claude_agent(): a standard Claude Code agent file (.claude/agents/<name>.md) -> Agent.

- The file stays a plain Claude Code subagent: name, description, tools, model, skills, disallowedTools; body = prompt
- Everything library-only is passed here, never written in the file: engine, setup, cwd, tool functions, ...
- tools: line absent -> all given custom tools + ask_user (+ all built-ins in project setup), like Claude Code
- model: inherit (or absent) -> the model passed here, else the engine default
- Unknown front-matter fields (color, permissionMode, ...) are kept in agent.extra, never rejected
"""
from __future__ import annotations

from pathlib import Path

from ..agent import Agent
from ..tools import Tool
from . import frontmatter
from .common import default_cwd, find_agent_file, reference_warnings

KNOWN = {"name", "description", "tools", "model", "skills", "disallowedTools"}


def load_claude_agent(name_or_path: str | Path, *, project: str | Path | None = None, engine: str = "claude",
                      setup: str = "lean", cwd: str | Path | None = None, tools: list[Tool] = (),
                      model: str | None = None, **overrides) -> Agent:
    """name_or_path: 'trend_reporter' (searched in <project>/.claude/agents then ~/.claude/agents) or a path.
    tools: Python implementations for custom tool names in the file. overrides: any other Agent field."""
    path = find_agent_file(name_or_path, ".claude/agents", project)
    meta, body = frontmatter.read(path)
    file_model = meta.get("model")
    agent = Agent(
        name=str(meta.get("name") or path.stem),
        description=str(meta.get("description") or "").strip(),
        instructions=body,
        engine=engine,
        model=model or (None if file_model in (None, "inherit") else str(file_model)),
        tools=frontmatter.as_list(meta.get("tools")),
        available_tools=list(tools),
        setup=setup,
        cwd=cwd if cwd is not None else default_cwd(path),
        skills=frontmatter.as_list(meta.get("skills")) or [],
        disallowed_tools=frontmatter.as_list(meta.get("disallowedTools")) or [],
        source=path,
        extra={k: v for k, v in meta.items() if k not in KNOWN},
        **overrides,
    )
    agent.resolved_tools()                    # fail now if a listed custom tool has no function
    agent.warnings.extend(reference_warnings(agent))
    return agent
