"""Regular session (display name "Claude Code"; role key pilot): a plain Claude Code chat in the launch folder. No plan, no orchestrator.

- setup="project": Claude Code system prompt, all built-in tools, the folder's CLAUDE.md, user + project
  settings (incl. the user's own permission allow/deny rules), skills, hooks. Nothing Launchpad-specific is
  added (no ask_user, empty agent body) and none of the builder guards apply: permissions are Claude Code's
- Permission modes: default | accept_edits | plan, switchable any time (between turns and mid-turn); no bypass
- Permission prompts, plan proposals and Claude's own questions (AskUserQuestion) become queue items tied to
  the chat (chat_id, session_id null), no timer; "always allow" offers this session or the project's local
  settings (.claude/settings.local.json)
- In plan mode edits reach on_permission (the engine does not hard-block them): denied here without a card
- Streaming (chat_delta), interrupt (chat_stop), activity feed + usage like any agent; activity.log in
  <project>/.launchpad/<chat-id>/
- Fake engine: project setup with tools=None approves every built-in, so the tools Claude Code would ask about
  are gated there (FAKE_ASKING) to make prompts visible; on Claude nothing is gated
"""
from __future__ import annotations

import asyncio
import contextlib

from agentlib import AgentError, PermissionDecision
from agentlib.events import Done, Text, TextDelta

from ...activity import summarize
from ...meter import Meter
from ...sessionfiles import SessionFolder, new_session_id
from .. import crew

MODES = ("default", "accept_edits", "plan")
EDIT_TOOLS = set(crew.WRITE_TOOLS)                 # file edits (denied without a card in plan mode)
FAKE_ASKING = ["Write", "Edit", "NotebookEdit", "Bash", "WebFetch", "AskUserQuestion"]
STOP_GRACE_S = 5.0
PLAN_EDIT_DENIED = "Plan mode is on: do not edit files until the user approves your plan."


def pilot_overrides(engine: str) -> dict:
    """Load-time settings for the Claude Code chat (library-only, never in the agent file)."""
    kw = dict(setup="project", include_ask_user=False, permission_mode="default", timeout_s=None)
    if engine == "fake":
        kw["gated_tools"] = list(FAKE_ASKING)
    return kw


def offers(req) -> tuple[list[dict], bool]:
    """'Always allow' choices for a permission card from the engine's suggestions -> ([{label, remember}], edits)."""
    rules = [r for s in req.suggestions if s.kind == "add_rules" and (s.behavior or "allow") == "allow"
             for r in s.rules]
    edits = any(s.kind == "set_mode" and s.mode == "accept_edits" for s in req.suggestions)
    what = ", ".join(dict.fromkeys(rules)) or req.tool
    first = ({"label": "Allow all edits this session (accept edits mode)", "remember": "session"} if edits
             else {"label": f"Always allow {what} this session", "remember": "session"})
    return [first, {"label": f"Always allow {what} in this project (saved to .claude/settings.local.json)",
                    "remember": "project_local"}], edits


class PilotChat:
    def __init__(self, hub, project=None, dir_id: str | None = None):
        self.hub = hub
        s = hub.settings
        self.id = new_session_id()
        self.dir_id = dir_id or hub.default_dir
        project = project or s.project                    # the chat's own directory (cwd, settings, records)
        self.folder = SessionFolder(project, self.id)
        self.agent = crew.load("pilot", engine=s.engine, project=project, model=s.pilot_model,
                               on_permission=self.permission, **pilot_overrides(s.engine))
        self.mode = self.agent.permission_mode
        self.meter = Meter(hub, session_id=None, chat_id=self.id, role="pilot", name=crew.display("pilot"))
        self.session = None
        self.resume_id: str | None = None
        self.history: list[dict] = []
        self.lock = asyncio.Lock()
        self.turn_task: asyncio.Task | None = None
        self.stopping = False
        self.last_reply = None
        self.counted = False                # one use count per chat (its agent started once)

    # ---------------------------------------------------------------- events
    async def emit(self, ev: dict) -> None:
        ev.setdefault("chat_id", self.id)
        await self.hub.emit(ev)

    def started_event(self) -> dict:
        return {"type": "chat_started", "chat_id": self.id, "mode": self.mode, "model": self.agent.model,
                "cwd": str(self.folder.project), "dir_id": self.dir_id}

    def snapshot(self) -> dict:
        return {"id": self.id, "dir_id": self.dir_id, "mode": self.mode, "model": self.agent.model,
                "cwd": str(self.folder.project),
                "busy": self.lock.locked(), "history": list(self.history)}

    async def _mode_changed(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            await self.emit({"type": "chat_mode", "mode": mode})

    # ---------------------------------------------------------------- turns
    async def message(self, text: str, *, echo: bool = False) -> None:
        """One user turn. echo: also send the user's text as chat_message role user (for messages the page did not
        type itself, e.g. the plan sent by chat_from_plan); the snapshot history holds it either way."""
        if self.lock.locked():
            await self.hub.emit({"type": "system", "chat_id": self.id,
                                 "text": f"{self.meter.name} is still answering; your message will follow."})
        async with self.lock:
            self.turn_task = asyncio.current_task()
            self.history.append({"role": "user", "markdown": text})
            if echo:
                await self.emit({"type": "chat_message", "role": "user", "markdown": text})
            self.stopping = False
            status, error = "ok", None
            await self.emit({"type": "chat_typing", "on": True})
            await self.meter.set_status("working")
            try:
                if self.session is None:
                    self.session = self.agent.session(resume=self.resume_id) if self.resume_id else self.agent.session()
                    await self.session.__aenter__()
                    if not self.counted:
                        self.counted = True
                        await self.hub.count_use(self.agent.name)
                async for ev in self.session.stream(text):
                    await self.meter.feed(ev)
                    if isinstance(ev, TextDelta):
                        await self.emit({"type": "chat_delta", "text": ev.text})
                    elif isinstance(ev, Text):
                        self.history.append({"role": "assistant", "markdown": ev.text})
                        await self.emit({"type": "chat_message", "role": "assistant", "markdown": ev.text})
                    elif isinstance(ev, Done):
                        self.last_reply = ev.reply
                        if ev.reply.status == "error" and not self.stopping:
                            status, error = "failed", ev.reply.error
            except AgentError as e:
                await self.meter.add_reply(e.reply)
                status, error = ("stopped", None) if self.stopping else ("failed", e.short)
            except asyncio.CancelledError:             # stop did not end the turn in time: drop the process
                status = "stopped"
                await self._drop_session()
            finally:
                self.turn_task = None
            if self.stopping:
                status, error = "stopped", None
            if self.session is not None:
                await self._mode_changed(self.session.permission_mode)
            await self.emit({"type": "chat_typing", "on": False})
            await self.meter.set_status("idle")
            await self.emit({"type": "chat_done", "status": status, **({"error": error} if error else {})})

    async def _drop_session(self) -> None:
        if self.session is not None:
            self.resume_id = self.session.session_id or self.resume_id
            with contextlib.suppress(Exception):
                await self.session.close()
            self.session = None

    async def stop(self) -> None:
        task = self.turn_task
        if task is None:
            return
        self.stopping = True
        await self.hub.incoming.cancel_chat(self.id)
        if self.session is not None:
            with contextlib.suppress(Exception):
                await self.session.interrupt()
        done, _ = await asyncio.wait({task}, timeout=STOP_GRACE_S)
        if not done:
            task.cancel()

    async def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            await self.hub.emit({"type": "system", "chat_id": self.id, "text": f"Unknown mode: {mode}"})
            return
        if self.session is not None:
            await self.session.set_permission_mode(mode)
        else:
            self.agent.permission_mode = mode
        self.mode = mode
        await self.emit({"type": "chat_mode", "mode": mode})        # always confirm, even if unchanged

    # ---------------------------------------------------------------- permissions, plans, questions
    async def _ask(self, **kw):
        return await self.hub.incoming.ask(chat_id=self.id, agent=self.meter.name, agent_id=self.meter.agent_id,
                                           **kw)

    async def permission(self, req):
        if self.stopping:
            return PermissionDecision("deny", message="The user stopped this turn.")
        if req.kind == "plan":
            return await self._plan(req)
        if req.tool == "AskUserQuestion":
            return await self._questions(req)
        if req.mode == "plan" and req.tool in EDIT_TOOLS:
            return PermissionDecision("deny", message=PLAN_EDIT_DENIED)
        choices, edits = offers(req)
        answer, _by, resp = await self._ask(
            kind="permission", title=req.title or f"{self.meter.name} wants to use {req.tool}",
            body=summarize(req.tool, req.input, self.folder.project),
            options=["allow", "deny", "always"], extra={"tool": req.tool, "suggestions": choices})
        if answer == "allow":
            return PermissionDecision("allow")
        if answer == "always":
            remember = resp.get("remember") if resp.get("remember") in ("session", "project_local") else "session"
            if remember == "session" and edits:            # Claude Code's "allow all edits this session"
                await self._mode_changed("accept_edits")
                return PermissionDecision("allow", mode="accept_edits")
            return PermissionDecision("always_allow", remember=remember)
        return PermissionDecision("deny", message=(resp.get("message") or None))

    async def _plan(self, req):
        answer, _by, resp = await self._ask(kind="plan", title="Plan proposal", body="",
                                            extra={"markdown": req.plan or ""})
        if answer in ("allow", "always"):
            mode = resp.get("mode") if resp.get("mode") in ("default", "accept_edits") else "default"
            await self._mode_changed(mode)
            return PermissionDecision("allow", mode=mode)
        return PermissionDecision("deny", message=(resp.get("message") or None))

    async def _questions(self, req):
        """Claude's own question tool: one question card per question; answers go back as the tool input."""
        qs = list(req.input.get("questions") or [])
        answers = {}
        for q in qs:
            labels = [str(o.get("label", o)) if isinstance(o, dict) else str(o) for o in q.get("options") or []]
            answer, _by, _ = await self._ask(kind="question", title=str(q.get("header") or "Question"),
                                             body=str(q.get("question", "")), options=labels or None)
            if answer is None:
                return PermissionDecision("deny", message="The user stopped this turn.")
            answers[str(q.get("question", ""))] = answer
        return PermissionDecision("allow", input={**req.input, "questions": qs, "answers": answers})

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.session is not None:
                await self.session.close()
