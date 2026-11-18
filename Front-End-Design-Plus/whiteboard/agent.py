"""The whiteboard's agent: one model conversation for the life of the page, kept as cheap as possible.

No tools: the agent answers in a strict plain-text format (see reply.py) that the server parses into cards,
so a turn is one model call. The system prompt holds a short brief, the columns, about three sample rows,
the style note, the session library's reference file, and (only when a session starts or restarts) the code
of cards already on the board. Each message starts with one line: card IDs and titles, deletions, and the
next free ID. All model access goes through engine.py.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import AsyncIterator, Callable

from .board import Board, BoardError
from .data import Table
from .engine import EngineError, TurnResult, make_engine
from .reply import ReplyParser

REFERENCES = Path(__file__).resolve().parent.parent / "references"
DEFAULT_MODEL = "sonnet"
DEFAULT_EFFORT = "low"
CHAT_IN_PROMPT = 12          # earlier messages shown to a new agent session after a restart
CHAT_TEXT_LIMIT = 300

BRIEF = """\
You write charts and tables for a whiteboard page. Each card runs your code on the full data in its own box.
You see only the column names, types and a few sample rows.

Code = the body of render(el, rows, lib). el: empty div filling the card (at least ~520 px wide). rows: array
of row objects (numbers are numbers, dates are strings, missing = null); group, sort and aggregate in code.
lib: the session library (absent for html). No wrapper, imports, fetch or comments. Always complete and
standalone (variants too), written compactly.

Reply in exactly this format and nothing else:
@card chart|table <parent ID or -> | <title>
```js
<code>
```
(one block per card), then one line:
@say <one short plain sentence naming the new IDs>

Rules:
- Several visuals asked for = several cards. A change to a card = a new card with that card as parent.
- The title says exactly what is drawn. Leave room so titles, labels and legends never overlap.
- Tables (kind table): plain HTML, no library, fit the width (wrap or shrink; no sideways scroll).
- New cards take IDs in order from the "next ID" in each message.
- Unclear request: make a sensible choice. Never ask questions or restate the request.
- Fixing a broken card: reply "@fix <ID> | <title>" with the corrected code block, then @say.
"""

TABLE_NOTES = """\
Tables: build a <table> with the DOM or innerHTML; width 100%, border-collapse, font 12px sans-serif, light
grey cell borders, header background #e8eef7, numbers right-aligned and formatted, long text wrapped."""


def read_reference(library: str, folder: Path = REFERENCES) -> str | None:
    p = folder / f"{library}.md"
    try:
        text = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    # Nest the file's headings under the prompt's "## Library notes" heading.
    return re.sub(r"^(#{1,4}) ", r"##\1 ", text, flags=re.M)


def current_visual(cards: list[dict]) -> dict | None:
    """The round-0 card: the deliverable's visual passed in with --existing."""
    return next((c for c in cards if int(c.get("round") or 0) == 0), None)


def prompt_parts(library: str, table: Table, style: str | None, cards: list[dict],
                 references: Path = REFERENCES, chat: list[dict] | None = None) -> list[tuple[str, str]]:
    """The system prompt, as named parts (so --debug-usage can show what each costs)."""
    parts = [("brief", BRIEF)]
    lib_note = ("Session library: html (plain DOM/SVG/canvas, no lib)." if library == "html"
                else f"Session library: {library}.")
    cols = ", ".join(f"{c['name']} ({c['type']})" for c in table.columns) or "(none)"
    samples = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in table.samples())
    parts.append(("data", f"{lib_note}\nData: {len(table.rows)} rows. Columns: {cols}\nSample rows:\n{samples}"))
    if style and style.strip():
        parts.append(("style", f"Style note from the user: {style.strip()}"))
    if cards:
        listing = []
        for c in cards:
            head = f"{c['id']} | {c['title']} ({c['kind']}" + (f", from {c['parent']})" if c.get("parent") else ")")
            listing.append(f"{head}\n```js\n{c['code']}\n```")
        parts.append(("cards", "Cards on the board:\n" + "\n".join(listing)))
        cv = current_visual(cards)
        if cv:
            parts.append(("current_visual",
                          f"{cv['id']} is the deliverable's visual as it is today. A change request that names no "
                          f"ID starts from {cv['id']}; its variants are new cards with parent {cv['id']}."))
    if chat:
        lines = []
        for m in chat[-CHAT_IN_PROMPT:]:
            text = " ".join(m["text"].split())
            lines.append(f"- {m['role']}: {text[:CHAT_TEXT_LIMIT]}{'...' if len(text) > CHAT_TEXT_LIMIT else ''}")
        parts.append(("chat", "Conversation so far (before the agent restarted):\n" + "\n".join(lines)))
    ref = read_reference(library, references)
    if ref:
        parts.append((f"{library}.md", f"## Library notes: {library}\n{ref}"))
    elif library != "html":
        parts.append(("library", f"`lib` is the {library} library's global object."))
    if library != "html":
        parts.append(("table_notes", TABLE_NOTES))
    return parts


def build_prompt(library: str, table: Table, style: str | None, cards: list[dict],
                 references: Path = REFERENCES, chat: list[dict] | None = None) -> str:
    return "\n\n".join(text for _, text in prompt_parts(library, table, style, cards, references, chat)) + "\n"


def board_header(board: Board) -> str:
    cards = board.snapshot()
    cv = current_visual(cards)
    listed = "; ".join(f"{c['id']} \"{c['title']}\"" + (" (current visual)" if c is cv else "") for c in cards)
    text = f"Board: {listed or 'empty'}."
    notes = board.take_notes()
    if notes:
        text += " Since your last reply the user " + ", ".join(notes) + "."
    text += f" Next ID: G{board.next_id}."
    return f"[{text}]"


class Designer:
    """Owns the model conversation. All methods run on one asyncio loop (the server's background loop)."""

    def __init__(self, board: Board, table: Table, style: str | None = None, *, engine: str = "claude",
                 model: str | None = DEFAULT_MODEL, effort: str | None = DEFAULT_EFFORT,
                 max_budget_usd: float | None = None, references: Path = REFERENCES,
                 replies=None, debug: bool = False, engine_factory: Callable | None = None):
        self.board = board
        self.table = table
        self.style = style
        self.engine_name = engine
        self.model = model
        self.effort = effort
        self.max_budget_usd = max_budget_usd
        self.references = references
        self.replies = replies
        self.debug = debug
        self.engine_factory = engine_factory or self._default_factory
        self.engine = None               # the open engine session, if any
        self.prompt = ""                 # the system prompt of the open session
        self.turns = 0
        self._lock: asyncio.Lock | None = None
        self._reported_model: str | None = None
        self.turn_cards: list[str] = []

    def _default_factory(self):
        return make_engine(self.engine_name, model=self.model, effort=self.effort,
                           max_budget_usd=self.max_budget_usd, replies=self.replies)

    # ---- session -----------------------------------------------------------------------------------
    def prompt_parts(self) -> list[tuple[str, str]]:
        return prompt_parts(self.board.library, self.table, self.style, self.board.snapshot(), self.references,
                            self.board.chat_log())

    async def _ensure_engine(self):
        if self.engine is None:
            parts = self.prompt_parts()
            self.prompt = "\n\n".join(t for _, t in parts) + "\n"
            engine = self.engine_factory()
            await engine.start(self.prompt)
            self.engine = engine
            if self.debug:
                sizes = ", ".join(f"{name} {len(text)}" for name, text in parts)
                self._log(f"session start: system prompt {len(self.prompt)} chars ({sizes})")
        return self.engine

    async def close(self) -> None:
        engine, self.engine = self.engine, None
        if engine is not None:
            try:
                await engine.close()
            except Exception:
                pass

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ---- usage -------------------------------------------------------------------------------------
    def model_name(self) -> str:
        if self.engine_name == "fake":
            return "fake engine"
        return self._reported_model or self.model or "engine default"

    def stats(self) -> dict:
        return {"usage": self.board.usage_view(), "model": self.model_name(), "round": self.board.round}

    def _record(self, result: TurnResult | None, label: str, message: str) -> None:
        if result is None:
            return
        if result.model and self.engine_name != "fake":
            self._reported_model = result.model
        self.turns += 1
        self.board.add_usage(result.usage, result.cost_usd, result.model)
        if self.debug:
            u = result.usage
            cost = "unknown" if result.cost_usd is None else f"${result.cost_usd:.4f}"
            self._log(f"turn {self.turns} ({label}): model calls {result.api_calls}, input {u['input_tokens']}, "
                      f"output {u['output_tokens']}, cache read {u['cache_read_tokens']}, cache write "
                      f"{u['cache_write_tokens']}, cost {cost}, message {len(message)} chars, reply "
                      f"{len(result.text)} chars")
            for model, m in result.by_model.items():
                self._log(f"    {model}: input {m['input_tokens']}, output {m['output_tokens']}, cache read "
                          f"{m['cache_read_tokens']}, cache write {m['cache_write_tokens']}, ${m['cost_usd']:.4f}")
            if self.turns == 1 and getattr(self.engine, "info", None):
                self._log(f"    session given: {json.dumps(self.engine.info, default=str)}")

    @staticmethod
    def _log(text: str) -> None:
        print(f"[whiteboard usage] {text}", file=sys.stderr, flush=True)

    # ---- turns -------------------------------------------------------------------------------------
    async def chat(self, message: str) -> AsyncIterator[dict]:
        """One user message -> events for the page: text, card, error, then done."""
        message = (message or "").strip()
        if not message:
            yield {"type": "error", "error": "Type a request first.", "message": "Type a request first."}
            yield {"type": "done", "cards": [], **self.stats()}
            return
        said: list[str] = []
        try:
            async with self._get_lock():
                self.board.new_round()
                async for ev in self._turn(f"{board_header(self.board)}\n{message}", "chat"):
                    if ev["type"] == "text":
                        said.append(ev["text"])
                    yield ev
        finally:
            # Recorded after the turn, so a session started for this turn does not see it twice.
            self.board.add_chat("user", message)
            self.board.add_chat("agent", "".join(said))

    async def fix(self, card_id: str, error: str) -> dict:
        """A card failed to render. Sent to the agent once per card; returns the fixed card if any."""
        if not self.board.error_reported(card_id):
            card = self.board.get(card_id)
            why = "is not on the board" if card is None else "was already sent back once"
            return {"ok": True, "fixed": False, "card": None, "cards": [], "text": "",
                    "message": f"{card_id} {why}; not sent to the agent again.", **self.stats()}
        text, cards, errors = [], [], []
        msg = (f"{board_header(self.board)}\n{card_id} failed in the browser: "
               f"{(error or 'unknown error').strip()[:1500]}\nReply with @fix {card_id} and the corrected code.")
        try:
            async with self._get_lock():
                async for ev in self._turn(msg, f"fix {card_id}"):
                    if ev["type"] == "text":
                        text.append(ev["text"])
                    elif ev["type"] == "card":
                        cards.append({k: v for k, v in ev.items() if k != "type"})
                    elif ev["type"] == "error":
                        errors.append(ev["error"])
        finally:
            self.board.fix_finished(card_id)
        fixed = next((c for c in cards if c["id"] == card_id), None)
        note = "".join(text).strip() or (f"{card_id} fixed." if fixed else "")
        self.board.add_chat("agent", note)
        out = {"ok": not errors, "fixed": fixed is not None, "card": fixed, "cards": cards, "text": "".join(text),
               **self.stats()}
        if errors:
            out["error"] = "; ".join(errors)
        return out

    def _apply(self, ev: dict, said: list[int]) -> list[dict]:
        """One parsed reply event -> page events (and a card on the board)."""
        if ev["kind"] in ("text", "note"):
            text = ev["text"] if ev["kind"] == "text" else f"({ev['text']})"
            out = [{"type": "text", "text": ("\n" if said[0] else "") + text}]
            out[0]["delta"] = out[0]["text"]
            said[0] += 1
            return out
        try:
            card = self._place(ev)
        except BoardError as e:
            return self._apply({"kind": "note", "text": f"A card was skipped: {e}"}, said)
        self.turn_cards.append(card["id"])
        return [{"type": "card", **card}]

    def _place(self, ev: dict) -> dict:
        b = self.board
        if ev["fix"]:
            if ev["fix"] in b.fixing:
                return b.replace(ev["fix"], ev["title"], ev["code"])
            # A fix nobody asked for: keep it as a variant of that card instead of changing it in place.
            parent = ev["fix"] if b.get(ev["fix"]) else None
            return b.add(ev["title"], ev["code"], "chart", parent)
        try:
            return b.add(ev["title"], ev["code"], ev["card_kind"], ev["parent"])
        except BoardError:
            if ev["parent"] is None:
                raise
            return b.add(ev["title"], ev["code"], ev["card_kind"], None)   # unknown parent: keep the card

    async def _turn(self, message: str, label: str) -> AsyncIterator[dict]:
        self.turn_cards.clear()
        parser, result, said = ReplyParser(), None, [0]
        try:
            engine = await self._ensure_engine()
            async for item in engine.send(message):
                if isinstance(item, TurnResult):
                    result = item
                    continue
                for ev in parser.feed(item):
                    for out in self._apply(ev, said):
                        yield out
            for ev in parser.finish():
                for out in self._apply(ev, said):
                    yield out
            self._record(result, label, message)
            if result is not None and result.error:
                yield {"type": "error", "error": result.error, "message": result.error}
        except EngineError as e:
            self._record(e.result, label, message)
            # The conversation cannot be reopened: start afresh next turn. The new prompt lists every card on
            # the board with its code, and the recent chat, so IDs still mean the same thing.
            await self.close()
            msg = f"The agent could not run: {e}"
            yield {"type": "error", "error": msg, "message": msg}
        except Exception as e:  # setup problems show in the chat instead of killing the page
            await self.close()
            msg = f"The agent could not run: {type(e).__name__}: {e}"
            yield {"type": "error", "error": msg, "message": msg}
        yield {"type": "done", "cards": list(self.turn_cards), **self.stats()}
