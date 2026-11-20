#!/usr/bin/env python3
"""Create a report folder from the template, and add one line to the project's map.

Usage:
  new_report.py [<parent folder>] <name> --title "Report title" --question "The question"
                [--for "who reads it"] [--source NAME=FILE ...] [--map <project CLAUDE.md>]
                [--theme TH-02] [--library <design library folder>]

No parent folder: reports/<name>/ under the folder you run this from.
Creates <parent>/<name>/ with report.py, run.py, page.html and sections/_shared.py.
--source: fill SOURCES (FILE as seen from where you run this; stored relative to the report folder).
--map: add a row for the new folder to the "| Folder or file | Holds |" table in that file.
--theme: a design-library theme for the page (needs Node.js); default the library's TH-01.
The design library (for --theme and later add-section) is found: --library; the map's `Design library:`
line; design-library beside .claude; Toolkit Update/design-library. Its host files are copied into page.html.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
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


def find_library(given, claude_md):
    """First that exists: --library; the map's `Design library:` line; design-library beside .claude;
    Toolkit Update/design-library."""
    cands = [Path(given)] if given else []
    if claude_md and Path(claude_md).is_file():
        m = re.search(r"Design library:\**\s*`?([^`\n|]+?)`?\s*(?:\||$)", Path(claude_md).read_text(encoding="utf-8"), re.M)
        if m:
            p = Path(m.group(1).strip()).expanduser()
            cands.append(p if p.is_absolute() else Path(claude_md).resolve().parent / p)
    home = Path(__file__).resolve().parents[4]          # the folder holding .claude
    cands += [home / "design-library", home / "Toolkit Update" / "design-library"]
    return next((c.resolve() for c in cands if (c / "item.js").is_file()), None)


def dress_page(page: Path, lib, theme) -> str:
    """The library's current host files into page.html, and the theme's tokens when one is given."""
    if lib is None:
        return "note: design library not found; page.html keeps the template's copy of its host files"
    text = page.read_text(encoding="utf-8")
    for tag, ident, f in (("style", "host-css", "host.css"), ("script", "host-runtime", "host-runtime.js"),
                          ('script', 'host-motion" type="text/x-host-motion', "host-motion.js")):
        body = (lib / f).read_text(encoding="utf-8").strip()
        text = re.sub(rf'(<{tag} id="{ident}">\n)[\s\S]*?(\n</{tag}>)', lambda m: m.group(1) + body + m.group(2),
                      text, count=1)
    page.write_text(text, encoding="utf-8")
    if not theme:
        return ""
    r = subprocess.run([sys.executable, str(page.parent / "run.py"), "theme", theme, "--library", str(lib)],
                       capture_output=True, text=True, encoding="utf-8", cwd=page.parent)
    return r.stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("where", nargs="+", metavar="[parent] name",
                    help="short name, e.g. may-claims-spike; a parent folder before it (default: reports)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--map", help="the project's CLAUDE.md")
    ap.add_argument("--source", action="append", default=[], help="NAME=FILE, repeatable")
    ap.add_argument("--for", dest="reader", default="", help="who reads it, from the brief")
    ap.add_argument("--theme", help="a design-library theme id, e.g. TH-02")
    ap.add_argument("--library", help="the design library folder, when it is not found by itself")
    args = ap.parse_args(argv)

    if len(args.where) > 2:
        print("STOP: give at most a parent folder and a name")
        return 2
    parent, raw = (args.where if len(args.where) == 2 else ["reports", args.where[0]])
    name = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if not name:
        print("STOP: the name needs letters or digits")
        return 2
    dest = Path(parent).resolve() / name
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
    lib = find_library(args.library, args.map)
    try:
        rel_lib = Path(os.path.relpath(lib, dest)).as_posix() if lib else ""
    except ValueError:                                   # another drive: search for it each time instead
        rel_lib = ""
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
                .replace('LIBRARY = ""', "LIBRARY = " + json.dumps(rel_lib))
                .replace("__DATE__", dt.date.today().isoformat()))
    (dest / "report.py").write_text(text, encoding="utf-8")

    print(f"Created {dest}")
    said = dress_page(dest / "page.html", lib, args.theme)
    if said:
        print(said)
    if args.map:
        print(add_map_line(Path(args.map).resolve(), dest, one(args.title)))
    print("Next: python run.py list (sources and columns), then python run.py add-section NAME --use <id> ... per section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
