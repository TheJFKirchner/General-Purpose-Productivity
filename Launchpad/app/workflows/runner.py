"""One workflow run: stages in order, each agent stage on its Crew agent (agentlib), review stops with sign-off.

- WorkflowRun holds the run's state (the contract's `run` object, app/server.py header "Workflows") and emits
  workflow_run_state on every change, plus Missions events under mission_id ("wf-<run id>"): run_started,
  step_update, run_finished. Agent meters / activity / question and permission cards use the same session id
- Agent stage: the agent as Launchpad runs it for a plan step (app/agents/builder/builder.py StepContext: the same
  ask_question, permission checks, Builder guards / read-only rules, timers, Auto answers and Autopilot), with
  Launchpad's stage tools (ask_question, submit_report with `result`). Its first message holds the stage instruction,
  the run's inputs, the workflow-level and stage-level attached files (read at the start of the run), the results
  of all earlier stages, and any reviewer's send-back note. Code writes the result file from submit_report
- Writes inside the run folder are allowed without a card even when it is outside the connected folder (it is
  also given to the agent as an additional folder); everything else follows the Builder's rules
- Review stage: the run waits (status awaiting_review) until workflow_review; approve -> next stage; send_back ->
  that agent stage and everything after it run again (old attempts kept, marked rejected). Review stages always
  stop, whatever unattended / autopilot / auto answers say
- Unattended = autopilot + auto_answers for this run (hub.set_autopilot / set_auto_answers on mission_id switch them)
- Run folder files: records.py; Launchpad's bookkeeping (activity.log, operations-manual.md with costs) goes to
  <folder>/.launchpad/workflow-runs/<run id>/
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import os
import re
import secrets
import shutil
import stat
import sys
from pathlib import Path

from agentlib import AgentError, tool
from agentlib.events import Done

from .. import costs
from .. import skills as skills_mod
from ..agents import crew
from ..agents.builder.builder import READ_ONLY_RULE, StepContext, strs
from ..meter import Meter
from ..sessionfiles import SessionFolder, inside, one_line, question_slug
from . import records
from .format import WorkflowError, stage_agent

MARKER = ".launchpad-test-folder"
TEST_FOLDER = "test"
CAP_FILE = 60_000            # characters of one attachment / earlier result put into a stage's first message
CAP_SHOWN = 100_000          # result_markdown sent to the page
STAGE_STATUSES = ("done", "failed", "blocked")
MISSION_STATUS = {"waiting": "todo", "running": "in_progress", "awaiting_review": "blocked", "done": "done",
                  "failed": "failed"}
NUDGE = "You have not called submit_report yet. Call it now with result (your stage's result as markdown) and status."

SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {"type": "string", "description": "this stage's full result as markdown; Launchpad saves it as the "
                                                    "stage's result file, which later stages and the reviewer read"},
        "status": {"type": "string", "enum": list(STAGE_STATUSES)},
        "issues": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "files": {"type": "array", "items": {"type": "string"},
                  "description": "data files you wrote in the run folder (paths)"},
    },
    "required": ["result", "status"],
}

STAGE_RULES = """--- how this works in Launchpad ---
- You are one stage of a workflow run (not a plan step): do this stage's job only, as the instruction says.
- Your working folder is the project folder. The run folder (above) is where any data files you produce go.
- Unsure? ask_question (blocking true only if a wrong guess would invalidate the stage; otherwise give a recommended answer and you proceed on it if nobody answers).
- Finish with submit_report: result = this stage's full result as markdown (Launchpad saves it as the stage's result file; later stages and the reviewer read it), status done | failed, plus issues, assumptions and files (data files you wrote in the run folder). Call it last.
- There is no plan, orchestrator or flight log here; ignore anything in your own definition about them."""


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def new_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def check_report(r: dict) -> dict:
    status = r.get("status")
    if status not in STAGE_STATUSES:
        raise ValueError(f"status must be one of {', '.join(STAGE_STATUSES)}")
    result = r.get("result")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("result is required: your stage's result as markdown (not empty)")
    return {"result": result.strip(), "status": "done" if status == "done" else "failed",
            "issues": strs(r.get("issues"), "issues"), "assumptions": strs(r.get("assumptions"), "assumptions"),
            "files": strs(r.get("files"), "files")}


def read_capped(path: Path, cap: int) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if len(text) <= cap else text[:cap] + f"\n\n(... cut at {cap} characters; the full file: {path})"


# --------------------------------------------------------------------------- folders
def _remove(p: Path) -> None:
    """Delete one entry of the test folder: links (symlinks, junctions) are removed, never followed."""
    def unlock(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if p.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(p)):
        try:
            p.unlink()
        except OSError:
            os.rmdir(p)
    elif p.is_dir():
        if sys.version_info >= (3, 12):
            shutil.rmtree(p, onexc=unlock)
        else:
            shutil.rmtree(p, onerror=unlock)
    else:
        try:
            p.unlink()
        except PermissionError:
            os.chmod(p, stat.S_IWRITE)
            p.unlink()


def check_test_folder(output: Path) -> Path:
    """The test folder, or WorkflowError when a `test` folder exists that Launchpad did not make (nothing deleted)."""
    folder = output / TEST_FOLDER
    link = folder.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(folder))
    if (folder.exists() or link) and (link or not folder.is_dir() or not (folder / MARKER).is_file()):
        raise WorkflowError(f"The folder {folder} was not created by Launchpad, so it will not be emptied. Rename or "
                            "remove it, or choose another output folder.")
    return folder


def prepare_test_folder(output: Path, workflow_name: str) -> Path:
    """Empty Launchpad's own test folder completely (or make it, with the marker). Refuses a folder without it."""
    folder = check_test_folder(output)
    if folder.exists():
        try:
            for child in list(folder.iterdir()):
                _remove(child)
        except OSError as e:
            raise WorkflowError(f"could not empty the test folder {folder}: {e}") from None
    folder.mkdir(parents=True, exist_ok=True)
    (folder / MARKER).write_text(json.dumps({
        "created_by": "Launchpad", "workflow": workflow_name,
        "note": "Launchpad made this folder for test runs and empties it completely at the start of every test run. "
                "Do not keep anything else here."}, indent=1) + "\n", encoding="utf-8")
    return folder


def dated_folder(output: Path) -> Path:
    base = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    folder, k = output / base, 1
    while folder.exists():
        k += 1
        folder = output / f"{base}_{k}"
    folder.mkdir(parents=True)
    return folder


class RunRecords(SessionFolder):
    """The SessionFolder shape step agents write through, pointed at a workflow run: questions/ and assumptions.md go
    to the run folder (records); activity.log and operations-manual.md (costs) to Launchpad's hidden bookkeeping."""

    def __init__(self, project: Path, run_id: str, extra, run_folder: Path, test: bool):
        super().__init__(project, run_id, extra)
        self.path = Path(run_folder)
        self.questions = self.path / "questions"
        self.assumptions = self.path / "assumptions.md"
        self.books = self.root / "workflow-runs" / run_id
        self.activity = self.books / "activity.log"
        self.ops_manual = self.books / "operations-manual.md"
        self.test = test

    def ensure(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path

    def ensure_books(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        gi = self.root / ".gitignore"
        if not gi.exists():
            gi.write_text("# Launchpad session folders: local only\n*\n", encoding="utf-8")
        self.books.mkdir(parents=True, exist_ok=True)
        return self.books

    def _append(self, file: Path, title: str, text: str) -> None:
        (self.ensure_books if inside(file, self.books) else self.ensure)()
        new = not file.exists()
        with file.open("a", encoding="utf-8", newline="\n") as f:
            if new:
                f.write(f"# {title}\n\nWorkflow run {self.id}" + (" (test run)" if self.test else "") + "\n\n")
            f.write(text.rstrip("\n") + "\n")

    def add_activity(self, line: str) -> None:
        self.ensure_books()
        with self.activity.open("a", encoding="utf-8", newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    def add_flight_log(self, path: str, why: str, *, line=None, source: str) -> bool:
        return False                                      # no flight log in a workflow run


class _Owner:
    """What StepContext reads from `run.ls`: the session id its cards and meters use, the run number, the hub."""

    def __init__(self, run: "WorkflowRun"):
        self.run = run
        self.hub = run.hub
        self.run_count = 1
        self.dir_id = run.wf["folder"]

    @property
    def id(self) -> str:
        return self.run.mission_id

    @property
    def auto_answers(self) -> bool:
        return self.run.auto_answers


# --------------------------------------------------------------------------- one agent stage
def stage_tools(ctx) -> list:
    @tool
    async def ask_question(title: str, body: str, recommended: str, options: list[str] | None = None,
                           blocking: bool = False) -> str:
        """Ask the user one question. recommended (your own best answer) and body (why you ask) are always
        required, never empty. blocking=false: if nobody answers within a few minutes you get your
        recommended answer back and proceed on it (logged as an assumption). blocking=true only when a wrong
        guess would invalidate the stage: the run waits until the user answers. When the run is unattended,
        your recommended answer is taken as the answer at once."""
        return await ctx.ask(title, body, recommended, options, blocking)

    @tool(schema=SUBMIT_SCHEMA, ends_turn=True)
    def submit_report(**report) -> str:
        """Finish the stage: result (this stage's full result as markdown; saved as its result file), status
        done | failed, issues, assumptions, files (data files you wrote in the run folder). Call it last."""
        return ctx.submit(report)

    return [ask_question, submit_report]


class StageContext(StepContext):
    """A workflow stage's agent: StepContext's questions and permission checks, a workflow result, and the run folder
    counted as writable (no card) wherever it is."""

    def submit(self, report: dict) -> str:
        self.report = check_report(report)
        return "Result received. Stop now."

    def _classify(self, req):
        if req.tool in crew.WRITE_TOOLS:
            raw = str(req.input.get("file_path") or req.input.get("notebook_path") or "").strip()
            if raw:
                p = Path(raw)
                p = p if p.is_absolute() else self.run.folder.project / p
                folder = self.run.run_folder
                if inside(p, folder) and p.resolve() != (folder / MARKER).resolve():
                    return None
        return super()._classify(req)


# --------------------------------------------------------------------------- the run
class WorkflowRun:
    def __init__(self, manager, wf: dict, *, project: Path, extra: list[Path], inputs: dict, test: bool,
                 unattended: bool, run_folder: Path, attachments: dict[str, str]):
        self.manager, self.hub = manager, manager.hub
        self.settings = self.hub.settings
        self.wf = wf                                    # the workflow view at the start (the run keeps it)
        self.id = new_run_id()
        self.mission_id = "wf-" + self.id
        self.test, self.unattended = bool(test), bool(unattended)
        self.autopilot = self.auto_answers = self.unattended
        self.inputs = dict(inputs)
        self.run_folder = Path(run_folder)
        self.attach_text = attachments                  # resolved path -> text, read at the start
        self.attachments = [{"path": p, "chars": len(t)} for p, t in attachments.items()]
        self.folder = RunRecords(project, self.id, extra, self.run_folder, self.test)
        self.ls = _Owner(self)
        self.steps = {k + 1: {"title": st["title"]} for k, st in enumerate(wf["stages"])}   # StepContext reads titles
        self.always: set[str] = set()
        self.autopilot_log: list[str] = []
        self.assumptions: list[str] = []
        self.meters: list[Meter] = []
        self.status = "running"
        self.error: str | None = None
        self.current_stage: int | None = None
        self.started_at, self.finished_at = now_iso(), None
        self.sendbacks: list[dict] = []
        self.review_future: asyncio.Future | None = None
        self.task: asyncio.Task | None = None
        self.stages = []
        for st in wf["stages"]:
            base = {"index": st["index"], "kind": st["kind"], "title": st["title"], "status": "waiting",
                    "result_file": None, "result_markdown": None, "attempts": [], "review": None, "reviews": [],
                    "error": None, "cost_usd": 0.0}
            if st["kind"] == "agent":
                base.update(agent=st["agent"], agent_display=st["agent_display"], agent_purpose=st["agent_purpose"],
                            checklist=[])
            else:
                base.update(agent=None, agent_display="Review", agent_purpose="reviewing",
                            checklist=[dict(c) for c in st["checklist"]])
            self.stages.append(base)

    # ---------------------------------------------------------------- state
    @property
    def in_progress(self) -> bool:
        return self.status in ("running", "awaiting_review")

    def cost(self) -> float:
        return sum(m.cost_usd for m in self.meters)

    def data_files(self) -> list[str]:
        """Files in the run folder that are not Launchpad's own records."""
        ours = {"run-summary.md", "run.json", "assumptions.md", MARKER}
        out = []
        if not self.run_folder.is_dir():
            return out
        for p in sorted(self.run_folder.rglob("*")):
            rel = p.relative_to(self.run_folder).as_posix()
            if p.is_file() and rel not in ours and not rel.startswith("questions/") and not re.match(r"^\d\d-[^/]*\.md$", rel):
                out.append(rel)
        return out[:200]

    def view(self) -> dict:
        return {"id": self.id, "workflow_id": self.wf["id"], "workflow_name": self.wf["name"], "test": self.test,
                "folder": str(self.run_folder), "mission_id": self.mission_id, "inputs": dict(self.inputs),
                "unattended": self.unattended, "autopilot": self.autopilot, "auto_answers": self.auto_answers,
                "status": self.status, "current_stage": self.current_stage, "started_at": self.started_at,
                "finished_at": self.finished_at, "summary_file": str(self.run_folder / "run-summary.md"),
                "error": self.error, "cost_usd": costs.wire(self.cost()),
                "stages": [{**{k: v for k, v in st.items() if k != "agent_purpose"},
                            "cost_usd": costs.wire(st["cost_usd"]),
                            "attempts": [dict(a) for a in st["attempts"]]} for st in self.stages]}

    def state_event(self, error: str | None = None) -> dict:
        ev = {"type": "workflow_run_state", "run": self.view()}
        if error:
            ev["error"] = error
        return ev

    def write_records(self) -> None:
        """run-summary.md + run.json in the run folder (best-effort: a full disk must not stop the run)."""
        try:
            self.run_folder.mkdir(parents=True, exist_ok=True)
            (self.run_folder / "run-summary.md").write_text(records.summary_text(self), encoding="utf-8", newline="\n")
            (self.run_folder / "run.json").write_text(json.dumps(self.view(), indent=1, ensure_ascii=False),
                                                      encoding="utf-8", newline="\n")
        except OSError:
            pass

    async def changed(self) -> None:
        self.write_records()
        await self.hub.emit(self.state_event())

    # ---------------------------------------------------------------- Missions
    def marker(self) -> dict:
        """`workflow` on Missions events: this is a workflow run, not a planner's plan."""
        return {"id": self.wf["id"], "name": self.wf["name"], "run_id": self.id, "test": self.test}

    @staticmethod
    def waiting_field(st: dict) -> dict:
        return {"waiting_for": "review"} if st["status"] == "awaiting_review" else {}

    def steps_payload(self) -> list[dict]:
        return [{"n": st["index"] + 1, "title": st["title"], "status": MISSION_STATUS[st["status"]],
                 "agent": st["agent"], "agent_display": st["agent_display"], "agent_purpose": st["agent_purpose"],
                 **self.waiting_field(st)} for st in self.stages]

    def mission_name(self) -> str:
        return f"Workflow: {self.wf['name']}" + (" (test run)" if self.test else "")

    def started_event(self) -> dict:
        return {"type": "run_started", "session_id": self.mission_id, "name": self.mission_name(),
                "steps": self.steps_payload(), "run": 1, "revision": 0, "autopilot": self.autopilot,
                "auto_answers": self.auto_answers, "workflow": self.marker()}

    def switch_events(self) -> list[dict]:
        return [{"type": "autopilot", "session_id": self.mission_id, "on": self.autopilot},
                {"type": "auto_answers", "session_id": self.mission_id, "on": self.auto_answers}]

    def finished_event(self) -> dict:
        path = self.run_folder / "run-summary.md"
        return {"type": "run_finished", "session_id": self.mission_id,
                "status": {"done": "done", "stopped": "stopped"}.get(self.status, "failed"),
                "report_path": str(path), "markdown": read_capped(path, CAP_SHOWN),
                "total_cost_usd": costs.wire(self.cost()), "planner_cost_usd": 0.0, "workflow": self.marker()}

    def mission_events(self) -> list[dict]:
        out = [self.started_event(), *self.switch_events()]
        if not self.in_progress:
            out.append(self.finished_event())
        return out

    async def mission_step(self, k: int, status: str | None = None) -> None:
        st = self.stages[k]
        await self.hub.emit({"type": "step_update", "session_id": self.mission_id, "n": k + 1,
                             "status": status or MISSION_STATUS[st["status"]], "agent": st["agent"],
                             "agent_display": st["agent_display"], "agent_purpose": st["agent_purpose"],
                             **({"waiting_for": "review"} if status is None and st["status"] == "awaiting_review" else {}),
                             **({"report_path": st["result_file"]} if st["result_file"] else {})})

    async def set_stage(self, k: int, status: str) -> None:
        self.stages[k]["status"] = status
        await self.mission_step(k)

    async def set_step(self, n: int, status: str, **_kw) -> None:
        """StepContext marks its step blocked / in_progress around a card: Missions only (the stage stays running)."""
        await self.mission_step(n - 1, status)

    def note_assumption(self, text: str, *, agent: str, step: int | None, source: str) -> None:
        self.assumptions.append(self.folder.add_assumption(text, agent=agent, step=step, source=source))

    # ---------------------------------------------------------------- the loop
    async def go(self, start: int = 0) -> None:
        try:
            k = start
            while k < len(self.stages):
                st = self.stages[k]
                if st["kind"] == "agent":
                    if not await self.agent_stage(k):
                        self.status, self.error = "failed", f"stage {k + 1} ({st['title']}) failed"
                        break
                    k += 1
                else:
                    record = await self.review_stage(k)
                    if record["decision"] == "approve":
                        k += 1
                    else:
                        k = self.send_back(k, record)
            else:
                self.status = "done"
        except asyncio.CancelledError:
            self.status = self.status if self.status in ("failed",) else "stopped"
            self.error = self.error or "Stopped"
        except Exception as e:  # noqa: BLE001 -- a bug must still end the run with records
            import traceback
            traceback.print_exc()
            self.status, self.error = "failed", f"Launchpad error: {type(e).__name__}: {e}"
        await self.finish()

    async def finish(self) -> None:
        for k, st in enumerate(self.stages):
            if st["status"] == "running":
                st["status"], st["error"] = "failed", st["error"] or ("Stopped" if self.status == "stopped" else self.error)
                await self.mission_step(k)
            elif st["status"] == "awaiting_review":
                st["status"], st["error"] = "waiting", "Stopped before sign-off"
                await self.mission_step(k)
        for m in self.meters:
            if m.status != "done":
                await m.set_status("done")
        await self.hub.incoming.cancel_session(self.mission_id)
        self.current_stage = None
        self.review_future = None
        self.finished_at = now_iso()
        await self.changed()
        await self.hub.emit(self.finished_event())
        await self.manager.run_ended(self)

    # ---------------------------------------------------------------- agent stage
    def result_path(self, k: int, attempt: int) -> Path:
        slug = question_slug(self.stages[k]["title"], 40)
        return self.run_folder / (f"{k + 1:02d}-{slug}" + (f"-{attempt}" if attempt > 1 else "") + ".md")

    def notes_for(self, k: int) -> list[dict]:
        """Send-back notes that cover stage k (it lies between the stage sent back to and the review)."""
        return [sb for sb in self.sendbacks if sb["back_to"] <= k < sb["review"]]

    def stage_message(self, k: int, ctx: StageContext) -> str:
        wf, st = self.wf, self.wf["stages"][k]
        f = self.folder
        lines = [f"Workflow \"{wf['name']}\" · stage {k + 1} of {len(wf['stages'])}: {st['title']}"
                 + (" (test run)" if self.test else ""), "",
                 f"Working folder (project): {f.project}"]
        if f.extra:
            lines.append(f"Additional folders (also yours to work in): {', '.join(str(e) for e in f.extra)}")
        lines += [f"Run folder (write any data files here): {self.run_folder}", ""]
        lines += ["--- instruction ---", st["instruction"].strip(), ""]
        if self.inputs:
            labels = {i["name"]: i["label"] for i in wf["inputs"]}
            lines += ["--- inputs of this run ---"] + [f"- {labels.get(n, n)} ({n}): {v or '(empty)'}"
                                                      for n, v in self.inputs.items()] + [""]
        attached = [a["resolved"] for a in wf["files"]] + [a["resolved"] for a in st["files"]]
        if attached:
            lines.append("--- attached files (read at the start of this run; follow them) ---")
            for p in dict.fromkeys(attached):
                text = self.attach_text.get(p, "")
                if len(text) > CAP_FILE:
                    text = text[:CAP_FILE] + f"\n\n(... cut at {CAP_FILE} characters; read the rest from the file)"
                lines += [f"### {p}", text.strip() or "(empty file)", ""]
        earlier = [s for s in self.stages[:k] if s["kind"] == "agent" and s["result_file"]]
        lines.append("--- results of earlier stages ---")
        if not earlier:
            lines += ["none (this is the first agent stage)", ""]
        for s in earlier:
            lines += [f"### Stage {s['index'] + 1}: {s['title']} ({s['result_file']})",
                      read_capped(Path(s["result_file"]), CAP_FILE).strip(), ""]
        notes = self.notes_for(k)
        if notes:
            lines.append("--- sent back by a reviewer: do this stage again, acting on the note ---")
            for nb in notes:
                lines.append(f"- {nb['name']} at review \"{nb['review_title']}\": {nb['note']}")
            rejected = [a["result_file"] for a in self.stages[k]["attempts"] if a["rejected"]]
            if rejected:
                lines.append(f"- Your rejected result(s), kept for reference: {', '.join(rejected)}")
            lines.append("")
        lines.append(STAGE_RULES + ("\n" + READ_ONLY_RULE if ctx.read_only else ""))
        return "\n".join(lines)

    def load_worker(self, ctx: StageContext):
        add = list(self.folder.extra)
        if not any(inside(self.run_folder, d) for d in self.folder.folders):
            add.append(self.run_folder)
        kw: dict = {"add_dirs": add} if add else {}
        found = skills_mod.discover(self.folder.folders)
        setting = skills_mod.setting_of(self.hub.store.agent_skills(), ctx.worker["name"])
        names = skills_mod.allowed(setting, found)
        if names:
            kw.update(skills=names, skill_dirs=skills_mod.skill_dirs(self.folder.folders))
        common = dict(engine=self.settings.engine, project=self.folder.project, tools=stage_tools(ctx),
                      on_permission=ctx.permission, timeout_s=self.settings.builder_turn_timeout_s,
                      env=dict(crew.WAITING_ENV), **kw)
        role = ctx.worker.get("role")
        if role == "builder":
            return crew.load("builder", gated_tools=list(crew.BUILDER_GATED), engine_prompt=True, **common)
        if role == "astronaut":
            # the agent-file loader sets disallowed_tools itself: add the write / shell denials after loading
            agent = crew.load("astronaut", **common)
            agent.disallowed_tools = list(dict.fromkeys(list(agent.disallowed_tools or []) + list(crew.WRITE_SHELL)))
            agent.resolved_tools()
            return agent
        return crew.load_step_worker(ctx.worker, **common)

    async def _turn(self, s, message: str, meter: Meter):
        reply = None
        async for ev in s.stream(message):
            await meter.feed(ev)
            if isinstance(ev, Done):
                reply = ev.reply
        return reply

    async def agent_stage(self, k: int) -> bool:
        st = self.stages[k]
        attempt = len(st["attempts"]) + 1
        n = k + 1
        st.update(result_file=None, result_markdown=None, error=None)
        self.current_stage = k
        entry = stage_agent(st["agent"], self.folder.project)
        if entry is None:
            st["error"] = f"agent '{st['agent']}' is not a stage agent in this folder"
            await self.set_stage(k, "failed")
            await self.changed()
            return False
        ctx = StageContext(self, n, entry)
        try:
            agent = self.load_worker(ctx)
        except Exception as e:  # noqa: BLE001 -- a file the loader refuses fails the stage, never the app
            st["error"] = f"the agent could not be loaded: {one_line(str(e), 200)}"
            await self.set_stage(k, "failed")
            await self.changed()
            return False
        mcp_issues = await self.hub.give_mcp(agent, who=f"{ctx.agent_name} (stage {n})", session_id=self.mission_id,
                                             name=entry["name"])
        await self.hub.count_use(entry["name"])
        await self.set_stage(k, "running")
        await self.changed()
        meter = ctx.meter = Meter(self.hub, session_id=self.mission_id, role="builder", name=ctx.agent_name, step=n)
        meter.usage_info = {"stage": st["title"]}                     # the usage log names the stage
        self.meters.append(meter)
        await meter.set_status("working")
        cost_before = meter.cost_usd
        error = None
        try:
            async with agent.session() as s:
                await self._turn(s, self.stage_message(k, ctx), meter)
                if ctx.report is None:
                    await self._turn(s, NUDGE, meter)
        except AgentError as e:
            await meter.add_reply(e.reply)
            error = e.short
        report = ctx.report or {"result": "", "status": "failed", "assumptions": [], "files": [],
                                "issues": [f"The agent ended without submit_report{': ' + error if error else ''}"]}
        report["issues"] = list(report["issues"]) + ctx.refused + mcp_issues
        for a in report["assumptions"]:
            self.note_assumption(a, agent=ctx.agent_name, step=n, source="stage result")
        path = self.result_path(k, attempt)
        stage_cost = meter.cost_usd - cost_before
        text = records.result_text(self, st, attempt=attempt, report=report, agent=ctx.agent_name,
                                   tool_calls=meter.tool_calls, cost_usd=stage_cost, notes=self.notes_for(k))
        try:
            self.run_folder.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as e:
            report["status"], error = "failed", f"could not write the result file: {e}"
        self.folder.add_operations(agent=ctx.agent_name, role="workflow stage", step=n, notes="",
                                   tool_calls=meter.tool_calls, cost_usd=stage_cost)
        st["attempts"].append({"attempt": attempt, "result_file": str(path), "status": report["status"],
                               "rejected": False, "note": None})
        st["result_file"] = str(path)
        st["result_markdown"] = read_capped(path, CAP_SHOWN) or None
        st["cost_usd"] += stage_cost
        if report["status"] != "done":
            st["error"] = error or (report["issues"][0] if report["issues"] else "the agent reported failed")
        await meter.set_status("done")
        await self.set_stage(k, report["status"])
        await self.changed()
        return report["status"] == "done"

    def seed(self, results: dict[int, str]) -> int:
        """--fake demo: write finished results for the first agent stages (no agent runs) -> where the loop starts."""
        k = 0
        while k < len(self.stages) and self.stages[k]["kind"] == "agent" and k in results:
            st = self.stages[k]
            path = self.result_path(k, 1)
            report = {"result": results[k], "status": "done", "issues": [], "assumptions": [], "files": []}
            self.run_folder.mkdir(parents=True, exist_ok=True)
            path.write_text(records.result_text(self, st, attempt=1, report=report, agent=st["agent_display"],
                                                tool_calls=0, cost_usd=0.0, notes=[]), encoding="utf-8", newline="\n")
            st["attempts"].append({"attempt": 1, "result_file": str(path), "status": "done", "rejected": False,
                                   "note": None})
            st.update(status="done", result_file=str(path), result_markdown=read_capped(path, CAP_SHOWN))
            k += 1
        return k

    # ---------------------------------------------------------------- review stage
    async def review_stage(self, k: int) -> dict:
        """Wait for the sign-off (always, whatever unattended says) -> the review record."""
        st = self.stages[k]
        st.update(review=None, error=None)
        self.current_stage = k
        self.status = "awaiting_review"
        self.review_future = asyncio.get_running_loop().create_future()
        await self.set_stage(k, "awaiting_review")
        card = await self.hub.incoming.post(            # the "needs you" card in Incoming / Orbit / Missions
            kind="review", session_id=self.mission_id, agent="Review", step=k + 1,
            title=f"Sign-off needed: {st['title']}",
            body=f"{self.wf['name']}" + (" (test run)" if self.test else "") + f": stage {k + 1} is waiting for a "
                 "review sign-off. Sign it off (approve or send back) in the Workflows view.",
            extra={"workflow": self.marker(), "run_id": self.id, "stage": k})
        await self.changed()
        record = None
        try:
            record = await self.review_future
        finally:
            await self.hub.incoming.withdraw(card, record["decision"] if record else None)
        self.review_future = None
        self.status = "running"
        st["review"] = record
        st["reviews"].append(record)
        st["status"] = "done" if record["decision"] == "approve" else "waiting"
        await self.mission_step(k)
        await self.changed()
        return record

    def accept_review(self, k: int, record: dict) -> None:
        """Called by the manager once workflow_review is checked: write the record and wake the loop."""
        st = self.stages[k]
        results = [(f"Stage {s['index'] + 1}: {s['title']}", s["result_file"]) for s in self.stages[:k]
                   if s["kind"] == "agent" and s["result_file"]]
        passes = len(st["reviews"]) + 1
        slug = question_slug(st["title"], 40)
        path = self.run_folder / (f"{k + 1:02d}-{slug}-review" + (f"-{passes}" if passes > 1 else "") + ".md")
        record["record_file"] = str(path)
        try:
            self.run_folder.mkdir(parents=True, exist_ok=True)
            path.write_text(records.review_text(self, st, record, results), encoding="utf-8", newline="\n")
        except OSError as e:
            record["record_file"] = None
            record["note"] = (record["note"] + " " if record["note"] else "") + f"(record not saved: {e})"
        self.review_future.set_result(record)

    def send_back(self, k: int, record: dict) -> int:
        """A review sent the run back to agent stage `back_to`: mark the attempts there and after it rejected, reset
        every stage from back_to to the review; -> where the loop goes on."""
        back = record["back_to"]
        self.sendbacks.append({"back_to": back, "review": k, "note": record["note"], "name": record["name"],
                               "review_title": self.stages[k]["title"]})
        for j in range(back, k + 1):
            s = self.stages[j]
            if s["kind"] == "agent":
                for a in s["attempts"]:
                    if not a["rejected"]:
                        a["rejected"], a["note"] = True, record["note"]
                s.update(result_file=None, result_markdown=None)
            else:
                s["review"] = None
            s.update(status="waiting", error=None)
        return back

    # ---------------------------------------------------------------- stop
    async def stop(self) -> None:
        if self.task is not None and not self.task.done():
            await self.hub.incoming.cancel_session(self.mission_id)
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
