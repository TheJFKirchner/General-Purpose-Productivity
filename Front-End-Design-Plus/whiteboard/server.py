"""Local server for the whiteboard. Standard library only (ThreadingHTTPServer); the chat streams as
server-sent events written straight to the response, which needs nothing more.

Pages:
  GET  /, /index.html        whiteboard/ui/index.html
  GET  /ui/<file>            files in whiteboard/ui/ (also served at /<file>)
  GET  /vendor/<file>        local library copies in whiteboard/vendor/
API (JSON unless stated):
  GET  /api/session          {library, columns, style, cards (each with saved and round), saved, chat,
                              row_count, engine, round, usage, model}
  GET  /api/data             the full rows: a JSON array of row objects
  POST /api/chat {message}   text/event-stream: events text, card (recipe + round), error,
                             done {cards, round, usage, model} (data = JSON with "type")
  POST /api/card-error {id, error}   once per card: the agent fixes it
                             -> {ok, fixed, card, cards, text, round, usage, model}
  usage = {input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, total_tokens, cost_usd, turns},
  cumulative for this launch (in memory only; every launch starts at zero)
  POST /api/save {id} · /api/unsave {id} · /api/delete {id} · /api/done
  POST /api/heartbeat        {ok}; the page posts it every 15 s

Lifetime: Done ends the session. Without Done it also ends (result.json done: false) when the page has been
silent for IDLE_S seconds (no heartbeat or other request, and no agent turn running), or when no page has
connected within CONNECT_S seconds of launch.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .agent import Designer
from .board import Board, BoardError
from .data import Table

HERE = Path(__file__).resolve().parent
UI = HERE / "ui"
VENDOR = HERE / "vendor"
REQUEST_WAIT = 900  # seconds a JSON request waits for the agent (a fix may queue behind a chat turn)
IDLE_S = 90         # page silent this long (after connecting once) -> finish with done: false
CONNECT_S = 600     # no page at all this long after launch -> the same

# Windows can map .js to text/plain through the registry; set the types the page needs explicitly.
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".map": "application/json", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff",
         ".ttf": "font/ttf", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8"}

PLACEHOLDER = (b"<!doctype html><meta charset=utf-8><title>Whiteboard</title>"
               b"<p style='font:14px sans-serif'>The whiteboard page (whiteboard/ui/index.html) is missing.</p>")


class Whiteboard:
    """Board + data + agent + a background asyncio loop the agent runs on."""

    def __init__(self, board: Board, table: Table, designer: Designer, style: str | None, engine: str,
                 idle_s: float = IDLE_S, connect_s: float = CONNECT_S):
        self.board = board
        self.table = table
        self.designer = designer
        self.style = style
        self.engine = engine
        self.server: ThreadingHTTPServer | None = None
        self.finished = threading.Event()
        self.result: dict | None = None
        self.ended_by: str | None = None          # "done", or why it stopped on its own
        self.idle_s = idle_s
        self.connect_s = connect_s
        self.started = time.monotonic()
        self.last_seen: float | None = None       # last request from the page (None: never connected)
        self.busy = 0                             # agent turns running (they count as activity)
        self._state = threading.Lock()
        self._stopping = False
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="whiteboard-agent").start()

    def run(self, coro, timeout=REQUEST_WAIT):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    # ---- activity ----------------------------------------------------------------------------------
    def touch(self) -> None:
        with self._state:
            self.last_seen = time.monotonic()

    def _busy(self, delta: int) -> None:
        with self._state:
            self.busy += delta
            self.last_seen = time.monotonic()

    def watch(self) -> None:
        """Background check: end the session when the page has gone, or never came."""
        interval = max(0.05, min(2.0, self.idle_s / 4, self.connect_s / 4))
        while not self.finished.wait(interval):
            with self._state:
                busy, seen = self.busy, self.last_seen
            now = time.monotonic()
            if busy:
                continue
            if seen is None and now - self.started >= self.connect_s:
                return self.expire(f"no page connected within {self.connect_s:g} s")
            if seen is not None and now - seen >= self.idle_s:
                return self.expire(f"the page was silent for {self.idle_s:g} s")

    def expire(self, reason: str) -> None:
        if self.finished.is_set() or self.result is not None:
            return
        self.ended_by = reason
        self.result = self.board.finish(done=False)
        self.stop()

    # ---- routes ------------------------------------------------------------------------------------
    def session_info(self) -> dict:
        return {"library": self.board.library, "columns": self.table.columns, "style": self.style or "",
                "cards": self.board.snapshot(), "saved": list(self.board.saved), "chat": self.board.chat_log(),
                "row_count": len(self.table.rows), "engine": self.engine, **self.designer.stats()}

    def chat_events(self, message: str):
        """Run one chat turn on the agent loop; yield its events in this (HTTP) thread."""
        q: queue.Queue = queue.Queue()

        async def pump():
            try:
                async for ev in self.designer.chat(message):
                    q.put(ev)
            except Exception as e:  # never leave the page waiting
                q.put({"type": "error", "error": f"{type(e).__name__}: {e}", "message": str(e)})
                q.put({"type": "done", "cards": [], **self.designer.stats()})
            finally:
                q.put(None)

        self._busy(+1)
        try:
            asyncio.run_coroutine_threadsafe(pump(), self.loop)
            while True:
                ev = q.get()
                if ev is None:
                    return
                yield ev
        finally:
            self._busy(-1)

    def card_error(self, body: dict) -> dict:
        card_id = str(body.get("id") or "").strip().upper()
        if not card_id:
            return {"ok": False, "error": "id is required"}
        self._busy(+1)
        try:
            return self.run(self.designer.fix(card_id, str(body.get("error") or "")))
        finally:
            self._busy(-1)

    def done(self) -> dict:
        self.ended_by = "done"
        self.result = self.board.finish()
        threading.Timer(0.3, self.stop).start()  # let this response reach the page first
        return {"ok": True, "result": str(self.board.result_file), **self.result}

    def stop(self) -> None:
        with self._state:
            if self._stopping:
                return
            self._stopping = True
        try:
            self.run(self.designer.close(), 15)
        except Exception:
            pass
        self.finished.set()
        if self.server is not None:
            self.server.shutdown()
        self.loop.call_soon_threadsafe(self.loop.stop)

    # ---- server ------------------------------------------------------------------------------------
    def start(self, host: str = "127.0.0.1", port: int = 0) -> str:
        self.server = ThreadingHTTPServer((host, port), make_handler(self))
        self.server.daemon_threads = True
        return self.url

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}/"

    def serve(self, open_browser: bool) -> None:
        if open_browser:
            threading.Timer(0.5, lambda: webbrowser.open(self.url)).start()
        threading.Thread(target=self.watch, daemon=True, name="whiteboard-watch").start()
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if not self.finished.is_set():
                try:
                    self.run(self.designer.close(), 15)
                except Exception:
                    pass
            self.server.server_close()


def make_handler(app: Whiteboard):
    def need_id(body: dict) -> str:
        card_id = str(body.get("id") or "").strip().upper()
        if not card_id:
            raise BoardError("id is required")
        return card_id

    get_routes = {
        "/api/session": app.session_info,
        "/api/data": lambda: app.table.rows,
    }
    post_routes = {
        "/api/card-error": app.card_error,
        "/api/save": lambda b: app.board.save(need_id(b)),
        "/api/unsave": lambda b: app.board.unsave(need_id(b)),
        "/api/heartbeat": lambda b: {"ok": True},
        "/api/delete": lambda b: app.board.delete(need_id(b)),
        "/api/done": lambda b: app.done(),
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "Whiteboard/1"

        def do_GET(self):
            app.touch()
            path = unquote(urlparse(self.path).path)
            try:
                if path in get_routes:
                    return self._json(200, get_routes[path]())
                if path.startswith("/api/"):
                    return self._json(404, {"error": "not found"})
                if path in ("/", "/index.html"):
                    index = UI / "index.html"
                    if not index.is_file():
                        return self._send(200, PLACEHOLDER, TYPES[".html"])
                    return self._file(index, UI)
                if path.startswith("/vendor/"):
                    return self._file(VENDOR / path[len("/vendor/"):], VENDOR, cors=True)
                if path.startswith("/ui/"):
                    return self._file(UI / path[len("/ui/"):], UI)
                return self._file(UI / path.lstrip("/"), UI)
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        def do_POST(self):
            app.touch()
            path = urlparse(self.path).path
            # Read the body first, even for a refused request: answering with it unread can make the
            # connection reset instead of delivering the reply (seen on Windows).
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length > 0 else b""
            except (ValueError, OSError):
                return self._json(400, {"error": "bad request body"})
            if not self._same_origin():
                return self._json(403, {"error": "requests from other sites are refused"})
            try:
                body = json.loads(raw) if raw else {}
                if not isinstance(body, dict):
                    body = {}
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"error": "body must be JSON"})
            if path == "/api/chat":
                return self._stream(app.chat_events(str(body.get("message") or "")))
            route = post_routes.get(path)
            if route is None:
                return self._json(404, {"error": "not found"})
            try:
                return self._json(200, route(body))
            except BoardError as e:
                return self._json(200, {"ok": False, "error": str(e)})
            except Exception as e:
                return self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

        def _same_origin(self) -> bool:
            # Browsers send Origin on cross-site POSTs; the page itself is same-origin (or sends none).
            origin = self.headers.get("Origin")
            if not origin:
                return True
            port = app.server.server_address[1]
            return origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

        def _stream(self, events):
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            alive = True
            for ev in events:  # keep draining after a disconnect so the turn finishes cleanly
                if not alive:
                    continue
                chunk = f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                try:
                    self.wfile.write(chunk.encode("utf-8"))
                    self.wfile.flush()
                except OSError:
                    alive = False

        def _file(self, p: Path, root: Path, cors: bool = False):
            try:
                p = p.resolve()
                if root.resolve() not in p.parents:
                    return self._json(403, {"error": "outside the served folder"})
            except OSError:
                return self._json(404, {"error": "not found"})
            if not p.is_file():
                return self._json(404, {"error": "not found"})
            ctype = TYPES.get(p.suffix.lower(), "application/octet-stream")
            return self._send(200, p.read_bytes(), ctype, cors)

        def _json(self, status: int, payload):
            self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _send(self, status: int, data: bytes, ctype: str, cors: bool = False):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if cors:  # library files may be loaded from sealed (opaque-origin) card frames
                self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # keep the console quiet
            pass

    return Handler
