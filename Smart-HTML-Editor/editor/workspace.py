"""The open file: loading and saving it, what is selected, and talking to the open page.

One Workspace per editor server. The HTTP threads (the person's clicks and typing) and the assistant's
event-loop thread both change it, so every change goes through `lock`.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import threading
import time
from pathlib import Path

from htmldoc import Doc

STATE_DIR = ".smart-html-editor"      # next to the file: backups/


def read_html(path: Path) -> tuple[str, str, bytes]:
    """(text, encoding, bom). Keeps whatever the file uses so saving writes it back the same way."""
    raw = path.read_bytes()
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if raw.startswith(bom):
            return raw[len(bom):].decode(enc), enc, bom
    try:
        return raw.decode("utf-8"), "utf-8", b""
    except UnicodeDecodeError:
        pass
    m = re.search(rb"""charset\s*=\s*["']?([A-Za-z0-9_-]+)""", raw[:4096])
    for enc in ([m.group(1).decode("ascii")] if m else []) + ["cp1252"]:
        try:
            return raw.decode(enc), enc, b""
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("latin-1"), "latin-1", b""      # never fails, round-trips every byte


class Workspace:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"no such file: {self.path}")
        self.lock = threading.RLock()
        self.reload_seq = 0          # bumped when the open page must reload (changes it didn't make itself)
        self.selected: str | None = None
        self.select_seq = 0          # bumped when the assistant moves the selection
        self.click: dict | None = None   # looks the page reported for the person's last click
        self.last_poll = 0.0
        self.backup: Path | None = None
        self._req_seq = 0
        self.styles_req: dict | None = None
        self._styles_wait = None
        self.load()

    # ------------------------------------------------------------ file
    def load(self):
        with self.lock:
            text, self.encoding, self.bom = read_html(self.path)
            self.doc = Doc(text, self.path.name)
            st = self.path.stat()
            self.disk_stamp = (st.st_mtime_ns, st.st_size)
            self.selected = None
            self.reload_seq += 1

    def changed_on_disk(self) -> bool:
        st = self.path.stat()
        return (st.st_mtime_ns, st.st_size) != self.disk_stamp

    def save(self) -> dict:
        with self.lock:
            if not self.doc.dirty:
                return {"ok": True, "message": "Nothing to save."}
            if self.changed_on_disk():
                return {"ok": False, "message": "The file changed on disk since it was opened (another program or Claude Code "
                                                "edited it). Reload from disk first; your unsaved changes would overwrite that."}
            if self.backup is None:      # one backup per editing session: the file as it was when opened
                folder = self.path.parent / STATE_DIR / "backups"
                folder.mkdir(parents=True, exist_ok=True)
                self.backup = folder / f"{self.path.stem}.{time.strftime('%Y%m%d-%H%M%S')}{self.path.suffix}"
                shutil.copy2(self.path, self.backup)
            data = self.bom + self.doc.src.encode(self.encoding, errors="xmlcharrefreplace")
            tmp = self.path.with_name(self.path.name + ".she-tmp")
            tmp.write_bytes(data)
            tmp.replace(self.path)
            self.doc.original = self.doc.src
            st = self.path.stat()
            self.disk_stamp = (st.st_mtime_ns, st.st_size)
            return {"ok": True, "message": f"Saved. The version you opened is backed up in {STATE_DIR}/backups/{self.backup.name}."}

    # ------------------------------------------------------------ page
    def browser_alive(self) -> bool:
        return time.monotonic() - self.last_poll < 3.0

    def page_changed(self):
        """A change the open page didn't make itself: tell it to reload."""
        self.reload_seq += 1

    def state(self) -> dict:
        d = self.doc
        return {
            "file": self.path.name, "version": d.version, "struct_seq": d.struct_seq, "reload_seq": self.reload_seq,
            "dirty": d.dirty, "changes": len(d.undo_stack), "can_undo": bool(d.undo_stack),
            "selected": self.selected, "select_seq": self.select_seq, "styles_req": self.styles_req,
        }

    # ------------------------------------------------------------ asking the page for looks
    async def request_styles(self, node_id: str, timeout: float = 4.0) -> dict | None:
        """Ask the open page for the computed colors/fonts and matching CSS rules of an element
        (and its parents). Runs on the assistant's loop; the page answers through answer_styles."""
        if not self.browser_alive():
            return None
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        with self.lock:
            self._req_seq += 1
            req_id = self._req_seq
            self.styles_req = {"id": req_id, "node": node_id, "after": self.reload_seq}
            self._styles_wait = (req_id, loop, fut)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            with self.lock:
                if self.styles_req and self.styles_req["id"] == req_id:
                    self.styles_req = None
                    self._styles_wait = None

    def answer_styles(self, req_id: int, info: dict):
        with self.lock:
            wait = self._styles_wait
            if not wait or wait[0] != req_id:
                return
            _, loop, fut = wait
            self.styles_req = None
            self._styles_wait = None
        loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(info))
