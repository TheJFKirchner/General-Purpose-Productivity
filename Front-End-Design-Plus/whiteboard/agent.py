"""The whiteboard's agent: one agentlib chat session for the life of the page.

Its only tool is add_card. It has no file, shell or web tools, runs with permission_mode="never_ask" and
saves no conversation. It sees its brief, the column names and types, about three sample rows, the style
note, the recipes already on the board and the reference notes for the session's library (plus html.md for
tables). Each message it gets starts with the current board, so it can refer to cards by ID and knows which
were deleted.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import AsyncIterator, Callable

from agentlib import Agent, AgentError, TextDelta, tool

from .board import Board, BoardError
from .data import Table

AGENT_NAME = "whiteboard"
REFERENCES = Path(__file__).resolve().parent.parent / "references"
DEFAULT_MODEL = "sonnet"

BRIEF = """\
You design charts and tables on a whiteboard page. The user sees a grid of cards. Each card is a sealed
mini-page that runs one recipe of yours on the full real data. You never see the data itself: only the column
names and types, a few sample rows, and the user's requests.

## Adding a card
Call the add_card tool. It returns the card's ID (G1, G2, ...). Every visual must go through add_card: code
written in a chat reply is never drawn.

## The recipe contract
`code` is the body of a JavaScript function `render(el, rows, lib)`:
- `el` is the empty box (a div filling the card). Draw into it and nowhere else.
- `rows` is an array of row objects keyed by the column names below. Numbers are numbers, dates are
  strings, missing values are null. It holds every row, so group, sort and aggregate in the code.
- `lib` is the session library's global (see the library notes). It is absent in plain HTML.
- Write only the body: no `function render` wrapper, no <script> tags, no imports, no fetch or network
  calls, no outside files.

## Kinds
- `chart`: drawn with the session library.
- `table`: a plain HTML table built with the DOM or innerHTML, no library. Tables are available in every
  session, whatever the library.

## IDs and parents
- Several visuals asked for in one message means several cards: call add_card once for each.
- A change to an existing card ("G3 but stacked", "try G2 as a line") is an iteration: add a new card with
  `parent` set to that card's ID. Cards are never changed in place.
- Refer to cards by ID. If the user names an ID that is not on the board, say so.
- Each user message starts with the current board and any cards the user deleted. Do not build on a deleted
  card unless the user asks.

## Layout and titles
- The title must describe exactly what is drawn. If it names two measures, draw both; otherwise change the
  title.
- Leave room for titles: if the chart draws its own title, set top margin or padding so value labels, axis
  names and legends never overlap it or each other.
- Tables must fit the card's width with no sideways scrolling. The box can be as narrow as about 520 px:
  wrap text, use a smaller font, shorten headers, or leave out minor columns (and say which).

## Broken cards
If a card fails in the browser you get its error once. Fix it by calling add_card with `replaces` set to that
ID: the fixed card keeps the ID. Add no other cards in that turn.

## Replies
Chat replies are one short plain line per card: its ID and what it shows, e.g. "G4: monthly revenue by region,
stacked bars". No Markdown headings, no code in chat. If a request is unclear, make a sensible choice and say
which in one line; there is no way to ask questions.
"""

ADD_CARD_DESCRIPTION = (
    "Add a card (one chart or table) to the whiteboard. Returns the card's ID. Call it once per visual. "
    "For an iteration of an existing card set parent to that card's ID. Use replaces only to fix a card "
    "reported as broken.")

ADD_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short title shown on the card."},
        "code": {"type": "string", "description": "Body of render(el, rows, lib) in JavaScript."},
        "kind": {"enum": ["chart", "table"], "description": "chart = session library; table = plain HTML."},
        "parent": {"type": "string", "description": "ID of the card this one iterates on, e.g. G3."},
        "replaces": {"type": "string", "description": "Only when fixing a broken card: its ID."},
    },
    "required": ["title", "code"],
}


def read_reference(library: str, folder: Path = REFERENCES) -> str | None:
    p = folder / f"{library}.md"
    try:
        text = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    # Nest the file's headings under the prompt's "## Library notes" heading.
    return re.sub(r"^(#{1,4}) ", r"##\1 ", text, flags=re.M)


CHAT_IN_PROMPT = 12          # earlier messages shown to a new session (after a resume or a restart)
CHAT_TEXT_LIMIT = 300


def build_prompt(library: str, table: Table, style: str | None, cards: list[dict],
                 references: Path = REFERENCES, chat: list[dict] | None = None) -> str:
    parts = [BRIEF, f"## Session library: {library}"]
    if library == "html":
        parts.append("This session uses plain HTML and SVG: there is no library and `lib` is absent. "
                     "Charts are drawn with the DOM, SVG or canvas.")
    cols = "\n".join(f"- {c['name']} ({c['type']})" for c in table.columns) or "- (no columns)"
    parts.append(f"## Data\n{len(table.rows)} rows. Columns:\n{cols}\n\nSample rows (not the full data):\n"
                 f"```json\n{json.dumps(table.samples(), indent=2, ensure_ascii=False, default=str)}\n```")
    if style and style.strip():
        parts.append(f"## Style note from the user\n{style.strip()}")
    if cards:
        listing = []
        for c in cards:
            head = f"### {c['id']}: {c['title']} ({c['kind']}, library {c['library']}"
            head += f", iterates on {c['parent']})" if c.get("parent") else ")"
            listing.append(f"{head}\n```js\n{c['code']}\n```")
        parts.append("## Cards already on the board\n" + "\n\n".join(listing))
    if chat:
        lines = []
        for m in chat[-CHAT_IN_PROMPT:]:
            text = " ".join(m["text"].split())
            text = text if len(text) <= CHAT_TEXT_LIMIT else text[:CHAT_TEXT_LIMIT] + "..."
            lines.append(f"- {m['role']}: {text}")
        parts.append("## Conversation so far (before this session started; most recent last)\n" + "\n".join(lines))
    ref = read_reference(library, references)
    if ref:
        parts.append(f"## Library notes: {library}\n{ref}")
    elif library != "html":
        parts.append(f"## Library notes: {library}\n`lib` is the {library} library's global object.")
    if library != "html":
        html_ref = read_reference("html", references)
        if html_ref:
            parts.append(f"## Library notes: html (for tables)\n{html_ref}")
    return "\n\n".join(parts) + "\n"


def board_header(board: Board) -> str:
    cards = board.snapshot()
    if cards:
        lines = [f"{c['id']} \"{c['title']}\" ({c['kind']}"
                 + (f", from {c['parent']})" if c.get("parent") else ")") for c in cards]
        text = "Board now: " + "; ".join(lines) + "."
    else:
        text = "Board now: empty."
    notes = board.take_notes()
    if notes:
        text += " Since your last turn the user " + ", ".join(notes) + "."
    return f"[{text}]"


Sink = Callable[[dict], None]


class Designer:
    """Owns the agentlib session. All methods run on one asyncio loop (the server's background loop)."""

    def __init__(self, board: Board, table: Table, style: str | None = None, *, engine: str = "claude",
                 model: str | None = DEFAULT_MODEL, max_budget_usd: float | None = None,
                 references: Path = REFERENCES):
        self.board = board
        self.table = table
        self.style = style
        self.engine = engine
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.references = references
        self._session = None
        self._lock: asyncio.Lock | None = None
        self._outbox: list[dict] = []
        self.turn_cards: list[str] = []
        self.add_card = self._make_tool()

    # ---- the tool ----------------------------------------------------------------------------------
    def _make_tool(self):
        board, outbox, turn_cards = self.board, self._outbox, self.turn_cards

        async def add_card(title: str, code: str, kind: str | None = None, parent: str | None = None,
                           replaces: str | None = None) -> str:
            try:
                if replaces and replaces.strip():
                    card = board.replace(replaces.strip().upper(), title, code, kind)
                    note = f"{card['id']} replaced with the fix."
                else:
                    card = board.add(title, code, kind or "chart", parent)
                    note = f"Added {card['id']}."
            except BoardError as e:
                raise ValueError(str(e)) from None
            outbox.append({"type": "card", **card})
            turn_cards.append(card["id"])
            return f"{note} ID: {card['id']}"

        return tool(name="add_card", description=ADD_CARD_DESCRIPTION, schema=ADD_CARD_SCHEMA)(add_card)

    # ---- session -----------------------------------------------------------------------------------
    def make_agent(self) -> Agent:
        return Agent(
            AGENT_NAME,
            instructions=build_prompt(self.board.library, self.table, self.style, self.board.snapshot(),
                                      self.references, self.board.chat_log()),
            engine=self.engine, model=self.model, tools=[self.add_card],
            permission_mode="never_ask", save_conversation=False, max_budget_usd=self.max_budget_usd,
            cwd=str(self.board.out),
        )

    async def _ensure_session(self):
        if self._session is None:
            session = self.make_agent().session()
            await session.__aenter__()
            self._session = session
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            session, self._session = self._session, None
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ---- turns -------------------------------------------------------------------------------------
    async def chat(self, message: str) -> AsyncIterator[dict]:
        """One user message -> events for the page: text (delta), card, error, then done."""
        message = (message or "").strip()
        if not message:
            yield {"type": "error", "error": "Type a request first.", "message": "Type a request first."}
            yield {"type": "done", "cards": []}
            return
        reply: list[str] = []
        try:
            async with self._get_lock():
                async for ev in self._turn(f"{board_header(self.board)}\n\n{message}"):
                    if ev["type"] == "text":
                        reply.append(ev["text"])
                    yield ev
        finally:
            # Recorded after the turn, so a session started for this turn does not see it twice.
            self.board.add_chat("user", message)
            self.board.add_chat("agent", "".join(reply))

    async def fix(self, card_id: str, error: str) -> dict:
        """A card failed to render. Sent to the agent once per card; returns the fixed card if any."""
        if not self.board.error_reported(card_id):
            card = self.board.get(card_id)
            why = "is not on the board" if card is None else "was already sent back once"
            return {"ok": True, "fixed": False, "card": None, "cards": [], "text": "",
                    "message": f"{card_id} {why}; not sent to the agent again."}
        text, cards, errors = [], [], []
        msg = (f"{board_header(self.board)}\n\nCard {card_id} failed to render in the browser with this error:\n"
               f"{(error or 'unknown error').strip()[:2000]}\n\nFix it: call add_card once with "
               f"replaces=\"{card_id}\" and the corrected code. Add no other cards.")
        try:
            async with self._get_lock():
                async for ev in self._turn(msg):
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
        out = {"ok": not errors, "fixed": fixed is not None, "card": fixed, "cards": cards, "text": "".join(text)}
        if errors:
            out["error"] = "; ".join(errors)
        return out

    async def _turn(self, message: str) -> AsyncIterator[dict]:
        self._outbox.clear()
        self.turn_cards.clear()
        try:
            session = await self._ensure_session()
            async for ev in session.stream(message):
                while self._outbox:
                    yield self._outbox.pop(0)
                if isinstance(ev, TextDelta) and ev.text:
                    yield {"type": "text", "text": ev.text, "delta": ev.text}
                elif ev.type == "done":
                    reply = ev.reply
                    while self._outbox:
                        yield self._outbox.pop(0)
                    if reply.status == "error":
                        msg = reply.error or f"The agent stopped ({reply.error_kind or 'error'})."
                        yield {"type": "error", "error": msg, "message": msg}
            while self._outbox:
                yield self._outbox.pop(0)
        except AgentError as e:
            while self._outbox:
                yield self._outbox.pop(0)
            # The conversation is not saved, so it cannot be resumed: start afresh next turn. The new
            # prompt lists every card on the board, so IDs still mean the same thing.
            await self.close()
            msg = f"The agent could not run: {getattr(e, 'short', None) or e}"
            yield {"type": "error", "error": msg, "message": msg}
        except Exception as e:  # setup problems show in the chat instead of killing the page
            msg = f"The agent could not run: {type(e).__name__}: {e}"
            yield {"type": "error", "error": msg, "message": msg}
        yield {"type": "done", "cards": list(self.turn_cards)}
