"""The local setup file: how THIS user connects to each engine. Never committed (ignored by git).

- Where: setup/local.toml in the agentlib folder (beside setup/<engine>.md and setup/local.example.toml), or the
  file named by the AGENTLIB_SETUP_FILE environment variable (for installs that are not editable, or tests)
- No file = every engine uses its default (Claude: the ordinary Claude Code login)
- TOML, one [section] per engine name; each engine's EngineSetup.resolve() reads only its own section.
  Sections for engines this version does not know are ignored (a newer library may add them)
- connection(engine) -> Connection (problems listed, nothing raised); require(engine) -> Connection, or
  SetupError when there are problems. Engines call require() each time they start a process, so edits apply to
  the next session without restarting the app
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

from .engines import get_setup
from .engines.base import Connection
from .errors import SetupError

ENV_VAR = "AGENTLIB_SETUP_FILE"
LIB_ROOT = Path(__file__).resolve().parent.parent       # the agentlib folder (editable install)
SETUP_DIR = LIB_ROOT / "setup"
DEFAULT_FILE = SETUP_DIR / "local.toml"
EXAMPLE_FILE = SETUP_DIR / "local.example.toml"


def setup_file() -> Path:
    """The local setup file agentlib looks for (it may not exist)."""
    named = os.environ.get(ENV_VAR, "").strip()
    return Path(os.path.expanduser(named)) if named else DEFAULT_FILE


def doc_path(engine: str) -> Path | None:
    """The engine's setup guide (setup/<engine>.md), or None if it has none."""
    doc = get_setup(engine).doc
    return LIB_ROOT / doc if doc else None


def read() -> tuple[Path | None, dict, list[str]]:
    """-> (file in use or None, parsed data, problems). Never raises for a bad file: problems say what is wrong."""
    path = setup_file()
    if not path.is_file():
        if os.environ.get(ENV_VAR, "").strip():
            return None, {}, [f"{ENV_VAR} points at {path}, which does not exist. Fix the path, or unset {ENV_VAR} "
                              f"to use {DEFAULT_FILE}"]
        return None, {}, []
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        return path, {}, [f"{path} is not valid TOML ({e}). Compare it with {EXAMPLE_FILE.name}"]
    except OSError as e:
        return path, {}, [f"could not read {path}: {e.strerror or e}"]
    return path, data, []


def connection(engine: str) -> Connection:
    """How this user connects `engine`: its section of the local setup file, resolved by the engine's setup."""
    setup = get_setup(engine)
    path, data, problems = read()
    section = data.get(engine, {})
    if not isinstance(section, dict):
        problems.append(f"'{engine}' in {path} must be a [{engine}] section, not a single value")
        section = {}
    conn = setup.resolve(section, base=path.parent if path else SETUP_DIR)
    conn.problems = problems + conn.problems
    return conn


def require(engine: str) -> Connection:
    """connection(), raising SetupError (what to fix, where the guide is) if the setup has problems."""
    conn = connection(engine)
    if conn.problems:
        path = setup_file()
        doc = doc_path(engine)
        guide = f" Guide: {doc}." if doc else ""
        listed = " | ".join(p.rstrip(".") for p in conn.problems)
        raise SetupError(f"agentlib setup problem for '{engine}' ({path}): {listed}.{guide}")
    return conn
