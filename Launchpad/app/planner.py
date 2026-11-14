"""The planner chat (Planner): one agentlib session per Launchpad session.

- Tools: ask_user (file) + explore, read_markdown, write_plan, edit_plan, show_visuals (Launchpad-only, handed over
  at load time)
- Step agents: the registry's step workers (name, purpose, description; app/crew.py) reach the planner in its first
  message and again, as one short block before the user's next message, when the folder's agents change. The system
  prompt and the cached tool list never change for this. The planner may name an agent per step (write_plan /
  edit_plan `agent`); it never starts one: the orchestrator does, after approval
- Visual picks (app/visuals.py) reach the planner as short lines prefixed to the user's next message
- No shell, no write/edit, no general file reading: read_markdown only opens .md files inside the project
- ask_user questions -> question_round cards; round_answer -> session.answer()
- write_plan -> validated plan.md draft + plan_draft event; only the user's approval starts a run
"""
from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from agentlib import AgentError, tool
from agentlib.events import Done, Text

from . import astronaut, crew, visuals
from .meter import Meter
from .sessionfiles import inside

READ_LIMIT = 60_000          # characters returned by read_markdown
CRITERIA_FILE = Path(__file__).resolve().parent / "planner-promotion.md"

EDIT_PLAN_SCHEMA = {
    "type": "object",
    "properties": {"edits": {"type": "array", "minItems": 1, "items": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["replace", "rename", "set_goal", "set_step", "add_step",
                                                "remove_step", "move_step"]},
            "find": {"type": "string", "description": "replace: exact text, must occur once"},
            "replace": {"type": "string"},
            "name": {"type": "string", "description": "rename"},
            "goal": {"type": "string", "description": "set_goal"},
            "n": {"type": "integer", "description": "step number (set_step, remove_step, move_step)"},
            "to": {"type": "integer", "description": "move_step: new position"},
            "position": {"type": "integer", "description": "add_step: insert at (default: end)"},
            "title": {"type": "string"}, "details": {"type": "string"}, "done_when": {"type": "string"},
            "skill": {"type": "string"},
            "agent": {"type": "string", "description": "set_step / add_step: step agent name; \"\" = the Builder"},
            "after": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["op"]}}},
    "required": ["edits"],
}


# show_visuals: fixed text (the cached tool list never changes in a session); the folder's libraries reach the
# planner in its first message (visuals.libraries_note)
SHOW_VISUALS_SCHEMA = {
    "type": "object",
    "properties": {
        "brief": {"type": "string", "description": "one line: what to draw or design"},
        "options": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4,
                    "description": "short labels, one per option, e.g. [\"Bar\", \"Stacked bar\", \"Line\"]"},
        "library": {"type": "string", "description": "optional charting library; omit for ECharts"},
    },
    "required": ["brief", "options"],
}
SHOW_VISUALS_DESCRIPTION = (
    "Show the user 2-4 quick visual options beside the chat, drawn by a cheap agent on made-up data. For any "
    "visual or design question: charts, colour palettes, hero cards, layouts, tiles, type. Returns at once; you "
    "never see the visuals. The user's pick, if any, arrives as a short line with their next message.\n"
    "library: only when the user wants a particular charting library. Default ECharts. Chart.js and D3 always "
    "work; Plotly and Bokeh only when installed (your first message lists this folder's libraries). Anything "
    "else (matplotlib, seaborn, Recharts ...) is drawn in ECharts, styled like it, and labelled so.")


def promotion_criteria(settings) -> tuple[str, Path]:
    """The editable criteria (markdown) and the file they came from."""
    path = Path(settings.promotion_criteria_path) if getattr(settings, "promotion_criteria_path", None) else CRITERIA_FILE
    return path.read_text(encoding="utf-8").strip(), path


def planner_models(settings) -> tuple[str, str]:
    """(start, top). --model / planner_model pins one model (promotion off)."""
    if getattr(settings, "planner_model", None):
        return settings.planner_model, settings.planner_model
    return settings.planner_start_model, settings.planner_top_model

WRITE_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "short plan name"},
        "goal": {"type": "string", "description": "2-4 sentences: goal, audience, outputs"},
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "details": {"type": "string", "description": "what to do; key files; inputs and outputs"},
                    "done_when": {"type": "string", "description": "how to know the step is done"},
                    "skill": {"type": "string", "description": "optional skill or playbook name"},
                    "agent": {"type": "string", "description": "optional step agent name from Launchpad's list; "
                                                               "omit for the Builder"},
                    "after": {"type": "array", "items": {"type": "integer"},
                              "description": "earlier step numbers this step needs"},
                },
                "required": ["title", "details", "done_when"],
            },
        },
    },
    "required": ["name", "goal", "steps"],
}


def read_markdown_file(project: Path, path: str, limit: int = READ_LIMIT) -> str:
    """The planner's only file reader: markdown files inside the project folder. ValueError otherwise."""
    project = Path(project).resolve()
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("give a path relative to the project folder")
    cand = Path(raw)
    if not cand.is_absolute():
        cand = project / cand
    if not inside(cand, project):
        raise ValueError("only files inside the project folder can be read")
    target = cand.resolve()
    if target.suffix.lower() != ".md":
        raise ValueError("only markdown (.md) files can be read")
    if not target.is_file():
        raise ValueError(f"no such file: {raw}")
    text = target.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit] + f"\n\n[truncated at {limit} characters]"


def planner_tools(chat, *, criteria: str | None = None) -> list:
    """Launchpad-only planner tools bound to a PlannerChat (None = for describing only). criteria set = the
    promotion tool is offered (it stays offered all session, so the cached tool list never changes; outside
    the window it refuses)."""

    @tool
    async def explore(question: str) -> str:
        """Send the Explorer (fast read-only file finder) to answer one precise question about the project.
        Returns file links, each with a one or two sentence answer; they are also added to the flight log."""
        return (await astronaut.explore(chat.ls, question))["text"]

    @tool(read_only=True)
    def read_markdown(path: str) -> str:
        """Read a markdown (.md) file inside the project folder, e.g. CLAUDE.md, docs, or plan.md /
        flight-log.md / report.md of earlier sessions under .launchpad/. Path relative to the project folder."""
        return read_markdown_file(chat.ls.folder.project, path)

    @tool(schema=WRITE_PLAN_SCHEMA)
    async def write_plan(**plan) -> str:
        """Save the plan as a draft (plan.md in this session's folder). The user approves it in the app,
        which starts the run. Call again to replace the draft."""
        return await chat.ls.save_plan(plan)

    @tool(schema=SHOW_VISUALS_SCHEMA, description=SHOW_VISUALS_DESCRIPTION)
    async def show_visuals(**args) -> str:
        return await chat.ls.visuals.create(args.get("brief", ""), args.get("options") or [], args.get("library"))

    @tool(schema=EDIT_PLAN_SCHEMA)
    async def edit_plan(**args) -> str:
        """Change the current draft with targeted edits instead of rewriting it: replace an exact passage
        (find/replace), rename, set_goal, set_step (title/details/done_when/after of step n), add_step,
        remove_step, move_step; set_step / add_step may set the step's agent. Edits apply in order; step numbers refer to the plan at that moment. The plan is
        re-checked; an edit that would break it is refused with the reason and nothing changes."""
        return await chat.ls.edit_plan(args.get("edits"))

    tools = [explore, read_markdown, write_plan, edit_plan, show_visuals]
    if criteria:
        @tool(description=("Move this conversation to the stronger planner model for the rest of the session. "
                           "Call it at most once, only in your first turns, and only if the conversation meets "
                           "these criteria; give a one-line reason. Then just carry on.\n\n" + criteria))
        async def promote_planner(reason: str) -> str:
            return await chat.promote(by="criteria", reason=reason)
        tools.append(promote_planner)
    return tools


class PlannerChat:
    """Owns one planner session; turns UI messages into agent turns (one at a time)."""

    def __init__(self, ls):
        self.ls = ls
        hub = ls.hub
        self.start_model, self.top_model = planner_models(hub.settings)
        self.window = int(hub.settings.promotion_window_turns)
        criteria = promotion_criteria(hub.settings)[0] if self.start_model != self.top_model else None
        self.agent = crew.load("planner", engine=hub.settings.engine, project=ls.folder.project,
                               model=self.start_model, tools=planner_tools(self, criteria=criteria),
                               env=dict(crew.WAITING_ENV))
        self.model = self.start_model
        self.promoted, self.promote_reason, self.promoted_by = False, None, None
        self.turns = 0                          # planner turns so far (the promotion window counts these)
        self.meter = Meter(hub, session_id=ls.id, role="planner", name=crew.display("planner"))
        self.session = None
        self.lock = asyncio.Lock()
        self.round_no = 0
        self.rounds: dict[str, list] = {}
        self.first = True
        self.registry_dirty = False             # the folder's agents changed: tell the planner before the next message
        self.history: list[dict] = []           # for the reconnect snapshot: {role: user|assistant|system|round|answers, ...}

    async def emit(self, ev: dict) -> None:
        ev.setdefault("session_id", self.ls.id)
        await self.ls.hub.emit(ev)

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    def model_event(self) -> dict:
        return {"type": "planner_model", "session_id": self.ls.id, "model": self.model, "promoted": self.promoted,
                "reason": self.promote_reason, "by": self.promoted_by}

    async def promote(self, *, by: str, reason: str | None = None) -> str:
        """Move to the top model for the rest of the session (never twice, never down). by: criteria | user.
        The conversation carries over as is (same session, agentlib set_model); mid-turn, the next model call
        already uses the new model."""
        if self.start_model == self.top_model:
            raise ValueError("promotion is off for this session (the planner already runs on its only model)")
        if self.promoted:
            raise ValueError(f"already promoted to {self.top_model}; carry on")
        if by == "criteria" and self.turns > self.window:
            raise ValueError(f"the promotion window (first {self.window} turns) has closed; carry on with the "
                             "current model")
        if self.session is not None:
            await self.session.set_model(self.top_model)
        else:
            self.agent.model = self.top_model
        self.model, self.promoted, self.promoted_by = self.top_model, True, by
        self.promote_reason = (str(reason).strip()[:300] or None) if reason else None
        await self.ls.hub.emit(self.model_event())
        return f"Promoted to {self.top_model} for the rest of this session. Carry on with the conversation."

    def context_note(self) -> str:
        """Prefix for the first message: where the project and earlier sessions are, and the step agents."""
        f = self.ls.folder
        earlier = f.earlier_sessions()
        lines = [f"[Launchpad] Today is {dt.date.today().isoformat()}. Project folder: {f.project.name}. "
                 f"This session: {f.rel(f.path)}."]
        if earlier:
            lines.append("Earlier sessions (plan.md, flight-log.md, report.md readable with read_markdown): "
                         + ", ".join(earlier))
        lines.append(crew.registry_note(f.project))
        lines.append(visuals.libraries_note(f.project))
        return "\n".join(lines) + "\n\n"

    def registry_changed(self) -> None:
        """The folder's agents were added, edited or removed: the next message carries the new list (new plans)."""
        if not self.first:
            self.registry_dirty = True

    def take_registry_note(self) -> str:
        if not self.registry_dirty:
            return ""
        self.registry_dirty = False
        return "[Launchpad] The step agents changed. " + crew.registry_note(self.ls.folder.project) + "\n\n"

    @staticmethod
    def round_answers(msg: dict) -> list[dict]:
        """UI round_answer -> agentlib answers; anything unanswered (incl. "Skip for now") -> skipped."""
        out = []
        for qid, a in (msg.get("answers") or {}).items():
            if a.get("accepted"):
                out.append({"id": qid, "answer": True, "kind": "recommended"})
            elif a.get("option"):
                out.append({"id": qid, "answer": a["option"], "kind": "option"})
            elif a.get("text"):
                out.append({"id": qid, "answer": a["text"], "kind": "free_text"})
        return out

    async def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if self.lock.locked():
            await self.emit({"type": "system", "text": "Still working on the last message, one moment."})
        async with self.lock:
            self.turns += 1
            if self.session is None:
                self.session = self.agent.session()
                await self.session.__aenter__()
                await self.ls.hub.count_use(self.agent.name)        # one count per planner session started
            await self.emit({"type": "typing", "on": True})
            await self.meter.set_status("working")
            try:
                if kind == "round_answer":
                    self.history.append({"role": "answers", "roundId": msg.get("roundId"),
                                         "answers": msg.get("answers") or {}, "skipped": bool(msg.get("skipped"))})
                    qs = self.rounds.get(msg.get("roundId"), self.session.pending_questions)
                    stream = self.session.answer_stream(self.round_answers(msg), questions=[q.to_dict() for q in qs])
                else:
                    text = str(msg.get("text", ""))
                    self.history.append({"role": "system", "text": msg["history"]} if msg.get("history")
                                        else {"role": "user", "text": text})
                    text = self.ls.visuals.take_notes() + text       # visual picks: short lines, never HTML
                    text = self.take_registry_note() + text          # step agents changed since the last message
                    if self.first:
                        text, self.first = self.context_note() + text, False
                    stream = self.session.stream(text)
                async for ev in stream:
                    await self.meter.feed(ev)
                    if isinstance(ev, Text):
                        self.history.append({"role": "assistant", "text": ev.text})
                        await self.emit({"type": "planner_message", "text": ev.text})
                        await self.emit({"type": "typing", "on": True})
                    elif isinstance(ev, Done):
                        await self.finish(ev.reply)
            except AgentError as e:
                await self.meter.add_reply(e.reply)
                await self.emit({"type": "typing", "on": False})
                await self.emit({"type": "system", "text": f"Planner error: {e.short}"})
                await self.meter.set_status("idle")

    async def finish(self, reply) -> None:
        await self.emit({"type": "typing", "on": False})
        if reply.status == "needs_input":
            self.round_no += 1
            rid = f"{self.ls.id}-r{self.round_no}"
            self.rounds[rid] = list(reply.questions)
            ev = {"type": "question_round", "id": rid, "round": self.round_no, "questions": [
                {"id": q.id, "title": q.question, "body": q.why, "rec": q.recommended, "options": q.options}
                for q in reply.questions]}
            self.history.append({"role": "round", "round": {k: v for k, v in ev.items() if k != "type"}})
            await self.emit(ev)
            await self.meter.set_status("waiting")
        else:
            if reply.status == "error":
                await self.emit({"type": "system", "text": f"Planner stopped: {reply.error}"})
            await self.meter.set_status("idle")
