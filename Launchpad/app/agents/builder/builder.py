"""One plan step on its step agent: the Builder (or a folder agent), its Launchpad tools, permission checks and
its report back to the orchestrator.

- One fresh session per step. Read/Grep/Glob pre-approved; Write/Edit/Bash gated (every call reaches
  StepContext.permission in code). Launchpad tools: ask_question, add_to_flight_log, submit_report
- Each step runs on the agent the plan names (`agent`), else the Builder. A named agent that is missing, broken or
  not a step worker falls back to the Builder; the step report, report.md and the orchestrator's result say so
- Folder agents (app/agents/crew.py): building ones get exactly the Builder's gated tools, cards, guards and deny
  list; exploring / reviewing ones are read-only (write, edit and shell tools removed and denied, any such request
  refused in code without a card). Same Launchpad tools and hand-off as the Builder
- Edits inside the project and ordinary shell commands run without a card. Writes outside the project (or into
  .launchpad/ or .git/) and deny-listed shell commands (deny.py) become permission cards with a timer (default
  180 s): unanswered -> denied, the builder is told, the step records an issue. The session's additional folders
  count as inside the project (their .launchpad/ and .git/ ask too)
- Skills: the worker is loaded with its own allowlist plus the step's `skills` (crew.session_kw; app/skills.py)
- Autopilot (per session, switchable during a run): every such request is approved without a card and logged
  (assumptions.md, report section "Approved by autopilot", activity auto: true); turning it on approves open cards
- Timed questions auto-answer with the recommendation at the timeout (assumption logged by code); blocking
  questions mark the step blocked and wait for the user. ask_question needs a non-empty recommended answer and a
  reason (a tool error otherwise; the same tool serves folder agents). With the session's Auto answers switch on,
  EVERY question (blocking too) is answered at once with the worker's own recommendation, the step never shows
  blocked (app/incoming.py). Every answered or timed-out question is saved as a file in
  <session folder>/questions/ (sessionfiles.add_question)
- The orchestrator receives only cap_result(): the report path plus short, length-capped lists
- Undefined roles: a step with a `role`, or naming an agent that does not exist, that ran on the Builder is recorded
  in the per-user tally when it ends (hub.record_role_use: outcome, questions asked, assumptions logged, questions
  timed out, the step text as a sample). A step run by a registered agent is not recorded
- `run` below is the orchestrator's Run (app/agents/orchestrator/run.py): settings, folder, plan, hub, steps
"""
from __future__ import annotations

import datetime as dt
import json

from agentlib import AgentError, PermissionDecision, tool

from ... import plan as plan_mod
from ...meter import Meter
from ...sessionfiles import inside, one_line
from .. import crew
from .deny import deny_match

STEP_STATUSES = ("done", "blocked", "failed")

# Caps on what the orchestrator receives from one builder
CAP_ITEMS, CAP_LIST, CAP_LINE, CAP_NOTES = 8, 5, 160, 300

NUDGE_BUILDER = "You have not called submit_report yet. Call it now with what you built and status done | blocked | failed."

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


def strs(v, field: str) -> list[str]:
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
    return {"built": built, "assumptions": strs(r.get("assumptions"), "assumptions"),
            "issues": strs(r.get("issues"), "issues"),
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


def builder_tools(ctx) -> list:
    """Launchpad-only builder tools bound to a StepContext (None = for describing only)."""

    @tool
    async def ask_question(title: str, body: str, recommended: str, options: list[str] | None = None,
                           blocking: bool = False) -> str:
        """Ask the user one question. recommended (your own best answer) and body (why you ask) are always
        required, never empty. blocking=false: if nobody answers within a few minutes you get your
        recommended answer back and proceed on it (logged as an assumption). blocking=true only when a wrong
        guess would invalidate the step: the run waits until the user answers. With the user's Auto answers
        switch on, your recommended answer is taken as the answer at once."""
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


READ_ONLY_DENIED = ("This agent is read-only here (purpose {purpose}): no writes, edits or shell commands. Do not "
                    "retry; report what you found with submit_report.")

STEP_WORKER_RULES = """--- how this works in Launchpad ---
- You are one step of an approved plan; your working folder is the project folder. Stay on your step.
- Unsure? ask_question (blocking true only if a wrong guess would invalidate the step; otherwise give a recommended answer and you proceed on it if nobody answers).
- add_to_flight_log: a file later steps will need, with one line on why.
- Finish with submit_report: built (or checked / found: item + one line), assumptions, issues, short notes for the orchestrator, routing_notes, status done | blocked | failed."""

READ_ONLY_RULE = "- You are read-only here: no writes, edits or shell commands. Report findings and problems via submit_report."


class StepContext:
    """One step's state while its agent runs: the Launchpad tools' callbacks, permission checks, its report."""

    def __init__(self, run, n: int, worker: dict | None = None, fallback: str | None = None):
        self.run, self.n = run, n
        self.title = run.steps[n]["title"]
        self.worker = worker or {"name": crew.DEFAULT_STEP_AGENT, "display_name": crew.display("builder"),
                                 "purpose": "building", "builtin": True, "role": "builder"}
        self.fallback = fallback                   # why the planned agent was not used (then: the Builder)
        self.meter: Meter | None = None
        self.report: dict | None = None
        self.refused: list[str] = []
        self.error: str | None = None
        self.questions = 0                         # questions the worker asked (tally evidence)
        self.timed_out = 0                         # of those, answered by the timer

    @property
    def agent_name(self) -> str:
        return self.worker["display_name"]

    @property
    def read_only(self) -> bool:
        return self.worker["purpose"] in crew.READ_ONLY_PURPOSES

    async def ask(self, title, body, recommended, options, blocking) -> str:
        run = self.run
        if not str(recommended or "").strip():
            raise ValueError("recommended is required: give your own best answer (not empty) and call ask_question again")
        if not str(body or "").strip():
            raise ValueError("body is required: say why you are asking (not empty) and call ask_question again")
        self.questions += 1
        timeout = None if blocking else run.settings.question_timeout_s
        auto = run.hub.incoming.auto_applies(run.ls.id)     # Auto answers on: answered at once, the step never shows blocked
        flipped = blocking and not auto
        if flipped:
            await run.set_step(self.n, "blocked")
        if not auto:
            await self.meter.set_status("waiting")
        asked_at = dt.datetime.now()
        answer, by, _ = await run.hub.incoming.ask(
            session_id=run.ls.id, kind="question", agent=self.agent_name, agent_id=self.meter.agent_id,
            step=self.n, title=str(title), body=str(body), rec=str(recommended),
            options=[str(o) for o in options or []] or None, timeout_s=timeout, auto_ok=True)
        if not auto:
            await self.meter.set_status("working")
        if flipped:
            await run.set_step(self.n, "in_progress")
        if by == "stopped" or answer is None:
            return "The run was stopped. Call submit_report now with status blocked."
        assumed = ""
        if by == "timer":
            self.timed_out += 1
            secs = int(timeout)
            assumed = (f"{one_line(title, 160)} -> {one_line(recommended, 200)} "
                       f"(no answer within {secs}s; the timer used the recommendation)")
            run.note_assumption(assumed, agent=self.agent_name, step=self.n, source="timer")
        try:                                               # one file per question in <session folder>/questions/
            run.folder.add_question(
                title=str(title), asked_by="Builder", agent=self.agent_name, asked_at=asked_at, run=run.ls.run_count,
                run_name=run.ls.hub.run_name(run.ls.id), step=self.n, options=[str(o) for o in options or []], answer=str(answer), how=by, reason=str(body),
                recommended=str(recommended), assumption=assumed)
        except OSError:
            pass                                           # a file that cannot be written must not stop the step
        if by == "auto":
            return f"Auto answers is on: your recommendation was taken as the answer: {answer}"
        if by == "timer":
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
        if req.tool in crew.WRITE_TOOLS:
            raw = str(req.input.get("file_path") or req.input.get("notebook_path") or "")
            target = folder.resolve_in_project(raw)
            where = ("outside the project folder" if target is None else
                     "inside .launchpad/ (session records)" if any(inside(target, f / ".launchpad")
                                                                   for f in folder.folders) else
                     "inside .git/" if any(inside(target, f / ".git") for f in folder.folders) else None)
            return (f"{req.tool} {where}", one_line(raw, 300)) if where else None
        if req.tool == "Bash":
            command = str(req.input.get("command", ""))
            label = deny_match(command, folder.project, folder.extra)
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


# --------------------------------------------------------------------------- one step
def builder_message(run, n: int, brief: str, ctx: StepContext | None = None) -> str:
    """The step agent's first message: brief, its step from plan.md, the flight log (+ Launchpad's hand-off rules
    for a folder agent)."""
    f = run.folder
    earlier = [run.reports[k] for k in sorted(run.reports) if k != n]
    log = f.read(f.flight_log).strip() or "(empty)"
    folder_agent = ctx is not None and not ctx.worker.get("builtin")
    rules = ""
    if folder_agent:                        # the agent's own file knows nothing about Launchpad's hand-off
        rules = STEP_WORKER_RULES + ("\n" + READ_ONLY_RULE if ctx.read_only else "") + "\n\n"
    lead = "Work on" if folder_agent else "Build"
    extra = (f"Additional folders (also yours to work in; absolute paths): {', '.join(str(e) for e in f.extra)}\n"
             if f.extra else "")
    step_skills = list((run.steps.get(n) or {}).get("skills") or [])
    skills_line = (f"Skills for this step (see your Skills section; read each SKILL.md first): {', '.join(step_skills)}\n"
                   if step_skills else "")
    return (f"{lead} step {n} of the plan \"{run.plan['name']}\". Your working folder is the project folder; "
            "work only inside it.\n"
            f"{extra}{skills_line}"
            f"Plan (only if you need the bigger picture): {f.rel(f.plan)}\n"
            f"Earlier step reports: {', '.join(earlier) if earlier else 'none'}\n\n"
            f"--- brief from the orchestrator ---\n{brief.strip()}\n\n"
            f"--- your step ---\n{plan_mod.step_text(run.plan_text, n)}\n\n"
            f"--- flight log (files already known to matter) ---\n{log}\n\n"
            f"{rules}Finish with submit_report.")


def load_worker(run, ctx: StepContext):
    """The step's agent: the Builder as always, or a folder agent with purpose-based permissions."""
    common = dict(engine=run.settings.engine, project=run.folder.project, tools=builder_tools(ctx),
                  on_permission=ctx.permission, timeout_s=run.settings.builder_turn_timeout_s,
                  env=dict(crew.WAITING_ENV),
                  **crew.session_kw(run.ls, ctx.worker["name"], role=ctx.worker.get("role"),
                                    step_skills=run.step_skills(ctx.n)))

    if ctx.worker.get("builtin"):
        return crew.load("builder", gated_tools=list(crew.BUILDER_GATED),
                         engine_prompt=True,   # the harness's own prompt + the file text; still lean (no settings)
                         **common)
    return crew.load_step_worker(ctx.worker, **common)


async def run_step(run, n: int, brief: str) -> dict:
    """Run plan step n on its agent (the Builder, or the folder agent the plan names) -> the capped result the
    orchestrator receives. Writes the step report, assumptions and operations notes; emits step updates."""
    run.builder_runs += 1
    named = run.steps[n].get("agent")
    worker, fallback = crew.resolve_step_agent(named, run.folder.project)
    # tally (app/tally.py): the step's role, or the name of an agent that does not exist; never a registered agent
    role = run.steps[n].get("role") or (named if named and not crew.agent_exists(named, run.folder.project) else None)
    assumptions_before = len(run.assumptions)
    ctx = StepContext(run, n, worker, fallback)
    try:
        agent = load_worker(run, ctx)
    except Exception as e:  # noqa: BLE001 -- a folder file the loader refuses: run the Builder instead
        if ctx.worker.get("builtin"):
            raise
        ctx = StepContext(run, n, None, f"agent '{worker['name']}' could not be loaded ({one_line(str(e), 160)})")
        agent = load_worker(run, ctx)
    run.steps[n]["agent_display"] = ctx.agent_name
    run.steps[n]["agent_purpose"] = ctx.worker["purpose"]
    run.steps[n]["agent_fallback"] = bool(ctx.fallback)
    await run.hub.count_use(ctx.worker["name"])
    await run.set_step(n, "in_progress")
    meter = ctx.meter = Meter(run.hub, session_id=run.ls.id, role="builder", name=ctx.agent_name, step=n)
    run.meters.append(meter)
    await meter.set_status("working")
    try:
        async with agent.session() as s:
            await run._turn(s, builder_message(run, n, brief, ctx), meter)
            if ctx.report is None:
                await run._turn(s, NUDGE_BUILDER, meter)
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
    path = run.folder.write_step_report(n, ctx.title, report, agent=meter.name, tool_calls=meter.tool_calls,
                                        cost_usd=meter.cost_usd)
    rel = run.folder.rel(path)
    run.reports[n], run.results[n] = rel, report
    for a in report["assumptions"]:
        run.note_assumption(a, agent=meter.name, step=n, source="builder report")
    run.folder.add_operations(agent=meter.name, role="builder", step=n, notes=report["routing_notes"],
                              tool_calls=meter.tool_calls, cost_usd=meter.cost_usd)
    await run.set_step(n, report["status"], built=[one_line(f"{b['item']}: {b['does']}", CAP_LINE)
                                                   for b in report["built"]], report_path=rel)
    if role and ctx.worker.get("builtin"):
        f = run.folder
        await run.hub.record_role_use(role, sample=plan_mod.step_text(run.plan_text, n), use={
            "dir_id": run.ls.dir_id, "folder": f.project.name, "project": str(f.project), "extra_projects": [str(p) for p in f.extra], "session_id": run.ls.id,
            "run": run.ls.run_count, "step": n, "title": ctx.title, "skills": run.step_skills(n),
            "outcome": report["status"], "questions": ctx.questions,
            "assumptions": len(run.assumptions) - assumptions_before, "timed_out": ctx.timed_out,
            "named_agent": not run.steps[n].get("role")})
    await meter.set_status("done")
    return cap_result(n, report, rel)
