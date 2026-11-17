"""Skills (discovery, per-agent allowlists, plan-step skills) and primary + additional folders."""
import asyncio
from pathlib import Path

import pytest

from agentlib import fake

from app import plan as plan_mod
from app import skills as skills_mod
from app.agents import crew
from app.agents.builder import builder as builder_mod
from app.agents.builder.deny import deny_match
from app.store import Store
from conftest import PLAN, report, script_orchestrator_sequential


def skill(folder: Path, sub: str, name: str, desc: str = "does things") -> Path:
    d = folder / sub / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nSteps.\n", encoding="utf-8")
    return d


# --------------------------------------------------------------------------- discovery (assumptions 1-3)
def test_claude_folder_with_skills(tmp_path):
    skill(tmp_path, ".claude/skills", "memo", "Writes memos")
    found = skills_mod.discover([tmp_path], ["d1"])
    assert [(s["name"], s["source"], s["shadowed"], s["dir_id"]) for s in found] == [("memo", "claude", False, "d1")]
    assert found[0]["description"] == "Writes memos" and found[0]["path"].endswith("SKILL.md")


def test_agents_folder_only(tmp_path):
    skill(tmp_path, ".agents/skills", "tidy")
    found = skills_mod.discover([tmp_path])
    assert [(s["name"], s["source"]) for s in found] == [("tidy", "agents")]
    assert skills_mod.skill_dirs([tmp_path]) == [tmp_path / ".agents" / "skills"]


def test_both_present_only_claude_is_used(tmp_path):
    skill(tmp_path, ".claude/skills", "memo")
    skill(tmp_path, ".agents/skills", "tidy")
    assert [(s["name"], s["source"]) for s in skills_mod.discover([tmp_path])] == [("memo", "claude")]


def test_claude_folder_without_skills_gives_none(tmp_path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)          # .claude exists, no skills folder
    skill(tmp_path, ".agents/skills", "tidy")                      # ignored: .claude wins even when empty
    assert skills_mod.discover([tmp_path]) == [] and skills_mod.skill_dirs([tmp_path]) == []


def test_name_clash_primary_wins_other_shadowed(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    skill(a, ".claude/skills", "memo", "primary memo")
    skill(b, ".agents/skills", "memo", "other memo")
    skill(b, ".agents/skills", "extra")
    found = skills_mod.discover([a, b], ["da", "db"])
    assert [(s["name"], s["dir_id"], s["shadowed"]) for s in found] == [
        ("memo", "da", False), ("extra", "db", False), ("memo", "db", True)]
    assert [s["name"] for s in skills_mod.active(found)] == ["memo", "extra"]
    assert next(s for s in skills_mod.active(found) if s["name"] == "memo")["description"] == "primary memo"


def test_allowlist_rules():
    found = [{"name": n, "shadowed": False} for n in ("a", "b", "c")] + [{"name": "a", "shadowed": True}]
    assert skills_mod.allowed("all", found) == ["a", "b", "c"]
    assert skills_mod.allowed([], found) == []
    assert skills_mod.allowed(["c", "gone"], found, ["a"]) == ["a", "c"]          # unknown names dropped
    assert skills_mod.setting_of({}, "launchpad-planner", planner=True) == "all"
    assert skills_mod.setting_of({}, "launchpad-builder") == []
    assert skills_mod.setting_of({"x": ["b"]}, "x") == ["b"]
    with pytest.raises(ValueError):
        skills_mod.clean_setting("some")


# --------------------------------------------------------------------------- store
def test_store_keeps_additional_folders_and_agent_skills(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    s = Store(tmp_path / "settings.json")
    da, db = s.add(a)["dir_id"], s.add(b)["dir_id"]
    assert s.set_additional([db]) == [db]
    s.set_agent_skills("launchpad-builder", ["memo"])
    s2 = Store(tmp_path / "settings.json")
    assert s2.additional_ids() == [db] and s2.agent_skills() == {"launchpad-builder": ["memo"]}
    with pytest.raises(ValueError):
        s2.set_additional(["nope"])
    s2.remove(db)
    assert s2.additional_ids() == []


# --------------------------------------------------------------------------- folders: settings, sessions, chats
@pytest.fixture
def other(tmp_path) -> Path:
    p = tmp_path / "other"
    p.mkdir()
    return p


def _connect_additional(hub, path: Path) -> str:
    did = hub.store.add(path)["dir_id"]
    return did


def test_settings_tick_additional_and_new_session_gets_add_dirs(harness, project, other):
    h = harness()

    async def go():
        hub, c = await h.start()
        did = _connect_additional(hub, other)
        await hub.handle({"type": "set_settings", "patch": {"additional_dir_ids": [did]}})
        ev = c.of("settings")[-1]
        rows = {d["dir_id"]: d for d in ev["directories"]}
        assert ev["additional_dir_ids"] == [did] and rows[did]["is_additional"] and not rows[did]["is_default"]
        assert rows[hub.default_dir]["is_default"] and not rows[hub.default_dir]["is_additional"]
        ls = await hub.new_session()
        chat = await hub.chat_new()
        other_primary = await hub.new_session(did)          # ticked folder as primary: not also additional
        return hub, c, ls, chat, other_primary, did

    hub, c, ls, chat, op, did = asyncio.run(go())
    assert ls.folder.extra == [other.resolve()] and ls.extra_ids == [did]
    assert [Path(d) for d in ls.chat.agent.add_dirs] == [other.resolve()]
    assert c.of("session_started")[-2]["additional_dir_ids"] == [did]
    assert chat.agent.setup == "project" and [Path(d) for d in chat.agent.add_dirs] == [other.resolve()]
    assert chat.agent.cwd == project.resolve() and c.of("chat_started")[-1]["additional_dir_ids"] == [did]
    assert op.folder.extra == [] and op.chat.agent.add_dirs == []


def test_builder_guard_allows_writes_in_additional_folders(harness, project, other):
    answers = []
    h = harness(responder=lambda ev: (answers.append(ev["body"]) or {"type": "queue_response", "id": ev["id"],
                                                                      "decision": "deny"}
                                      if ev.get("type") == "queue_item" else None))
    target = other / "made.txt"
    fake.script("launchpad-planner", [[fake.call("write_plan", {**PLAN, "steps": PLAN["steps"][:1]}),
                                       fake.say("ok")]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("Write", {"file_path": str(target), "content": "x"}),
                                       fake.call("Write", {"file_path": str(other / ".git" / "x"), "content": "x"}),
                                       fake.call("submit_report", report())]])

    async def go():
        hub, c = await h.start()
        did = _connect_additional(hub, other)
        hub.store.set_additional([did])
        ls = await hub.new_session()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": ls.id})
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    assert answers == [str(other / ".git" / "x")]                  # the plain write in the extra folder: no card
    assert [x["title"] for x in c.of("queue_item")] == ["Write inside .git/"]
    assert deny_match(f'rm "{other / "old.txt"}"', project, [other]) is None
    assert deny_match(f'rm "{other / "old.txt"}"', project) == "delete outside the project"
    assert deny_match(f'rm -r "{other}"', project, [other]) == "delete outside the project"


# --------------------------------------------------------------------------- crew tab
def test_crew_list_skills_and_settings(harness, project, other):
    skill(project, ".claude/skills", "memo", "Writes memos")
    skill(other, ".agents/skills", "memo", "shadowed one")
    skill(other, ".agents/skills", "tidy")
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "agents" / "copy-reviewer.md").write_text(
        "---\nname: copy-reviewer\ndescription: Reviews copy\npurpose: reviewing\ntools: Read\n---\nReview.\n",
        encoding="utf-8")
    h = harness()

    async def go():
        hub, c = await h.start()
        hub.store.set_additional([_connect_additional(hub, other)])
        await hub.handle({"type": "get_crew"})
        first = c.of("crew_list")[-1]
        await hub.handle({"type": "set_agent_skills", "name": "launchpad-builder", "skills": ["tidy", "gone"]})
        await hub.handle({"type": "set_agent_skills", "name": "launchpad-planner", "skills": []})
        return hub, first, c.of("crew_list")[-1]

    hub, first, after = asyncio.run(go())
    assert [(s["name"], s["source"], s["shadowed"]) for s in first["skills"]] == [
        ("memo", "claude", False), ("memo", "agents", True), ("tidy", "agents", False)]
    by = {a["name"]: a for a in first["agents"]}
    assert by["launchpad-planner"]["skill_setting"] == "all" and by["launchpad-builder"]["skill_setting"] == []
    assert by["launchpad-pilot"]["skill_setting"] == "cli" and by["copy-reviewer"]["skill_setting"] == []
    by = {a["name"]: a for a in after["agents"]}
    assert by["launchpad-builder"]["skill_setting"] == ["tidy", "gone"]    # unknown kept (shown greyed)
    assert by["launchpad-planner"]["skill_setting"] == []
    assert hub.store.agent_skills()["launchpad-builder"] == ["tidy", "gone"]


# --------------------------------------------------------------------------- planner and plan steps
def test_plan_step_skills_round_trip():
    text = plan_mod.render(name="P", goal="g", session="s", steps=[
        {"title": "A", "details": "d", "done_when": "x", "skills": ["memo", "memo", " tidy "]},
        {"title": "B", "details": "d", "done_when": "x"}])
    assert plan_mod.validate(text) == []
    steps = plan_mod.parse(text)["steps"]
    assert steps[0]["skills"] == ["memo", "tidy"] and steps[1]["skills"] == []
    assert "skills" not in text.split("---")[1].splitlines()[-1]           # step 2's header line: no skills key
    new, _ = plan_mod.apply_edits(text, [{"op": "set_step", "n": 2, "skills": ["memo"]},
                                         {"op": "set_step", "n": 1, "skills": []}], session="s")
    assert [s["skills"] for s in plan_mod.parse(new)["steps"]] == [[], ["memo"]]
    old = text.replace('"skills": ["memo", "tidy"]', '"skill": "legacy"').replace('skills: ["memo", "tidy"]',
                                                                                   'skill: "legacy"')
    assert plan_mod.parse(old)["steps"][0]["skills"] == ["legacy"]


def test_planner_sees_skills_and_worker_gets_allowlist_plus_step_skills(harness, project, other, monkeypatch):
    skill(project, ".claude/skills", "memo", "Writes memos")
    skill(project, ".claude/skills", "sql-style", "SQL house style")
    skill(other, ".agents/skills", "tidy", "Tidies")
    seen_first = []
    plan = {**PLAN, "steps": [dict(PLAN["steps"][0], skills=["sql-style", "nope"]), PLAN["steps"][1]]}

    def planner_turn(msg):
        seen_first.append(msg)
        return [fake.call("write_plan", plan), fake.say("ok")]

    fake.script("launchpad-planner", [planner_turn])
    script_orchestrator_sequential(2)
    messages = []

    def builder(msg):
        messages.append(msg)
        return [fake.call("submit_report", report())]

    fake.script("launchpad-builder", [builder])
    loaded = []
    orig = builder_mod.load_worker
    monkeypatch.setattr(builder_mod, "load_worker", lambda run, ctx: loaded.append(orig(run, ctx)) or loaded[-1])
    h = harness()

    async def go():
        hub, c = await h.start()
        hub.store.set_additional([_connect_additional(hub, other)])
        hub.store.set_agent_skills("launchpad-builder", ["memo"])
        ls = await hub.new_session()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": ls.id})
        await h.wait(lambda: c.of("run_finished"))
        return hub, c, ls

    hub, c, ls = asyncio.run(go())
    note = seen_first[0]
    assert "- memo: Writes memos" in note and "- sql-style: SQL house style" in note and "- tidy: Tidies" in note
    assert "Additional folders" in note and str(other.resolve()) in note
    assert ls.chat.agent.skills == ["memo", "sql-style", "tidy"]                  # planner default: all
    assert [Path(d) for d in ls.chat.agent.skill_dirs] == [project / ".claude/skills", other / ".agents/skills"]
    draft = c.of("plan_draft")[-1]["steps"]
    assert draft[0]["skills"] == ["sql-style", "nope"] and draft[0]["skills_unknown"] == ["nope"]
    assert "skills" not in draft[1]
    assert c.of("run_started")[-1]["steps"][0]["skills"] == ["sql-style", "nope"]
    assert [a.skills for a in loaded] == [["memo", "sql-style"], ["memo"]]       # allowlist + step skills
    assert all([Path(d) for d in a.add_dirs] == [other.resolve()] for a in loaded)
    assert "Skills for this step" in messages[0] and "sql-style" in messages[0]
    assert "Skills for this step" not in messages[1]
    assert "unknown skills (ignored at run time): step 1: nope" in ls.agent_note(ls.plan_text)


def test_agent_with_no_skills_loads_as_before(harness, project):
    script_orchestrator_sequential(1)
    fake.script("launchpad-planner", [[fake.call("write_plan", {**PLAN, "steps": PLAN["steps"][:1]}),
                                       fake.say("ok")]])
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    loaded = []
    orig = builder_mod.load_worker
    h = harness()

    async def go():
        hub, c = await h.start()
        builder_mod.load_worker = lambda run, ctx: loaded.append(orig(run, ctx)) or loaded[-1]
        try:
            await hub.handle({"type": "user_message", "text": "go"})
            await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
            await h.wait(lambda: c.of("run_finished"))
        finally:
            builder_mod.load_worker = orig
        return hub

    hub = asyncio.run(go())
    a = loaded[0]
    assert a.skills == [] and a.skill_dirs is None and a.add_dirs == []
    assert hub.current.chat.agent.skills == [] and hub.current.skills == []     # no skills in the folder
