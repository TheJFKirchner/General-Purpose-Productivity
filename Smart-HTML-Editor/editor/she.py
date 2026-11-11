"""Smart HTML Editor command line.

    python she.py open    <file.html> [--port 8790] [--no-open] [--fake]   the interactive editor
    python she.py outline <file.html> [--node n12] [--depth 3]            data-free outline
    python she.py find    <file.html> "<text>"                             where some visible text is
    python she.py theme   <file.html>                                      theme variables and page rules
    python she.py edit    <file.html> '<json ops>' [--dry-run]             apply edits, back up, save

outline / find / theme / edit are for Claude Code: they show and change the page without its data
(numbers in text are {#k} tokens, scripts, charts and data tables are summarized), so the file never
has to be read. Ops for edit (a JSON list, applied in order):

    {"op": "set_text", "id": "t21", "text": "Sales rose {#1}", "old": "optional part to replace"}
    {"op": "set_style", "node": "n8", "styles": {"color": "#0f766e", "font-size": ""}}
    {"op": "set_attr", "node": "n9", "name": "class", "value": "subtitle lead"}
    {"op": "set_theme_var", "var": "v1", "value": "#dc2626"}
    {"op": "set_page_rule", "selector": ".card h2", "declarations": "color: teal"}
    {"op": "replace_markup", "node": "n13", "html": "<b>New</b> text {#1}"}

Typed numbers are allowed here (Claude Code works for the person directly). replace_markup renumbers
the elements after it: run outline again before using their ids.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from htmldoc import Doc, EditError  # noqa: E402
from workspace import STATE_DIR, read_html  # noqa: E402


def load(path: str) -> tuple[Path, Doc, str, bytes]:
    p = Path(path).resolve()
    text, enc, bom = read_html(p)
    return p, Doc(text, p.name), enc, bom


def flag(args: list[str], name: str, default=None):
    if name in args:
        i = args.index(name)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


def apply_op(d: Doc, op: dict) -> str:
    kind = op.get("op")
    if kind == "set_text":
        return d.set_text(op["id"], op["text"], op.get("old"), allowed_digits=None)
    if kind == "set_style":
        return d.set_style(op["node"], op["styles"])
    if kind == "set_attr":
        return d.set_attr(op["node"], op["name"], op.get("value"), allowed_digits=None)
    if kind == "set_theme_var":
        return d.set_theme_var(op["var"], op["value"])
    if kind == "set_page_rule":
        return d.set_page_rule(op["selector"], op.get("declarations", ""))
    if kind == "replace_markup":
        return d.replace_markup(op["node"], op["html"], allowed_digits=None)
    raise EditError(f"unknown op {kind!r}")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "open":
        from server import main as serve
        serve(args)
        return 0
    node = flag(args, "--node", "n0")
    depth = int(flag(args, "--depth", "3"))
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    path, d, enc, bom = load(args[0])
    if cmd == "outline":
        print(d.page_summary())
        print(d.outline(node, depth=depth, max_lines=400))
    elif cmd == "find":
        print(d.find_text(" ".join(args[1:])))
    elif cmd == "theme":
        print("Theme variables:\n" + d.theme_text() + "\nPage rules:\n" + d.page_rules_text())
    elif cmd == "edit":
        ops = json.loads(args[1])
        for i, op in enumerate(ops if isinstance(ops, list) else [ops], 1):
            try:
                print(f"{i}. {op.get('op')}: {apply_op(d, op)}")
            except (EditError, KeyError, TypeError) as e:
                print(f"{i}. {op.get('op')}: REFUSED: {e}\nNothing was saved.")
                return 1
        if dry or not d.dirty:
            print("Dry run: nothing saved." if dry else "No changes.")
            return 0
        backups = path.parent / STATE_DIR / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / f"{path.stem}.{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}"
        shutil.copy2(path, backup)
        path.write_bytes(bom + d.src.encode(enc, errors="xmlcharrefreplace"))
        print(f"Saved {path.name}. Backup: {STATE_DIR}/backups/{backup.name}")
    else:
        print(f"unknown command {cmd!r}\n{__doc__}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
