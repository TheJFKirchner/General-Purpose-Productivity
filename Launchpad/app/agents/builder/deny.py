"""The Builder's shell deny list: commands that need the user (or autopilot) before they run.

- git commit / git push; package installs (pip, npm, uv, conda, brew, winget ...); deletes outside the project
  (or of the project folder itself)
- Used by the Builder and by building folder agents (app/agents/builder/builder.py StepContext._classify)
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

from ...sessionfiles import inside

_GIT_DENY = {"commit": "git commit", "push": "git push"}
_GIT_VALUE_OPTS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_DENY = [
    ("package install", re.compile(
        r"^(?:pip3?|uv\s+pip|(?:python3?|py)(?:\s+-\S+)*\s+-m\s+pip)\s+install\b"
        r"|^(?:npm|pnpm|yarn|bun)\s+(?:install|i|add|ci)\b|^(?:uv|poetry)\s+add\b"
        r"|^(?:conda|mamba|choco|winget|brew|apt|apt-get|scoop|cargo|gem)\s+install\b"
        r"|^install-(?:module|package)\b", re.I)),
]
_DELETE = {"rm", "rmdir", "del", "erase", "rd", "remove-item", "ri", "unlink", "shred"}
_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def deny_match(command: str, project: Path) -> str | None:
    """Category of a deny-listed shell command ('git push', 'package install', 'delete outside the project'), else None."""
    project = Path(project).resolve()
    cwd = project
    for seg in _SPLIT.split(command or ""):
        seg = seg.strip()
        if not seg:
            continue
        try:
            tokens = shlex.split(seg, posix=True)
        except ValueError:
            tokens = seg.split()
        while tokens and (tokens[0] == "sudo" or re.match(r"^\w+=", tokens[0])):
            tokens = tokens[1:]
        if not tokens:
            continue
        head = Path(tokens[0]).name.lower().removesuffix(".exe")
        if head == "git":
            rest = tokens[1:]
            while rest and rest[0].startswith("-"):                 # skip git's global options
                rest = rest[2:] if rest[0] in _GIT_VALUE_OPTS else rest[1:]
            if rest and rest[0] in _GIT_DENY:
                return _GIT_DENY[rest[0]]
            continue
        flat = " ".join([head] + tokens[1:])
        for label, rx in _DENY:
            if rx.search(flat):
                return label
        if head == "cd" and len(tokens) > 1:
            cwd = (cwd / Path(tokens[1]).expanduser()).resolve()
            continue
        if head in _DELETE:
            for arg in tokens[1:]:
                if arg.startswith("-") or (head in ("del", "erase", "rd", "rmdir") and re.fullmatch(r"/\w{1,2}", arg)):
                    continue
                if "$" in arg or "%" in arg:
                    return "delete outside the project"
                target = Path(arg).expanduser()
                target = target if target.is_absolute() else cwd / target
                if not inside(target, project) or target.resolve() == project:   # incl. the project itself
                    return "delete outside the project"
    return None
