"""Live activity feed: one `activity` event per tool call (started, then done | denied | failed).

- summary = one short line: Bash command, file path, search pattern, or a brief label for custom tools;
  capped at SUMMARY_MAX characters; never file contents
- Every finished call is also appended to <session folder>/activity.log (pairs with operations-manual.md)
- The hub keeps the most recent events for the reconnect snapshot
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .sessionfiles import one_line

SUMMARY_MAX = 140
FILE_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path", "NotebookRead": "notebook_path"}
_DENIED = ("denied", "not allowed", "refused")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _path(p, project: Path | None) -> str:
    s = str(p or "")
    if project is not None and s:
        try:
            return Path(s).resolve().relative_to(project).as_posix() if Path(s).is_absolute() else s
        except (ValueError, OSError):
            return s
    return s


def summarize(tool: str, args: dict, project: Path | None = None) -> str:
    """One short line describing a tool call (no file contents)."""
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
        s = a.get("path", "")
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
