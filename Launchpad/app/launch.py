"""Start Launchpad: free port + access code -> server on a background thread -> pywebview window.

    python -m app.launch                     # own window (pywebview), project = current folder
    python -m app.launch --cwd <folder>      # plan and build in another project folder
    python -m app.launch --browser           # open in the default browser instead
    python -m app.launch --fake              # scripted demo on the fake engine (zero tokens)
    python -m app.launch --no-window --port 8765 --code dev [--fake]    # dev/testing: server only, fixed URL

- Session folders go to <project>/.launchpad/<session-id>/ (git-ignored)
- Server runs in its own Proactor event loop (Windows needs it for the Agent SDK subprocess)
- pywebview owns the main thread (D65)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from .server import create_app
from .settings import Settings

FAKE_QUESTION_TIMEOUT_S = 30          # demo default so the timer is watchable


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_server(port: int, code: str, settings: Settings, store=None, overridden=()):
    app = create_app(port, code, settings, store=store, overridden=overridden)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def target():
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    threading.Thread(target=target, name="launchpad-server", daemon=True).start()
    for _ in range(100):                      # wait until it answers
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5)
            break
        except OSError:
            time.sleep(0.1)
    return server, app


# launch option (argparse dest) -> setting name; an option given on the command line overrides the stored
# setting for this launch only (not saved)
LAUNCH_OPTIONS = {"question_timeout": "question_timeout_s", "permission_timeout": "permission_timeout_s",
                  "autopilot": "autopilot_default", "planner_start": "planner_start_model",
                  "planner_top": "planner_top_model", "promotion_window": "promotion_window_turns",
                  "promotion_criteria": "promotion_criteria_path", "pilot_model": "pilot_model",
                  "visual_model": "visual_model"}


def demo_directories() -> list[Path]:
    """Two scratch folders for the fake demo (File Explorer, sessions in either), in the temp folder. "Demo shop" has
    one folder agent (copy-reviewer, app/demo.py) that the demo plan names for a step. Every launch restores them to
    exactly these contents (earlier sessions, created agents and edits are removed, best-effort)."""
    import shutil
    import tempfile
    from .demo import FOLDER_AGENT_FILE, FOLDER_AGENT_NAME
    base = Path(tempfile.gettempdir()) / "launchpad-demo"
    out = []
    for name, files in (("Demo shop", {"README.md": "# Demo shop\nA small web shop (made up).\n",
                                       "notes/ideas.md": "# Ideas\n- CSV export on the orders page\n",
                                       "app.py": "print('shop')\n",
                                       f".claude/agents/{FOLDER_AGENT_NAME}.md": FOLDER_AGENT_FILE}),
                        ("Demo clinic", {"README.md": "# Demo clinic\nClinic operations scripts (made up).\n",
                                         "data/appointments.csv": "date,clinic,booked\n2026-11-01,North,42\n",
                                         "logo.png": None})):
        d = base / name
        shutil.rmtree(d, ignore_errors=True)            # a locked leftover must not stop the launch
        for rel, text in files.items():
            f = d / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00demo" if text is None else text.encode("utf-8"))
        out.append(d)
    return out


def build_settings(args):
    """-> (settings, store, overridden). Stored settings + connected folders from the per-user store; launch
    options override for this launch; --cwd is added to the folders and is this launch's default."""
    from .store import Store, launchpad_home
    if args.fake and not os.environ.get("LAUNCHPAD_HOME"):
        import tempfile
        os.environ["LAUNCHPAD_HOME"] = str(Path(tempfile.gettempdir()) / "launchpad-demo" / "home")
        reset_demo_home(launchpad_home())             # the demo's own store starts clean: counts at zero, no backups
    store = Store.default()
    if args.fake:
        for d in demo_directories():
            store.add(d)
    if args.cwd:
        project = Path(args.cwd).expanduser().resolve()
        if not project.is_dir():
            raise SystemExit(f"--cwd folder not found: {project}")
        store.add(project)
    else:
        did = store.default_id()
        entry = store.get(did) if did else None
        project = Path(entry["path"]) if entry and Path(entry["path"]).is_dir() else Path(os.getcwd()).resolve()
    values = store.values()
    if args.fake:                                    # watchable timers in the demo unless set on the command line
        values.update(question_timeout_s=float(FAKE_QUESTION_TIMEOUT_S), permission_timeout_s=45.0)
    overridden = set()
    for opt, name in LAUNCH_OPTIONS.items():
        v = getattr(args, opt)
        if v is not None:
            values[name] = v
            overridden.add(name)
    settings = Settings(project=project, engine="fake" if args.fake else "claude", planner_model=args.model, **values)
    if args.fake:
        from . import demo                    # imports agentlib.fake, which registers the "fake" engine
        demo.install(project)
        demo_app_root()                        # the editor in the demo edits a copy, never the real agent files
    print(f"Settings and connected folders: {launchpad_home() / 'settings.json'}", flush=True)
    return settings, store, overridden


def reset_demo_home(home: Path) -> None:
    """Best-effort wipe of the fake demo's own per-user folder (settings.json with folders + use counts, backups)."""
    import shutil
    for p in (home / "settings.json", home / "backups"):
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink(missing_ok=True)
        except OSError:
            pass


def demo_app_root() -> Path:
    """Fresh temporary copy of the app's editable files (agent definitions + criteria) for the fake demo."""
    import shutil
    import tempfile
    from .agents import crew
    dest = Path(tempfile.gettempdir()) / "launchpad-demo" / "app-files"
    for old in (dest.parent.glob("app-files-*") if dest.parent.is_dir() else []):   # copies from earlier launches
        shutil.rmtree(old, ignore_errors=True)
    if dest.exists():
        try:
            shutil.rmtree(dest)
        except OSError:                        # a leftover copy that cannot be removed (locked or protected): use a new folder
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest = Path(tempfile.mkdtemp(prefix="app-files-", dir=dest.parent))
    for rel, src in crew.editable_files(crew.ROOT).items():   # the real files, same layout (app/agents/...)
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / rel)
    crew.use_app_root(dest)
    return dest


def folder_picker():
    """Native folder dialog of the pywebview window (window mode only) -> path or None."""
    import webview
    if not webview.windows:
        return None
    kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or getattr(webview, "FOLDER_DIALOG", None)
    res = webview.windows[0].create_file_dialog(kind)
    return str(res[0]) if res else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Launchpad")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--code", default="", help="access code (dev only; random by default)")
    ap.add_argument("--cwd", default="", help="add this folder to the connected folders and use it as this launch's default (default: the last used folder, else the current one)")
    ap.add_argument("--model", default=None, help="pin the planner to one model (turns promotion off)")
    ap.add_argument("--planner-start", default=None, help="model every planner session starts on (setting; default sonnet)")
    ap.add_argument("--planner-top", default=None,
                    help="model the planner is promoted to (setting; default opus; same as --planner-start = no promotion)")
    ap.add_argument("--promotion-window", type=int, default=None, help="turns in which the planner may promote itself (setting; default 2)")
    ap.add_argument("--promotion-criteria", default=None, help="replacement criteria file (markdown)")
    ap.add_argument("--visual-model", default=None, help="visual agent (Visualizer) model override (default: haiku)")
    ap.add_argument("--pilot-model", default=None, help="Claude Code chat model override (default: sonnet, from its file)")
    ap.add_argument("--fake", action="store_true", help="scripted demo on the fake engine (zero tokens)")
    ap.add_argument("--question-timeout", type=float, default=None,
                    help=f"seconds before a timed builder question auto-answers (default 180; {FAKE_QUESTION_TIMEOUT_S} with --fake)")
    ap.add_argument("--permission-timeout", type=float, default=None,
                    help="seconds before a builder permission card is denied (default 180; 45 with --fake)")
    ap.add_argument("--autopilot", action="store_const", const=True, default=None,
                    help="new sessions start with autopilot on: every builder permission request is approved")
    ap.add_argument("--browser", action="store_true", help="open in the default browser instead of a window")
    ap.add_argument("--no-window", action="store_true", help="server only; print the URL")
    args = ap.parse_args()

    settings, store, overridden = build_settings(args)
    port = args.port or free_port()
    code = args.code or secrets.token_urlsafe(16)
    server, app = run_server(port, code, settings, store, overridden)
    url = f"http://127.0.0.1:{port}/?port={port}&code={code}"
    mode = " (fake engine demo, zero tokens)" if args.fake else ""
    print(f"Launchpad running{mode}: {url}\nDefault folder: {settings.project}", flush=True)

    try:
        if args.no_window:
            while True:
                time.sleep(3600)
        elif args.browser:
            webbrowser.open(url)
            while True:
                time.sleep(3600)
        else:
            import webview
            app.state.hub.picker = folder_picker      # native folder picker for "Add folder"
            webview.create_window("Launchpad", url, width=1360, height=880, min_size=(980, 640))
            webview.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        time.sleep(1.5)                        # let agent sessions close


if __name__ == "__main__":
    main()
