"""Command line: python -m whiteboard --data <file> --library <name> --out <folder> [--style <text>]
[--existing <file>] [--fake] [--no-open] [--port N] [--model M] [--effort E] [--debug-usage]

Exit codes: 0 after Done, Ctrl+C, or the page going away (result.json then has done: false); 2 for a bad
launch (unsupported library, unreadable data, an output folder holding files from an earlier session).
Every launch starts a fresh board; only saved visuals (<id>.json) and result.json are written. The last line
printed is "RESULT: <out>/result.json"; that line is the signal the session is over.

Environment (for tests and demos): WHITEBOARD_FAKE=1 (fake engine, scripted demo replies, zero tokens),
WHITEBOARD_NO_OPEN=1 (no browser), WHITEBOARD_PORT, WHITEBOARD_MODEL, WHITEBOARD_EFFORT (default low),
WHITEBOARD_BUDGET (USD cap for the session), WHITEBOARD_DEBUG_USAGE=1 (per-turn model calls, tokens, cost
and prompt part sizes on stderr), WHITEBOARD_IDLE_S (default 90) and WHITEBOARD_CONNECT_S (default 600): how
long the page may be silent, or absent at launch, before the session ends on its own.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import LIBRARIES
from .agent import DEFAULT_EFFORT, DEFAULT_MODEL, Designer
from .board import Board, OutputNotEmpty
from .data import DataError, load
from .server import CONNECT_S, IDLE_S, Whiteboard

ALIASES = {"chart.js": "chartjs", "chart-js": "chartjs", "vega-lite": "vegalite", "vega_lite": "vegalite",
           "vega": "vegalite", "d3js": "d3", "d3.js": "d3", "svg": "html", "plain": "html"}

# Variables a Claude Code session passes to its child processes. If the whiteboard was launched from
# inside one (the skill does that), drop them so the agent's own `claude` process starts like a normal
# terminal one. Sign-in variables (ANTHROPIC_*, the ones below) are left alone.
SESSION_VAR_KEEP = {"CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
                    "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_GIT_BASH_PATH", "CLAUDE_CONFIG_DIR"}


class LaunchError(Exception):
    """A launch that must stop with a clear message and exit code 2."""


def flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def normalise_library(name: str) -> str:
    key = (name or "").strip().lower()
    key = ALIASES.get(key, key)
    if key not in LIBRARIES:
        raise LaunchError(
            f"Library '{name}' is not supported by the whiteboard. Supported: {', '.join(LIBRARIES)}. "
            "Python-only libraries (matplotlib, seaborn, plotnine, ...) cannot run in the browser page.")
    return key


def load_existing(path: str | Path, library: str) -> dict:
    """The visual being tweaked, as G1. A recipe JSON ({code, title?, kind?}) or a file holding the body
    of render(el, rows, lib)."""
    p = Path(path)
    if not p.is_file():
        raise LaunchError(f"--existing file not found: {p}")
    text = p.read_text(encoding="utf-8-sig")
    title, kind, code = "Current visual", "chart", text
    if p.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LaunchError(f"--existing {p.name} is not valid JSON: {e}") from None
        if not isinstance(data, dict) or not isinstance(data.get("code"), str):
            raise LaunchError(f"--existing {p.name} must be a recipe object with a 'code' string.")
        code = data["code"]
        title = str(data.get("title") or "").strip() or title
        kind = data.get("kind") if data.get("kind") in ("chart", "table") else kind
        saved_lib = data.get("library")
        if saved_lib == "html" and library != "html" and kind == "chart":
            kind = "table"
        elif saved_lib and saved_lib != "html" and saved_lib != library:
            raise LaunchError(f"--existing {p.name} was made for library '{saved_lib}', not '{library}'. "
                              f"Launch with --library {saved_lib} to keep working on it.")
    if not code.strip():
        raise LaunchError(f"--existing {p.name} is empty.")
    return {"title": title, "kind": kind, "code": code}


def clean_environment() -> None:
    if "CLAUDE_CODE_ENTRYPOINT" not in os.environ and "CLAUDECODE" not in os.environ:
        return
    for k in list(os.environ):
        if k in SESSION_VAR_KEEP:
            continue
        if k in ("CLAUDECODE", "CLAUDE_PID") or k.startswith(("CLAUDE_CODE_", "CLAUDE_AGENT_SDK_")):
            del os.environ[k]


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="python -m whiteboard",
                                 description="Open the whiteboard page for designing charts and tables.")
    ap.add_argument("--data", required=True, help="CSV, or JSON array of row objects")
    ap.add_argument("--library", required=True, help=f"one of: {', '.join(LIBRARIES)}")
    ap.add_argument("--out", required=True, help="new or empty output folder (<id>.json per saved visual, result.json)")
    ap.add_argument("--style", default=None, help="optional style note for the agent")
    ap.add_argument("--existing", default=None, help="the visual being tweaked, e.g. a saved <id>.json (becomes G1, the current visual)")
    ap.add_argument("--fake", action="store_true", help="fake engine: scripted replies, zero tokens")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--port", type=int, default=int(os.environ.get("WHITEBOARD_PORT") or 0),
                    help="port (default: any free port)")
    ap.add_argument("--model", default=os.environ.get("WHITEBOARD_MODEL") or DEFAULT_MODEL,
                    help=f"model alias or full id (default {DEFAULT_MODEL}; env WHITEBOARD_MODEL)")
    ap.add_argument("--effort", default=os.environ.get("WHITEBOARD_EFFORT") or DEFAULT_EFFORT,
                    choices=["low", "medium", "high", "xhigh", "max"],
                    help=f"model effort (default {DEFAULT_EFFORT}; env WHITEBOARD_EFFORT)")
    ap.add_argument("--debug-usage", action="store_true",
                    help="print model calls, tokens, cost and prompt part sizes per turn (stderr)")
    return ap.parse_args(argv)


def build(args: argparse.Namespace) -> Whiteboard:
    """Everything up to (not including) serving. Raises LaunchError for a bad launch."""
    library = normalise_library(args.library)
    fake = bool(args.fake) or flag("WHITEBOARD_FAKE")
    try:
        table = load(args.data)
    except DataError as e:
        raise LaunchError(str(e)) from None
    existing = load_existing(args.existing, library) if args.existing else None

    board = Board(Path(args.out).expanduser().resolve(), library)
    try:
        board.open()
    except OutputNotEmpty as e:
        raise LaunchError(str(e)) from None
    except (OSError, ValueError) as e:
        raise LaunchError(f"Cannot use output folder {args.out}: {e}") from None
    if existing:
        board.add(existing["title"], existing["code"], existing["kind"], card_id="G1", round=0)

    engine = "fake" if fake else "claude"
    replies = None
    if fake:
        from . import demo
        replies = demo.replies(library, table)
    else:
        clean_environment()
    budget = os.environ.get("WHITEBOARD_BUDGET")
    designer = Designer(board, table, args.style, engine=engine, model=None if fake else args.model,
                        effort=args.effort, max_budget_usd=float(budget) if budget else None, replies=replies,
                        debug=bool(args.debug_usage) or flag("WHITEBOARD_DEBUG_USAGE"))
    return Whiteboard(board, table, designer, args.style, engine,
                      idle_s=seconds("WHITEBOARD_IDLE_S", IDLE_S), connect_s=seconds("WHITEBOARD_CONNECT_S", CONNECT_S))


def seconds(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name) or default)
    except ValueError:
        return default
    return value if value > 0 else default


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        app = build(args)
        url = app.start(port=args.port)
    except LaunchError as e:
        print(f"whiteboard: {e}", file=sys.stderr, flush=True)
        return 2
    except OSError as e:
        print(f"whiteboard: cannot start the server: {e}", file=sys.stderr, flush=True)
        return 2
    b = app.board
    mode = ("fake engine (no tokens)" if app.engine == "fake"
            else f"model {args.model}, effort {args.effort}")
    print(f"Whiteboard: {url}", flush=True)
    start = "starting from the current visual (G1)" if b.cards else "new board"
    print(f"  library {b.library}, {len(app.table.rows)} rows, {start}, {mode}", flush=True)
    print(f"  output: {b.out} (saved visuals and result.json only)", flush=True)
    print("  Press Done in the page to finish (Ctrl+C also stops it). Unsaved cards are not kept.", flush=True)
    app.serve(open_browser=not (args.no_open or flag("WHITEBOARD_NO_OPEN")))
    if app.result is None:  # stopped without Done: still leave a result reflecting what was saved
        app.result = b.finish(done=False)
    if app.ended_by and app.ended_by != "done":
        print(f"Stopped without Done: {app.ended_by}.", flush=True)
    saved =", ".join(s["id"] for s in app.result["saved"]) or "none"
    print(f"Saved: {saved}", flush=True)
    print(f"RESULT: {b.result_file}", flush=True)
    return 0
