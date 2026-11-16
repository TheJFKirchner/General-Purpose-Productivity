"""The planner chat (Planner): one agentlib session per Launchpad session.

- Tools: ask_user (file) + explore, read_markdown, write_plan, edit_plan, show_visuals (Launchpad-only, handed over
  at load time)
- Step agents: the registry's step workers (name, purpose, description; app/agents/crew.py) reach the planner in its first
  message and again, as one short block before the user's next message, when the folder's agents change. The system
  prompt and the cached tool list never change for this. The planner may name an agent per step (write_plan /
  edit_plan `agent`); it never starts one: the orchestrator does, after approval
- Skills: the session's skills (app/skills.py, found in its folders) reach the planner in its first message; a step
  may name some (`skills`), and that step's worker gets them on top of its own allowlist. The planner itself runs
  with its own allowlist (default all) through agentlib skills
- Folders: the primary folder is the project; the additional folders are listed in the first message and
  read_markdown may open .md files in them (absolute paths)
- Visual picks (app/agents/visualizer/visuals.py) reach the planner as short lines prefixed to the user's next message
- No shell, no write/edit, no general file reading: read_markdown only opens .md files inside the project
- ask_user questions -> question_round cards; round_answer -> session.answer()
- write_plan -> validated plan.md draft + plan_draft event; only the user's approval starts a run
- Harness and model (choices.py, the picker): loaded on the chosen harness's engine and start model; until the first
  message the session follows settings changes (configure); afterwards only promotion moves it. Auto-promote off =
  no promote_planner tool, and promote(by="criteria") refuses
"""
from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from agentlib import AgentError, tool
from agentlib.events import Done, Text

from ... import skills as skills_mod
from ...meter import Meter
from ...sessionfiles import inside

from .. import crew
from . import choices
from ..explorer import astronaut
from ..visualizer import libraries

READ_LIMIT = 60_000          # characters returned by read_markdown
CRITERIA_FILE = Path(__file__).resolve().parent / "promotion.md"     # app/agents/planner/promotion.md

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
            "skills": {"type": "array", "items": {"type": "string"},
                       "description": "set_step / add_step: skill names for the step's worker; [] = none"},
            "agent": {"type": "string", "description": "set_step / add_step: step agent name; \"\" = the Builder"},
            "after": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["op"]}}},
    "required": ["edits"],
}


# show_visuals: fixed text (the cached tool list never changes in a session); the folder's libraries reach the
# planner in its first message (libraries.libraries_note)
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
                    "skills": {"type": "array", "items": {"type": "string"},
                               "description": "optional skill names from Launchpad's list; the step's worker "
                                              "gets them"},
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


def read_markdown_file(project: Path, path: str, limit: int = READ_LIMIT, extra: list[Path] = ()) -> str:
    """The planner's only file reader: markdown files inside the project folder (or the session's additional
    folders, by absolute path). ValueError otherwise."""
    project = Path(project).resolve()
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("give a path relative to the project folder")
    cand = Path(raw)
    if not cand.is_absolute():
        cand = project / cand
    if not any(inside(cand, f) for f in [project, *extra]):
        raise ValueError("only files inside the project folder (or an additional folder) can be read")
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
        return read_markdown_file(chat.ls.folder.project, path, extra=chat.ls.folder.extra)

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
        remove_step, move_step; set_step / add_step may set the step's agent and skills. Edits apply in order; step numbers refer to the plan at that moment. The plan is
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
        self.configure()
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

    def configure(self) -> None:
        """(Re)load the planner agent from the current settings: harness (-> engine, choices.py), start / top model,
        auto-promote. Called at creation, and again while nobody has written to the session yet (configurable)."""
        settings = self.ls.hub.settings
        self.start_model, self.top_model = planner_models(settings)
        self.window = int(settings.promotion_window_turns)
        self.harness = choices.chosen_harness(settings)
        self.engine = choices.planner_engine(settings)
        self.auto_promote = bool(getattr(settings, "planner_auto_promote", True))
        # the promote tool is offered only when the planner may promote itself (it never changes mid-session)
        criteria = (promotion_criteria(settings)[0]
                    if self.start_model != self.top_model and self.auto_promote else None)
        self.agent = crew.load("planner", engine=self.engine, project=self.ls.folder.project,
                               model=self.start_model, tools=planner_tools(self, criteria=criteria),
                               env=dict(crew.WAITING_ENV),
                               **crew.session_kw(self.ls, crew.builtin_name("planner"), role="planner"))
        self.model = self.start_model

    @property
    def started(self) -> bool:
        """Someone wrote to this planner: its harness and start model are fixed from now on."""
        return self.session is not None or self.turns > 0 or self.lock.locked()

    def can_promote(self) -> bool:
        return self.start_model != self.top_model and not self.promoted

    def switchable_to(self) -> list[str]:
        """Picker options (choices.option_id) this session can move to right now: any available one before the first
        message; afterwards only the top model of its own harness (= promotion by hand)."""
        if not self.started:
            return [o["id"] for o in choices.options(self.ls.hub.settings) if o["available"]]
        return [choices.option_id(self.harness, self.top_model)] if self.can_promote() else []

    async def emit(self, ev: dict) -> None:
        ev.setdefault("session_id", self.ls.id)
        await self.ls.hub.emit(ev)

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    def model_event(self) -> dict:
        return {"type": "planner_model", "session_id": self.ls.id, "model": self.model, "promoted": self.promoted,
                "reason": self.promote_reason, "by": self.promoted_by,
                "harness": self.harness, "start_model": self.start_model, "top_model": self.top_model,
                "label": choices.label(self.harness, self.model), "option_id": choices.option_id(self.harness, self.model),
                "auto_promote": self.auto_promote and self.start_model != self.top_model, "started": self.started,
                "switchable_to": self.switchable_to()}

    async def promote(self, *, by: str, reason: str | None = None) -> str:
        """Move to the top model for the rest of the session (never twice, never down). by: criteria | user.
        The conversation carries over as is (same session, agentlib set_model); mid-turn, the next model call
        already uses the new model. With auto-promote off (now, in settings) the planner never promotes itself."""
        if self.start_model == self.top_model:
            raise ValueError("promotion is off for this session (the planner already runs on its only model)")
        if self.promoted:
            raise ValueError(f"already promoted to {self.top_model}; carry on")
        if by == "criteria" and not (self.auto_promote and getattr(self.ls.hub.settings, "planner_auto_promote", True)):
            raise ValueError("automatic promotion is off; carry on with the current model")
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
        if f.extra:
            lines.append("Additional folders (steps may work there too; give absolute paths): "
                         + ", ".join(str(e) for e in f.extra))
        lines.append(crew.registry_note(f.project))
        lines.append(skills_mod.note(getattr(self.ls, "skills", [])))
        lines.append(libraries.libraries_note(f.project))
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
                await self.ls.hub.emit(self.model_event())          # started: the picker's choices narrow
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
