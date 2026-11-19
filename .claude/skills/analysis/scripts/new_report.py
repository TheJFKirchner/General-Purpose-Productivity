#!/usr/bin/env python3
"""Create a report folder from the template, and add one line to the project's map.

Usage:
  new_report.py <parent folder> <name> --title "Report title" --question "The question"
                [--for "who reads it"] [--source NAME=FILE ...] [--map <project CLAUDE.md>]

Creates <parent>/<name>/ with report.py, run.py, page.html and sections/_shared.py.
--source: fill SOURCES (FILE as seen from where you run this; stored relative to the report folder).
--map: add a row for the new folder to the "| Folder or file | Holds |" table in that file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "template"
MAP_HEAD = "| Folder or file | Holds |"


def add_map_line(claude_md: Path, folder: Path, title: str) -> str:
    if not claude_md.exists():
        return f"note: {claude_md.name} not found; add the map line yourself"
    lines = claude_md.read_text(encoding="utf-8").splitlines()
    rel = Path(os.path.relpath(folder, claude_md.parent)).as_posix()
    row = (f"| `{rel}/` | Report: {title.replace('|', '/')}. Refresh: new input files go where `report.py` "
           f"SOURCES points (same names), then `python run.py report` in this folder |")
    start = next((i for i, l in enumerate(lines) if l.strip().startswith(MAP_HEAD)), None)
    if start is not None:
        end = start + 1
        while end < len(lines) and lines[end].strip().startswith("|"):
            end += 1

        def path_of(line):
            return line.strip().strip("|").split("|")[0].strip().strip("`").rstrip("/")
        placeholder = [i for i in range(start + 2, end) if "not yet created" in lines[i].lower()
                       and path_of(lines[i]) in (rel, Path(rel).parent.as_posix())]
        if placeholder:
            lines[placeholder[0]] = row
            what = f"map: replaced the placeholder row with {row}"
        elif any(f"`{rel}/`" in l for l in lines[start:end]):
            return "map line already there"
        else:
            lines.insert(end, row)
            what = f"map: added {row}"
    else:
        # no table yet: add it, in the toolbox format, at the end of "## Map" (or a new "## Map")
        table = [MAP_HEAD, "| --- | --- |", row]
        head = next((i for i, l in enumerate(lines) if l.strip().lower() == "## map"), None)
        if head is None:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += ["", "## Map", "", *table]
        else:
            end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("#")), len(lines))
            while end > head + 1 and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = ["", *table] + ([""] if end < len(lines) and lines[end].strip() else [])
        what = f"map: added the map table with {row}"
    claude_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return what


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parent")
    ap.add_argument("name", help="short name, e.g. may-claims-spike")
    ap.add_argument("--title", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--map", help="the project's CLAUDE.md")
    ap.add_argument("--source", action="append", default=[], help="NAME=FILE, repeatable")
    ap.add_argument("--for", dest="reader", default="", help="who reads it, from the brief")
    args = ap.parse_args(argv)

    name = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
    if not name:
        print("STOP: the name needs letters or digits")
        return 2
    dest = Path(args.parent).resolve() / name
    if dest.exists():
        print(f"STOP: {dest} already exists")
        return 2
    sources = {}
    for s in args.source:
        key, _, path = s.partition("=")
        if not re.match(r"^[a-z][a-z0-9_]*$", key) or not path or not Path(path).exists():
            print(f"STOP: --source {s}: use name=file, a lower_snake_case name and a file that exists")
            return 2
        sources[key] = Path(os.path.relpath(Path(path).resolve(), dest)).as_posix()
    dest.mkdir(parents=True)
    for f in ("run.py", "page.html"):
        shutil.copy2(TEMPLATE / f, dest / f)
    (dest / "sections").mkdir()
    shutil.copy2(TEMPLATE / "_shared.py", dest / "sections" / "_shared.py")

    one = lambda s: " ".join(s.split())  # noqa: E731
    esc = lambda s: one(s).replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
    text = (TEMPLATE / "report.py").read_text(encoding="utf-8")
    text = (text.replace('"__TITLE__"', f'"{esc(args.title)}"').replace('"__QUESTION__"', f'"{esc(args.question)}"')
                .replace('"__FOR__"', f'"{esc(args.reader)}"')
                .replace("__TITLE__", one(args.title)).replace("__QUESTION__", one(args.question))
                .replace("__FOR__", one(args.reader))
                .replace("SOURCES = {}", "SOURCES = " + (repr(sources) if sources else "{}"))
                .replace("__DATE__", dt.date.today().isoformat()))
    (dest / "report.py").write_text(text, encoding="utf-8")

    print(f"Created {dest}")
    if args.map:
        print(add_map_line(Path(args.map).resolve(), dest, one(args.title)))
    print("Next: python run.py list (sources and columns), then python run.py add-section ... for each section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
