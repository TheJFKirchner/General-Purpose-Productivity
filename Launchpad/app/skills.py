"""Skill discovery for a session's folders, and each agent's skill allowlist.

- A session's folders: [primary, *additional] (fixed when the session starts; app/hub.py). Skills come only from
  these folders, never from the user's home folder
- Per folder: a `.claude` folder present -> its `.claude/skills` only (`.agents` ignored, even when `.claude/skills`
  is missing or empty); no `.claude` folder -> `.agents/skills`. Never both for one folder
- A skill = a sub-folder holding SKILL.md (front matter name + description; read by agentlib.skills.list_skills)
- Name clash: the primary folder wins, then the additional folders in order; the others are listed as shadowed
- Allowlist per agent (store key agent_skills, keyed by agent name): "all" | [skill names]. Default: the planner
  "all", everyone else none. Names not found in the session's folders are ignored at run time
- The CLI chat (role pilot) is not covered: project setup, the harness's own skill discovery
- Agents get skills through agentlib: Agent(skills=[names], skill_dirs=<active skill folders, primary first>)
"""
from __future__ import annotations

from pathlib import Path

from agentlib.skills import list_skills

ALL = "all"


def skill_root(folder: Path) -> tuple[Path | None, str | None]:
    """(skills folder, source "claude" | "agents") for one working folder; (None, None) when it has none."""
    folder = Path(folder)
    if (folder / ".claude").is_dir():
        root = folder / ".claude" / "skills"
        return (root, "claude") if root.is_dir() else (None, None)
    root = folder / ".agents" / "skills"
    return (root, "agents") if root.is_dir() else (None, None)


def discover(folders: list[Path], dir_ids: list[str | None] | None = None) -> list[dict]:
    """Every skill in the folders (primary first): {name, description, path (SKILL.md), folder (the working
    folder), folder_name, dir_id, source: claude | agents, skills_dir, shadowed}. The first of a name wins."""
    out, seen = [], set()
    ids = list(dir_ids or [None] * len(folders))
    for folder, did in zip(folders, ids + [None] * (len(folders) - len(ids))):
        root, source = skill_root(folder)
        if root is None:
            continue
        for s in list_skills(root):
            out.append({"name": s.name, "description": s.description, "path": str(s.file),
                        "folder": str(Path(folder).resolve()), "folder_name": Path(folder).resolve().name,
                        "dir_id": did, "source": source, "skills_dir": str(root.resolve()),
                        "shadowed": s.name in seen})
            seen.add(s.name)
    return out


def active(found: list[dict]) -> list[dict]:
    """The skills an agent can be given (shadowed ones dropped)."""
    return [s for s in found if not s["shadowed"]]


def skill_dirs(folders: list[Path]) -> list[Path]:
    """The skills folders to hand agentlib (skill_dirs), in priority order."""
    return [r for r in (skill_root(f)[0] for f in folders) if r is not None]


def setting_of(agent_skills: dict, agent_name: str, *, planner: bool = False) -> str | list[str]:
    """An agent's stored setting ("all" | [names]); when nothing is stored: "all" for the planner, else none."""
    v = (agent_skills or {}).get(agent_name)
    if v == ALL:
        return ALL
    if isinstance(v, list):
        return [str(x) for x in v if isinstance(x, str) and x.strip()]
    return ALL if planner else []


def clean_setting(value) -> str | list[str]:
    """A setting sent by the page -> "all" or a list of names (ValueError otherwise)."""
    if value == ALL:
        return ALL
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return list(dict.fromkeys(x.strip() for x in value if x.strip()))
    raise ValueError('skills must be "all" or a list of skill names')


def allowed(setting, found: list[dict], extra: list[str] = ()) -> list[str]:
    """Skill names an agent runs with: its setting (all, or the listed names) plus `extra` (a plan step's skills),
    limited to the session's active skills, in discovery order."""
    names = [s["name"] for s in active(found)]
    want = (set(names) if setting == ALL else set(setting or [])) | set(extra or [])
    return [n for n in names if n in want]


def note(found: list[dict]) -> str:
    """The skill list as the planner sees it (first message): one bullet per active skill."""
    act = active(found)
    if not act:
        return "Skills: none in this session's folders."
    lines = [f"- {s['name']}: {_short(s['description'])}" for s in act]
    return ("Skills (set a step's `skills` only to ones the step must follow; its worker then gets them):\n"
            + "\n".join(lines))


def _short(text: str, limit: int = 160) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"
