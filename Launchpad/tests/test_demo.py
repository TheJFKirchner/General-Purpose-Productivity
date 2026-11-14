"""The --fake demo script runs the whole loop: draft, approval, 3 steps, timed + blocking question, permission card."""
import asyncio

from app import demo


def test_demo_runs_end_to_end(harness, project):
    def responder(ev):
        if ev.get("type") != "queue_item":
            return None
        if ev["kind"] == "permission":
            return {"type": "queue_response", "id": ev["id"], "decision": "allow"}
        if ev["blocking"]:
            return {"type": "queue_response", "id": ev["id"], "answer": ev["rec"]}
        return None                                               # timed question: let the timer answer

    h = harness(timeout_s=0.2, responder=responder)
    demo.install(project)
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "agents" / f"{demo.FOLDER_AGENT_NAME}.md").write_text(demo.FOLDER_AGENT_FILE, encoding="utf-8")

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "Refresh the landing page"})
        rnd = c.of("question_round")[-1]
        await hub.handle({"type": "round_answer", "roundId": rnd["id"],
                          "answers": {q["id"]: {"accepted": True} for q in rnd["questions"]}})
        assert c.of("plan_draft")
        assert c.of("planner_model")[-1]["promoted"] is True and c.of("planner_model")[-1]["by"] == "criteria"
        await hub.handle({"type": "user_message", "text": "Add a changelog step please"})      # edit-based revision
        assert c.of("plan_draft")[-1]["revision"] == 2 and "changelog" in c.of("plan_draft")[-1]["markdown"]
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "report_to_planner", "session_id": hub.current.id})
        assert c.of("plan_draft")[-1]["revision"] == 3 and c.of("plan_draft")[-1]["previous_runs"] == 1
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})       # send-back -> approve
        await h.wait(lambda: len(c.of("run_finished")) == 2)
        await hub.handle({"type": "get_crew"})
        return hub, c

    hub, c = asyncio.run(go())
    kinds = sorted((e["kind"], e["blocking"]) for e in c.of("queue_item"))
    assert kinds == [("permission", False), ("permission", False), ("question", False), ("question", True)]
    assert [e["by"] for e in c.of("queue_resolved")].count("timer") == 1
    assert [e["status"] for e in c.of("run_finished")] == ["done", "done"]
    assert c.of("run_started")[1]["name"] == "Demo: landing page, round 2"
    sets = {}
    for e in c.of("visual_set"):
        sets[e["set_id"]] = e                                       # the last event of each set
    assert [s["brief"] for s in sets.values()] == [b for b, _, _ in demo.VISUAL_SETS]
    assert all(o["status"] == "ready" for s in sets.values() for o in s["options"]), \
        [o.get("error") for s in sets.values() for o in s["options"]]
    v1, v2, v3, v4, v5 = sets.values()
    assert [o["label"] for o in v1["options"]] == demo.VISUAL_OPTIONS
    assert v1["library"] is None and v1["drawn_with"] == "echarts" and v1["library_note"] is None
    assert all("echarts.init" in o["html"] for o in v1["options"])
    assert v2["drawn_with"] == "chartjs" and all("new Chart(" in o["html"] for o in v2["options"])
    assert v3["drawn_with"] == "d3" and all("d3.select(" in o["html"] for o in v3["options"])
    assert v4["library"] == "matplotlib" and v4["drawn_with"] == "echarts"                      # labelled fallback
    assert v4["library_note"] == "drawn in ECharts, styled like matplotlib"
    assert all("echarts.init" in o["html"] and "#1f77b4" in o["html"] for o in v4["options"])
    assert [o["label"] for o in v5["options"]] == ["Colour palette", "Hero card"]
    assert all("<script" not in o["html"] for o in v5["options"])                              # design briefs: HTML/CSS
    assert {"echarts", "chartjs", "d3"} <= set(v1["libraries"])
    uses = [e["uses"] for e in c.of("agent_uses") if e["name"] == "launchpad-visual"]
    assert uses[-1] == sum(len(s["options"]) for s in sets.values())                           # one use per visual
    finished = [e for e in c.of("activity") if e["status"] != "started"]
    assert len(finished) >= 25 and {e["status"] for e in finished} <= {"done", "denied"}
    assert [e["n"] for e in c.of("step_update") if e["status"] == "done"] == [1, 2, 3, 4, 5, 1, 2]
    assert c.of("crew_list") and "round 2" in c.of("planner_message")[-1]["text"]
    # the folder agent: named in the draft, ran step 4 read-only (its Write refused without a card), counted
    first = c.of("plan_draft")[0]["steps"][3]
    assert first["agent"] == "copy-reviewer" and first["agent_display"] == "Copy reviewer" and "agent_fallback" not in first
    step4 = [e for e in c.of("step_update") if e["n"] == 4 and e["status"] == "done"][0]
    assert step4["agent_display"] == "Copy reviewer"
    reviewer = [e for e in c.of("activity") if e["name"] == "Copy reviewer" and e["tool"] == "Write"]
    assert reviewer and reviewer[-1]["status"] == "denied"
    crew_names = {a["name"]: a for a in c.of("crew_list")[-1]["agents"]}
    assert crew_names["copy-reviewer"]["uses"] == 1 and crew_names["copy-reviewer"]["purpose"] == "reviewing"
    assert crew_names["launchpad-builder"]["uses"] == 6                 # 4 builder steps in run 1, 2 in run 2
    f = hub.current.folder
    for p in (f.plan, f.flight_log, f.assumptions, f.ops_manual, f.report, f.step_path(2),
              f.path / "run-1" / "steps" / "step-03.md", f.path / "run-1" / "report.md"):
        assert p.is_file(), p
    assert not (project / "demo-output").exists()                 # fake built-ins never touch disk


def test_demo_regular_chat(harness, project):
    def responder(ev):
        if ev.get("type") != "queue_item" or not ev.get("chat_id"):
            return None
        if ev["kind"] == "question":
            return {"type": "queue_response", "id": ev["id"], "answer": ev["options"][0]}
        if ev["kind"] == "plan":
            return {"type": "queue_response", "id": ev["id"], "decision": "allow", "mode": "accept_edits"}
        return {"type": "queue_response", "id": ev["id"], "decision": "allow"}

    h = harness(responder=responder)
    demo.install(project)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "look around"})
        await hub.handle({"type": "chat_set_mode", "chat_id": cid, "mode": "plan"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "make a plan"})
        return c

    c = asyncio.run(go())
    kinds = [e["kind"] for e in c.of("queue_item")]
    assert kinds == ["permission", "permission", "permission", "question", "plan"]   # plan approved -> edits unasked
    assert [e["status"] for e in c.of("chat_done")] == ["ok", "ok"]
    assert c.of("chat_mode")[-1]["mode"] == "accept_edits"


def test_fake_launch_starts_clean_every_time(tmp_path, monkeypatch):
    """--fake: own store reset (counts at zero), scratch folders restored, old app-files-* copies removed best-effort."""
    import argparse
    import shutil
    import tempfile
    from app import launch
    from app.agents import crew
    from app.agents.planner import planner
    from app.store import Store
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    monkeypatch.delenv("LAUNCHPAD_HOME", raising=False)
    for name in ("APP_ROOT", "AGENTS_DIR"):
        monkeypatch.setattr(crew, name, getattr(crew, name))
    monkeypatch.setattr(planner, "CRITERIA_FILE", planner.CRITERIA_FILE)
    args = argparse.Namespace(fake=True, cwd="", model=None, question_timeout=None, permission_timeout=None,
                              autopilot=None, planner_start=None, planner_top=None, promotion_window=None,
                              promotion_criteria=None, pilot_model=None, visual_model=None)
    base = tmp_path / "tmp" / "launchpad-demo"

    settings, store, _ = launch.build_settings(args)                  # launch 1: dirty everything
    store.add_use("launchpad-visual")
    shop = base / "Demo shop"
    (shop / ".claude" / "agents" / "made-earlier.md").write_text("---\nname: made-earlier\n---\nx\n", encoding="utf-8")
    (shop / "README.md").write_text("edited\n", encoding="utf-8")
    (shop / ".launchpad" / "old-session").mkdir(parents=True)
    (base / "app-files-old1").mkdir()
    (base / "app-files-old2" / "x").mkdir(parents=True)
    real_rmtree = shutil.rmtree

    def rmtree(path, *a, **kw):                                       # one leftover that cannot be deleted
        if "app-files-old2" in str(path):
            if kw.get("ignore_errors"):
                return None
            raise OSError("locked")
        return real_rmtree(path, *a, **kw)
    monkeypatch.setattr(shutil, "rmtree", rmtree)
    monkeypatch.delenv("LAUNCHPAD_HOME", raising=False)

    settings, store, _ = launch.build_settings(args)                  # launch 2: clean
    assert store.uses() == {} and Store(base / "home" / "settings.json").uses() == {}
    assert not (shop / ".claude" / "agents" / "made-earlier.md").exists()
    assert (shop / ".claude" / "agents" / f"{demo.FOLDER_AGENT_NAME}.md").read_text(encoding="utf-8") == demo.FOLDER_AGENT_FILE
    assert (shop / "README.md").read_text(encoding="utf-8").startswith("# Demo shop")
    assert not (shop / ".launchpad").exists()
    assert not (base / "app-files-old1").exists() and (base / "app-files-old2").exists()   # locked one: launch went on
    assert len(store.directories()) == 2 and settings.project.name == "Demo shop"
