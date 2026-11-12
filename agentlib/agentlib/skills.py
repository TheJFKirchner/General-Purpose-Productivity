"""Find standard skill folders (<name>/SKILL.md) for lean agents.

- project setup: the engine loads skills natively; this module is not used
- lean setup: each listed skill is found here, its name + description go into the prompt (prompts/skills_index.md),
  and the agent may read files inside that skill folder only, on demand. Nothing is pasted in up front.
- search order: <cwd>/.claude/skills, <cwd>/.cursor/skills, ~/.claude/skills, ~/.cursor/skills
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


def search_roots(cwd: str | Path | None) -> list[Path]:
    bases = [Path(cwd) if cwd else Path.cwd(), Path.home()]
    return [b / d for b in bases for d in SKILL_DIRS]


def find_skill(name: str, cwd: str | Path | None = None) -> Skill:
    for root in search_roots(cwd):
        folder = root / name
        if (folder / "SKILL.md").is_file():
            meta, _ = frontmatter.read(folder / "SKILL.md")
            return Skill(name=str(meta.get("name") or name),
                         description=str(meta.get("description") or "").strip(),
                         folder=folder.resolve())
    raise AgentFileError(f"skill '{name}' not found in: " + ", ".join(str(r) for r in search_roots(cwd)))


def index_text(skills: list[Skill]) -> str:
    lines = [f"- {s.name}: {s.description} (SKILL.md: {s.file})" for s in skills]
    return prompt_files.fill("skills_index", skills="\n".join(lines))


def inside(path: str | Path, folders: list[Path]) -> bool:
    try:
        p = Path(path).resolve()
    except (OSError, ValueError):
        return False
    return any(p == f or f in p.parents for f in folders)
