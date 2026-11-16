"""One run of an approved plan: a fresh orchestrator session hands steps, one at a time, to fresh step sessions.

- Orchestrator: tools run_builder + write_report only, both end its turn. Code then runs the step's agent
  (app/agents/builder/builder.py run_step) and sends ONLY the capped structured result back as the orchestrator's
  next message
- Run holds the run's state (steps, reports, assumptions, autopilot log, meters) and emits step_update /
  run_finished / plan_meta; step agents read and update it through their StepContext
- Code writes steps/step-NN.md, assumptions.md, operations-manual.md and report.md (report.py)
- A step's `skills` (plan.md) go to its worker on top of the worker's allowlist (step_skills; builder.load_worker);
  names not found in the session's folders are dropped there
"""
from __future__ import annotations

import asyncio
import json

from agentlib import AgentError, tool
from agentlib.events import Done

from ... import plan as plan_mod
from ...meter import Meter
from .. import crew
from ..builder.builder import run_step, strs
from .report import render_report

NUDGE_ORCH = "Call run_builder for the next step that is not done, or write_report if nothing more can run."

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "3-6 lines: what the run achieved"},
        "built": {"type": "array", "items": {"type": "string"}, "description": "what was built, one line each"},
        "issues": {"type": "array", "items": {"type": "string"}, "description": "every issue still open"},
    },
    "required": ["summary", "built", "issues"],
}


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


# --------------------------------------------------------------------------- the run
class Run:
    def __init__(self, ls):
        self.ls, self.hub, self.folder = ls, ls.hub, ls.folder
        self.settings = ls.hub.settings
        self.plan_text = self.folder.read(self.folder.plan)
        self.plan = plan_mod.parse(self.plan_text)
        reg = crew.registry(self.folder.project)
        self.steps = {s["n"]: {"n": s["n"], "title": s["title"], "after": s["after"], "status": "todo",
                               **crew.step_fields(s.get("agent"), self.folder.project, reg),
                               **(ls.step_skill_fields(s) if hasattr(ls, "step_skill_fields") else {})}
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
                      "built": strs(report.get("built"), "built"), "issues": strs(report.get("issues"), "issues")}
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
        """agent / agent_display (+ agent_fallback) and skills (+ skills_unknown) of step n for UI events."""
        s = self.steps[n]
        out = {"agent": s.get("agent"), "agent_display": s.get("agent_display") or crew.display("builder"),
               "agent_purpose": s.get("agent_purpose") or "building"}
        if s.get("agent_fallback"):
            out["agent_fallback"] = True
        if s.get("skills"):
            out["skills"] = list(s["skills"])

        if s.get("skills_unknown"):
            out["skills_unknown"] = list(s["skills_unknown"])
        return out

    def step_skills(self, n: int) -> list[str]:
        """The skills plan step n names (its worker gets them on top of its allowlist)."""
        return list((self.steps.get(n) or {}).get("skills") or [])

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
                          + (f" [skills: {', '.join(s['skills'])}]" if s.get("skills") else "")
                          for s in self.steps.values())
        log = f.read(f.flight_log).strip() or "(empty)"
        return (f"Run the approved plan \"{self.plan['name']}\".\n"
                f"Plan file: {f.rel(f.plan)} · flight log: {f.rel(f.flight_log)} · step reports: {f.rel(f.steps)}/\n\n"
                f"Steps:\n{steps}\n\n--- plan.md ---\n{self.plan_text.strip()}\n\n--- flight log ---\n{log}\n\n"
                "Start with run_builder.")

    @staticmethod
    def result_message(capped: dict) -> str:
        return (f"Step {capped['step']} result:\n{json.dumps(capped, ensure_ascii=False, indent=1)}\n"
                "Next: run_builder for the next step, or write_report when nothing more can run.")

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
                          tools=orchestrator_tools(self),
                          **crew.session_kw(self.ls, crew.builtin_name("orchestrator"), role="orchestrator"))

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
                        message, nudges = self.result_message(await run_step(self, n, brief)), 0
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
        self.report_markdown = render_report(self, status, issue)
        path = self.folder.write_report(self.report_markdown)
        await self.hub.emit({"type": "run_finished", "session_id": self.ls.id, "status": status,
                             "report_path": self.folder.rel(path), "markdown": self.report_markdown,
                             "total_cost_usd": round(self.total_cost, 6),
                             "planner_cost_usd": round(self.planner_cost, 6)})
        await self.hub.emit({"type": "plan_meta", "session_id": self.ls.id, "name": self.plan["name"],
                             "mode": "Run", "status": {"done": "Done", "stopped": "Stopped"}.get(status, "Failed")})
