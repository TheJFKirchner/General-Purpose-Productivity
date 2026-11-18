"""Workflows on the fake engine (zero tokens): file checking, runs, run folders, test runs, attachments, unattended,
review sign-off, send-back, reconnect, the form's save / remove, and the --fake demo seed."""
import asyncio
import json
import re
from pathlib import Path

from agentlib import fake

from app.hub import Hub
from app.settings import Settings
from app.workflows.runner import MARKER
from conftest import Client


def wf_def(**over) -> dict:
    d = {"name": "Claims study", "description": "Monthly claims study.", "output_folder": "out/claims",
         "unattended_default": False,
         "inputs": [{"name": "valuation_date", "label": "Valuation date", "kind": "date"},
                    {"name": "data_file", "label": "Data file", "kind": "file", "required": False}],
         "files": ["docs/method.md"],
         "stages": [
             {"kind": "agent", "title": "Load data", "agent": "launchpad-builder",
              "instruction": "Load the claims data.", "files": ["docs/stage-notes.md"]},
             {"kind": "review", "title": "Check data", "checklist": [
                 {"text": "Counts match", "kind": "tick"}, {"text": "Anything odd?", "kind": "answer"}]},
             {"kind": "agent", "title": "Write report", "agent": "launchpad-builder",
              "instruction": "Write the report."}]}
    d.update(over)
    return d


def put(project: Path, slug: str, data) -> Path:
    p = project / "workflows" / f"{slug}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return p


def docs(project: Path) -> None:
    (project / "docs" / "method.md").write_text("# Method\nUse the CHAIN-LADDER rule.\n", encoding="utf-8")
    (project / "docs" / "stage-notes.md").write_text("# Stage notes\nSTAGE-ONLY note.\n", encoding="utf-8")


def script_builder(seen: list, extra=None) -> None:
    """Every builder stage: optional extra steps, then submit_report with a result naming its stage."""
    def turn(msg):
        seen.append(msg)
        title = re.search(r"stage \d+ of \d+: (.+?)(?: \(test run\))?$", msg, re.M).group(1)
        steps = list(extra(msg) if extra else [])
        return steps + [fake.spend(0.01), fake.call("submit_report", {
            "result": f"RESULT OF {title.upper()}", "status": "done", "issues": [], "assumptions": []})]
    fake.script("launchpad-builder", [turn] * 4)


def make_hub(project: Path, **kw) -> Hub:
    return Hub(Settings(project=project, engine="fake", question_timeout_s=0.3, **kw))


async def wait(cond, timeout=10.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise AssertionError("timed out waiting for condition")
        await asyncio.sleep(0.01)


def last_run(c: Client) -> dict | None:
    states = [e for e in c.of("workflow_run_state") if e.get("run")]
    return states[-1]["run"] if states else None


def no_errors(c: Client) -> None:
    errs = [e["text"] for e in c.of("system") if "error" in e["text"].lower()]
    assert not errs, errs


# --------------------------------------------------------------------------- file checking
def test_files_with_mistakes_show_warnings_and_cannot_run(project):
    put(project, "broken", "{not json")
    put(project, "bad", {"name": "", "stages": [{"kind": "loop", "title": ""}], "extra_key": 1})
    put(project, "lost", wf_def(name="Lost", stages=[{"kind": "agent", "title": "A", "agent": "nobody",
                                                      "instruction": "x"}]))

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "workflows_get"})
        lst = c.of("workflows_list")[-1]
        by = {w["slug"]: w for w in lst["workflows"]}
        for wid in [w["id"] for w in lst["workflows"]]:
            await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "2026-10-31"}})
        return hub, c, lst, by

    hub, c, lst, by = asyncio.run(go())
    assert set(by) == {"broken", "bad", "lost"}
    assert by["broken"]["warnings"][0]["code"] == "invalid_file" and not by["broken"]["can_run"]
    assert by["broken"]["name"] == "broken" and by["broken"]["stages"] == []
    codes = {w["code"] for w in by["bad"]["warnings"]}
    assert {"invalid", "no_output_folder", "unknown_field"} <= codes and not by["bad"]["can_run"]
    unknown = [w for w in by["lost"]["warnings"] if w["code"] == "unknown_agent"]
    assert unknown and unknown[0]["stage"] == 0 and by["lost"]["stages"][0]["agent_purpose"] == "other"
    missing = [w for w in by["lost"]["warnings"] if w["code"] == "missing_file"]
    assert missing and "docs/method.md" in missing[0]["message"]
    refused = c.of("workflow_run_state")
    assert len(refused) == 3 and all(e["run"] is None and e["error"] for e in refused)
    assert "cannot run" in refused[0]["error"]
    assert not (project / "out").exists()
    assert lst["folders"][0]["is_primary"] and lst["reviewer_name"] == ""
    names = [a["name"] for a in lst["agents"][lst["folders"][0]["dir_id"]]]
    assert names[:2] == ["launchpad-builder", "launchpad-astronaut"] and "launchpad-planner" not in names


# --------------------------------------------------------------------------- a full run
def test_run_writes_dated_folder_results_review_record_and_summary(project):
    docs(project)
    (project / "data.csv").write_text("a,b\n", encoding="utf-8")
    put(project, "claims", wf_def())
    seen = []
    script_builder(seen)

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "test": False, "unattended": False,
                          "inputs": {"valuation_date": "2026-10-31", "data_file": "data.csv"}})
        await wait(lambda: (last_run(c) or {}).get("status") == "awaiting_review")
        run = last_run(c)
        open_cards = hub.incoming.open_events()
        # approve with an open item is refused, the run unchanged
        await hub.handle({"type": "workflow_review", "run_id": run["id"], "stage": 1, "decision": "approve",
                          "name": "Ann", "answers": [{"ticked": True}, {"answer": ""}]})
        refused = c.of("workflow_run_state")[-1]
        await hub.handle({"type": "workflow_review", "run_id": run["id"], "stage": 1, "decision": "approve",
                          "name": "Ann", "note": "fine", "answers": [{"ticked": True}, {"answer": "Nothing odd"}]})
        await wait(lambda: (last_run(c) or {}).get("status") == "done")
        return hub, c, run, refused, open_cards

    hub, c, waiting, refused, open_cards = asyncio.run(go())
    no_errors(c)
    assert "Still open: Anything odd?" in refused["error"] and refused["run"]["status"] == "awaiting_review"
    run = last_run(c)
    folder = Path(run["folder"])
    assert folder.parent == (project / "out" / "claims").resolve()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}(_\d+)?", folder.name)
    names = sorted(p.name for p in folder.iterdir())
    assert {"01-load-data.md", "02-check-data-review.md", "03-write-report.md", "run-summary.md", "run.json"} <= set(names)
    # inputs and attachments reached every agent stage; later stages got earlier results
    assert all("Valuation date (valuation_date): 2026-10-31" in m and "CHAIN-LADDER" in m for m in seen)
    assert "STAGE-ONLY" in seen[0] and "STAGE-ONLY" not in seen[1]
    assert "RESULT OF LOAD DATA" in seen[1]
    # records
    review = (folder / "02-check-data-review.md").read_text(encoding="utf-8")
    assert "**Ann**" in review and "[x] Counts match" in review and "Nothing odd" in review and "Approved" in review
    summary = (folder / "run-summary.md").read_text(encoding="utf-8")
    assert "Valuation date (valuation_date): 2026-10-31" in summary and "**Done**" in summary and "Test run" not in summary
    assert json.loads((folder / "run.json").read_text(encoding="utf-8"))["inputs"]["valuation_date"] == "2026-10-31"
    assert run["inputs"] == {"valuation_date": "2026-10-31", "data_file": "data.csv"}
    st = run["stages"]
    assert [s["status"] for s in st] == ["done", "done", "done"]
    assert st[0]["result_markdown"] and "RESULT OF LOAD DATA" in st[0]["result_markdown"]
    assert st[1]["review"]["decision"] == "approve" and st[1]["review"]["record_file"].endswith("02-check-data-review.md")
    assert waiting["stages"][1]["status"] == "awaiting_review" and waiting["current_stage"] == 1
    # Missions events under the mission id
    mid = run["mission_id"]
    assert mid.startswith("wf-")
    started = [e for e in c.of("run_started") if e["session_id"] == mid]
    assert started and started[0]["name"] == "Workflow: Claims study"
    assert [s["agent_display"] for s in started[0]["steps"]] == ["Builder", "Review", "Builder"]
    assert (2, "blocked") in [(e["n"], e["status"]) for e in c.of("step_update") if e["session_id"] == mid]
    fin = [e for e in c.of("run_finished") if e["session_id"] == mid]
    assert fin and fin[-1]["status"] == "done" and "Run summary" in fin[-1]["markdown"]
    marker = {"id": run["workflow_id"], "name": "Claims study", "run_id": run["id"], "test": False}
    assert started[0]["workflow"] == marker and fin[-1]["workflow"] == marker
    assert started[0]["auto_answers"] is False and started[0]["autopilot"] is False
    # waiting at the review: the step says so and Incoming has the "needs you" card until the sign-off
    blocked = [e for e in c.of("step_update") if e["session_id"] == mid and e["status"] == "blocked"]
    assert blocked and blocked[0]["waiting_for"] == "review" and blocked[0]["n"] == 2
    cards = [e for e in open_cards if e["kind"] == "review"]
    assert len(cards) == 1 and cards[0]["session_id"] == mid and cards[0]["stage"] == 1
    assert cards[0]["run_id"] == run["id"] and cards[0]["workflow"] == marker and cards[0]["blocking"]
    assert {"id": cards[0]["id"], "answer": "approve", "by": "user"} in [
        {k: e[k] for k in ("id", "answer", "by")} for e in c.of("queue_resolved")]
    assert not hub.incoming.open_events()
    assert any(e["session_id"] == mid for e in c.of("agent_usage"))
    # bookkeeping in the hidden folder, the name remembered
    books = project / ".launchpad" / "workflow-runs" / run["id"]
    assert (books / "operations-manual.md").is_file()
    assert hub.store.reviewer_name() == "Ann" and c.of("workflows_list")[-1]["reviewer_name"] == "Ann"


def test_bad_inputs_and_one_run_at_a_time(project):
    docs(project)
    put(project, "claims", wf_def())
    script_builder([])

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "31/10/2026"}})
        await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "2026-10-31",
                                                                         "data_file": "nope.csv"}})
        bad = [e["error"] for e in c.of("workflow_run_state")]
        await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "2026-10-31"}})
        await wait(lambda: (last_run(c) or {}).get("status") == "awaiting_review")
        await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "2026-10-31"}})
        second = c.of("workflow_run_state")[-1]
        run = last_run(c)
        await hub.handle({"type": "workflow_stop", "run_id": run["id"]})
        await wait(lambda: (last_run(c) or {}).get("status") == "stopped")
        return c, bad, second

    c, bad, second = asyncio.run(go())
    assert "YYYY-MM-DD" in bad[0] and "file not found: nope.csv" in bad[1]
    assert second["run"] is None and "already running" in second["error"] and "review" in second["error"]
    stopped = last_run(c)
    assert stopped["stages"][1]["status"] == "waiting" and stopped["finished_at"]


# --------------------------------------------------------------------------- test runs
def test_test_run_reuses_and_clears_its_own_folder_and_refuses_a_foreign_one(project):
    docs(project)
    put(project, "claims", wf_def(stages=[{"kind": "agent", "title": "Load data", "agent": "launchpad-builder",
                                           "instruction": "Load."}]))
    script_builder([])
    foreign = project / "out" / "claims" / "test"
    foreign.mkdir(parents=True)
    (foreign / "keep.txt").write_text("mine", encoding="utf-8")

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        inputs = {"valuation_date": "2026-10-31"}
        await hub.handle({"type": "workflow_run", "id": wid, "test": True, "inputs": inputs})
        refused = c.of("workflow_run_state")[-1]
        kept = (foreign / "keep.txt").is_file()
        (foreign / "keep.txt").unlink()
        foreign.rmdir()
        await hub.handle({"type": "workflow_run", "id": wid, "test": True, "inputs": inputs})
        await wait(lambda: (last_run(c) or {}).get("status") == "done")
        first = last_run(c)
        (Path(first["folder"]) / "leftover.csv").write_text("x", encoding="utf-8")
        (Path(first["folder"]) / "sub").mkdir()
        await hub.handle({"type": "workflow_run", "id": wid, "test": True, "inputs": inputs})
        await wait(lambda: last_run(c)["id"] != first["id"] and last_run(c)["status"] == "done")
        return c, refused, kept, first, last_run(c)

    c, refused, kept, first, second = asyncio.run(go())
    assert refused["run"] is None and "was not created by Launchpad" in refused["error"] and kept
    assert first["folder"] == second["folder"] and Path(first["folder"]).name == "test"
    folder = Path(second["folder"])
    assert (folder / MARKER).is_file() and not (folder / "leftover.csv").exists() and not (folder / "sub").exists()
    assert "Test run" in (folder / "01-load-data.md").read_text(encoding="utf-8")
    assert "test run" in (folder / "run-summary.md").read_text(encoding="utf-8")
    assert second["test"] is True
    assert [p.name for p in (project / "out" / "claims").iterdir()] == ["test"]       # no dated folders


# --------------------------------------------------------------------------- attachments
def test_missing_attachment_blocks_the_run(project):
    docs(project)
    put(project, "claims", wf_def())

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        w = c.of("workflows_list")[-1]["workflows"][0]
        assert w["can_run"] and w["files"][0]["exists"]
        (project / "docs" / "method.md").unlink()                # deleted after the card was shown
        await hub.handle({"type": "workflow_run", "id": w["id"], "inputs": {"valuation_date": "2026-10-31"}})
        await hub.handle({"type": "workflows_get"})
        return c

    c = asyncio.run(go())
    ev = c.of("workflow_run_state")[-1]
    assert ev["run"] is None and "docs/method.md" in ev["error"]
    w = c.of("workflows_list")[-1]["workflows"][0]
    assert not w["can_run"] and not w["files"][0]["exists"]
    assert not (project / "out").exists()


# --------------------------------------------------------------------------- unattended
def test_unattended_answers_and_approves_but_never_skips_a_review(project, tmp_path):
    docs(project)
    put(project, "claims", wf_def())
    seen = []
    outside = tmp_path / "elsewhere.txt"

    def extra(msg):
        if "stage 1 of" not in msg:
            return []
        return [fake.call("ask_question", {"title": "Which basis?", "body": "Two bases exist.",
                                           "recommended": "Paid basis", "blocking": True}),
                fake.call("Write", {"file_path": str(outside), "content": "x"}),
                fake.call("Write", {"file_path": re.search(r"Run folder \(write any data files here\): (.+)", msg)
                                    .group(1) + "/data.csv", "content": "x"})]
    script_builder(seen, extra)

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "unattended": True,
                          "inputs": {"valuation_date": "2026-10-31"}})
        await wait(lambda: (last_run(c) or {}).get("status") == "awaiting_review")
        await asyncio.sleep(0.2)
        return hub, c, last_run(c)

    hub, c, run = asyncio.run(go())
    no_errors(c)
    assert run["status"] == "awaiting_review" and run["unattended"] and run["autopilot"] and run["auto_answers"]
    started = [e for e in c.of("run_started") if e["session_id"] == run["mission_id"]][0]
    assert started["auto_answers"] is True and started["autopilot"] is True
    assert {"type": "auto_answers", "session_id": run["mission_id"], "on": True} in c.of("auto_answers")
    assert {"type": "autopilot", "session_id": run["mission_id"], "on": True} in c.of("autopilot")
    autos = c.of("auto_answer")
    assert autos and autos[0]["answer"] == "Paid basis" and autos[0]["session_id"] == run["mission_id"]
    assert not [q for q in c.of("queue_item") if q["kind"] in ("question", "permission")]
    folder = Path(run["folder"])
    assert any(folder.joinpath("questions").glob("*-which-basis.md"))
    summary = (folder / "run-summary.md").read_text(encoding="utf-8")
    assert "Approved without a card" in summary and "outside the project" in summary
    assert "data.csv" not in summary.split("Approved without a card")[1]          # run-folder writes need no card


# --------------------------------------------------------------------------- send-back
def test_send_back_reruns_from_the_chosen_stage_and_keeps_rejected_results(project):
    docs(project)
    put(project, "claims", wf_def(stages=[
        {"kind": "agent", "title": "Load data", "agent": "launchpad-builder", "instruction": "Load."},
        {"kind": "agent", "title": "Fit model", "agent": "launchpad-builder", "instruction": "Fit."},
        {"kind": "review", "title": "Check", "checklist": []}]))
    seen = []
    script_builder(seen)

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "2026-10-31"}})
        await wait(lambda: (last_run(c) or {}).get("status") == "awaiting_review")
        run = last_run(c)
        base = {"type": "workflow_review", "run_id": run["id"], "stage": 2, "name": "Bo", "answers": []}
        await hub.handle({**base, "decision": "send_back", "back_to": 1})           # no note
        no_note = c.of("workflow_run_state")[-1]["error"]
        await hub.handle({**base, "decision": "send_back", "back_to": 2, "note": "x"})   # not an agent stage
        bad_stage = c.of("workflow_run_state")[-1]["error"]
        n_before = len(seen)
        await hub.handle({**base, "decision": "send_back", "back_to": 1, "note": "Use the 2025 factors."})
        await wait(lambda: len(seen) > n_before and (last_run(c) or {}).get("status") == "awaiting_review"
                   and len(last_run(c)["stages"][2]["reviews"]) == 1)
        await hub.handle({**base, "decision": "approve"})                            # empty checklist: plain sign-off
        await wait(lambda: (last_run(c) or {}).get("status") == "done")
        return c, no_note, bad_stage, n_before

    c, no_note, bad_stage, n_before = asyncio.run(go())
    no_errors(c)
    assert "note" in no_note and "earlier agent stage" in bad_stage
    assert n_before == 2 and len(seen) == 3                    # only stage 2 ran again; stage 1 did not
    assert "Use the 2025 factors." in seen[2] and "Bo" in seen[2] and "02-fit-model.md" in seen[2]
    run = last_run(c)
    folder = Path(run["folder"])
    assert (folder / "02-fit-model.md").is_file() and (folder / "02-fit-model-2.md").is_file()
    assert (folder / "03-check-review.md").is_file() and (folder / "03-check-review-2.md").is_file()
    fit = run["stages"][1]
    assert [a["rejected"] for a in fit["attempts"]] == [True, False]
    assert fit["attempts"][0]["note"] == "Use the 2025 factors." and fit["result_file"].endswith("02-fit-model-2.md")
    assert len(run["stages"][0]["attempts"]) == 1
    assert [r["decision"] for r in run["stages"][2]["reviews"]] == ["send_back", "approve"]
    summary = (folder / "run-summary.md").read_text(encoding="utf-8")
    assert "Rejected results (kept)" in summary and "02-fit-model.md" in summary
    assert "Use the 2025 factors." in (folder / "02-fit-model-2.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- reconnect
def test_a_run_waiting_at_review_survives_a_page_reload(project):
    docs(project)
    put(project, "claims", wf_def())
    script_builder([])

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "inputs": {"valuation_date": "2026-10-31"}})
        await wait(lambda: (last_run(c) or {}).get("status") == "awaiting_review")
        hub.disconnect(c)
        c2 = Client(hub)
        await hub.connect(c2)                                    # the page reloads
        run = last_run(c2)
        card = [e for e in c2.of("queue_item") if e["kind"] == "review"]
        await hub.handle({"type": "queue_response", "id": card[0]["id"], "answer": "approve"})
        still = last_run(c2)["status"]
        await hub.handle({"type": "run_stop", "session_id": run["mission_id"]})     # Missions' Stop
        await wait(lambda: last_run(c2)["status"] == "stopped")
        return hub, c2, run, card, still

    hub, c2, run, card, still = asyncio.run(go())
    assert len(card) == 1 and card[0]["session_id"] == run["mission_id"] and still == "awaiting_review"
    assert any("Workflows view" in e["text"] for e in c2.of("system"))
    assert [e for e in c2.of("queue_resolved") if e["id"] == card[0]["id"]][-1]["answer"] is None
    assert not hub.incoming.open_events()
    assert run["status"] == "awaiting_review" and run["stages"][1]["checklist"][1]["kind"] == "answer"
    assert [e for e in c2.of("run_started") if e["session_id"] == run["mission_id"]]
    lst = c2.of("workflows_list")[0]["workflows"][0]
    assert lst["running_run_id"] == run["id"] and lst["last_run_id"] == run["id"]
    assert [e for e in c2.of("run_finished") if e["session_id"] == run["mission_id"]][-1]["status"] == "stopped"


# --------------------------------------------------------------------------- the form
def test_form_save_edit_remove(project):
    docs(project)

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        did = c.of("workflows_list")[-1]["folders"][0]["dir_id"]
        await hub.handle({"type": "workflow_save", "folder": did, "workflow": wf_def(output_folder="")})
        no_out = c.of("workflows_list")[-1].get("error")
        await hub.handle({"type": "workflow_save", "folder": did,
                          "workflow": wf_def(files=[{"path": "docs/method.md"}, "docs/missing.md"])})
        saved = c.of("workflows_list")[-1]
        await hub.handle({"type": "workflow_save", "folder": did, "workflow": wf_def()})
        dup = c.of("workflows_list")[-1].get("error")
        wid = saved["workflows"][0]["id"]
        await hub.handle({"type": "workflow_save", "folder": did, "original_id": wid,
                          "workflow": wf_def(name="Claims study v2", files=["docs/method.md"])})
        edited = c.of("workflows_list")[-1]
        data = json.loads((project / "workflows" / "claims-study.json").read_text(encoding="utf-8"))
        await hub.handle({"type": "list_backups", "root": did, "path": "workflows/claims-study.json"})
        backups = c.of("backups")[-1]
        await hub.handle({"type": "workflow_remove", "id": wid})
        removed = c.of("workflows_list")[-1]
        return no_out, saved, dup, edited, backups, removed, data

    no_out, saved, dup, edited, backups, removed, data = asyncio.run(go())
    assert "output folder" in no_out
    assert "error" not in saved
    w = saved["workflows"][0]
    assert w["slug"] == "claims-study" and not w["can_run"]                      # missing file saved, blocks Run
    assert [f["path"] for f in w["files"]] == ["docs/method.md", "docs/missing.md"]
    assert "already exists" in dup
    e = edited["workflows"][0]
    assert e["name"] == "Claims study v2" and e["slug"] == "claims-study" and e["can_run"]
    assert data["format"] == 1 and data["stages"][1]["checklist"][0] == {"text": "Counts match", "kind": "tick"}
    assert backups["items"]
    assert removed["workflows"] == [] and not (project / "workflows" / "claims-study.json").exists()


# --------------------------------------------------------------------------- the shipped example + the demo
def test_shipped_example_is_valid():
    from app.workflows import format as fmt
    path = Path(__file__).resolve().parent.parent / "app" / "workflows" / "example-workflow.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    clean, warns = fmt.check(raw, path.parent)
    assert not fmt.blocking(warns), warns
    kinds = [s["kind"] for s in clean["stages"]]
    assert "review" in kinds and "agent" in kinds and clean["inputs"]


def test_fake_demo_seeds_a_run_waiting_at_its_review(tmp_path):
    from app import demo
    shop = tmp_path / "Demo shop"
    ex_rel, ex_text = demo.example_workflow_file()
    files = {**demo.workflow_files(), ex_rel: ex_text,
             f".claude/agents/{demo.FOLDER_AGENT_NAME}.md": demo.FOLDER_AGENT_FILE}
    for rel, text in files.items():
        (shop / rel).parent.mkdir(parents=True, exist_ok=True)
        (shop / rel).write_text(text, encoding="utf-8")
    demo.install(shop)

    async def go():
        hub = Hub(Settings(project=shop, engine="fake", demo=True))
        c = Client(hub)
        await hub.connect(c)
        await wait(lambda: (last_run(c) or {}).get("status") == "awaiting_review")
        run = last_run(c)
        names = sorted(w["name"] for w in c.of("workflows_list")[-1]["workflows"])
        assert names == ["Example: weekly status note", "Monthly sales report"]
        await hub.handle({"type": "workflow_review", "run_id": run["id"], "stage": 3, "decision": "approve",
                          "name": "Sales lead", "answers": [{"ticked": True}, {"ticked": True}, {"answer": "Quiet month"}]})
        await wait(lambda: last_run(c)["status"] in ("done", "failed"))
        return c, run

    c, run = asyncio.run(go())
    no_errors(c)
    assert run["workflow_name"] == "Monthly sales report" and run["current_stage"] == 3
    assert [s["status"] for s in run["stages"][:3]] == ["done", "done", "done"]
    assert run["stages"][1]["result_markdown"] and "85.50" in run["stages"][1]["result_markdown"]
    final = last_run(c)
    assert final["status"] == "done", final
    assert "October sales" in final["stages"][4]["result_markdown"]


# --------------------------------------------------------------------------- the real load path of every stage agent
READER = """---
name: figure-checker
description: Checks figures against a method and lists what looks off.
purpose: reviewing
tools: Read, Grep, Glob
---
- Check the figures; list problems, one line each.
"""


def test_explorer_and_folder_agent_stages_load_and_run(project):
    docs(project)
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "agents" / "figure-checker.md").write_text(READER, encoding="utf-8")
    put(project, "mixed", wf_def(name="Mixed", files=[], inputs=[], stages=[
        {"kind": "agent", "title": "Find inputs", "agent": "launchpad-astronaut", "instruction": "Find the data."},
        {"kind": "agent", "title": "Check figures", "agent": "figure-checker", "instruction": "Check them."},
        {"kind": "agent", "title": "Write report", "agent": "launchpad-builder", "instruction": "Write it."}]))
    seen = {}

    def reader(name):
        def turn(msg):
            seen[name] = msg
            return [fake.call("Read", {"file_path": "docs/method.md"}),
                    fake.call("Write", {"file_path": "docs/method.md", "content": "x"}),      # read-only: refused
                    fake.call("submit_report", {"result": f"{name} found things", "status": "done"})]
        return [turn]
    fake.script("launchpad-astronaut", reader("explorer"))
    fake.script("figure-checker", reader("checker"))
    script_builder([])

    async def go():
        hub = make_hub(project)
        c = Client(hub)
        await hub.connect(c)
        w = c.of("workflows_list")[-1]["workflows"][0]
        assert w["can_run"], w["warnings"]
        await hub.handle({"type": "workflow_run", "id": w["id"], "inputs": {}})
        await wait(lambda: (last_run(c) or {}).get("status") in ("done", "failed"))
        return c

    c = asyncio.run(go())
    no_errors(c)
    run = last_run(c)
    assert run["status"] == "done", [s["error"] for s in run["stages"]]
    assert [s["agent_display"] for s in run["stages"]] == ["Explorer", "Figure checker", "Builder"]
    assert "explorer found things" in run["stages"][0]["result_markdown"]
    assert "checker found things" in run["stages"][1]["result_markdown"]
    assert "read-only" in seen["explorer"] and "explorer found things" in seen["checker"]
    # the read-only agents' Write is denied by their deny list: never a card
    assert not [q for q in c.of("queue_item") if q["kind"] == "permission"]


def test_fake_demo_sample_workflow_runs_from_the_start(tmp_path):
    """A new run of the demo's sample (Explorer, Builder, copy-reviewer, review) gets to its review; unattended
    answers the Builder's question with its recommendation."""
    from app import demo
    shop = tmp_path / "Demo shop"
    files = {**demo.workflow_files(), f".claude/agents/{demo.FOLDER_AGENT_NAME}.md": demo.FOLDER_AGENT_FILE}
    for rel, text in files.items():
        (shop / rel).parent.mkdir(parents=True, exist_ok=True)
        (shop / rel).write_text(text, encoding="utf-8")
    demo.install(shop)

    async def go():
        hub = Hub(Settings(project=shop, engine="fake", question_timeout_s=30))
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "unattended": True, "inputs": {}})
        await wait(lambda: (last_run(c) or {}).get("status") in ("awaiting_review", "failed", "done"))
        return c, last_run(c)

    c, run = asyncio.run(go())
    no_errors(c)
    assert run["status"] == "awaiting_review", [s["error"] for s in run["stages"]]
    assert [s["status"] for s in run["stages"]] == ["done", "done", "done", "awaiting_review", "waiting"]
    autos = c.of("auto_answer")
    assert autos and autos[0]["answer"] == "Two decimals, as the method says"
    assert autos[0]["session_id"] == run["mission_id"]
    assert not [q for q in c.of("queue_item") if q["kind"] == "question"]
