"""Connection test: Claude Code. One of the CLI tests listed in app/connections/__init__.py (Settings > Connections).

Run alone from the Launchpad folder (either form):
    python -m app.connections.claude_code              # all three steps (one tiny request: a fraction of a cent)
    python app/connections/claude_code.py --no-request # find + version only, sends nothing
    ... --engine fake                                  # the request goes to agentlib's fake engine (zero tokens)
    ... --json                                         # the result as JSON (what the page receives)

Steps
1. Installed: `claude` on PATH, else the copy bundled with the Claude Agent SDK (what agentlib starts; agentlib's
   connection_status says whether it is there)
2. Version: `claude --version` (the bundled copy: agentlib's version line)
3. Reachable: one minimal request through agentlib (check_connection: no tools, nothing saved, the cheapest model).
   Never the raw SDK. Skipped when the program is missing
Result: {installed, version, reachable, usable, detail}; usable = installed and reachable. Self-contained: imports only
the standard library and agentlib, so it runs on its own.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys

ID = "claude_code"
NAME = "Claude Code"
VERSION_TIMEOUT_S = 20


_VERSION = re.compile(r"\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?")


def version_number(text: str | None) -> str | None:
    """'2.1.160 (Claude Code)' -> '2.1.160'; the trimmed text when it holds no version number."""
    s = " ".join(str(text or "").split())
    m = _VERSION.search(s)
    return m.group(0) if m else (s[:60] or None)


def find_program() -> str | None:
    return shutil.which("claude")


def program_version(path: str) -> str | None:
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT_S,
                             encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return version_number(out.stdout or out.stderr)


async def test(engine: str = "claude", *, request: bool = True) -> dict:
    """The three steps -> {installed, version, reachable, usable, detail}. engine "fake" = the demo: the request goes
    to agentlib's fake engine (nothing sent, nothing spent)."""
    import agentlib
    demo = engine == "fake"
    path = await asyncio.to_thread(find_program)
    version = await asyncio.to_thread(program_version, path) if path else None
    notes = []
    if path:
        installed = True
    elif demo:
        installed, version = True, None        # demo on a machine without Claude Code: shown as installed
    else:
        st = agentlib.connection_status("claude")
        missing = [p for p in st.problems if "not found" in p or "not installed" in p]
        installed = not missing
        # agentlib's line: "claude-agent-sdk 0.2.175 (bundled Claude Code 2.1.160)" -> the bundled Claude Code's number
        bundled = re.search(r"Claude Code ([^)\s]+)", st.version or "")
        version = (bundled.group(1) if bundled and bundled.group(1) != "?" else None) if installed else None
        if installed:
            notes.append("`claude` is not on PATH; Launchpad uses the copy bundled with the Claude Agent SDK.")
        else:
            return {"installed": False, "version": None, "reachable": None, "usable": False,
                    "detail": "Claude Code was not found. " + " ".join(missing)}
    if not request:
        return {"installed": installed, "version": version, "reachable": None, "usable": None,
                "detail": " ".join(notes + ["Not contacted (install check only)."])}
    res = await agentlib.check_connection(engine)
    if res.ok:
        what = ("Demo: the request went to agentlib's fake engine; nothing was sent or spent." if demo else
                f"Answered one tiny request (model {res.model or '?'}, {res.duration_s:.1f} s, ${res.cost_usd:.4f}).")
        return {"installed": installed, "version": version, "reachable": True, "usable": True,
                "detail": " ".join(notes + [what])}
    fix = f" What to do: {res.fix}" if res.fix else ""
    return {"installed": installed, "version": version, "reachable": False, "usable": False,
            "detail": " ".join(notes + [f"Could not reach Claude: {res.error}.{fix}"]).strip()}


def report(r: dict) -> str:
    yes = {True: "yes", False: "no", None: "not checked"}
    return "\n".join([f"{NAME} connection test", f"  Installed: {yes[r['installed']]}",
                      f"  Version:   {r['version'] or '-'}", f"  Reachable: {yes[r['reachable']]}",
                      f"  Usable:    {yes[r['usable']]}", f"  {r['detail']}"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{NAME} connection test")
    ap.add_argument("--engine", default="claude", help="agentlib engine for the request (fake = zero tokens)")
    ap.add_argument("--no-request", action="store_true", help="find the program and its version only")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)
    if args.engine == "fake":
        from agentlib import fake  # noqa: F401  (registers the fake engine)
    r = asyncio.run(test(args.engine, request=not args.no_request))
    print(json.dumps(r, indent=1) if args.json else report(r))
    return 0 if r["usable"] or (args.no_request and r["installed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
