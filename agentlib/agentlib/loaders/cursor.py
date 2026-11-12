"""load_cursor_agent(): a standard Cursor agent file (.cursor/agents/<name>.md) -> Agent.

- The file stays a plain Cursor subagent: name, description, model, readonly, is_background; body = prompt
- Cursor files have no tools list: readonly: true -> Read, Grep, Glob; otherwise not specified
  (all given custom tools, + all built-ins in project setup). ask_user is given unless ask_user=False
- Runs on the claude engine until the cursor engine exists (DEFAULT_ENGINE); Cursor model names that
  aren't Claude models fall back to the engine default, with a warning
- Unknown front-matter fields are kept in agent.extra
"""
from __future__ import annotations

from pathlib import Path

from ..agent import Agent
from ..tools import ASK_USER_NAME, Tool
from . import frontmatter
from .common import default_cwd, find_agent_file, reference_warnings

DEFAULT_ENGINE = "claude"          # switch to "cursor" when engines/cursor.py is built
KNOWN = {"name", "description", "model", "readonly"}
READONLY_TOOLS = ["Read", "Grep", "Glob"]
CLAUDE_ALIASES = ("opus", "sonnet", "haiku")


def _claude_model(cursor_model) -> tuple[str | None, str | None]:
    if cursor_model in (None, "inherit"):
        return None, None
    m = str(cursor_model).lower()
    for alias in CLAUDE_ALIASES:
        if alias in m:
            return alias, None
    return None, f"Cursor model '{cursor_model}' has no Claude equivalent; using the engine default"


def load_cursor_agent(name_or_path: str | Path, *, project: str | Path | None = None,
                      engine: str = DEFAULT_ENGINE, setup: str = "lean", cwd: str | Path | None = None,
                      tools: list[Tool] = (), model: str | None = None, ask_user: bool = True,
                      **overrides) -> Agent:
    path = find_agent_file(name_or_path, ".cursor/agents", project)
    meta, body = frontmatter.read(path)
    warnings: list[str] = []
    if model is None and engine != "cursor":
        model, warn = _claude_model(meta.get("model"))
        if warn:
            warnings.append(warn)
    elif model is None:
        model = None if meta.get("model") in (None, "inherit") else str(meta.get("model"))

    tool_list = None
    if meta.get("readonly"):
        tool_list = READONLY_TOOLS + [t.name for t in tools] + ([ASK_USER_NAME] if ask_user else [])
    agent = Agent(
        name=str(meta.get("name") or path.stem),
        description=str(meta.get("description") or "").strip(),
        instructions=body,
        engine=engine,
        model=model,
        tools=tool_list,
        available_tools=list(tools),
        include_ask_user=ask_user,
        setup=setup,
        cwd=cwd if cwd is not None else default_cwd(path),
        source=path,
        extra={k: v for k, v in meta.items() if k not in KNOWN},
        **overrides,
    )
    agent.warnings.extend(warnings + reference_warnings(agent))
    return agent
