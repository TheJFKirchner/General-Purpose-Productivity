"""The board: every card, the IDs, the chat and the usage, for one launch only.

Every launch starts fresh (plus the round-0 card from --existing). The board lives in memory, so a page
reload within a running session shows everything, but nothing of it is written to disk or loaded later.
The only files, in <out>:
  <id>.json         one saved recipe {id, parent, title, library, kind, code}; no data
  result.json       {library, done, saved: [{id, title, library, kind, file}]}

The output folder must be empty (or missing) at launch: files from an earlier session are never loaded or
overwritten. A saved visual comes back only through --existing <id>.json.

Rounds: 0 = the card from --existing; each user chat message starts the next round and the cards added in
that turn carry it. A card replaced by an error fix keeps its round.

Used from the HTTP threads and the agent's event loop, so every public method takes the lock.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

RECIPE_KEYS = ("id", "parent", "title", "library", "kind", "code")
CARD_KEYS = RECIPE_KEYS + ("round",)
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")


class BoardError(Exception):
    """A request the board cannot carry out (unknown ID, bad recipe)."""


class OutputNotEmpty(Exception):
    """--out already holds files from an earlier session."""


def recipe(card: dict) -> dict:
    """The saved-file shape (no round)."""
    return {k: card.get(k) for k in RECIPE_KEYS}


def card_view(card: dict) -> dict:
    """The page shape: the recipe plus its round."""
    return {k: card.get(k) for k in CARD_KEYS}


def empty_usage() -> dict:
    return {**{k: 0 for k in USAGE_KEYS}, "total_tokens": 0, "cost_usd": 0.0, "turns": 0}


def _write_json(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class Board:
    def __init__(self, out: str | Path, library: str):
        self.out = Path(out)
        self.library = library
        self.cards: list[dict] = []        # card dicts (recipe + round), in the order they were made
        self.saved: list[str] = []
        self.next_id = 1
        self.round = 0                     # latest round; 0 until the first chat message
        self.fix_sent: set[str] = set()    # cards whose error already went back to the agent
        self.fixing: set[str] = set()      # cards the agent may replace right now
        self.notes: list[str] = []         # board changes the agent has not been told about
        self.chat: list[dict] = []         # the visible conversation: {role: "user"|"agent", text}
        self.usage: dict = empty_usage()   # cumulative over every agent turn of this launch
        self.model: str | None = None      # model last reported by the engine
        self.lock = threading.RLock()

    @property
    def result_file(self) -> Path:
        return self.out / "result.json"

    def open(self) -> None:
        """Check the output folder is empty or missing (no *.json from an earlier session), then create it."""
        if self.out.exists() and not self.out.is_dir():
            raise OutputNotEmpty(f"--out {self.out} is a file, not a folder. Use a new, empty output folder.")
        if self.out.is_dir():
            old = sorted(p.name for p in self.out.glob("*.json"))
            if old:
                shown = ", ".join(old[:5]) + (", ..." if len(old) > 5 else "")
                raise OutputNotEmpty(
                    f"--out {self.out} already holds files from an earlier session ({shown}). The whiteboard "
                    "does not load or overwrite them. Use a new, empty output folder; to keep working on a "
                    "saved visual, pass its file with --existing.")
        self.out.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _number(card_id: str) -> int:
        try:
            return int(str(card_id).lstrip("Gg"))
        except ValueError:
            return 0

    # ---- reading -----------------------------------------------------------------------------------
    def get(self, card_id: str) -> dict | None:
        with self.lock:
            for c in self.cards:
                if c["id"] == card_id:
                    return c
            return None

    def snapshot(self) -> list[dict]:
        """Every card as the page sees it: the recipe, its round and `saved`."""
        with self.lock:
            return [{**card_view(c), "saved": c["id"] in self.saved} for c in self.cards]

    def take_notes(self) -> list[str]:
        with self.lock:
            notes, self.notes = self.notes, []
            return notes

    def usage_view(self) -> dict:
        with self.lock:
            out = dict(self.usage)
            if out["cost_usd"] is not None:
                out["cost_usd"] = round(out["cost_usd"], 6)
            return out

    def chat_log(self) -> list[dict]:
        with self.lock:
            return [dict(m) for m in self.chat]

    # ---- changing ----------------------------------------------------------------------------------
    def new_round(self) -> int:
        """A user chat message starts the next round."""
        with self.lock:
            self.round += 1
            return self.round

    def add_usage(self, tokens: dict, cost_usd: float | None, model: str | None) -> None:
        """Add one agent turn. cost_usd None = the engine gave no cost: the total becomes unknown."""
        with self.lock:
            for k in USAGE_KEYS:
                self.usage[k] += int(tokens.get(k) or 0)
            self.usage["total_tokens"] = sum(self.usage[k] for k in USAGE_KEYS)
            if cost_usd is None or self.usage["cost_usd"] is None:
                self.usage["cost_usd"] = None
            else:
                self.usage["cost_usd"] += float(cost_usd)
            self.usage["turns"] += 1
            if model:
                self.model = model

    def add_chat(self, role: str, text: str) -> None:
        text = (text or "").strip()
        if text:
            with self.lock:
                self.chat.append({"role": role, "text": text})

    def add(self, title: str, code: str, kind: str = "chart", parent: str | None = None,
            card_id: str | None = None, round: int | None = None) -> dict:
        """Add a card. `card_id` is used only for G1 from --existing; otherwise the next free ID.
        `round` defaults to the current round (at least 1); only G1 from --existing passes 0."""
        round = max(self.round, 1) if round is None else int(round)
        title = (title or "").strip() or ("Current visual" if round == 0 else "Untitled")
        if not isinstance(code, str) or not code.strip():
            raise BoardError("code is empty: pass the body of render(el, rows, lib).")
        kind = kind if kind in ("chart", "table") else "chart"
        parent = (parent or "").strip().upper() or None
        with self.lock:
            # A deleted parent is fine (the link is kept); an ID never issued is a mistake.
            if parent is not None and not self.get(parent) and not 0 < self._number(parent) < self.next_id:
                raise BoardError(f"parent {parent} does not exist. Cards on the board: "
                                 f"{', '.join(c['id'] for c in self.cards) or 'none'}.")
            if card_id is None:
                card_id = f"G{self.next_id}"
            self.next_id = max(self.next_id, self._number(card_id) + 1)
            card = {"id": card_id, "parent": parent, "title": title, "library": self.card_library(kind),
                    "kind": kind, "code": code, "round": round}
            self.cards.append(card)
            return dict(card)

    def replace(self, card_id: str, title: str, code: str, kind: str | None = None) -> dict:
        """The one-time fix of a broken card: same ID, parent and round; new code."""
        if not isinstance(code, str) or not code.strip():
            raise BoardError("code is empty: pass the body of render(el, rows, lib).")
        with self.lock:
            card = self.get(card_id)
            if card is None:
                raise BoardError(f"{card_id} is not on the board (it may have been deleted).")
            if card_id not in self.fixing:
                raise BoardError(f"replaces is only for fixing a card reported as broken; {card_id} is not. "
                                 f"To change a card, add a new one with parent=\"{card_id}\".")
            self.fixing.discard(card_id)
            if kind in ("chart", "table") and kind != card["kind"]:
                card["kind"] = kind
                card["library"] = self.card_library(kind)
            card["code"] = code
            if title and title.strip():
                card["title"] = title.strip()
            if card_id in self.saved:
                self._write_recipe(card)
                self._write_result(done=False)
            return dict(card)

    def card_library(self, kind: str) -> str:
        return "html" if kind == "table" else self.library

    def delete(self, card_id: str) -> dict:
        """Remove a card. A saved card is also unsaved (its recipe file removed)."""
        with self.lock:
            card = self.get(card_id)
            if card is None:
                raise BoardError(f"{card_id} is not on the board.")
            self.cards.remove(card)
            self.fixing.discard(card_id)
            if card_id in self.saved:
                self.saved.remove(card_id)
                (self.out / f"{card_id}.json").unlink(missing_ok=True)
                self._write_result(done=False)
            self.notes.append(f"deleted {card_id}")
            return {"ok": True, "id": card_id}

    def save(self, card_id: str) -> dict:
        with self.lock:
            card = self.get(card_id)
            if card is None:
                raise BoardError(f"{card_id} is not on the board.")
            path = self._write_recipe(card)
            if card_id not in self.saved:
                self.saved.append(card_id)
            self._write_result(done=False)
            return {"ok": True, "id": card_id, "file": str(path), "saved": list(self.saved)}

    def unsave(self, card_id: str) -> dict:
        """Take a card out of the output (its recipe file and result.json entry); the card stays."""
        with self.lock:
            if self.get(card_id) is None:
                raise BoardError(f"{card_id} is not on the board.")
            if card_id in self.saved:
                self.saved.remove(card_id)
                (self.out / f"{card_id}.json").unlink(missing_ok=True)
                self._write_result(done=False)
            return {"ok": True, "id": card_id, "saved": list(self.saved)}

    def error_reported(self, card_id: str) -> bool:
        """Record a render error. True if it should go to the agent (first time for this card)."""
        with self.lock:
            if self.get(card_id) is None or card_id in self.fix_sent:
                return False
            self.fix_sent.add(card_id)
            self.fixing.add(card_id)
            return True

    def fix_finished(self, card_id: str) -> None:
        with self.lock:
            self.fixing.discard(card_id)

    def finish(self, done: bool = True) -> dict:
        """Write result.json. done=False: stopped without the Done button (unsaved cards are dropped)."""
        with self.lock:
            return self._write_result(done=done)

    # ---- files -------------------------------------------------------------------------------------
    def _write_recipe(self, card: dict) -> Path:
        path = self.out / f"{card['id']}.json"
        _write_json(path, recipe(card))
        return path

    def result(self, done: bool) -> dict:
        with self.lock:
            saved = []
            for i in self.saved:
                c = self.get(i)
                if c:
                    saved.append({"id": i, "title": c["title"], "library": c["library"], "kind": c["kind"],
                                  "file": str(self.out / f"{i}.json")})
            return {"library": self.library, "done": done, "saved": saved}

    def _write_result(self, done: bool) -> dict:
        data = self.result(done)
        _write_json(self.result_file, data)
        return data
