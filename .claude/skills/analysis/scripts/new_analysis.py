#!/usr/bin/env python3
"""Create a new analysis folder from the template and add it to the parent folder's index.

Usage: new_analysis.py <parent folder> <name> --title "Report title" --question "The question"

Creates <parent>/<yyyy-mm>-<name>/ and adds a row to <parent>/README.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "template"
INDEX_HEAD = ("# Analyses\n\nOne folder per analysis. Open a folder's README.md for its request and storyline; "
              "run it with `python run.py`.\n\n| Folder | Question | Created |\n| --- | --- | --- |\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parent")
    ap.add_argument("name", help="short name, e.g. claims-source-compare")
    ap.add_argument("--title", required=True)
    ap.add_argument("--question", required=True)
    args = ap.parse_args(argv)

    name = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
    if not name:
        print("STOP: name needs letters or digits")
        return 2
    today = dt.date.today()
    folder = name if re.match(r"^\d{4}-\d{2}-", name) else f"{today:%Y-%m}-{name}"
    parent = Path(args.parent).resolve()
    dest = parent / folder
    if dest.exists():
        print(f"STOP: {dest} already exists")
        return 2
    parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns("__pycache__"))
    one_line = lambda s: " ".join(s.split())  # noqa: E731
    for rel in ("README.md", "config.py"):
        p = dest / rel
        text = p.read_text(encoding="utf-8")
        quote = (lambda s: s.replace("\\", "\\\\").replace('"', '\\"')) if rel.endswith(".py") else (lambda s: s)
        text = (text.replace("__TITLE__", quote(one_line(args.title)))
                    .replace("__QUESTION__", quote(one_line(args.question)))
                    .replace("__DATE__", today.isoformat()))
        p.write_text(text, encoding="utf-8")

    index = parent / "README.md"
    if not index.exists():
        index.write_text(INDEX_HEAD, encoding="utf-8")
    if "| Folder | Question | Created |" in index.read_text(encoding="utf-8"):
        with index.open("a", encoding="utf-8") as f:
            f.write(f"| [{folder}]({folder}/README.md) | {one_line(args.question).replace('|', '/')} | {today.isoformat()} |\n")
    else:
        print(f"note: {index} exists without an analyses table; no index row added")

    print(f"Created {dest}")
    print("Next: copy the approved brief into README.md, fill SOURCES in config.py, "
          "rename sections/s1_rename_me.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
