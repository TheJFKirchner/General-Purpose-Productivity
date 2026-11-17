"""Undefined roles (request 2026-11-17 role review, task 2): the plan step `role`, the per-user tally (record, threshold,
dismiss, resurfacing, merge, concurrent writes, send-back), the planner's role list, the Role Reviewer (case, questions,
read-only, one at a time), the define path through the drafter, and the fake demo. Fake engine only, zero tokens."""
from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap

import pytest

from agentlib import fake

from app import demo
from app import plan as plan_mod
from app.agents import crew
from app.agents.role_reviewer import reviewer
from app.hub import Hub
from app.settings import Settings
from app.store import Store, launchpad_home
from app.tally import RESURFACE_USES, Tally, TallyError, visibility

from conftest import ROOT, Client, report

ROLE_PLAN = {
    "name": "Role plan",
    "goal": "Tune a query, then write notes.",
    "steps": [
        {"title": "Tune the slow query", "details": "Rewrite the orders query with an index.", "done_when": "It is fast.",
         "role": "sql-tuner", "skills": ["sql-style"]},
        {"title": "Write notes", "details": "Note what changed.", "done_when": "Notes exist.", "after": [1]},
    ],
}


def use(**kw) -> dict:
    u = {"session_id": "S1", "run": 1, "step": 1, "title": "Do it", "outcome": "done", "dir_id": "d1", "folder": "proj"}
    u.update(kw)
    return u


def script_two_steps(step1: list | None = None) -> None:
    from conftest import script_orchestrator_sequential
    script_orchestrator_sequential(2)
    first = step1 or [fake.call("submit_report", report())]
    fake.script("launchpad-builder", [lambda msg: first if "Build step 1" in msg else
                                      [fake.call("submit_report", report())]])


# --------------------------------------------------------------------------- plan.md role field
def test_plan_round_trip_with_role_and_old_plans_load():
    text = plan_mod.render(name="P", goal="G", steps=[dict(s) for s in ROLE_PLAN["steps"]], session="S")
    assert plan_mod.validate(text) == []
    p = plan_mod.parse(text)
    assert [s["role"] for s in p["steps"]] == ["sql-tuner", None]
    assert 'role: "sql-tuner"' in text and text.count("role:") == 1           # written only when set
    f = plan_mod.to_fields(text)
    assert f["steps"][0]["role"] == "sql-tuner"
    again = plan_mod.render(name=f["name"], goal=f["goal"], steps=f["steps"], session="S")
    assert plan_mod.parse(again)["steps"] == p["steps"]
    old = plan_mod.render(name="Old", goal="G", steps=[{"title": "A", "details": "a", "done_when": "x"}], session="S")
    assert "role" not in old and plan_mod.parse(old)["steps"][0]["role"] is None
    edited, _ = plan_mod.apply_edits(text, [{"op": "set_step", "n": 2, "role": "Tech Writer"},
                                            {"op": "add_step", "title": "C", "details": "c", "role": "qa-checker"}],
                                     session="S")
    assert [s["role"] for s in plan_mod.parse(edited)["steps"]] == ["sql-tuner", "tech-writer", "qa-checker"]
    cleared, _ = plan_mod.apply_edits(edited, [{"op": "set_step", "n": 2, "role": ""}], session="S")
    assert plan_mod.parse(cleared)["steps"][1]["role"] is None


def test_agent_and_role_together_are_rejected():
    both = plan_mod.render(name="P", goal="G", session="S", steps=[
        {"title": "A", "details": "a", "done_when": "x", "agent": "copy-reviewer", "role": "copy-editor"}])
    assert any("agent or role, not both" in p for p in plan_mod.validate(both))
    bad = plan_mod.render(name="P", goal="G", session="S", steps=[{"title": "A", "details": "a", "role": "x" * 41}])
    assert any("role must be a short slug" in p for p in plan_mod.validate(bad))
    text = plan_mod.render(name="P", goal="G", steps=[dict(s) for s in ROLE_PLAN["steps"]], session="S")
    with pytest.raises(plan_mod.PlanError):
        plan_mod.apply_edits(text, [{"op": "set_step", "n": 1, "agent": "copy-reviewer", "role": "sql-tuner"}], session="S")
    swapped, _ = plan_mod.apply_edits(text, [{"op": "set_step", "n": 1, "agent": "copy-reviewer"}], session="S")
    step = plan_mod.parse(swapped)["steps"][0]
    assert step["agent"] == "copy-reviewer" and step["role"] is None           # a listed agent replaces the role


def test_write_plan_with_agent_and_role_is_refused_to_the_planner(harness):
    h = harness()
    bad = {"name": "P", "goal": "G", "steps": [{"title": "A", "details": "a", "done_when": "x",
                                                 "agent": "launchpad-builder", "role": "sql-tuner"}]}
    fake.script("launchpad-planner", [[fake.call("write_plan", bad), fake.say("ok")]])

    async def go():
        hub, c = await h.start()
        chat = hub.current.chat
        chat.session = chat.agent.session()
        await chat.session.__aenter__()
        return await chat.session.send("plan"), c

    reply, c = asyncio.run(go())
    call = reply.tool_calls[0]
    assert call.is_error and "not both" in call.result and not c.of("plan_draft")


# --------------------------------------------------------------------------- recording from a run
def test_role_step_is_recorded_with_its_evidence(harness, project):
    (project / ".claude" / "skills" / "sql-style").mkdir(parents=True)
    (project / ".claude" / "skills" / "sql-style" / "SKILL.md").write_text(
        "---\nname: sql-style\ndescription: SQL rules\n---\n- Upper-case keywords\n", encoding="utf-8")
    h = harness(timeout_s=0.1)
    fake.script("launchpad-planner", [[fake.call("write_plan", ROLE_PLAN), fake.say("Draft saved.")]])
    script_two_steps([fake.call("ask_question", {"title": "Which index?", "body": "Two fit.", "recommended": "btree"}),
                      fake.call("submit_report", report(assumptions=["The table is small"]))])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "plan it"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    assert c.of("plan_draft")[-1]["steps"][0]["role"] == "sql-tuner" and "role" not in c.of("plan_draft")[-1]["steps"][1]
    assert c.of("run_started")[-1]["steps"][0]["role"] == "sql-tuner"
    entries = hub.tally.entries()
    assert [e["name"] for e in entries] == ["sql-tuner"]                     # the plain step is not tallied
    e = entries[0]
    assert e["base_agent"] == "Builder" and e["purpose"] == "building" and e["uses_total"] == 1
    assert e["skills"] == ["sql-style"] and e["folders"] == [{"dir_id": hub.current.dir_id, "name": project.name}]
    u = e["uses"][0]
    assert (u["session_id"], u["run"], u["step"], u["title"]) == (hub.current.id, 1, 1, "Tune the slow query")
    assert u["outcome"] == "done" and u["questions"] == 1 and u["timed_out"] == 1
    assert u["assumptions"] == 2                                           # the timer's + the report's
    assert u["sent_back"] is False and u["named_agent"] is False and u["project"] == str(project.resolve())
    assert e["samples"][0]["text"].startswith("### Step 1: Tune the slow query")
    listed = c.of("roles_list")[-1]["entries"][0]
    assert listed["name"] == "sql-tuner" and listed["state"] == "few_uses" and listed["visible"] is False
    assert "project" not in listed["uses"][0]
    assert [e["uses"] for e in c.of("agent_uses") if e["name"] == "launchpad-builder"][-1] == 2   # unchanged count


def test_registered_agent_not_recorded_and_missing_agent_tallied_under_its_name(harness, project):
    agents = project / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "copy-reviewer.md").write_text(demo.FOLDER_AGENT_FILE, encoding="utf-8")
    plan = {"name": "P", "goal": "G", "steps": [
        {"title": "Review", "details": "Review it.", "done_when": "Done.", "agent": "copy-reviewer"},
        {"title": "Gone", "details": "Use the old helper.", "done_when": "Done.", "agent": "old-helper"}]}
    h = harness()
    fake.script("launchpad-planner", [[fake.call("write_plan", plan), fake.say("Draft saved.")]])
    from conftest import script_orchestrator_sequential
    script_orchestrator_sequential(2)
    fake.script("copy-reviewer", [[fake.call("submit_report", report())]])
    fake.script("launchpad-builder", [[fake.call("submit_report", report(status="failed"))]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "plan it"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        return hub

    hub = asyncio.run(go())
    entries = hub.tally.entries()
    assert [e["name"] for e in entries] == ["old-helper"]
    u = entries[0]["uses"][0]
    assert u["named_agent"] is True and u["outcome"] == "failed" and u["step"] == 2


# --------------------------------------------------------------------------- tally rules
def test_two_use_threshold_and_dismiss_then_reappear():
    t = Tally(None)
    e = t.record_use("sql-tuner", use=use())
    assert visibility(e)["state"] == "few_uses" and not visibility(e)["visible"]
    e = t.record_use("sql-tuner", use=use(step=2))
    assert visibility(e) == {"state": "listed", "visible": True, "uses_to_list": 0, "resurfaced": False}
    assert visibility(t.dismiss("sql-tuner"))["state"] == "dismissed"
    assert not t.list_event()["entries"][0]["visible"]
    e = t.record_use("sql-tuner", use=use(step=3))                           # used again: back
    assert visibility(e)["visible"] and e["dismissed"] is False
    with pytest.raises(TallyError):
        t.dismiss("nope")


@pytest.mark.parametrize("decision", ["keep", "not_yet"])
def test_keep_or_not_yet_rest_until_five_more_uses(decision):
    t = Tally(None)
    for k in range(3):
        t.record_use("frontend-dev", use=use(step=k))
    e = t.set_decision("frontend-dev", decision, reviewer_verdict="keep")
    v = visibility(e)
    assert v["state"] == "resting" and not v["visible"] and v["uses_to_list"] == RESURFACE_USES
    for k in range(RESURFACE_USES - 1):
        e = t.record_use("frontend-dev", use=use(step=10 + k))
    assert visibility(e)["state"] == "resting"
    e = t.record_use("frontend-dev", use=use(step=99))
    assert visibility(e) == {"state": "listed", "visible": True, "uses_to_list": 0, "resurfaced": True}


@pytest.mark.parametrize("problem", ["failed", "blocked", "sent_back"])
def test_resting_role_resurfaces_on_a_new_problem_use(problem):
    t = Tally(None)
    t.record_use("frontend-dev", use=use(outcome="failed"))                 # a problem BEFORE the decision
    t.record_use("frontend-dev", use=use(step=2))
    t.set_decision("frontend-dev", "not_yet")
    assert visibility(t.record_use("frontend-dev", use=use(session_id="S2", step=1)))["state"] == "resting"
    if problem == "sent_back":
        assert t.mark_sent_back("S2", 1) == 1
        e = t.get("frontend-dev")
    else:
        e = t.record_use("frontend-dev", use=use(session_id="S3", outcome=problem))
    assert visibility(e)["resurfaced"] is True


def test_define_decision_stays_listed_until_created():
    t = Tally(None)
    t.record_use("data-migrator", use=use())
    t.record_use("data-migrator", use=use(step=2))
    assert visibility(t.set_decision("data-migrator", "define"))["state"] == "defining"
    assert t.remove("data-migrator") and t.get("data-migrator") is None and not t.remove("data-migrator")
    with pytest.raises(TallyError):
        t.set_decision("x", "maybe")


def test_merge_folds_one_entry_into_another():
    t = Tally(None)
    t.record_use("sql-tuner", use=use(skills=["sql-style"], dir_id="d1", folder="a"), sample="tune A")
    t.record_use("sql-tuning", use=use(skills=["perf"], dir_id="d2", folder="b", outcome="failed"), sample="tune B")
    t.record_use("sql-tuning", use=use(step=2, dir_id="d2", folder="b"), sample="tune C")
    e = t.merge("sql-tuning", "sql-tuner")
    assert t.get("sql-tuning") is None and e["uses_total"] == 3 and len(e["uses"]) == 3
    assert e["skills"] == ["sql-style", "perf"] and [f["dir_id"] for f in e["folders"]] == ["d1", "d2"]
    assert [s["text"] for s in e["samples"]] == ["tune A", "tune B", "tune C"]
    assert [u["seq"] for u in e["uses"]] == sorted(u["seq"] for u in e["uses"])
    with pytest.raises(TallyError):
        t.merge("sql-tuner", "sql-tuner")


def test_samples_keep_three_distinct_and_uses_keep_twenty():
    t = Tally(None)
    for k in range(25):
        e = t.record_use("r", use=use(step=k), sample=f"text {k % 5}" if k < 10 else "text 0")
    assert e["uses_total"] == 25 and len(e["uses"]) == 20 and e["uses"][0]["step"] == 5
    assert len(e["samples"]) == 3 and len({s["text"] for s in e["samples"]}) == 3


def test_writes_from_two_processes_both_survive(tmp_path):
    """Two Launchpad processes writing the same tally at once: re-read + lock + replace, nothing lost."""
    path = tmp_path / "home" / "roles.json"
    a, b = Tally(path), Tally(path)
    a.record_use("one", use=use())
    b.record_use("two", use=use())                                          # b never loaded before writing
    a.record_use("one", use=use(step=2))
    assert {e["name"]: e["uses_total"] for e in Tally(path).entries()} == {"one": 2, "two": 1}
    code = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(ROOT)!r})
        from app.tally import Tally
        t = Tally({str(path)!r})
        for k in range(15):
            t.record_use(sys.argv[1], use={{"session_id": "S", "run": 1, "step": k}})
    """)
    procs = [subprocess.Popen([sys.executable, "-c", code, name]) for name in ("proc-a", "proc-b")]
    assert [p.wait(timeout=60) for p in procs] == [0, 0]
    counts = {e["name"]: e["uses_total"] for e in Tally(path).entries()}
    assert counts == {"one": 2, "two": 1, "proc-a": 15, "proc-b": 15}
    assert not path.with_name("roles.json.lock").exists()


def test_send_back_marks_the_right_runs_uses(harness):
    h = harness()
    fake.script("launchpad-planner", [[fake.call("write_plan", ROLE_PLAN), fake.say("Draft saved.")]] * 3)
    script_two_steps()

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "plan it"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: len(c.of("run_finished")) == 1)
        first = hub.current
        await hub.new_session()                                            # another session's use stays unmarked
        await hub.handle({"type": "user_message", "text": "plan it"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: len(c.of("run_finished")) == 2)
        await first.save_plan(ROLE_PLAN)                                   # revised draft after run 1 = sent back
        return hub, first

    hub, first = asyncio.run(go())
    uses = hub.tally.get("sql-tuner")["uses"]
    assert {(u["session_id"], u["run"]): u["sent_back"] for u in uses} == {(first.id, 1): True,
                                                                           (hub.current.id, 1): False}


def test_planner_sees_at_most_twenty_recent_role_names(harness):
    h = harness()

    async def go():
        hub, _ = await h.start()
        for k in range(25):
            hub.tally.record_use(f"role-{k:02d}", use=use())
        return hub.current.chat.context_note()

    note = asyncio.run(go())
    line = next(ln for ln in note.splitlines() if ln.startswith("Role names in use"))
    names = line.split(": ", 1)[1].split(", ")
    assert names == [f"role-{k:02d}" for k in range(24, 4, -1)] and len(names) == 20


# --------------------------------------------------------------------------- the Role Reviewer
def case_data(verdict="keep", questions=(), **kw) -> dict:
    tests = [{"test": k, "finding": f"{k} finding", "strength": "moderate",
              "evidence": [{"quote": f"quote {k}", "source": "session S1 step 1"}]} for k, _ in reviewer.TESTS]
    d = {"tests": tests, "history_thin": False, "verdict": verdict, "reason": "Because.",
         "skill_notes": "- cover X" if verdict == "keep" else "",
         "proposal": ({"name": "sql-tuner", "purpose": "building", "description": "Tunes SQL.",
                       "instructions": "- Check the plan first."} if verdict == "define" else
                      {"name": "", "purpose": "", "description": "", "instructions": ""}),
         "questions": list(questions)}
    d.update(kw)
    return d


def user_hub(project, responder=None) -> tuple[Hub, Client]:
    """A hub with a per-user store in the test's home (so the tally and case files are files)."""
    settings = Settings(project=project, engine="fake", question_timeout_s=5)
    hub = Hub(settings, store=Store(launchpad_home() / "settings.json"))
    return hub, Client(hub, responder)


def seed(hub, name="sql-tuner", n=3, project=None, **kw):
    for k in range(n):
        hub.tally.record_use(name, use=use(step=k + 1, project=str(project or ""), **kw), sample=f"step text {k}")


def test_review_produces_a_case_with_five_sections_verdict_tokens_and_cost(project):
    fake.script("launchpad-role-reviewer", [[fake.spend(0.012), fake.output(case_data("keep"))]])

    async def go():
        hub, c = user_hub(project)
        await hub.connect(c)
        seed(hub, project=project)
        await hub.handle({"type": "review_start", "role": "sql-tuner"})
        return hub, c

    hub, c = asyncio.run(go())
    started, case_ev = c.of("review_started")[0], c.of("review_case")[0]
    assert started["role"] == "sql-tuner" and started["model"] == "sonnet"
    assert c.of("review_progress") and c.of("review_progress")[0]["phase"] == "reading"
    case = case_ev["case"]
    assert [s["test"] for s in case["sections"]] == ["value", "logic", "history", "fixes", "independent"]
    assert all(s["finding"] and s["strength"] == "moderate" and s["evidence"] for s in case["sections"])
    assert case["verdict"] == "keep" and case["reason"] == "Because." and case["skill_notes"] == "- cover X"
    cost = case["usage"]["cost"]
    assert cost >= 0.012 and case["usage"]["tokens"] > 0 and case["usage"]["output_tokens"] >= 0
    assert case["decision"] is None and case["uses_total"] == 3
    path = hub.tally.cases_dir / case["case_file"]
    text = path.read_text(encoding="utf-8")
    assert "# Role review: sql-tuner" in text and f"Cost: ${cost:.4f}" in text and "## 5. Independent view" in text
    app = [e for e in c.of("usage") if e.get("scope") == "app"][-1]
    assert app["by_role"]["reviewer"] == pytest.approx(cost)                  # app-wide only
    assert all(e["cost"] == 0 for e in c.of("usage") if e.get("scope") == "session")
    rv = [e for e in c.of("agent_usage") if e["role"] == "reviewer"][-1]
    assert rv["session_id"] is None and rv["chat_id"] is None and rv["name"] == "Role Reviewer"
    assert hub.tally.get("sql-tuner")["last_review"]["verdict"] == "keep"
    assert not hub.reviews.running and c.of("roles_list")[-1]["entries"][0]["reviewing"] is False
    asyncio.run(_decide(hub, c, "not_yet"))                                   # the user may differ from the reviewer
    assert hub.tally.get("sql-tuner")["verdict"]["decision"] == "not_yet"
    assert hub.tally.get("sql-tuner")["verdict"]["reviewer_verdict"] == "keep"
    assert c.of("review_decided")[-1]["decision"] == "not_yet"
    assert "## Decision (user): Not yet" in path.read_text(encoding="utf-8")
    assert c.of("roles_list")[-1]["entries"][0]["state"] == "resting"


async def _decide(hub, c, decision):
    await hub.connect(c)
    await hub.handle({"type": "review_decide", "role": "sql-tuner", "decision": decision})


def test_reviewer_questions_reach_the_user_and_are_never_auto_answered(project):
    q = {"test": "logic", "question": "Is the index rule always wanted?", "why": "Steps repeat it.",
         "recommended": "Yes"}
    seen = []

    def second(msg):
        seen.append(msg)
        return [fake.output(case_data("not_yet"))]
    fake.script("launchpad-role-reviewer", [[fake.output(case_data("not_yet", [q]))], second])

    def responder(ev):
        if ev.get("type") == "queue_item" and ev.get("review_id"):
            return {"type": "queue_response", "id": ev["id"], "answer": "Only for big tables"}
        return None

    async def go():
        hub, c = user_hub(project, responder)
        await hub.connect(c)
        await hub.set_auto_answers(hub.current.id, True)                    # Auto answers on: builders only
        seed(hub)
        await hub.handle({"type": "review_start", "role": "sql-tuner"})
        return c

    c = asyncio.run(go())
    card = c.of("queue_item")[0]
    assert card["kind"] == "question" and card["session_id"] is None and card["chat_id"] is None
    assert card["agent"] == "Role Reviewer" and card["role"] == "sql-tuner" and card["review_id"]
    assert card["rec"] == "Yes" and card["timeout_s"] == 5
    assert not c.of("auto_answer") and c.of("queue_resolved")[0]["by"] == "user"
    assert seen and "Only for big tables" in seen[0]
    case = c.of("review_case")[0]["case"]
    assert case["questions"][0]["answer"] == "Only for big tables"
    assert [e["phase"] for e in c.of("review_progress")][-2:] == ["asking", "finalising"]


def test_reviewer_is_read_only_and_kept_to_its_brief(project):
    a = reviewer.load_agent(engine="fake", project=project, model="sonnet", on_permission=lambda r: "deny")
    r = a.resolved_tools()
    assert sorted(r.builtin_rules) == ["Glob", "Grep", "Read"] and r.custom == [] and r.approved_rules == []
    assert {"Write", "Edit", "Bash"} <= set(a.disallowed_tools) and a.setup == "lean"
    session = project / ".launchpad" / "S1"
    (session / "steps").mkdir(parents=True)
    (session / "steps" / "step-01.md").write_text("# Step 1\n", encoding="utf-8")
    fake.script("launchpad-role-reviewer", [[
        fake.call("Read", {"file_path": str(session / "steps" / "step-01.md")}),
        fake.call("Read", {"file_path": str(project / "app" / "main.py")}),          # code: refused
        fake.call("Grep", {"pattern": "x"}),                                         # no path: refused
        fake.call("Write", {"file_path": str(session / "x.md"), "content": "x"}),
        fake.output(case_data())]])
    results = []

    async def go():
        hub, c = user_hub(project)
        await hub.connect(c)
        seed(hub, project=project, session_id="S1")
        await hub.handle({"type": "review_start", "role": "sql-tuner"})
        return c

    c = asyncio.run(go())
    acts = {}
    for e in c.of("activity"):
        if e["role"] == "reviewer" and e["status"] != "started":
            acts.setdefault(e["tool"], []).append(e["status"])
    assert acts["Read"] == ["done", "denied"] and acts["Grep"] == ["denied"] and acts["Write"] != ["done"]
    assert c.of("review_case")


def test_brief_reading_depth_and_missing_session_folders(project):
    t = Tally(None)
    for k in range(1, 9):
        sid = f"S{k}"
        if k != 8:                                                            # S8's folder is gone
            d = project / ".launchpad" / sid
            (d / "steps").mkdir(parents=True)
        t.record_use("r", use=use(session_id=sid, step=1, project=str(project),
                                  outcome="failed" if k == 1 else "done", sent_back=k == 2))
    brief, roots, seen = reviewer.build_brief(t.get("r"))
    assert seen["opened"] == ["U7", "U6", "U5", "U4", "U2", "U1"] and seen["missing"] == ["U8"]
    assert "U3 (session" not in brief and brief.count("U3 |") == 1           # tally line only
    assert brief.count("- activity.log:") == 2                               # problem uses only (U1 failed, U2 sent back)
    assert "U8: session folder gone" in brief and len([ln for ln in brief.splitlines() if ln.startswith("U")]) >= 8
    assert crew.agent_file("builder") in roots and (project / ".launchpad" / "S3") not in roots


def test_brief_finds_skills_in_the_additional_folders_like_a_session(project, tmp_path):
    extra = tmp_path / "extra-folder"
    skill = extra / ".claude" / "skills" / "sql-style"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: sql-style\ndescription: SQL rules\n---\nBody\n", encoding="utf-8")
    t = Tally(None)
    t.record_use("r", use=use(skills=["sql-style"], project=str(project), extra_projects=[str(extra)]))
    brief, roots, _ = reviewer.build_brief(t.get("r"))
    assert (skill / "SKILL.md").as_posix() in brief and "SKILL.md not found" not in brief
    assert skill in roots
    assert "extra_projects" not in t.list_event(set())["entries"][0]["uses"][0]       # never sent to the page
    t2 = Tally(None)                                                                  # no additional folders recorded: not found
    t2.record_use("r", use=use(skills=["sql-style"], project=str(project)))
    assert "SKILL.md not found" in reviewer.build_brief(t2.get("r"))[0]


def test_one_review_at_a_time_and_a_failed_review_stays_reviewable(project):
    q = {"test": "value", "question": "Worth it?", "why": "No record says.", "recommended": "No"}

    async def go():
        fake.script("launchpad-role-reviewer", [[fake.fail("engine down")]])
        hub, c = user_hub(project)
        await hub.connect(c)
        seed(hub)
        await hub.handle({"type": "review_start", "role": "sql-tuner"})
        assert c.of("review_failed") and "engine down" in c.of("review_failed")[0]["error"]
        assert not hub.reviews.running and c.of("roles_list")[-1]["entries"][0]["reviewing"] is False
        fake.script("launchpad-role-reviewer", [[fake.output(case_data("keep", [q]))], [fake.output(case_data())]])
        first = asyncio.create_task(hub.handle({"type": "review_start", "role": "sql-tuner"}))
        while not c.of("queue_item"):                                        # the first review waits on its card
            await asyncio.sleep(0.01)
        assert c.of("roles_list")[-1]["entries"][0]["reviewing"] is True
        await hub.handle({"type": "review_start", "role": "sql-tuner"})        # while the first runs: refused
        await hub.handle({"type": "queue_response", "id": c.of("queue_item")[0]["id"], "answer": "No"})
        await first
        await hub.handle({"type": "review_start", "role": "unknown-role"})
        return c

    c = asyncio.run(go())
    refused = c.of("review_refused")
    assert refused[0]["role"] == "sql-tuner" and "already running" in refused[0]["error"]
    assert "no role" in refused[1]["error"]
    assert len(c.of("review_case")) == 1


def test_define_path_feeds_the_drafter_and_create_removes_the_entry(project):
    fake.script("launchpad-role-reviewer", [[fake.output(case_data("define"))]])
    drafted = []

    def drafter_turn(msg):
        drafted.append(msg)
        return [fake.spend(0.0004), fake.output({"name": "sql-tuner", "description": "Tunes SQL.", "purpose": "building",
                                                 "model": "sonnet", "tools": ["Read", "Edit"],
                                                 "instructions": "- Check the plan first."})]
    fake.script("launchpad-drafter", [drafter_turn])

    async def go():
        hub, c = user_hub(project)
        await hub.connect(c)
        seed(hub, skills=["sql-style"])
        await hub.handle({"type": "review_start", "role": "sql-tuner"})
        await hub.handle({"type": "review_decide", "role": "sql-tuner", "decision": "define"})
        assert c.of("roles_list")[-1]["entries"][0]["state"] == "defining"
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "", "role": "sql-tuner"})
        fields = c.of("agent_drafted")[-1]["fields"]
        await hub.handle({"type": "agent_create", "dir_id": hub.default_dir, "fields": fields, "role": "sql-tuner"})
        return hub, c

    hub, c = asyncio.run(go())
    msg = drafted[0]
    assert "Reviewer's proposed name: sql-tuner" in msg and "Instructions the agent needs beyond the skill" in msg
    assert "Sample step 1: step text 0" in msg and "sql-style" in msg
    d = c.of("agent_drafted")[-1]
    assert d["ok"] and d["role"] == "sql-tuner" and d["usage"]["cost"] >= 0.0004
    assert set(d["fields"]) == {"name", "description", "purpose", "model", "tools", "instructions"}
    saved = c.of("agent_saved")[-1]
    assert saved["ok"] and saved["role"] == "sql-tuner" and saved["case_path"] == ".claude/agent-cases/sql-tuner.md"
    assert hub.tally.get("sql-tuner") is None and c.of("roles_list")[-1]["entries"] == []
    copy = project / ".claude" / "agent-cases" / "sql-tuner.md"
    assert copy.is_file() and "Agent created: sql-tuner" in copy.read_text(encoding="utf-8")
    assert [e["name"] for e in crew.folder_agents(project)] == ["sql-tuner"]          # the case is not an agent
    cards = [a["name"] for a in c.of("crew_list")[-1]["agents"] if not a["builtin"]]
    assert cards == ["sql-tuner"]
    case_file = hub.tally.cases_dir / c.of("review_case")[0]["case"]["case_file"]
    assert "Decision (user): Define an agent" in case_file.read_text(encoding="utf-8")


def test_plain_agent_draft_still_works_and_reports_its_cost(harness):
    h = harness()
    fake.script("launchpad-drafter", [[fake.spend(0.0003), fake.output(demo.draft_fields("reviews copy"))]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "an agent that reviews copy"})
        return c

    d = asyncio.run(go()).of("agent_drafted")[-1]
    assert d["ok"] and "role" not in d and d["usage"]["cost"] >= 0.0003 and "tokens" in d["usage"]


# --------------------------------------------------------------------------- the fake demo
def test_demo_tally_and_reviewer_walk_all_three_verdicts(project):
    demo.install(project)

    def responder(ev):
        if ev.get("type") == "queue_item" and ev.get("review_id"):
            return {"type": "queue_response", "id": ev["id"], "answer": ev["rec"]}
        return None

    async def go():
        hub, c = user_hub(project, responder)
        demo.seed_tally(hub.tally, hub.store)
        await hub.connect(c)
        for role in ("frontend-dev", "copy-editor", "data-migrator"):
            await hub.handle({"type": "review_start", "role": role})
        await hub.handle({"type": "review_decide", "role": "data-migrator", "decision": "define"})
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "", "role": "data-migrator"})
        return hub, c

    hub, c = asyncio.run(go())
    states = {e["name"]: e["state"] for e in c.of("roles_list")[0]["entries"]}
    assert states == {"release-checker": "few_uses", "frontend-dev": "listed", "copy-editor": "listed",
                      "data-migrator": "listed"}
    assert next(e for e in c.of("roles_list")[0]["entries"] if e["name"] == "data-migrator")["problems"] == 1
    verdicts = {e["role"]: e["case"]["verdict"] for e in c.of("review_case")}
    assert verdicts == {"frontend-dev": "keep", "copy-editor": "not_yet", "data-migrator": "define"}
    assert len([e for e in c.of("queue_item") if e.get("review_id")]) == 1
    migr = next(e["case"] for e in c.of("review_case") if e["role"] == "data-migrator")
    assert migr["missing"] and migr["proposal"]["name"] == "data-migrator"
    assert c.of("agent_drafted")[-1]["fields"]["name"] == "data-migrator"
    assert c.of("agent_drafted")[-1]["fields"]["purpose"] == "building"


def test_demo_plan_step_carries_a_role():
    assert [s.get("role") for s in demo.PLAN["steps"]] == [None, "frontend-dev", None, None]


def test_fake_launch_never_touches_the_real_store(tmp_path, monkeypatch):
    import argparse
    import tempfile
    from pathlib import Path
    from app import launch
    from app.agents.planner import planner
    real_home = tmp_path / "real-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: real_home))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    monkeypatch.delenv("LAUNCHPAD_HOME", raising=False)
    for name in ("APP_ROOT", "AGENTS_DIR"):
        monkeypatch.setattr(crew, name, getattr(crew, name))
    monkeypatch.setattr(planner, "CRITERIA_FILE", planner.CRITERIA_FILE)
    args = argparse.Namespace(fake=True, cwd="", model=None)
    settings, store, _ = launch.build_settings(args)
    hub = Hub(settings, store=store)
    demo_home = tmp_path / "tmp" / "launchpad-demo" / "home"
    assert hub.tally.path == demo_home / "roles.json" and hub.tally.path.is_file()
    assert {e["name"] for e in hub.tally.entries()} == set(demo.DEMO_ROLES)
    assert (tmp_path / "tmp" / "launchpad-demo" / "app-files" / "app" / "agents" / "role_reviewer" / "agent.md").is_file()
    assert not (real_home / ".launchpad").exists()
    # a fake hub whose store is NOT in a temp folder keeps its tally in memory
    elsewhere = Hub(Settings(project=settings.project, engine="fake"), store=Store(real_home / ".launchpad" / "settings.json"))
    assert elsewhere.tally.path is None
