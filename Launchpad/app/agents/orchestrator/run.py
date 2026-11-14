"""One run of an approved plan: a fresh orchestrator session hands steps, one at a time, to fresh step sessions.

- Orchestrator: tools run_builder + write_report only, both end its turn. Code then runs the step's agent and sends
  ONLY the capped structured result back as the orchestrator's next message
- Each step runs on the agent the plan names (`agent`), else the Builder. A named agent that is missing, broken or
  not a step worker falls back to the Builder; the step report, report.md and the orchestrator's result say so
- Builder: one session per step. Read/Grep/Glob pre-approved; Write/Edit/Bash gated (every call reaches
  permission() in code). Launchpad tools: ask_question, add_to_flight_log, submit_report
- Folder agents (app/crew.py): building ones get exactly the Builder's gated tools, cards, guards and deny list;
  exploring / reviewing ones are read-only (write, edit and shell tools removed and denied, any such request
  refused in code without a card). Same Launchpad tools and hand-off as the Builder
- Edits inside the project and ordinary shell commands run without a card. Writes outside the project (or into
  .launchpad/ or .git/) and deny-listed shell commands become permission cards with a timer (default 180 s):
  unanswered -> denied, the builder is told, the step records an issue
- Autopilot (per session, switchable during a run): every such request is approved without a card and logged
  (assumptions.md, report section "Approved by autopilot", activity auto: true); turning it on approves open cards
- Timed questions auto-answer with the recommendation at the timeout (assumption logged by code); blocking
  questions mark the step blocked and wait for the user
- Code writes steps/step-NN.md, assumptions.md, operations-manual.md and report.md
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
import shlex
from pathlib import Path

from agentlib import AgentError, PermissionDecision, tool
from agentlib.events import Done

from . import crew
from . import plan as plan_mod
from .meter import Meter
from .sessionfiles import inside, one_line

STEP_STATUSES = ("done", "blocked", "failed")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
GATED = ["Write", "Edit", "Bash"]

# Caps on what the orchestrator receives from one builder
CAP_ITEMS, CAP_LIST, CAP_LINE, CAP_NOTES = 8, 5, 160, 300

NUDGE_ORCH = "Call run_builder for the next step that is not done, or write_report if nothing more can run."
NUDGE_BUILDER = "You have not called submit_report yet. Call it now with what you built and status done | blocked | failed."

# --------------------------------------------------------------------------- shell deny list
_GIT_DENY = {"commit": "git commit", "push": "git push"}
_GIT_VALUE_OPTS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_DENY = [
    ("package install", re.compile(
        r"^(?:pip3?|uv\s+pip|(?:python3?|py)(?:\s+-\S+)*\s+-m\s+pip)\s+install\b"
        r"|^(?:npm|pnpm|yarn|bun)\s+(?:install|i|add|ci)\b|^(?:uv|poetry)\s+add\b"
        r"|^(?:conda|mamba|choco|winget|brew|apt|apt-get|scoop|cargo|gem)\s+install\b"
        r"|^install-(?:module|package)\b", re.I)),
]
_DELETE = {"rm", "rmdir", "del", "erase", "rd", "remove-item", "ri", "unlink", "shred"}
_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def deny_match(command: str, project: Path) -> str | None:
    """Category of a deny-listed shell command ('git push', 'package install', 'delete outside the project'), else None."""
    project = Path(project).resolve()
    cwd = project
    for seg in _SPLIT.split(command or ""):
        seg = seg.strip()
        if not seg:
            continue
        try:
            tokens = shlex.split(seg, posix=True)
        except ValueError:
            tokens = seg.split()
        while tokens and (tokens[0] == "sudo" or re.match(r"^\w+=", tokens[0])):
            tokens = tokens[1:]
        if not tokens:
            continue
        head = Path(tokens[0]).name.lower().removesuffix(".exe")
        if head == "git":
            rest = tokens[1:]
            while rest and rest[0].startswith("-"):                 # skip git's global options
                rest = rest[2:] if rest[0] in _GIT_VALUE_OPTS else rest[1:]
            if rest and rest[0] in _GIT_DENY:
                return _GIT_DENY[rest[0]]
            continue
        flat = " ".join([head] + tokens[1:])
        for label, rx in _DENY:
            if rx.search(flat):
                return label
        if head == "cd" and len(tokens) > 1:
            cwd = (cwd / Path(tokens[1]).expanduser()).resolve()
            continue
        if head in _DELETE:
            for arg in tokens[1:]:
                if arg.startswith("-") or (head in ("del", "erase", "rd", "rmdir") and re.fullmatch(r"/\w{1,2}", arg)):
                    continue
                if "$" in arg or "%" in arg:
                    return "delete outside the project"
                target = Path(arg).expanduser()
                target = target if target.is_absolute() else cwd / target
                if not inside(target, project) or target.resolve() == project:   # incl. the project itself
                    return "delete outside the project"
    return None


# --------------------------------------------------------------------------- tool schemas
SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "built": {"type": "array", "items": {
            "type": "object",
            "properties": {"item": {"type": "string", "description": "what it is (file, function, page...)"},
                           "does": {"type": "string", "description": "what it does, one line"}},
            "required": ["item", "does"]}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "issues": {"type": "array", "items": {"type": "string"}},
        "notes_for_orchestrator": {"type": "string", "description": "one or two lines"},
        "routing_notes": {"type": "string", "description": "where navigation went wrong; empty if smooth"},
        "status": {"type": "string", "enum": list(STEP_STATUSES)},
    },
    "required": ["built", "assumptions", "issues", "notes_for_orchestrator", "routing_notes", "status"],
}

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "3-6 lines: what the run achieved"},
        "built": {"type": "array", "items": {"type": "string"}, "description": "what was built, one line each"},
        "issues": {"type": "array", "items": {"type": "string"}, "description": "every issue still open"},
    },
    "required": ["summary", "built", "issues"],
}


def _strs(v, field: str) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"{field} must be a list of strings")
    return [x.strip() for x in v if x.strip()]


def check_report(r: dict) -> dict:
    """Validate a submit_report call -> normalised dict; ValueError (sent back to the builder) if bad."""
    status = r.get("status")
    if status not in STEP_STATUSES:
        raise ValueError(f"status must be one of {', '.join(STEP_STATUSES)}")
    built = []
    for b in r.get("built") or []:
        if not isinstance(b, dict) or not str(b.get("item", "")).strip():
            raise ValueError("each built entry needs item (what it is) and does (what it does)")
        built.append({"item": str(b["item"]).strip(), "does": str(b.get("does", "")).strip()})
    return {"built": built, "assumptions": _strs(r.get("assumptions"), "assumptions"),
            "issues": _strs(r.get("issues"), "issues"),
            "notes_for_orchestrator": str(r.get("notes_for_orchestrator") or "").strip(),
            "routing_notes": str(r.get("routing_notes") or "").strip(), "status": status}


def cap_result(n: int, report: dict, report_path: str) -> dict:
    """What the orchestrator receives from a builder: the report path plus short, length-capped lists."""
    def lines(items, k):
        out = [one_line(x, CAP_LINE) for x in items[:k]]
        if len(items) > k:
            out.append(f"(+{len(items) - k} more in the report)")
        return out
    return {"step": n, "status": report["status"], "agent": report.get("agent") or crew.display("builder"),
            "report_path": report_path,
            "built": lines([f"{b['item']}: {b['does']}" for b in report["built"]], CAP_ITEMS),
            "assumptions": lines(report["assumptions"], CAP_LIST),
            "issues": lines(report["issues"], CAP_LIST),
            "notes": one_line(report["notes_for_orchestrator"], CAP_NOTES)}


# --------------------------------------------------------------------------- tools
def orchestrator_tools(run) -> list:
    """Launchpad-only orchestrator tools bound to a Run (None = for describing only)."""

    @tool(ends_turn=True)
    def run_builder(step: int, brief: str) -> str:
        """Start plan step `step` with a short brief (2-5 lines), on the agent the plan names for it (the Builder
        if none). Steps run one at a time; the step's short result arrives as your next message."""
        return run.request_step(step, brief)

    @tool(schema=REPORT_SCHEMA, ends_turn=True)
    def write_report(**report) -> str:
        """Finish the run with a short summary, what was built and every open issue. The app adds all
        assumptions and per-agent costs and saves report.md."""
        return run.request_report(report)

    return [run_builder, write_report]


def builder_tools(ctx) -> list:
    """Launchpad-only builder tools bound to a StepContext (None = for describing only)."""

    @tool
    async def ask_question(title: str, body: str, recommended: str, options: list[str] | None = None,
                           blocking: bool = False) -> str:
        """Ask the user one question. blocking=false: if nobody answers within a few minutes you get your
        recommended answer back and proceed on it (logged as an assumption). blocking=true only when a wrong
        guess would invalidate the step: the run waits until the user answers."""
        return await ctx.ask(title, body, recommended, options, blocking)

    @tool
    def add_to_flight_log(path: str, why: str, line: int = 0) -> str:
        """Add a file that later steps or sessions will need to the session flight log: path relative to the
        project folder, one line on why it matters, optional line number."""
        return ctx.log_file(path, why, line)

    @tool(schema=SUBMIT_SCHEMA, ends_turn=True)
    def submit_report(**report) -> str:
        """Finish the step: built (each item: what it is, what it does), assumptions, issues, short notes for
        the orchestrator, routing_notes, status done | blocked | failed. One line per entry. Call it last."""
        return ctx.submit(report)

    return [ask_question, add_to_flight_log, submit_report]


# --------------------------------------------------------------------------- one builder step
READ_ONLY_DENIED = ("This agent is read-only here (purpose {purpose}): no writes, edits or shell commands. Do not "
                    "retry; report what you found with submit_report.")

STEP_WORKER_RULES = """--- how this works in Launchpad ---
- You are one step of an approved plan; your working folder is the project folder. Stay on your step.
- Unsure? ask_question (blocking true only if a wrong guess would invalidate the step; otherwise give a recommended answer and you proceed on it if nobody answers).
- add_to_flight_log: a file later steps will need, with one line on why.
- Finish with submit_report: built (or checked / found: item + one line), assumptions, issues, short notes for the orchestrator, routing_notes, status done | blocked | failed."""

READ_ONLY_RULE = "- You are read-only here: no writes, edits or shell commands. Report findings and problems via submit_report."


class StepContext:
    def __init__(self, run: "Run", n: int, worker: dict | None = None, fallback: str | None = None):
        self.run, self.n = run, n
        self.title = run.steps[n]["title"]
        self.worker = worker or {"name": crew.DEFAULT_STEP_AGENT, "display_name": crew.display("builder"),
                                 "purpose": "building", "builtin": True, "role": "builder"}
        self.fallback = fallback                   # why the planned agent was not used (then: the Builder)
        self.meter: Meter | None = None
        self.report: dict | None = None
        self.refused: list[str] = []
        self.error: str | None = None

    @property
    def agent_name(self) -> str:
        return self.worker["display_name"]

    @property
    def read_only(self) -> bool:
        return self.worker["purpose"] in crew.READ_ONLY_PURPOSES

    async def ask(self, title, body, recommended, options, blocking) -> str:
        run = self.run
        timeout = None if blocking else run.settings.question_timeout_s
        if blocking:
            await run.set_step(self.n, "blocked")
        await self.meter.set_status("waiting")
        answer, by, _ = await run.hub.incoming.ask(
            session_id=run.ls.id, kind="question", agent=self.agent_name, agent_id=self.meter.agent_id,
            step=self.n, title=str(title),
            body=str(body), rec=str(recommended), options=[str(o) for o in options or []] or None, timeout_s=timeout)
        await self.meter.set_status("working")
        if blocking:
            await run.set_step(self.n, "in_progress")
        if by == "stopped" or answer is None:
            return "The run was stopped. Call submit_report now with status blocked."
        if by == "timer":
            secs = int(timeout)
            run.note_assumption(f"{one_line(title, 160)} -> {one_line(recommended, 200)} "
                                f"(no answer within {secs}s; the timer used the recommendation)",
                                agent=self.agent_name, step=self.n, source="timer")
            return (f"No answer within {secs}s. Proceed on your recommendation: {recommended}. "
                    "This is logged as an assumption.")
        return f"The user answered: {answer}"

    def log_file(self, path: str, why: str, line: int = 0) -> str:
        ok = self.run.folder.add_flight_log(path, why, line=line or None,
                                            source=f"{self.agent_name} · step {self.n}")
        return "Added to the flight log." if ok else "Not added (outside the project, missing, or already logged)."

    def submit(self, report: dict) -> str:
        self.report = check_report(report)
        return "Report received. Stop now."

    def _classify(self, req) -> tuple[str, str] | None:
        """-> (label, detail) when this request needs the user (or autopilot); None = auto-approved."""
        folder = self.run.folder
        if req.tool in WRITE_TOOLS:
            raw = str(req.input.get("file_path") or req.input.get("notebook_path") or "")
            target = folder.resolve_in_project(raw)
            where = ("outside the project folder" if target is None else
                     "inside .launchpad/ (session records)" if inside(target, folder.root) else
                     "inside .git/" if inside(target, folder.project / ".git") else None)
            return (f"{req.tool} {where}", one_line(raw, 300)) if where else None
        if req.tool == "Bash":
            command = str(req.input.get("command", ""))
            label = deny_match(command, folder.project)
            return (f"Bash · {label}", command) if label else None
        return (req.tool, one_line(json.dumps(req.input, default=str), 300))     # anything unexpected asks

    async def permission(self, req):
        run = self.run
        if self.read_only and req.tool in crew.WRITE_SHELL:
            self.refused.append(f"Read-only agent: {req.tool} refused (no card): "
                                f"{one_line(json.dumps(req.input, default=str), 160)}")
            return PermissionDecision("deny", message=READ_ONLY_DENIED.format(purpose=self.worker["purpose"]))
        need = self._classify(req)
        if need is None:
            return "allow"                                  # edits inside the project, ordinary shell commands
        label, detail = need
        if run.autopilot:
            await self._auto_approved(req, label, detail)
            return "allow"
        if label in run.always:
            return "allow"
        secs = run.settings.permission_timeout_s
        await run.set_step(self.n, "blocked")
        await self.meter.set_status("waiting")
        decision, by, _ = await run.hub.incoming.ask(
            session_id=run.ls.id, kind="permission", agent=self.agent_name, agent_id=self.meter.agent_id,
            step=self.n, title=label, body=detail, options=["allow", "deny", "always"], timeout_s=secs,
            timer_answer="deny", extra={"tool": req.tool, "command": detail})
        await self.meter.set_status("working")
        await run.set_step(self.n, "in_progress")
        if by == "autopilot":
            await self._auto_approved(req, label, detail)
            return "allow"
        if decision == "always":
            run.always.add(label)
        if decision in ("allow", "always"):
            return "allow"
        if by == "timer":
            self.refused.append(f"Permission request denied after {int(secs)}s with no answer: {label}: {one_line(detail, 160)}")
            return PermissionDecision("deny", message=(
                f"Nobody answered this permission request within {int(secs)} seconds, so it was denied. Do not "
                "retry it; work without it if you can and list it under issues in your report."))
        self.refused.append(f"User denied: {label}: {one_line(detail, 160)}")
        return PermissionDecision("deny", message="The user denied this request. Do not retry it; note it in your report.")

    async def _auto_approved(self, req, label: str, detail: str) -> None:
        """Autopilot let a request through: log it (assumptions.md, report section, activity auto: true)."""
        run = self.run
        run.note_assumption(f"Autopilot approved {label}: {one_line(detail, 200)}", agent=self.agent_name,
                            step=self.n, source="autopilot")
        run.autopilot_log.append(f"Step {self.n}: {label}: {one_line(detail, 200)}")
        if req.call_id and req.call_id in self.meter.open_calls:
            self.meter.open_calls[req.call_id]["auto"] = True


# --------------------------------------------------------------------------- the run
class Run:
    def __init__(self, ls):
        self.ls, self.hub, self.folder = ls, ls.hub, ls.folder
        self.settings = ls.hub.settings
        self.plan_text = self.folder.read(self.folder.plan)
        self.plan = plan_mod.parse(self.plan_text)
        reg = crew.registry(self.folder.project)
        self.steps = {s["n"]: {"n": s["n"], "title": s["title"], "after": s["after"], "status": "todo",
                               **crew.step_fields(s.get("agent"), self.folder.project, reg)}
                      for s in self.plan["steps"]}
        self.reports: dict[int, str] = {}          # n -> project-relative report path
        self.results: dict[int, dict] = {}         # n -> full builder report
        self.pending: tuple[int, str] | None = None
        self.final: dict | None = None
        self.always: set[str] = set()
        self.autopilot_log: list[str] = []         # requests autopilot let through (report section)
        self.assumptions: list[str] = []
        self.meters: list[Meter] = []
        self.builder_runs = 0
        self.status = "running"
        self.report_markdown = ""
        self.total_cost = 0.0                      # session total: orchestrator + builders + astronauts
        self.planner_cost = 0.0                    # shown separately, never in the total
        self.task: asyncio.Task | None = None

    @property
    def autopilot(self) -> bool:
        """Read live on every request: the switch can change while the run is in flight."""
        return self.ls.autopilot

    # ---------------------------------------------------------------- tool entry points
    def request_step(self, step: int, brief: str) -> str:
        if self.pending is not None:
            raise ValueError("one step at a time: a builder is already starting")
        s = self.steps.get(int(step))
        if s is None:
            raise ValueError(f"no step {step}; steps are 1-{len(self.steps)}")
        if s["status"] == "done":
            raise ValueError(f"step {step} is already done")
        waiting = [a for a in s["after"] if self.steps[a]["status"] != "done"]
        if waiting:
            raise ValueError(f"step {step} needs step(s) {', '.join(map(str, waiting))} done first")
        if self.builder_runs >= len(self.steps) * self.settings.builder_runs_per_step:
            raise ValueError("builder limit for this run reached; call write_report")
        self.pending = (int(step), str(brief))
        return f"Step {step} started. Its result arrives as your next message."

    def request_report(self, report: dict) -> str:
        self.final = {"summary": str(report.get("summary") or "").strip(),
                      "built": _strs(report.get("built"), "built"), "issues": _strs(report.get("issues"), "issues")}
        return "Report received. The run is finishing."

    def note_assumption(self, text: str, *, agent: str, step: int | None, source: str) -> None:
        self.assumptions.append(self.folder.add_assumption(text, agent=agent, step=step, source=source))

    # ---------------------------------------------------------------- state + events
    async def set_step(self, n: int, status: str, *, built: list[str] | None = None,
                       report_path: str | None = None) -> None:
        self.steps[n]["status"] = status
        try:
            text = plan_mod.set_status(self.folder.read(self.folder.plan), step=n, step_status=status)
            self.folder.write_plan(text)
        except plan_mod.PlanError:
            pass
        ev = {"type": "step_update", "session_id": self.ls.id, "n": n, "status": status,
              **self.step_agent(n)}
        if built is not None:
            ev["built"] = built
        if report_path is not None:
            ev["report_path"] = report_path
        await self.hub.emit(ev)

    def step_agent(self, n: int) -> dict:
        """agent / agent_display (+ agent_fallback) of step n for UI events."""
        s = self.steps[n]
        out = {"agent": s.get("agent"), "agent_display": s.get("agent_display") or crew.display("builder"),
               "agent_purpose": s.get("agent_purpose") or "building"}
        if s.get("agent_fallback"):
            out["agent_fallback"] = True
        return out

    def steps_payload(self) -> list[dict]:
        """run_started steps: [{n, title, status, agent, agent_display, agent_fallback?}]."""
        return [{"n": s["n"], "title": s["title"], "status": s["status"], **self.step_agent(s["n"])}
                for s in self.steps.values()]

    async def _turn(self, s, message: str, meter: Meter):
        reply = None
        async for ev in s.stream(message):
            await meter.feed(ev)
            if isinstance(ev, Done):
                reply = ev.reply
        return reply

    # ---------------------------------------------------------------- messages
    def kickoff(self) -> str:
        f = self.folder
        steps = "\n".join(f"{s['n']}. {s['title']}" + (f" (after {', '.join(map(str, s['after']))})" if s["after"] else "")
                          + (f" [agent: {s['agent_display']}]" if s.get("agent") and not s.get("agent_fallback") else "")
                          for s in self.steps.values())
        log = f.read(f.flight_log).strip() or "(empty)"
        return (f"Run the approved plan \"{self.plan['name']}\".\n"
                f"Plan file: {f.rel(f.plan)} · flight log: {f.rel(f.flight_log)} · step reports: {f.rel(f.steps)}/\n\n"
                f"Steps:\n{steps}\n\n--- plan.md ---\n{self.plan_text.strip()}\n\n--- flight log ---\n{log}\n\n"
                "Start with run_builder.")

    def builder_message(self, n: int, brief: str, ctx: "StepContext | None" = None) -> str:
        f = self.folder
        earlier = [self.reports[k] for k in sorted(self.reports) if k != n]
        log = f.read(f.flight_log).strip() or "(empty)"
        folder_agent = ctx is not None and not ctx.worker.get("builtin")
        rules = ""
        if folder_agent:                            # the agent's own file knows nothing about Launchpad's hand-off
            rules = STEP_WORKER_RULES + ("\n" + READ_ONLY_RULE if ctx.read_only else "") + "\n\n"
        lead = "Work on" if folder_agent else "Build"
        return (f"{lead} step {n} of the plan \"{self.plan['name']}\". Your working folder is the project folder; "
                "work only inside it.\n"
                f"Plan (only if you need the bigger picture): {f.rel(f.plan)}\n"
                f"Earlier step reports: {', '.join(earlier) if earlier else 'none'}\n\n"
                f"--- brief from the orchestrator ---\n{brief.strip()}\n\n"
                f"--- your step ---\n{plan_mod.step_text(self.plan_text, n)}\n\n"
                f"--- flight log (files already known to matter) ---\n{log}\n\n"
                f"{rules}Finish with submit_report.")

    @staticmethod
    def result_message(capped: dict) -> str:
        return (f"Step {capped['step']} result:\n{json.dumps(capped, ensure_ascii=False, indent=1)}\n"
                "Next: run_builder for the next step, or write_report when nothing more can run.")

    # ---------------------------------------------------------------- builder step
    def _load_worker(self, ctx: StepContext):
        """The step's agent: the Builder as always, or a folder agent with purpose-based permissions."""
        common = dict(engine=self.settings.engine, project=self.folder.project, tools=builder_tools(ctx),
                      on_permission=ctx.permission, timeout_s=self.settings.builder_turn_timeout_s,
                      env=dict(crew.WAITING_ENV))
        if ctx.worker.get("builtin"):
            return crew.load("builder", gated_tools=list(GATED),
                             engine_prompt=True,   # Claude Code's own prompt + the file text; still lean (no settings)
                             **common)
        return crew.load_step_worker(ctx.worker, **common)

    async def run_step(self, n: int, brief: str) -> dict:
        self.builder_runs += 1
        worker, fallback = crew.resolve_step_agent(self.steps[n].get("agent"), self.folder.project)
        ctx = StepContext(self, n, worker, fallback)
        try:
            agent = self._load_worker(ctx)
        except Exception as e:  # noqa: BLE001 -- a folder file the loader refuses: run the Builder instead
            if ctx.worker.get("builtin"):
                raise
            ctx = StepContext(self, n, None, f"agent '{worker['name']}' could not be loaded ({one_line(str(e), 160)})")
            agent = self._load_worker(ctx)
        self.steps[n]["agent_display"] = ctx.agent_name
        self.steps[n]["agent_purpose"] = ctx.worker["purpose"]
        self.steps[n]["agent_fallback"] = bool(ctx.fallback)
        await self.hub.count_use(ctx.worker["name"])
        await self.set_step(n, "in_progress")
        meter = ctx.meter = Meter(self.hub, session_id=self.ls.id, role="builder", name=ctx.agent_name, step=n)
        self.meters.append(meter)
        await meter.set_status("working")
        try:
            async with agent.session() as s:
                await self._turn(s, self.builder_message(n, brief, ctx), meter)
                if ctx.report is None:
                    await self._turn(s, NUDGE_BUILDER, meter)
        except AgentError as e:
            await meter.add_reply(e.reply)
            ctx.error = e.short
        report = ctx.report or {
            "built": [], "assumptions": [], "notes_for_orchestrator": "", "routing_notes": "", "status": "failed",
            "issues": [f"Builder ended without submit_report{': ' + ctx.error if ctx.error else ''}"]}
        fallback_issue = ([f"Plan named another agent but {ctx.fallback}; the step ran on the "
                           f"{crew.display('builder')} instead."] if ctx.fallback else [])
        report["issues"] = fallback_issue + list(report["issues"]) + ctx.refused
        report["agent"] = ctx.agent_name
        path = self.folder.write_step_report(n, ctx.title, report, agent=meter.name, tool_calls=meter.tool_calls,
                                             cost_usd=meter.cost_usd)
        rel = self.folder.rel(path)
        self.reports[n], self.results[n] = rel, report
        for a in report["assumptions"]:
            self.note_assumption(a, agent=meter.name, step=n, source="builder report")
        self.folder.add_operations(agent=meter.name, role="builder", step=n, notes=report["routing_notes"],
                                   tool_calls=meter.tool_calls, cost_usd=meter.cost_usd)
        await self.set_step(n, report["status"], built=[one_line(f"{b['item']}: {b['does']}", CAP_LINE)
                                                        for b in report["built"]], report_path=rel)
        await meter.set_status("done")
        return cap_result(n, report, rel)

    # ---------------------------------------------------------------- the loop
    async def go(self) -> None:
        issue = None
        try:
            status = await self._loop()
        except asyncio.CancelledError:
            status = "stopped"
        except AgentError as e:
            status, issue = "failed", f"Orchestrator error: {e.short}"
        except Exception as e:  # noqa: BLE001 -- a bug must still end the run with a report
            import traceback
            traceback.print_exc()
            status, issue = "failed", f"Launchpad error: {type(e).__name__}: {e}"
        await self._finish(status, issue)

    async def _loop(self) -> str:
        agent = crew.load("orchestrator", engine=self.settings.engine, project=self.folder.project,
                          tools=orchestrator_tools(self))
        await self.hub.count_use(agent.name)
        meter = Meter(self.hub, session_id=self.ls.id, role="orchestrator", name=crew.display("orchestrator"))
        self.meters.insert(0, meter)
        await meter.set_status("working")
        try:
            async with agent.session() as s:
                message, nudges = self.kickoff(), 0
                while True:
                    self.pending = None
                    reply = await self._turn(s, message, meter)
                    if self.final is not None:
                        return "done"
                    if self.pending is not None:
                        n, brief = self.pending
                        message, nudges = self.result_message(await self.run_step(n, brief)), 0
                        continue
                    nudges += 1
                    if nudges > self.settings.orchestrator_nudges or (reply is not None and reply.status == "error"):
                        self.final = {"summary": "", "built": [],
                                      "issues": ["The orchestrator stopped without writing a report."]}
                        return "failed"
                    message = NUDGE_ORCH
        finally:
            await meter.set_status("done")

    async def _finish(self, status: str, issue: str | None) -> None:
        for n, s in self.steps.items():
            if s["status"] in ("in_progress", "blocked"):
                await self.set_step(n, "failed" if status != "stopped" else "todo")
        for m in self.meters:
            if m.status != "done":
                await m.set_status("done")
        self.status = status
        self.report_markdown = self.render_report(status, issue)
        path = self.folder.write_report(self.report_markdown)
        await self.hub.emit({"type": "run_finished", "session_id": self.ls.id, "status": status,
                             "report_path": self.folder.rel(path), "markdown": self.report_markdown,
                             "total_cost_usd": round(self.total_cost, 6),
                             "planner_cost_usd": round(self.planner_cost, 6)})
        await self.hub.emit({"type": "plan_meta", "session_id": self.ls.id, "name": self.plan["name"],
                             "mode": "Run", "status": {"done": "Done", "stopped": "Stopped"}.get(status, "Failed")})

    # ---------------------------------------------------------------- report.md
    def render_report(self, status: str, issue: str | None) -> str:
        final = self.final or {"summary": "", "built": [], "issues": []}
        f = self.folder
        out = [f"# Report: {self.plan['name']}", "",
               f"Session {self.ls.id} · status **{status}** · {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
               "## Summary", final["summary"] or "(The run ended without an orchestrator summary.)", "",
               "## Built"]
        out += [f"- {b}" for b in final["built"]] or ["- (none listed by the orchestrator)"]
        out += ["", "### Steps", "", "| Step | Title | Agent | Status | Report |", "|---|---|---|---|---|"]
        for n, s in self.steps.items():
            link = f"[step-{n:02d}.md](steps/step-{n:02d}.md)" if n in self.reports else "-"
            who = s.get("agent_display") or crew.display("builder")
            if s.get("agent_fallback"):
                who += f" (fallback: {s.get('agent')} not available)"
            out.append(f"| {n} | {s['title']} | {who} | {s['status']} | {link} |")
        out += ["", "## Assumptions"]
        logged = [ln for ln in f.read(f.assumptions).splitlines() if ln.startswith("- ")]
        out += [ln for ln in logged if not ln.endswith("_(autopilot)_")] or ["- none"]
        if self.autopilot_log:
            out += ["", "## Approved by autopilot (no card shown)"] + [f"- {x}" for x in self.autopilot_log]
        issues = list(final["issues"]) + ([issue] if issue else [])
        for n in sorted(self.results):
            issues += [f"Step {n}: {i}" for i in self.results[n]["issues"]]
        out += ["", "## Issues"] + ([f"- {one_line(i, 600)}" for i in issues] or ["- none"])
        out += ["", "## Costs per agent", "",
                "| Agent | Role | Step | Input (uncached) | Output | Cache read | Cache write | Tool calls | Cost (USD) |",
                "|---|---|---|---|---|---|---|---|---|"]
        session_meters = [m for m in self.hub.meters if m.session_id == self.ls.id]
        run_meters = [m for m in session_meters if m.role != "planner"]
        for m in run_meters:
            u = m.usage
            out.append(f"| {m.name} | {m.role} | {m.step or '-'} | {u.input_tokens} | {u.output_tokens} | "
                       f"{u.cache_read_tokens} | {u.cache_write_tokens} | {m.tool_calls} | {m.cost_usd:.4f} |")
        self.total_cost, self.planner_cost = self.hub.session_costs(self.ls.id)
        out += ["", f"Session total (orchestrator, step agents, explorer, visualizer): **${self.total_cost:.4f}**",
                f"Planner (separate, not in the session total): ${self.planner_cost:.4f}", ""]
        return "\n".join(out)
