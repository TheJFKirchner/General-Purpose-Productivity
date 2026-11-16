"""User-added agents in a connected folder (<folder>/.claude/agents/<name>.md): form fields, create, remove.

- Draft: the agent drafter (app/agents/drafter/) turns a sentence or two into the form's fields; normalise() here
  cleans them; the user edits them before saving
- Create: fields -> a standard agent file <folder>/.claude/agents/<name>.md (front matter name, description,
  purpose, model, tools; body = instructions), checked by app/files.py agent_problems and saved through the File
  Explorer's save (size cap, no overwrite). Refused: planning purpose, a built-in name, an existing file
- Remove: folder agents only (built-ins are never removed); the file is backed up exactly like a hand-edited save
  (<home>/.launchpad/backups/<dir_id>/<path>/<timestamp>.md, restorable from the File Explorer) and then deleted
- Fields: {name, description, purpose, model, tools: [..], instructions}; empty tools = the default set for the
  purpose (no tools line: building -> the Builder's tools, read-only -> Read, Grep, Glob)
"""
from __future__ import annotations

import re
from pathlib import Path

from ..files import FileError, agent_problems
from . import crew

ADDABLE_PURPOSES = ("exploring", "building", "reviewing")        # planning agents cannot be added (this version)
MODELS = ("haiku", "sonnet", "opus")
MAX_INSTRUCTIONS = 8000


class AgentFormError(ValueError):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = list(problems or [])


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:60].strip("-")


def normalise(fields: dict, *, strict: bool) -> tuple[dict, list[str]]:
    """Form fields -> (clean fields, problems). strict=False (drafts) repairs what it can; strict=True (create)
    reports every problem instead."""
    f = fields if isinstance(fields, dict) else {}
    problems: list[str] = []
    raw_name = str(f.get("name") or "").strip()
    name = raw_name if strict else slug(raw_name)
    if not name:
        problems.append("name: give the agent a name")
    elif not crew.AGENT_NAME.match(name):
        problems.append("name: lowercase letters, digits and dashes only")
    description = " ".join(str(f.get("description") or "").split())
    if not description:
        problems.append("description: say in one sentence what the agent does")
    purpose = str(f.get("purpose") or "").strip().lower() or crew.DEFAULT_PURPOSE
    if purpose == "planning":
        problems.append("purpose: planning agents cannot be added in this version")
    elif purpose not in ADDABLE_PURPOSES:
        if strict:
            problems.append(f"purpose: choose {', '.join(ADDABLE_PURPOSES)}")
        purpose = crew.DEFAULT_PURPOSE
    model = str(f.get("model") or "").strip()
    if model and model not in MODELS and not re.fullmatch(r"claude-[\w.\[\]-]+", model):
        if strict:
            problems.append(f"model: choose {', '.join(MODELS)}")
        model = ""
    tools_in = f.get("tools") or []
    if not isinstance(tools_in, list):
        tools_in = [t.strip() for t in str(tools_in).split(",")]
    tools = []
    for t in tools_in:
        t = str(t).strip()
        if not t:
            continue
        if t not in crew.TOOL_CHOICES:
            if strict:
                problems.append(f"tools: '{t}' is not offered ({', '.join(crew.TOOL_CHOICES)})")
            continue
        if purpose in crew.READ_ONLY_PURPOSES and t in crew.WRITE_SHELL:
            if strict:
                problems.append(f"tools: {purpose} agents are read-only, so '{t}' cannot be given")
            continue
        if t not in tools:
            tools.append(t)
    instructions = str(f.get("instructions") or "").replace("\r\n", "\n").strip()
    if not instructions:
        problems.append("instructions: say what the agent should do")
    elif len(instructions) > MAX_INSTRUCTIONS:
        problems.append(f"instructions: too long (max {MAX_INSTRUCTIONS:,} characters)")
    return ({"name": name, "description": description, "purpose": purpose, "model": model or None,
             "tools": tools, "instructions": instructions}, problems)


def file_text(fields: dict) -> str:
    """Clean fields -> the agent file (standard front matter + Launchpad's purpose field)."""
    def q(v: str) -> str:
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
    lines = ["---", f"name: {fields['name']}", f"description: {q(fields['description'])}",
             f"purpose: {fields['purpose']}"]
    if fields.get("model"):
        lines.append(f"model: {fields['model']}")
    if fields.get("tools"):
        lines.append("tools: " + ", ".join(fields["tools"]))
    lines += ["---", fields["instructions"].strip(), ""]
    return "\n".join(lines)


def agent_rel(name: str) -> str:
    return f".claude/agents/{name}.md"


# --------------------------------------------------------------------------- create / remove
def create(files, dir_id: str, folder: Path, fields: dict) -> str:
    """Write <folder>/.claude/agents/<name>.md -> name. AgentFormError (with problems) if refused."""
    clean, problems = normalise(fields, strict=True)
    if problems:
        raise AgentFormError("the agent was not saved", problems)
    name = clean["name"]
    if name in crew.builtin_names():
        raise AgentFormError("the agent was not saved", [f"name: '{name}' is a built-in agent; choose another name"])
    if any(e["name"] == name for e in crew.folder_agents(folder)):
        raise AgentFormError("the agent was not saved", [f"name: this folder already has an agent '{name}'"])
    target = folder / ".claude" / "agents" / f"{name}.md"
    if target.exists():
        raise AgentFormError("the agent was not saved", [f"name: {agent_rel(name)} already exists"])
    text = file_text(clean)
    problems = agent_problems(text)
    if problems:
        raise AgentFormError("the agent was not saved", problems)
    try:
        files.save(dir_id, agent_rel(name), text, None)            # validation, size cap, never overwrites
    except FileError as e:
        raise AgentFormError("the agent was not saved", [e.message]) from None
    return name


def remove(files, dir_id: str, folder: Path, name: str) -> str:
    """Delete a folder agent's file after backing it up -> name. AgentFormError if refused."""
    name = str(name or "").strip()
    if not name:
        raise AgentFormError("say which agent to remove")
    if name in crew.builtin_names():
        raise AgentFormError(f"'{name}' is a built-in agent: built-ins can be edited, not removed")
    entry = next((e for e in crew.folder_agents(folder) if e["name"] == name), None)
    if entry is None:
        raise AgentFormError(f"this folder has no agent '{name}'")
    target, rel = files.resolve(dir_id, entry["rel"])
    if not target.is_file():
        raise AgentFormError(f"this folder has no agent '{name}'")
    files._backup(dir_id, rel, target)                              # same place and format as a save's backup
    target.unlink()
    return name
