"""Connection test: Cursor. One of the CLI tests listed in app/connections/__init__.py (Settings > Connections).

Run alone from the Launchpad folder (either form):
    python -m app.connections.cursor
    python app/connections/cursor.py --json

Install check only (nothing is sent): the Cursor CLI is `cursor-agent` (older installs) or `agent` (newer installs,
https://cursor.com/docs/cli/installation), looked for on PATH and in the installers' usual folders; its version from
`--version`. usable stays false while agentlib's Cursor engine is a stub (agentlib says so: get_engine("cursor")
.capabilities.available), with a plain explanation; when that engine is built, usable = installed. Self-contained:
imports only the standard library and agentlib.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ID = "cursor"
NAME = "Cursor"
COMMANDS = ("cursor-agent", "agent")
VERSION_TIMEOUT_S = 20


def _candidates() -> list[Path]:
    home = Path.home()
    out = [home / ".local" / "bin" / c for c in COMMANDS]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for sub in ("cursor-agent", "Programs\\cursor-agent"):
            out += [Path(local) / sub / f"{c}{ext}" for c in COMMANDS for ext in (".cmd", ".exe", ".ps1")]
    return out


def find_program() -> str | None:
    for c in COMMANDS:
        p = shutil.which(c)
        if p and (c != "agent" or program_version(p)):      # a bare `agent` must answer --version to count
            return p
    return next((str(p) for p in _candidates() if p.is_file()), None)


def program_version(path: str) -> str | None:
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT_S,
                             encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return version_number(out.stdout or out.stderr)


_VERSION = re.compile(r"\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?")


def version_number(text: str | None) -> str | None:
    """'cursor-agent 2026.11.01-abc123' -> '2026.11.01-abc123'; the trimmed text when it holds no version number."""
    s = " ".join(str(text or "").split())
    m = _VERSION.search(s)
    return m.group(0) if m else (s[:60] or None)


def engine_ready() -> bool:
    try:
        from agentlib import get_engine
        return bool(get_engine("cursor").capabilities.available)
    except Exception:  # noqa: BLE001 -- no engine = not usable
        return False


async def test(engine: str = "claude", *, request: bool = True) -> dict:
    """Install check -> {installed, version, reachable: None, usable, detail}. engine / request are accepted so every
    connection test has the same call; nothing is ever sent here."""
    path = await asyncio.to_thread(find_program)
    version = await asyncio.to_thread(program_version, path) if path else None
    ready = engine_ready()
    if not path:
        editor = " The Cursor editor is installed, but not its command-line tool." if shutil.which("cursor") else ""
        tail = "" if ready else " Launchpad cannot use Cursor yet either way: its Cursor engine is not built."
        return {"installed": False, "version": None, "reachable": None, "usable": False,
                "detail": f"The Cursor CLI was not found (looked for {' and '.join(COMMANDS)}).{editor}{tail}"}
    if not ready:
        return {"installed": True, "version": version, "reachable": None, "usable": False,
                "detail": ("Installed, but Launchpad cannot use it yet: Launchpad's Cursor engine (in agentlib) is "
                           "not built. Nothing was sent.")}
    return {"installed": True, "version": version, "reachable": None, "usable": True,
            "detail": "Installed. Not contacted (install check only)."}


def report(r: dict) -> str:
    yes = {True: "yes", False: "no", None: "not checked"}
    return "\n".join([f"{NAME} connection test", f"  Installed: {yes[r['installed']]}",
                      f"  Version:   {r['version'] or '-'}", f"  Usable:    {yes[r['usable']]}", f"  {r['detail']}"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{NAME} connection test (install check only)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)
    r = asyncio.run(test())
    print(json.dumps(r, indent=1) if args.json else report(r))
    return 0 if r["installed"] else 1


if __name__ == "__main__":
    sys.exit(main())
