#!/usr/bin/env python3
"""Commentary batch for this dashboard. Run after each data refresh.

No arguments needed. Optional: --override all | --override <unit_id> ...
Stamped from the commentary skill's scripts/run_dashboard.py template.
Runs on your machine (the writer uses your login), by hand or a local scheduler.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "commentary_shell.json"


def _find_skill() -> Path:
    stamped = Path("/home/user/commentary-generation/.claude/skills/commentary/scripts")
    if (stamped / "generate.py").exists():
        return stamped
    rel = Path(".claude") / "skills" / "commentary" / "scripts"
    for base in [HERE, *HERE.parents, Path.home()]:
        if (base / rel / "generate.py").exists():
            return base / rel
    sys.exit("commentary skill not found: expected .claude/skills/commentary in this repo or your home folder")


SKILL_SCRIPTS = _find_skill()

sys.path.insert(0, str(SKILL_SCRIPTS))
from generate import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run([str(PLAN), "--batch", *sys.argv[1:]]))
