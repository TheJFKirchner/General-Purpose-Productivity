"""Per-agent-session usage: tokens, cost, tool calls -> live agent_usage + activity events.

- One Meter per agent session (planner, the Explorer, each orchestrator, each step agent)
- feed(event): ToolCall -> tool_calls + 1 (pushed live) + activity "started"; ToolResult -> activity
  done | denied | failed; Done -> usage + cost added (pushed)
- failed turns: add_reply(AgentError.reply) keeps whatever usage the engine saw; open calls close as failed
- agent_usage keeps the old planner-header fields (agent, cache_read, cache_write, input, output, last)
"""
from __future__ import annotations

import uuid

from agentlib.events import Done, ToolCall, ToolResult
from agentlib.reply import Usage

from . import activity


class Meter:
    def __init__(self, hub, *, session_id: str | None, role: str, name: str, step: int | None = None,
                 chat_id: str | None = None):
        self.hub = hub
        self.path_roots: list = []                 # extra folders its paths are shown relative to (the Role Reviewer's)
        self.session_id = session_id
        self.chat_id = chat_id                     # regular chats (role "pilot"): session_id None, chat_id set
        self.role = role
        self.name = name
        self.step = step
        self.agent_id = f"{role}-{uuid.uuid4().hex[:8]}"
        self.status = "idle"
        self.usage = Usage()
        self.last = Usage()
        self.cost_usd = 0.0
        self.tool_calls = 0
        self.open_calls: dict[str, dict] = {}      # tool call id -> its "started" activity event
        self.by_model: dict[str, dict] = {}         # model id -> {"usage": Usage, "cost_usd": float} (cumulative)
        hub.meters.append(self)

    def event(self) -> dict:
        u = self.usage
        ev = {"type": "agent_usage", "session_id": self.session_id, "chat_id": self.chat_id, "agent_id": self.agent_id,
                "role": self.role, "name": self.name, "step": self.step,
                "status": "idle" if self.status == "waiting" else self.status,   # waiting = on the user (crew only)
                "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                "cache_read_tokens": u.cache_read_tokens, "cache_write_tokens": u.cache_write_tokens,
                "cost_usd": round(self.cost_usd, 6), "tool_calls": self.tool_calls,
                # older fields (planner chat header), kept for compatibility
                "agent": self.role if self.role == "planner" else self.agent_id,
                "cache_read": u.cache_read_tokens, "cache_write": u.cache_write_tokens,
                "input": u.input_tokens, "output": u.output_tokens,
                "last": {"cache_read": self.last.cache_read_tokens, "cache_write": self.last.cache_write_tokens}}
        if len(self.by_model) > 1 or self.role == "planner":        # the split (e.g. Sonnet then Opus)
            ev["by_model"] = [{"model": m, "cost_usd": round(v["cost_usd"], 6),
                               "input_tokens": v["usage"].input_tokens, "output_tokens": v["usage"].output_tokens,
                               "cache_read_tokens": v["usage"].cache_read_tokens,
                               "cache_write_tokens": v["usage"].cache_write_tokens} for m, v in self.by_model.items()]
        return ev

    async def push(self) -> None:
        await self.hub.emit(self.event())

    async def set_status(self, status: str) -> None:
        if status in ("done", "idle") and self.open_calls:
            await self.close_calls()
        if status != self.status:
            self.status = status
            await self.push()
            await self.hub.emit_crew()

    async def feed(self, ev) -> None:
        if isinstance(ev, ToolCall):
            self.tool_calls += 1
            await self.push()
            await self._activity_start(ev)
        elif isinstance(ev, ToolResult):
            await self._activity_end(ev.id, activity.final_status(ev.is_error, ev.text))
        elif isinstance(ev, Done):
            for rec in (ev.reply.tool_calls if ev.reply else []):     # results the stream did not show
                if rec.id in self.open_calls:
                    await self._activity_end(rec.id, activity.final_status(rec.is_error, rec.result or ""))
            await self.add_reply(ev.reply)

    # ---------------------------------------------------------------- activity feed
    async def _activity_start(self, call) -> None:
        owner = self.hub.sessions.get(self.session_id or "") or self.hub.chats.get(self.chat_id or "")
        wf = getattr(self.hub, "workflows", None)
        run = wf.mission(self.session_id) if wf is not None and owner is None else None
        project = (owner.folder.project if owner is not None else
                   run.folder.project if run is not None else self.hub.settings.project)
        roots = [project, *self.path_roots]
        try:
            roots += self.hub.extra_dirs(None)[1]
        except Exception:
            pass
        home = getattr(getattr(self.hub, "tally", None), "home", None)
        if home:
            roots.append(home)
        project = roots
        ev = {"type": "activity", "id": f"{self.agent_id}:{call.id}", "session_id": self.session_id,
              "chat_id": self.chat_id,
              "agent_id": self.agent_id, "role": self.role, "name": self.name, "step": self.step,
              "tool": call.name, "summary": activity.summarize(call.name, call.input, project),
              "status": "started", "ts": activity.now_iso()}
        self.open_calls[call.id] = ev
        await self.hub.activity(dict(ev))      # a copy: the open entry may still gain auto: true

    async def activity_begin(self, tool: str, summary: str) -> str:
        """An activity entry for work that is not a tool call (e.g. a visual render) -> its call id."""
        cid = f"job-{uuid.uuid4().hex[:8]}"
        ev = {"type": "activity", "id": f"{self.agent_id}:{cid}", "session_id": self.session_id,
              "chat_id": self.chat_id, "agent_id": self.agent_id, "role": self.role, "name": self.name,
              "step": self.step, "tool": tool, "summary": activity.one_line(summary, activity.SUMMARY_MAX),
              "status": "started", "ts": activity.now_iso()}
        self.open_calls[cid] = ev
        await self.hub.activity(dict(ev))
        return cid

    async def activity_end(self, call_id: str, status: str) -> None:
        await self._activity_end(call_id, status)

    async def _activity_end(self, call_id: str, status: str) -> None:
        started = self.open_calls.pop(call_id, None)
        if started is None:
            return
        await self.hub.activity({**started, "status": status, "ts": activity.now_iso()}, started=started["ts"])

    async def close_calls(self, status: str = "failed") -> None:
        """A turn ended without results for some calls (stopped, crashed): close them in the feed."""
        for call_id in list(self.open_calls):
            await self._activity_end(call_id, status)

    async def add_reply(self, reply, *, count_tools: bool = False) -> None:
        if reply is None:
            return
        self.last = reply.usage
        self.usage = self.usage + reply.usage
        self.cost_usd += float(reply.cost_usd or 0.0)
        for mid, v in (getattr(reply, "usage_by_model", None) or {}).items():
            cur = self.by_model.setdefault(mid, {"usage": Usage(), "cost_usd": 0.0})
            cur["usage"] = cur["usage"] + v["usage"]
            cur["cost_usd"] += float(v.get("cost_usd") or 0.0)
        if count_tools:
            self.tool_calls += len(reply.tool_calls)
        await self.push()
        await self.hub.emit_totals(self)

    def tokens(self) -> int:
        return self.usage.total_input_tokens + self.usage.output_tokens
