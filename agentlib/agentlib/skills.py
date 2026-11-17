"""Find standard skill folders (<name>/SKILL.md) for lean agents.

- project setup: the engine loads skills natively; this module is not used
- lean setup: each listed skill is found here, its name + description go into the prompt (prompts/skills_index.md),
  and the agent may read files inside that skill folder only, on demand. Nothing is pasted in up front.
- search order: Agent(skill_dirs=[...]) when given (exactly those folders, in order); else <cwd>/.claude/skills,
  <cwd>/.cursor/skills, ~/.claude/skills, ~/.cursor/skills
- a skill is found by its folder name (<root>/<name>/SKILL.md), else by the `name:` in a SKILL.md in that root
- list_skills(root): every skill in one folder (apps use it to show what is available)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import prompt_files
from .errors import AgentFileError
from .loaders import frontmatter

SKILL_DIRS = (".claude/skills", ".cursor/skills")


@dataclass
class Skill:
    name: str
    description: str
    folder: Path

    @property
    def file(self) -> Path:
        return self.folder / "SKILL.md"


def search_roots(cwd: str | Path | None, dirs: list[str | Path] | None = None) -> list[Path]:
    """Where skills are looked for: `dirs` when given (explicit skill folders), else the default search."""
    if dirs is not None:
        return [Path(d) for d in dirs]
    bases = [Path(cwd) if cwd else Path.cwd(), Path.home()]
    return [b / d for b in bases for d in SKILL_DIRS]


def _read(folder: Path, fallback: str) -> Skill:
    meta, _ = frontmatter.read(folder / "SKILL.md")
    return Skill(name=str(meta.get("name") or fallback).strip(),
                 description=str(meta.get("description") or "").strip(),
                 folder=folder.resolve())


def list_skills(root: str | Path) -> list[Skill]:
    """Every skill in one skill folder (sub-folders holding a SKILL.md), sorted by folder name. A SKILL.md whose
    front matter cannot be read is skipped. A missing folder -> []."""
    root = Path(root)
    if not root.is_dir():
        return []
    out = []
    for sub in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        if (sub / "SKILL.md").is_file():
            try:
                out.append(_read(sub, sub.name))
            except Exception:  # noqa: BLE001 -- one broken skill must not hide the others
                continue
    return out


def find_skill(name: str, cwd: str | Path | None = None, dirs: list[str | Path] | None = None) -> Skill:
    roots = search_roots(cwd, dirs)
    for root in roots:
        folder = root / name
        if (folder / "SKILL.md").is_file():
            return _read(folder, name)
        hit = next((s for s in list_skills(root) if s.name == name), None)
        if hit is not None:
            return hit
    raise AgentFileError(f"skill '{name}' not found in: " + ", ".join(str(r) for r in roots))


def index_text(skills: list[Skill]) -> str:
    lines = [f"- {s.name}: {s.description} (SKILL.md: {s.file})" for s in skills]
    return prompt_files.fill("skills_index", skills="\n".join(lines))


def inside(path: str | Path, folders: list[Path]) -> bool:
    try:
        p = Path(path).resolve()
    except (OSError, ValueError):
        return False
    return any(p == f or f in p.parents for f in folders)
