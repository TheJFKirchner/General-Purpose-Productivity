"""Workflows in the hub: discovery, the form's save / remove, starting runs, stop, review sign-off, reconnect replay.

- Folders a workflow can live in: the primary folder (hub.default_dir), then the folders ticked as additional
- Messages (app/server.py header, "Workflows"): workflows_get, workflow_save, workflow_remove -> workflows_list;
  workflow_run, workflow_stop, workflow_review -> workflow_run_state (refusals carry `error`)
- One run per workflow at a time; runs live in memory (latest per workflow kept for the card and a reconnect)
- Missions: runs answer to their mission id ("wf-<run id>") for run_stop / set_autopilot / set_auto_answers
"""
from __future__ import annotations

import asyncio
import datetime as dt
import re
from pathlib import Path

from . import format as fmt
from .format import WorkflowError
from .runner import WorkflowRun, check_test_folder, dated_folder, now_iso, prepare_test_folder

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Workflows:
    def __init__(self, hub):
        self.hub = hub
        self.runs: dict[str, WorkflowRun] = {}       # run id -> run (the latest per workflow is kept)
        self.latest: dict[str, str] = {}             # workflow id -> its latest run id
        self.missions: dict[str, WorkflowRun] = {}   # mission id -> run

    # ---------------------------------------------------------------- folders + discovery
    def folders(self) -> list[dict]:
        """Where workflows live: the primary folder, then the ticked additional folders (existing ones only)."""
        hub = self.hub
        out = []
        for did in [hub.default_dir, *hub.store.additional_ids()]:
            entry = hub.store.get(did)
            if entry is None or any(f["dir_id"] == did for f in out) or not Path(entry["path"]).is_dir():
                continue
            out.append({"dir_id": did, "name": entry["name"], "path": str(Path(entry["path"]).resolve()),
                        "is_primary": did == hub.default_dir})
        return out

    def scan(self) -> tuple[list[dict], dict, dict]:
        """-> (workflow views, agents per folder, id -> {view, clean, folder, file})."""
        views, agents, found = [], {}, {}
        for f in self.folders():
            folder = Path(f["path"])
            choices = fmt.agent_choices(folder)
            agents[f["dir_id"]] = choices
            items = []
            for path in fmt.files_in(folder):
                view, clean = fmt.load(path, dir_id=f["dir_id"], folder=folder, folder_name=f["name"], agents=choices)
                run = self.running(view["id"])
                view["running_run_id"] = run.id if run else None
                view["last_run_id"] = self.latest.get(view["id"])
                found[view["id"]] = {"view": view, "clean": clean, "folder": folder, "file": path,
                                     "dir_id": f["dir_id"]}
                items.append(view)
            views += sorted(items, key=lambda v: v["name"].lower())
        return views, agents, found

    def list_event(self, error: str | None = None) -> dict:
        views, agents, _ = self.scan()
        ev = {"type": "workflows_list", "workflows": views, "folders": self.folders(), "agents": agents,
              "reviewer_name": self.hub.store.reviewer_name()}
        if error:
            ev["error"] = error
        return ev

    def find(self, wid: str) -> dict | None:
        return self.scan()[2].get(str(wid or ""))

    def running(self, wid: str) -> WorkflowRun | None:
        rid = self.latest.get(wid)
        run = self.runs.get(rid) if rid else None
        return run if run is not None and run.in_progress else None

    def mission(self, sid: str | None) -> WorkflowRun | None:
        return self.missions.get(sid or "") if sid else None

    # ---------------------------------------------------------------- messages
    async def handle(self, kind: str, msg: dict) -> None:
        if kind in ("workflows_get", "workflow_save", "workflow_remove"):
            error = None
            try:
                if kind == "workflow_save":
                    self.save(msg)
                elif kind == "workflow_remove":
                    self.remove(str(msg.get("id") or ""))
            except WorkflowError as e:
                error = str(e)
            except OSError as e:
                error = f"the file could not be written: {e}"
            await self.hub.emit(self.list_event(error))
        elif kind == "workflow_run":
            wid = str(msg.get("id") or "")
            try:
                await self.start(wid, msg.get("inputs"), test=bool(msg.get("test")),
                                 unattended=bool(msg.get("unattended")))
            except WorkflowError as e:
                await self.hub.emit({"type": "workflow_run_state", "run": None, "workflow_id": wid, "error": str(e)})
        elif kind == "workflow_stop":
            await self.stop(str(msg.get("run_id") or ""))
        elif kind == "workflow_review":
            await self.review(msg)

    # ---------------------------------------------------------------- save / remove
    def save(self, msg: dict) -> str:
        did = str(msg.get("folder") or "")
        place = next((f for f in self.folders() if f["dir_id"] == did), None)
        if place is None:
            raise WorkflowError("not saved: choose the primary folder or a folder ticked as additional")
        folder = Path(place["path"])
        raw = msg.get("workflow")
        if not isinstance(raw, dict):
            raise WorkflowError("not saved: the workflow is missing")
        clean, warns = fmt.check(raw, folder)
        problems = fmt.structural(warns)
        if problems:
            raise WorkflowError("not saved: " + "; ".join(problems))
        orig_id = str(msg.get("original_id") or "").strip()
        orig = None
        if orig_id:
            orig = self.find(orig_id)
            if orig is None:
                raise WorkflowError("not saved: the workflow being edited was not found (removed or renamed?)")
        slug = orig["file"].stem if orig else fmt.slugify(clean["name"])
        rel = f"{fmt.WORKFLOWS_DIR}/{slug}.json"
        target = folder / fmt.WORKFLOWS_DIR / f"{slug}.json"
        moving = orig is not None and orig["dir_id"] != did
        if (orig is None or moving) and target.exists():
            raise WorkflowError(f"not saved: {place['name']}/{rel} already exists; choose another name")
        if target.exists():
            self.hub.files._backup(did, rel, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fmt.file_text(clean), encoding="utf-8", newline="\n")
        if moving:
            self.hub.files._backup(orig["dir_id"], rel, orig["file"])
            orig["file"].unlink(missing_ok=True)
        return f"{did}/{slug}"

    def remove(self, wid: str) -> None:
        found = self.find(wid)
        if found is None:
            raise WorkflowError("that workflow was not found")
        if self.running(wid):
            raise WorkflowError("that workflow is running; stop the run first")
        rel = f"{fmt.WORKFLOWS_DIR}/{found['file'].name}"
        self.hub.files._backup(found["dir_id"], rel, found["file"])
        found["file"].unlink()

    # ---------------------------------------------------------------- runs
    @staticmethod
    def check_inputs(view: dict, folder: Path, given) -> dict:
        given = given if isinstance(given, dict) else {}
        out, problems = {}, []
        for i in view["inputs"]:
            v = given.get(i["name"])
            v = (str(v).strip() if v is not None else "") or i["default"]
            label = i["label"]
            if not v:
                if i["required"]:
                    problems.append(f"fill in {label}")
                out[i["name"]] = ""
                continue
            if i["kind"] == "date":
                try:
                    if not DATE.match(v):
                        raise ValueError
                    dt.date.fromisoformat(v)
                except ValueError:
                    problems.append(f"{label} must be a date as YYYY-MM-DD")
            elif i["kind"] == "number":
                try:
                    float(v)
                except ValueError:
                    problems.append(f"{label} must be a number")
            elif i["kind"] == "choice" and v not in i["options"]:
                problems.append(f"{label} must be one of: {', '.join(i['options'])}")
            elif i["kind"] == "file" and not fmt.resolve(folder, v).is_file():
                problems.append(f"{label}: file not found: {v}")
            out[i["name"]] = v
        if problems:
            raise WorkflowError("The run did not start: " + "; ".join(problems) + ".")
        return out

    @staticmethod
    def read_attachments(view: dict) -> dict[str, str]:
        """Every attached file (workflow-level and stage-level), read now; a missing one refuses the run."""
        out, missing = {}, []
        paths = [a for a in view["files"]] + [a for st in view["stages"] if st["kind"] == "agent" for a in st["files"]]
        for a in paths:
            if a["resolved"] in out:
                continue
            try:
                out[a["resolved"]] = Path(a["resolved"]).read_text(encoding="utf-8", errors="replace")
            except OSError:
                missing.append(a["path"])
        if missing:
            raise WorkflowError("The run did not start: attached file(s) not found: " + ", ".join(missing) + ".")
        return out

    async def start(self, wid: str, inputs, *, test: bool, unattended: bool,
                    seed_results: dict[int, str] | None = None) -> WorkflowRun:
        """Start a run. seed_results (the --fake demo only): {stage index: result markdown} for the first agent
        stages, written as finished results so the run opens further along (e.g. waiting at its review)."""
        found = self.find(wid)
        if found is None:
            raise WorkflowError("That workflow was not found (removed, or its folder is no longer connected).")
        view, folder = found["view"], found["folder"]
        errors = fmt.blocking(view["warnings"])
        if errors:
            raise WorkflowError("This workflow cannot run until these are fixed: " + "; ".join(errors) + ".")
        running = self.running(wid)
        if running:
            waiting = " (it is waiting at a review)" if running.status == "awaiting_review" else ""
            raise WorkflowError(f"This workflow is already running{waiting}. One run at a time: stop it or let it "
                                "finish first.")
        values = self.check_inputs(view, folder, inputs)
        attachments = self.read_attachments(view)
        output = Path(view["output_path"])
        if test:
            check_test_folder(output)                    # refuse before anything is made or deleted
        try:
            output.mkdir(parents=True, exist_ok=True)
            run_folder = prepare_test_folder(output, view["name"]) if test else dated_folder(output)
        except WorkflowError:
            raise
        except OSError as e:
            raise WorkflowError(f"The run did not start: the output folder cannot be used ({e}).") from None
        extra = self.hub.extra_dirs(found["dir_id"])[1]
        run = WorkflowRun(self, view, project=folder, extra=extra, inputs=values, test=test, unattended=unattended,
                          run_folder=run_folder, attachments=attachments)
        self.register(run)
        start = run.seed(seed_results) if seed_results else 0
        await self.hub.emit(run.started_event())
        for ev in run.switch_events():
            await self.hub.emit(ev)
        await run.changed()
        run.task = asyncio.get_running_loop().create_task(run.go(start), name=f"launchpad-workflow-{run.id}")
        await self.hub.emit(self.list_event())
        return run

    def register(self, run: WorkflowRun) -> None:
        old = self.latest.get(run.wf["id"])
        if old and old in self.runs and not self.runs[old].in_progress:
            gone = self.runs.pop(old)                    # keep only the latest run per workflow
            self.missions.pop(gone.mission_id, None)
        self.runs[run.id] = run
        self.missions[run.mission_id] = run
        self.latest[run.wf["id"]] = run.id

    async def run_ended(self, run: WorkflowRun) -> None:
        await self.hub.emit(self.list_event())

    async def stop(self, run_id: str) -> None:
        run = self.runs.get(run_id)
        if run is None:
            await self.hub.emit({"type": "workflow_run_state", "run": None, "error": "That run is not known."})
            return
        if not run.in_progress:
            await self.hub.emit(run.state_event("That run is not in progress."))
            return
        await run.stop()

    async def review(self, msg: dict) -> None:
        run = self.runs.get(str(msg.get("run_id") or ""))
        if run is None:
            await self.hub.emit({"type": "workflow_run_state", "run": None, "error": "That run is not known."})
            return
        try:
            k, record = self.check_review(run, msg)
        except WorkflowError as e:
            await self.hub.emit(run.state_event(str(e)))
            return
        self.hub.store.set_reviewer_name(record["name"])
        run.accept_review(k, record)                     # the run's loop goes on and sends the new state

    @staticmethod
    def check_review(run: WorkflowRun, msg: dict) -> tuple[int, dict]:
        try:
            k = int(msg.get("stage"))
        except (TypeError, ValueError):
            raise WorkflowError("Say which stage is being reviewed.") from None
        if run.status != "awaiting_review" or run.current_stage != k or run.review_future is None:
            raise WorkflowError("The run is not waiting at that review.")
        decision = str(msg.get("decision") or "")
        if decision not in ("approve", "send_back"):
            raise WorkflowError("Choose approve or send back.")
        name = str(msg.get("name") or "").strip()
        if not name:
            raise WorkflowError("Type your name to sign off.")
        note = str(msg.get("note") or "").strip()
        given = msg.get("answers") if isinstance(msg.get("answers"), list) else []
        answers, missing = [], []
        for i, item in enumerate(run.stages[k]["checklist"]):
            a = given[i] if i < len(given) and isinstance(given[i], dict) else {}
            ticked, text = bool(a.get("ticked")), str(a.get("answer") or "").strip()
            answers.append({"text": item["text"], "kind": item["kind"], "ticked": ticked, "answer": text})
            if (item["kind"] == "tick" and not ticked) or (item["kind"] == "answer" and not text):
                missing.append(item["text"])
        back_to = None
        if decision == "approve":
            if missing:
                raise WorkflowError("Every item must be ticked or answered before sign-off. Still open: "
                                    + "; ".join(missing) + ".")
        else:
            if not note:
                raise WorkflowError("Write a note saying what to change when sending work back.")
            try:
                back_to = int(msg.get("back_to"))
            except (TypeError, ValueError):
                raise WorkflowError("Choose the stage to send the work back to.") from None
            if not (0 <= back_to < k) or run.stages[back_to]["kind"] != "agent":
                raise WorkflowError("Send work back to an earlier agent stage.")
        return k, {"decision": decision, "name": name, "note": note, "at": now_iso(), "answers": answers,
                   "back_to": back_to, "record_file": None}

    # ---------------------------------------------------------------- Missions switches + reconnect
    async def set_switch(self, run: WorkflowRun, which: str, on: bool) -> None:
        """set_autopilot / set_auto_answers on a workflow run's mission id (review stages still stop)."""
        setattr(run, which, bool(on))
        await self.hub.emit({"type": which, "session_id": run.mission_id, "on": bool(on)})
        if on and which == "autopilot":
            await self.hub.incoming.resolve_open(run.mission_id, kind="permission", answer="allow", by="autopilot")
        if on and which == "auto_answers":
            await self.hub.incoming.auto_open(run.mission_id)
        await run.changed()

    def connect_events(self) -> list[dict]:
        out = []
        for run in self.runs.values():
            out += run.mission_events()
            out.append(run.state_event())
        try:
            out.append(self.list_event())
        except Exception as e:  # noqa: BLE001 -- an unreadable folder must not break a connection
            out.append({"type": "workflows_list", "workflows": [], "folders": [], "agents": {}, "reviewer_name": "",
                        "error": f"workflows could not be read ({e})"})
        return out

    async def close(self) -> None:
        for run in list(self.runs.values()):
            if run.task is not None and not run.task.done():
                run.task.cancel()
