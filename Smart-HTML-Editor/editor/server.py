"""Local server for the Smart HTML Editor. Standard library only; the Claude Agent SDK is imported
lazily so the editor works (typing, quick styles, theme, save) even without it.

    python she.py open <file.html> [--port 8790] [--no-open] [--fake]

Pages:
  GET  /                         the editor (ui/editor.html)
  GET  /ui/<file>                its script and styles
  GET  /doc/<file name>          the page, with data-she-id on each element (served only; never saved)
  GET  /doc/<other path>         files next to the page (images, CSS, scripts it links to)
API (JSON):
  GET  /api/state                polled by the editor: version, unsaved changes, selection, look requests
  GET  /api/info                 file, page summary, theme variables, page rules, assistant setup
  GET  /api/runs?nodes=n1,n2     direct texts of elements, for typing in place (stays in the browser)
  GET  /api/node?node=n12        what an element is (label, path) for the panel
  POST /api/select   {node, struct_seq, info}           the person clicked an element
  POST /api/text     {run, old, text, struct_seq}       the person typed new text
  POST /api/style    {node, styles}                     quick style controls
  POST /api/var      {var, value}                       theme panel
  POST /api/rule     {selector, declarations}           page rules ("" removes)
  POST /api/styles   {id, info}                         the page answering a look request
  POST /api/undo · /api/save · /api/discard · /api/reload
  POST /api/chat     {message}  ·  /api/chat/reset
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import mimetypes
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from assistant import Assistant  # noqa: E402
from htmldoc import EditError  # noqa: E402
from workspace import Workspace  # noqa: E402

UI = HERE / "ui"
REQUEST_WAIT = 150          # seconds an HTTP request waits for the assistant

# Variables a Claude Code session injects into child processes. If the editor was started from
# inside one, drop them so the assistant signs in like a normal terminal.
SESSION_VAR_KEEP = {"CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
                    "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_GIT_BASH_PATH", "CLAUDE_CONFIG_DIR"}


def clean_environment():
    if "CLAUDE_CODE_ENTRYPOINT" not in os.environ and "CLAUDECODE" not in os.environ:
        return
    for k in list(os.environ):
        if k in SESSION_VAR_KEEP:
            continue
        if k in ("CLAUDECODE", "CLAUDE_PID", "ANTHROPIC_BASE_URL") or k.startswith(("CLAUDE_CODE_", "CLAUDE_AGENT_SDK_")):
            del os.environ[k]


def auth_source() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "API key (ANTHROPIC_API_KEY)"
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "gateway token (ANTHROPIC_AUTH_TOKEN)"
    if any(os.environ.get(v) for v in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")):
        return "cloud provider (Bedrock / Vertex / Foundry)"
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return "Claude token (CLAUDE_CODE_OAUTH_TOKEN)"
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    if (config_dir / ".credentials.json").exists():
        return "your Claude Code login"
    return None


class App:
    def __init__(self, ws: Workspace, settings: dict):
        self.ws = ws
        self.settings = settings
        self.assistant = Assistant(ws, settings)
        self.busy = False
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def run(self, coro, timeout=REQUEST_WAIT):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def health(self) -> dict:
        problems = []
        if not self.settings["fake"]:
            if importlib.util.find_spec("claude_agent_sdk") is None:
                problems.append("Python package claude-agent-sdk is not installed: pip install -r editor/requirements.txt")
            if not auth_source():
                problems.append("No Claude sign-in found: run `claude` in a terminal and /login, then restart the editor")
        return {"ok": not problems, "problems": problems, "auth": auth_source(), "model": self.settings["model"],
                "effort": self.settings["effort"], "test_mode": self.settings["fake"]}

    def info(self) -> dict:
        ws = self.ws
        with ws.lock:
            d = ws.doc
            return {"file": ws.path.name, "folder": str(ws.path.parent), "summary": d.page_summary(),
                    "vars": [{"id": v["id"], "name": v["name"], "value": v["value"], "context": v["context"]} for v in d.css_vars()],
                    "rules": [{"selector": s, "declarations": dcl} for s, dcl in d.page_rules()],
                    "health": self.health(), **ws.state()}

    async def chat(self, message: str) -> dict:
        if self.busy:
            return {"error": "The assistant is still working on the last request."}
        if not message.strip():
            return {"error": "Type a request first."}
        self.busy = True
        try:
            return await self.assistant.ask(message.strip())
        except Exception as e:  # setup / sign-in problems show in the chat instead of a 500
            return {"reply": f"The assistant couldn't run: {type(e).__name__}: {e}", "cost": None,
                    "chat_cents": self.assistant.chat_cents}
        finally:
            self.busy = False

    async def reset_chat(self):
        await self.assistant.close()
        self.assistant = Assistant(self.ws, self.settings)
        return {"ok": True}



def make_handler(app: App):
    ws = app.ws

    def edit(fn, page_reload=False):
        try:
            with ws.lock:
                message = fn()
                if page_reload and message != "No change.":
                    ws.page_changed()
                return {"ok": True, "message": message, **ws.state()}
        except EditError as e:
            return {"ok": False, "error": str(e), **ws.state()}

    def stale(body) -> bool:
        return body.get("struct_seq") is not None and int(body["struct_seq"]) != ws.doc.struct_seq

    def select(b):
        with ws.lock:
            if stale(b):
                return {"ok": False, "error": "stale", **ws.state()}
            node = b.get("node")
            ws.selected = node if node in ws.doc.nodes else None
            ws.click = b.get("info")
            return {"ok": True, **node_info(node), **ws.state()}

    def node_info(node):
        d = ws.doc
        if not node or node not in d.nodes or node == "n0":
            return {"node": None}
        nd = d.nodes[node]
        hidden = d.hidden_context(nd)
        return {"node": node, "label": d.label(nd), "tag": nd.tag,
                "path": [{"id": a.id, "label": d.tag_label(a)} for a in reversed(list(d.ancestors(nd))) if a.tag != "html"]
                + [{"id": nd.id, "label": d.tag_label(nd)}],
                "hidden": d.hidden_summary(hidden) if hidden is not None else None}

    def runs(q):
        with ws.lock:
            out = {}
            for n in (q.get("nodes", [""])[0]).split(","):
                if n in ws.doc.nodes and n != "n0":
                    out[n] = ws.doc.direct_runs(n)
            return {"runs": out, **ws.state()}

    def text(b):
        if stale(b):
            return {"ok": False, "error": "The page changed; reloading it.", "reload": True, **ws.state()}
        return edit(lambda: ws.doc.set_text(b["run"], b["text"], masked=False, expect=b.get("old")))

    def undo(_b):
        with ws.lock:
            label = ws.doc.undo()
            ws.page_changed()
            return {"ok": True, "message": f"Undid {label}." if label else "Nothing to undo.", **ws.state()}

    def discard(_b):
        with ws.lock:
            ws.doc.discard_all()
            ws.page_changed()
            return {"ok": True, "message": "All unsaved changes discarded.", **ws.state()}

    def reload(_b):
        ws.load()
        return {"ok": True, "message": "Reloaded from disk.", **ws.state()}

    def save(_b):
        return {**ws.save(), **ws.state()}

    def poll(_q):
        ws.last_poll = time.monotonic()
        with ws.lock:
            return {**ws.state(), "busy": app.busy, "on_disk_changed": ws.changed_on_disk()}

    get_routes = {
        "/api/state": poll,
        "/api/info": lambda q: app.info(),
        "/api/runs": runs,
        "/api/node": lambda q: (lambda n: {**node_info(n), **ws.state()})(q.get("node", [""])[0]),
    }
    post_routes = {
        "/api/select": select,
        "/api/text": text,
        "/api/style": lambda b: edit(lambda: ws.doc.set_style(b["node"], b["styles"]), page_reload=bool(b.get("reload"))),
        "/api/var": lambda b: edit(lambda: ws.doc.set_theme_var(b["var"], b["value"]), page_reload=True),
        "/api/rule": lambda b: edit(lambda: ws.doc.set_page_rule(b["selector"], b.get("declarations", "")), page_reload=True),
        "/api/styles": lambda b: (ws.answer_styles(int(b["id"]), b.get("info") or {}), {"ok": True})[1],
        "/api/undo": undo, "/api/save": save, "/api/discard": discard, "/api/reload": reload,
        "/api/chat": lambda b: app.run(app.chat(b.get("message", ""))),
        "/api/chat/reset": lambda b: app.run(app.reset_chat()),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            path = unquote(url.path)
            try:
                if path in ("/", "/index.html"):
                    return self._file(UI / "editor.html")
                if path.startswith("/ui/"):
                    return self._file(UI / path[4:], inside=UI)
                if path.startswith("/doc/"):
                    rel = path[5:]
                    if rel == ws.path.name:
                        with ws.lock:
                            body = ws.doc.served_html().encode("utf-8")
                        return self._send(200, body, "text/html; charset=utf-8")
                    return self._file(ws.path.parent / rel, inside=ws.path.parent)
                route = get_routes.get(path)
                if route is None:
                    return self._json(404, {"error": "not found"})
                return self._json(200, route(parse_qs(url.query)))
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        def do_POST(self):
            path = urlparse(self.path).path
            route = post_routes.get(path)
            if route is None:
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                return self._json(200, route(body))
            except EditError as e:
                return self._json(200, {"ok": False, "error": str(e)})
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        def _file(self, p: Path, inside: Path | None = None):
            p = p.resolve()
            if inside is not None and inside.resolve() not in p.parents:
                return self._json(403, {"error": "outside the page's folder"})
            if not p.is_file() or any(part == ".smart-html-editor" for part in p.parts):
                return self._json(404, {"error": "not found"})
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8" if p.parent == UI else ""
            return self._send(200, p.read_bytes(), ctype)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _send(self, status: int, data: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # keep the console quiet
            pass

    return Handler


def serve(file: str, port: int, open_browser: bool, fake: bool):
    clean_environment()
    settings = {"model": os.environ.get("SHE_MODEL", "claude-haiku-5-5"), "effort": os.environ.get("SHE_EFFORT", "low"),
                "fake": fake or os.environ.get("SHE_FAKE") == "1"}
    ws = Workspace(file)
    app = App(ws, settings)
    server = None
    for p in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), make_handler(app))
            break
        except OSError:
            continue
    if server is None:
        sys.exit(f"No free port between {port} and {port + 19}.")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    mode = "TEST MODE (scripted model)" if settings["fake"] else f"{settings['model']}, effort {settings['effort']}"
    print(f"Smart HTML Editor: {ws.path.name} ({ws.doc.page_summary()})", flush=True)
    print(f"  open {url}   assistant: {mode}; sign-in: {auth_source() or 'none found'}", flush=True)
    print("  Ctrl+C stops the editor. Unsaved changes are lost when it stops.", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            app.run(app.assistant.close(), 10)
        except Exception:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="she.py open", description="Open an HTML file in the Smart HTML Editor.")
    ap.add_argument("file")
    ap.add_argument("--port", type=int, default=int(os.environ.get("SHE_PORT", 8790)))
    ap.add_argument("--no-open", action="store_true", help="don't open a browser window")
    ap.add_argument("--fake", action="store_true", help="test mode: scripted model, no tokens")
    a = ap.parse_args(argv)
    serve(a.file, a.port, not a.no_open, a.fake)


if __name__ == "__main__":
    main()
