"""Live activity feed: one `activity` event per tool call (started, then done | denied | failed).

- summary = one short line: Bash command, file path, search pattern, or a brief label for custom tools;
  capped at SUMMARY_MAX characters; never file contents
- Every finished call is also appended to <session folder>/activity.log (pairs with operations-manual.md)
- The hub keeps the most recent events for the reconnect snapshot
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .sessionfiles import one_line

SUMMARY_MAX = 140
FILE_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "NotebookRead": "notebook_path"}
_DENIED = ("denied", "not allowed", "refused")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


APP_DIR = Path(__file__).resolve().parent.parent      # the Launchpad folder: built-in files are shown relative to it


def _roots(project) -> list[Path]:
    """`project` may be one folder, a list of them, or None; the app folder is always the last root."""
    items = project if isinstance(project, (list, tuple, set)) else [project]
    out: list[Path] = []
    for r in items:
        if r is None:
            continue
        try:
            r = Path(r).resolve()
        except OSError:
            continue
        out.append(r.parent if r.is_file() else r)
    return out + [APP_DIR]


def _is_abs(s: str) -> bool:
    return Path(s).is_absolute() or bool(re.match(r"^[A-Za-z]:[\\/]", s)) or s.startswith(("\\\\", "/"))


def _path(p, project) -> str:
    """A file path for the feed and activity.log: relative to the first folder it is inside (the session's folders
    first, then the app folder); never an absolute path (one outside every known folder shows as .../parent/name)."""
    s = str(p or "")
    if not s or not _is_abs(s):
        return s
    try:
        full = Path(s).resolve()
    except OSError:
        full = Path(s)
    for r in _roots(project):
        try:
            return full.relative_to(r).as_posix()
        except ValueError:
            continue
    parts = [x for x in re.split(r"[\\/]", s) if x and not x.endswith(":")]
    return ".../" + "/".join(parts[-2:])


def summarize(tool: str, args: dict, project=None) -> str:
    """One short line describing a tool call (no file contents). `project` = the folder(s) paths are shown relative to."""
    a = args or {}
    if tool == "Bash":
        s = a.get("command", "")
    elif tool in FILE_TOOLS:
        s = _path(a.get(FILE_TOOLS[tool]), project)
    elif tool == "Grep":
        s = f"{a.get('pattern', '')}" + (f" in {_path(a.get('path'), project)}" if a.get("path") else "")
    elif tool == "Glob":
        s = f"{a.get('pattern', '')}" + (f" in {_path(a.get('path'), project)}" if a.get("path") else "")
    elif tool == "WebFetch":
        s = a.get("url", "")
    elif tool == "WebSearch":
        s = a.get("query", "")
    elif tool == "explore":
        s = f"Explorer: {a.get('question', '')}"
    elif tool == "read_markdown":
        s = _path(a.get("path", ""), project)
    elif tool == "show_visuals":
        s = f"visuals: {a.get('brief', '')} ({len(a.get('options') or [])} options)"
    elif tool == "write_plan":
        s = f"plan draft: {a.get('name', '')} ({len(a.get('steps') or [])} steps)"
    elif tool == "run_builder":
        s = f"start step {a.get('step', '?')}"
    elif tool == "write_report":
        s = "final report"
    elif tool == "ask_question":
        s = f"{'blocking' if a.get('blocking') else 'timed'} question: {a.get('title', '')}"
    elif tool == "add_to_flight_log":
        s = f"flight log: {a.get('path', '')}"
    elif tool == "submit_report":
        s = f"step report ({a.get('status', '?')})"
    elif tool == "ask_user":
        s = f"question round ({len(a.get('questions') or [])} questions)"
    else:
        s = tool
    return one_line(s, SUMMARY_MAX) or tool


def final_status(is_error: bool, text: str) -> str:
    if not is_error:
        return "done"
    return "denied" if any(w in (text or "").lower() for w in _DENIED) else "failed"


def log_line(ev: dict, started: str) -> str:
    return (f"{started} | {ev['status']:<7} | {ev['name']} | {ev['tool']} | {ev['summary']}")
