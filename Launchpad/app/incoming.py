"""The "Incoming" queue: questions, permission cards and plan proposals, with server-side timers.

- ask(...) emits queue_item and waits for queue_response (or the timer) -> (answer, by, response)
- timed (timeout_s set): on expiry resolves with the recommendation, by "timer"
- blocking (timeout_s None): waits until the user answers or the run / chat is stopped
- respond(msg): UI queue_response {id, answer} or {id, decision, remember?, mode?, message?} -> resolves,
  emits queue_resolved by "user"; the whole message is handed back as `response`
- Items belong to a run (session_id) or to a regular chat (chat_id); cancel_session / cancel_chat resolve
  every open item of one with None
- Permission cards carry no recommendation (rec null): the page must not badge a choice
- Builder permission cards are timed (deny on expiry); autopilot resolves open ones with "allow", by "autopilot"
- Auto answers (per session, hub.set_auto_answers): a question WITH a recommendation is answered at once with it
  (by "auto", no card; the hub adds the chat line); one without waits as a normal card. auto_open() does the same for
  questions already waiting when the switch is turned on. Permission and plan items are never affected
"""
from __future__ import annotations

import asyncio
import datetime as dt
import itertools
from dataclasses import dataclass, field


@dataclass
class Item:
    id: str
    session_id: str | None
    chat_id: str | None
    kind: str                      # question | permission | plan | info
    agent: str
    agent_id: str | None
    step: int | None
    title: str
    body: str
    rec: str | None
    options: list[str] | None
    blocking: bool
    timeout_s: float | None
    expires_at: str | None
    extra: dict = field(default_factory=dict)
    future: asyncio.Future | None = None

    def event(self) -> dict:
        ev = {"type": "queue_item", "id": self.id, "session_id": self.session_id, "chat_id": self.chat_id,
              "kind": self.kind, "agent": self.agent, "agent_id": self.agent_id, "step": self.step,
              "title": self.title, "body": self.body, "rec": self.rec, "blocking": self.blocking,
              "timeout_s": self.timeout_s, "expires_at": self.expires_at}
        if self.options:
            ev["options"] = list(self.options)
        ev.update(self.extra)
        return ev


class Incoming:
    def __init__(self, hub):
        self.hub = hub
        self.items: dict[str, Item] = {}
        self._ids = itertools.count(1)

    async def ask(self, *, kind: str, agent: str, title: str, body: str, session_id: str | None = None,
                  chat_id: str | None = None, agent_id: str | None = None, step: int | None = None,
                  rec: str | None = None, options: list[str] | None = None, timeout_s: float | None = None,
                  extra: dict | None = None, timer_answer: str | None = None) -> tuple[str | None, str, dict]:
        """-> (answer, by, response) with by = "user" | "timer" | "autopilot" | "auto" | "stopped"; response = the UI
        message. On timer expiry the answer is timer_answer if given, else the recommendation."""
        if kind == "question" and session_id and str(rec or "").strip() and self._auto_on(session_id):
            qid = f"q{next(self._ids)}"
            await self.hub.auto_answered(session_id, id=qid, agent=agent, step=step, title=title, answer=str(rec))
            return str(rec), "auto", {}
        expires = None
        if timeout_s is not None:
            expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=timeout_s)).isoformat()
        item = Item(id=f"q{next(self._ids)}", session_id=session_id, chat_id=chat_id, kind=kind, agent=agent,
                    agent_id=agent_id, step=step, title=title, body=body, rec=rec, options=options or None,
                    blocking=timeout_s is None, timeout_s=timeout_s, expires_at=expires, extra=dict(extra or {}),
                    future=asyncio.get_running_loop().create_future())
        self.items[item.id] = item
        await self.hub.emit(item.event())
        try:
            done, _ = await asyncio.wait({item.future}, timeout=timeout_s)
            if not done:                                   # timer expired: the server decides, not the UI
                await self._resolve(item, timer_answer if timer_answer is not None else rec, "timer")
            return item.future.result()
        except asyncio.CancelledError:                     # run / chat stopped while waiting: clear the card
            await self._resolve(item, None, "stopped")
            raise
        finally:
            self.items.pop(item.id, None)

    def _auto_on(self, session_id: str) -> bool:
        ls = getattr(self.hub, "sessions", {}).get(session_id)
        return bool(ls is not None and getattr(ls, "auto_answers", False))

    async def auto_open(self, session_id: str) -> int:
        """Auto answers just turned on: answer every waiting question of the session that has a recommendation."""
        n = 0
        for item in list(self.items.values()):
            if item.session_id == session_id and item.kind == "question" and str(item.rec or "").strip():
                await self.hub.auto_answered(session_id, id=item.id, agent=item.agent, step=item.step,
                                             title=item.title, answer=str(item.rec))
                await self._resolve(item, str(item.rec), "auto")
                n += 1
        return n

    async def _resolve(self, item: Item, answer, by: str, response: dict | None = None) -> None:
        if item.future.done():
            return
        item.future.set_result((answer, by, dict(response or {})))
        await self.hub.emit({"type": "queue_resolved", "id": item.id, "answer": answer,
                             "by": "user" if by == "stopped" else by})

    async def respond(self, msg: dict) -> bool:
        item = self.items.get(str(msg.get("id")))
        if item is None:
            return False
        answer = msg.get("decision") if item.kind in ("permission", "plan") else msg.get("answer")
        if answer is None:
            answer = msg.get("answer", msg.get("decision"))
        if answer is None or str(answer).strip() == "":
            return False
        await self._resolve(item, str(answer), "user", msg)
        return True

    async def cancel_session(self, session_id: str) -> None:
        for item in list(self.items.values()):
            if item.session_id == session_id:
                await self._resolve(item, None, "stopped")

    async def resolve_open(self, session_id: str, *, kind: str, answer: str, by: str) -> int:
        """Resolve every open item of one kind in a session (autopilot approving open permission cards)."""
        n = 0
        for item in list(self.items.values()):
            if item.session_id == session_id and item.kind == kind:
                await self._resolve(item, answer, by)
                n += 1
        return n

    async def cancel_chat(self, chat_id: str) -> None:
        for item in list(self.items.values()):
            if item.chat_id == chat_id:
                await self._resolve(item, None, "stopped")

    def open_events(self) -> list[dict]:
        return [i.event() for i in self.items.values()]
