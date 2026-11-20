"""Make a new dashboard from this skill's starter.

    python <skill>/tools/setup.py <new dashboard folder> --title "Claims dashboard" [--theme TH-02]
        [--library <folder>]  the design library, when it is not found by itself
        [--keep-examples]   keep the two example sections, their sample data, commentary and report (a first look)
        [--no-install]      skip npm install and the check

What it does, and nothing else:
  - copies starter/ and themes/ (as Themes/) into the folder, which must be new or empty
    (dot-folders like .git or .claude are fine)
  - finds the design library (--library; a project CLAUDE.md "Design library:" line; design-library beside
    .claude; Toolkit Update/design-library; looking up from the new folder, then from this skill), takes the
    theme from it (--theme, default TH-01) and its current page files (host.css, host-runtime.js)
  - removes the example sections, their analytics, sample-data script and report (unless --keep-examples)
  - writes dashboard.config.json: title, a free port for the analysis server, and the Python command to use
  - runs npm install, checks the Python packages, and runs npm run check

After this the dashboard is self-contained: nothing in it runs from, imports from or looks up this skill folder.
It never writes outside the new folder and never overwrites a file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
STARTER = SKILL / "starter"
THEMES = SKILL / "themes"
EXAMPLES = [
    "Src/Sections/s1_summary.jsx",
    "Src/Sections/s2_revenue_trend.jsx",
    "Analysis/example.py",
    "Pipeline/example_sales_monthly.py",
    "Reports/example.json",
    "Reports/example.py",
]
EXAMPLE_COMMENTARY = [
    {"id": "C1", "commentary": ["Revenue follows a December peak each year.", "Growth is steady across the window."],
     "source": "Example text for the sample data. The commentary skill writes the real file."},
    {"id": "C1", "filters": {"region": "East"}, "commentary": ["East is the largest region in the sample data."],
     "source": "Example text for the sample data, East only."},
]
EMPTY_INDEX = """// The sections in the order they appear, and the tabs if there are any.
// npm run new-section -- <name> adds to these lists; editing by hand is fine too.
// One page: leave `tabs` empty and give sections no meta.tab. Tabs: list them here and give each section a meta.tab.

export const tabs = [];

export default [];
"""
HOST_FILES = {"host.css": "Src/host.css", "host-runtime.js": "Src/Lib/host-runtime.js"}
PY_PACKAGES = ["fastapi", "uvicorn", "duckdb", "pyarrow", "pandas"]
IGNORE = shutil.ignore_patterns("node_modules", "__pycache__", "*.pyc", ".vite*", ".export", "Data", "Dist")


def say(msg: str = "") -> None:
    print(msg, flush=True)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "dashboard"


def free_port(start: int = 8765, tries: int = 200) -> int:
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=(os.name == "nt" and cmd[0] in ("npm", "npx")))
    except (FileNotFoundError, OSError) as e:
        return 127, f"{cmd[0]} not found ({e})"
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def missing_packages(python: str, cwd: Path) -> list[str] | None:
    """Python packages this command lacks, or None when the command doesn't run at all."""
    code, _ = run([python, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"], cwd)
    if code != 0:
        return None
    return [p for p in PY_PACKAGES if run([python, "-c", f"import {p}"], cwd)[0] != 0]


def pick_python(cwd: Path) -> tuple[str, list[str]]:
    """The Python command to record: the plain command if it has everything, else this Python if it does."""
    default = "python" if os.name == "nt" else "python3"
    plain = missing_packages(default, cwd)
    if plain == []:
        return default, []
    mine = missing_packages(sys.executable, cwd)
    if mine == []:
        return sys.executable, []
    return default, (plain if plain is not None else PY_PACKAGES)


def find_library(given: str | None, dest: Path) -> Path | None:
    """The design library folder (it holds item.js), or None."""
    def ok(p: Path) -> bool:
        return (p / "item.js").is_file()
    if given:
        p = Path(given).expanduser().resolve()
        return p if ok(p) else None
    for start in (dest, SKILL):
        for d in [start, *start.parents]:
            claude_md = d / "CLAUDE.md"
            if claude_md.is_file():
                m = re.search(r"Design library:\s*`?([^`\n]+?)`?\s*$", claude_md.read_text(encoding="utf-8", errors="replace"), re.M)
                if m and ok((d / m.group(1).strip()).resolve()):
                    return (d / m.group(1).strip()).resolve()
            if (d / ".claude").is_dir() and ok(d / "design-library"):
                return d / "design-library"
            if ok(d / "Toolkit Update" / "design-library"):
                return d / "Toolkit Update" / "design-library"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Make a new dashboard from the starter.")
    ap.add_argument("folder", help="the new dashboard folder (created if missing; must be empty)")
    ap.add_argument("--title", default=None, help="dashboard title (default: the folder name)")
    ap.add_argument("--theme", default="TH-01", help="the design library theme id (default TH-01)")
    ap.add_argument("--library", default=None, help="the design library folder, when it is not found by itself")
    ap.add_argument("--keep-examples", action="store_true", help="keep the example sections, sample data and report")
    ap.add_argument("--no-install", action="store_true", help="skip npm install and the check")
    a = ap.parse_args()

    dest = Path(a.folder).expanduser().resolve()
    title = a.title or dest.name.replace("-", " ").replace("_", " ").strip().title()

    # ---- the folder must be new or empty (dot-folders allowed)
    if dest.exists() and not dest.is_dir():
        say(f"setup: {dest} is a file, not a folder. Pick a folder name.")
        return 1
    if dest.exists():
        contents = [p for p in dest.iterdir() if not p.name.startswith(".")]
        if contents:
            names = ", ".join(sorted(p.name for p in contents)[:8])
            say(f"setup: {dest} isn't empty ({names}{', ...' if len(contents) > 8 else ''}).")
            say("  Nothing was changed. Use a new folder, e.g. a 'dashboard' subfolder inside it.")
            return 1
    if dest == SKILL or SKILL in dest.parents:
        say("setup: the dashboard can't go inside the skill folder. Pick another place.")
        return 1
    if "onedrive" in str(dest).lower():
        say("note: this folder is in OneDrive. It works, but the installed packages (node_modules) sync slowly;")
        say("      a folder outside OneDrive is better if you have the choice.")

    # ---- copy
    say(f"Setting up '{title}' in {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STARTER, dest, ignore=IGNORE, dirs_exist_ok=True)
    shutil.copytree(THEMES, dest / "Themes", ignore=IGNORE, dirs_exist_ok=True)
    (dest / "Data" / "Current").mkdir(parents=True, exist_ok=True)
    say("  copied the starter and the theme")

    if a.keep_examples:
        (dest / "commentary.json").write_text(json.dumps(EXAMPLE_COMMENTARY, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        for rel in EXAMPLES:
            (dest / rel).unlink(missing_ok=True)
        (dest / "Src" / "Sections" / "index.js").write_text(EMPTY_INDEX, encoding="utf-8", newline="\n")
        say("  removed the example sections (add your own with: npm run new-section -- <name> --use <id> ...)")

    # ---- config
    python, missing = pick_python(dest)
    cfg_path = dest / "dashboard.config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    cfg["project"] = slug(dest.name)
    cfg["title"] = title
    cfg["python"] = python
    if not a.keep_examples:
        cfg["dataSource"] = ""
        # the example's "region" filter belongs to the sample data; real filters are added once the data is known
        cfg["filters"] = {"_note": "Fast filters: every value is already in the loaded tables, e.g. \"region\": {\"label\": \"Region\", \"column\": \"region\"}. "
                                   "Each lives at one level: no tab/section = the whole dashboard (above the tabs); \"tab\": \"<tab id>\" = that tab; \"section\": \"<section id>\" = that section. "
                                   "A filter whose data must be re-queried goes under parameters (slow, always dashboard-wide). "
                                   "See the dashboard skill, references/data.md."}
    port = free_port(8765)
    lib = find_library(a.library, dest)
    cfg.setdefault("server", {})["port"] = port
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8", newline="\n")
    say(f"  title set; analysis server port {port}; python: {python}")

    # ---- the design library: theme and page files
    problems = []
    if lib:
        for name, rel in HOST_FILES.items():
            shutil.copyfile(lib / name, dest / rel)
        code, text = run(["node", "Tools/theme.mjs", a.theme.upper(), "--library", str(lib)], dest)
        say(f"  {text.strip().splitlines()[-1] if text.strip() else 'theme: no output'}")
        if code != 0:
            problems.append(f"theme {a.theme} not set: {text.strip().splitlines()[-1] if text.strip() else 'no output'}")
    else:
        problems.append("no design library found, so the dashboard has theme TH-01 and cannot add library items yet; "
                        "run setup again with --library <folder>, or later in the dashboard: npm run theme -- TH-01 --library <folder>")

    # ---- install and check
    if missing:
        problems.append(f"Python 3.10+ packages missing: {' '.join(missing)}  ->  {python} -m pip install {' '.join(missing)}")
    if not a.no_install:
        say("  npm install (a minute or two)...")
        code, text = run(["npm", "install", "--no-audit", "--no-fund"], dest)
        if code != 0:
            problems.append("npm install failed: " + (text.strip().splitlines()[-1] if text.strip() else "no output"))
    if a.keep_examples and not missing:
        code, text = run([python, "Pipeline/run_all.py"], dest)
        say("  made the sample data" if code == 0 else "  sample data failed: " + text.strip().splitlines()[-1])
    if not a.no_install and not problems:
        code, text = run(["npm", "run", "check", "--silent"], dest)
        last = [line for line in text.strip().splitlines() if line.strip()]
        say(f"  check: {last[-1] if last else 'no output'}")

    say()
    for p in problems:
        say(f"TO DO: {p}")
    say("Next:")
    say("  - data: one write_source line per input file in Pipeline/sources.py, then npm run pipeline")
    say("  - sections: npm run new-section -- <name> --use <library id> --page <tab> --tables <table> --slot <slot>=<column>")
    say("  - look: npm run shot -- <tab>  (saved in Data/.shots/; or npm run dev; npm run stop)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:  # say what went wrong in plain words instead of a traceback
        print(f"setup: stopped: {type(e).__name__}: {e}")
        sys.exit(1)
