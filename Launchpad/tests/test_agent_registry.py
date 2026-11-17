"""Agents feature (fake engine, zero tokens): registry + crew_list, plan step agents, routing + fallback, read-only
enforcement, the use counter, agent draft / create / remove, chat_from_plan."""
import asyncio
import os
from pathlib import Path

import pytest

from agentlib import fake

from app.agents import crew, folder_agents
from app.agents.drafter import drafter
from app import plan as plan_mod
from app.store import Store
from conftest import PLAN, Client, report, script_orchestrator_sequential

ONE = {**PLAN, "steps": PLAN["steps"][:1]}


def agent_file(project: Path, name: str, *, purpose: str | None = "building", tools: str | None = "Read, Grep, Glob",
               body: str = "- Do the step well.", description: str = "Does a thing.", model: str | None = "haiku") -> Path:
    d = project / ".claude" / "agents"
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name}", f"description: {description}"]
    if purpose:
        lines.append(f"purpose: {purpose}")
    if model:
        lines.append(f"model: {model}")
    if tools is not None:
        lines.append(f"tools: {tools}")
    p = d / f"{name}.md"
    p.write_text("\n".join(lines + ["---", body, ""]), encoding="utf-8")
    return p


def run_plan(h, plan: dict, *, steps: int = 1):
    """Planner writes `plan`, the user approves, the run finishes -> (hub, client)."""
    fake.script("launchpad-planner", [[fake.call("write_plan", plan), fake.say("Draft saved.")]])
    script_orchestrator_sequential(steps)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        return hub, c
    return asyncio.run(go())


# ------------------------------------------------------------------ registry and crew_list
def test_registry_builtins_folder_agents_and_purposes(project):
    agent_file(project, "copy-reviewer", purpose="reviewing")
    agent_file(project, "csv-maker", purpose=None, tools=None)                  # no purpose -> other
    agent_file(project, "idea-planner", purpose="planning")                     # listed, not a step worker
    (project / ".claude" / "agents" / "broken.md").write_text("---\nname: Broken Name\n---\nx\n", encoding="utf-8")
    (project / ".claude" / "agents" / "launchpad-builder.md").write_text(
        "---\nname: launchpad-builder\ndescription: impostor\n---\nx\n", encoding="utf-8")   # built-in name: skipped
    reg = {e["name"]: e for e in crew.registry(project)}
    builtins = [e for e in reg.values() if e["builtin"]]
    assert len(builtins) == 6 and {e["display_name"] for e in builtins} == {
        "Planner", "Explorer", "Orchestrator", "Builder", "Visualizer", "CLI"}
    assert {e["role"]: e["purpose"] for e in builtins} == {
        "planner": "planning", "visual": "planning", "astronaut": "exploring", "builder": "building",
        "orchestrator": "building", "pilot": "building"}
    assert reg["launchpad-builder"]["description"] != "impostor"
    assert reg["copy-reviewer"]["purpose"] == "reviewing" and reg["copy-reviewer"]["display_name"] == "Copy reviewer"
    assert reg["csv-maker"]["purpose"] == "other"
    assert reg["idea-planner"]["step_worker"] is False
    assert reg["Broken Name"]["problems"] and reg["Broken Name"]["step_worker"] is False
    assert [e["name"] for e in crew.step_agents(project)] == ["launchpad-builder", "copy-reviewer", "csv-maker"]
    note = crew.registry_note(project)
    assert "copy-reviewer (reviewing): Does a thing." in note and "idea-planner" not in note and "broken" not in note


def test_crew_list_carries_purpose_uses_builtin_and_folder_agents(project):
    agent_file(project, "copy-reviewer", purpose="reviewing", tools="Read, Write, Bash")
    store = Store(None)
    store.add_use("launchpad-builder")
    store.add_use("copy-reviewer")
    ev = crew.crew_list("fake", project, store=store, folder=project, dir_id="dX")
    assert ev["dir_id"] == "dX" and ev["tool_choices"] == crew.TOOL_CHOICES
    by = {a["name"]: a for a in ev["agents"]}
    for a in ev["agents"]:
        assert {"purpose", "uses", "builtin", "display_name", "model", "description", "instructions"} <= set(a)
    assert by["launchpad-builder"]["uses"] == 1 and by["launchpad-planner"]["uses"] == 0
    rev = by["copy-reviewer"]
    assert rev["builtin"] is False and rev["role"] is None and rev["root"] == "dX"
    assert rev["path"] == ".claude/agents/copy-reviewer.md" and rev["uses"] == 1 and rev["step_worker"]
    assert "Write" not in rev["builtin_tools"] and "Bash" not in rev["builtin_tools"]      # read-only as run
    assert {"Write", "Bash"} <= set(rev["disallowed_tools"])
    assert [t["name"] for t in rev["custom_tools"]] == ["ask_question", "add_to_flight_log", "submit_report"]


# ------------------------------------------------------------------ plan.py: optional agent per step
def test_plan_step_agent_render_parse_validate_and_edit():
    steps = [{"title": "A", "details": "a", "done_when": "x"},
             {"title": "B", "details": "b", "done_when": "y", "agent": "copy-reviewer", "after": [1]}]
    text = plan_mod.render(name="P", goal="G", steps=steps, session="s1")
    assert plan_mod.validate(text) == []
    assert "agent" not in text.split("\n")[6] and 'agent: "copy-reviewer"' in text   # only written when set
    p = plan_mod.parse(text)
    assert [s["agent"] for s in p["steps"]] == [None, "copy-reviewer"]
    assert plan_mod.to_fields(text)["steps"][1]["agent"] == "copy-reviewer"
    bad = text.replace('agent: "copy-reviewer"', 'agent: "Copy Reviewer!"')
    assert any("agent must be an agent name" in x for x in plan_mod.validate(bad))
    edited, _ = plan_mod.apply_edits(text, [{"op": "set_step", "n": 1, "agent": "csv-maker"},
                                            {"op": "set_step", "n": 2, "agent": ""},
                                            {"op": "add_step", "title": "C", "details": "c", "agent": "copy-reviewer"}],
                                     session="s1")
    assert [s["agent"] for s in plan_mod.parse(edited)["steps"]] == ["csv-maker", None, "copy-reviewer"]
    moved, _ = plan_mod.apply_edits(edited, [{"op": "move_step", "n": 3, "to": 1}], session="s1")
    assert plan_mod.parse(moved)["steps"][0]["agent"] == "copy-reviewer"            # the agent moves with the step


def test_planner_gets_registry_in_first_message_and_hears_changes(harness, project):
    agent_file(project, "copy-reviewer", purpose="reviewing")
    h = harness()
    seen = []
    fake.script("launchpad-planner", [lambda m: seen.append(m) or [fake.say("ok")]] * 3)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "hello"})
        await hub.handle({"type": "agent_create", "dir_id": hub.current.dir_id, "fields": {
            "name": "csv-maker", "description": "Makes CSV files.", "purpose": "building", "model": "haiku",
            "tools": ["Read", "Write"], "instructions": "- Write the CSV."}})
        await hub.handle({"type": "user_message", "text": "again"})
        await hub.handle({"type": "user_message", "text": "third"})
        return c
    asyncio.run(go())
    assert "copy-reviewer (reviewing)" in seen[0] and "launchpad-builder (building)" in seen[0]
    assert seen[1].startswith("[Launchpad] The step agents changed.") and "csv-maker (building)" in seen[1]
    assert seen[2] == "third"                                                    # told once


def test_planner_tool_list_and_prompt_do_not_depend_on_the_folder(project, tmp_path):
    """Cache-friendly: the registry is in messages, never in the system prompt or tool definitions."""
    from app.agents.planner.planner import planner_tools
    other = tmp_path / "other"
    other.mkdir()
    agent_file(other, "copy-reviewer", purpose="reviewing")
    a = crew.load("planner", engine="fake", project=project, tools=planner_tools(None))
    b = crew.load("planner", engine="fake", project=other, tools=planner_tools(None))
    assert a.instructions == b.instructions
    assert [(t.name, t.description, t.schema) for t in a.resolved_tools().custom] == \
           [(t.name, t.description, t.schema) for t in b.resolved_tools().custom]


# ------------------------------------------------------------------ routing, fallback, read-only
def test_step_runs_on_the_named_building_agent_with_builder_guards(harness, project):
    agent_file(project, "csv-maker", purpose="building", tools="Read, Write, Bash(git push:*)")
    h = harness(responder=lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "deny"}
                                      if ev.get("type") == "queue_item" else None))
    got = []

    def worker(msg):
        got.append(msg)
        return [fake.call("Write", {"file_path": "out/data.csv", "content": "a,b"}),
                fake.call("Bash", {"command": "git push origin main"}),
                fake.call("submit_report", report())]
    fake.script("csv-maker", [worker])
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    plan = {**ONE, "steps": [{**ONE["steps"][0], "agent": "csv-maker"}]}
    hub, c = run_plan(h, plan)
    assert got and got[0].startswith("Work on step 1") and "submit_report" in got[0] and "read-only" not in got[0]
    results = h.tool_results()
    assert ("Write", "(fake) ran Write", False) in [(n, r, e) for n, r, e in results]       # inside: allowed
    perm = c.of("queue_item")[0]                                                  # deny list card, as for the Builder
    assert perm["kind"] == "permission" and perm["agent"] == "Csv maker" and "git push" in perm["title"]
    upd = [e for e in c.of("step_update") if e["status"] == "in_progress"][0]
    assert upd["agent"] == "csv-maker" and upd["agent_display"] == "Csv maker" and "agent_fallback" not in upd
    assert c.of("run_started")[0]["steps"][0]["agent_display"] == "Csv maker"
    assert "| 1 | First thing | Csv maker | done |" in c.of("run_finished")[0]["markdown"]
    usage = [e for e in c.of("agent_usage") if e["role"] == "builder"]
    assert usage and usage[-1]["name"] == "Csv maker"


def test_other_agent_takes_a_plan_step_with_builder_guards(harness, project):
    agent_file(project, "odd-jobs", purpose="other", tools="Read, Write, Bash")
    h = harness(responder=lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "deny"}
                                      if ev.get("type") == "queue_item" else None))
    got = []

    def worker(msg):
        got.append(msg)
        return [fake.call("Write", {"file_path": "out/x.txt", "content": "a"}),
                fake.call("Bash", {"command": "git push origin main"}),
                fake.call("submit_report", report())]
    fake.script("odd-jobs", [worker])
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    plan = {**ONE, "steps": [{**ONE["steps"][0], "agent": "odd-jobs"}]}
    hub, c = run_plan(h, plan)
    assert next(e for e in crew.registry(project) if e["name"] == "odd-jobs")["step_worker"] is True
    assert c.of("plan_draft")[0]["steps"][0]["agent_purpose"] == "other"
    assert got and "read-only" not in got[0]                                     # not read-only: guarded like building
    assert ("Write", "(fake) ran Write", False) in h.tool_results()                # inside the project: allowed
    perm = c.of("queue_item")[0]                                                  # the deny list reaches a card
    assert perm["kind"] == "permission" and perm["agent"] == "Odd jobs" and "git push" in perm["title"]
    assert "other" in crew.registry_note(project)                                # the planner's registry names it
    entry = next(e for e in crew.registry(project) if e["name"] == "odd-jobs")
    r = crew.load_step_worker(entry, engine="fake", project=project, tools=[]).resolved_tools()
    assert "Write" in r.builtin_names and "Bash" in r.builtin_names and r.gated


def test_unknown_purpose_is_listed_as_other_and_other_can_be_added(project):
    agent_file(project, "mystery", purpose="banana")
    reg = {e["name"]: e for e in crew.registry(project)}
    assert reg["mystery"]["purpose"] == "other" and reg["mystery"]["problems"] and reg["mystery"]["step_worker"] is False
    assert "other" in folder_agents.ADDABLE_PURPOSES and "other" in crew.PURPOSES
    clean, problems = folder_agents.normalise({"name": "misc-helper", "description": "Odd jobs.", "purpose": "other",
                                               "tools": ["Read", "Write", "Bash"], "instructions": "Do it."}, strict=True)
    assert not problems and clean["purpose"] == "other" and clean["tools"] == ["Read", "Write", "Bash"]   # not read-only


def test_agent_purpose_on_every_step_entry_incl_reconnect(harness, project):
    agent_file(project, "csv-maker", purpose="building")
    agent_file(project, "copy-reviewer", purpose="reviewing")
    h = harness()
    fake.script("csv-maker", [[fake.call("submit_report", report())]])
    fake.script("copy-reviewer", [[fake.call("submit_report", report())]])
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    plan = {**PLAN, "steps": [{**PLAN["steps"][0], "agent": "copy-reviewer"}, {**PLAN["steps"][1]}]}
    hub, c = run_plan(h, plan, steps=2)
    want = ["reviewing", "building"]
    assert [s["agent_purpose"] for s in c.of("plan_draft")[0]["steps"]] == want
    assert [s["agent_purpose"] for s in c.of("run_started")[0]["steps"]] == want
    assert all(e["agent_purpose"] == want[e["n"] - 1] for e in c.of("step_update"))
    late = Client(hub)

    async def again():
        await hub.connect(late)
    asyncio.run(again())
    assert [s["agent_purpose"] for s in late.of("run_started")[0]["steps"]] == want


def test_building_agent_tools_are_gated_and_pattern_rules_reduced(project):
    agent_file(project, "csv-maker", purpose="building", tools="Read, Write, Bash(git push:*), ask_user")
    entry = next(e for e in crew.registry(project) if e["name"] == "csv-maker")
    a = crew.load_step_worker(entry, engine="fake", project=project, tools=[])
    r = a.resolved_tools()
    assert r.builtin_names == ["Read", "Write", "Bash"] and r.approved_rules == ["Read"]   # writes + shell reach code
    assert [t.name for t in r.custom] == [] and a.engine_prompt and a.setup == "lean"
    assert a.model == "haiku"


def test_missing_agent_falls_back_to_the_builder_and_the_report_says_so(harness, project):
    h = harness()
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    plan = {**ONE, "steps": [{**ONE["steps"][0], "agent": "gone-agent"}]}
    hub, c = run_plan(h, plan)
    draft = c.of("plan_draft")[0]["steps"][0]
    assert draft["agent"] == "gone-agent" and draft["agent_display"] == "Builder" and draft["agent_fallback"] is True
    assert draft["agent_purpose"] == "building"                                  # the Builder's, not a guess
    planner_results = [tc.result for tc in hub.current.chat.session.last_reply.tool_calls if tc.name == "write_plan"]
    assert "would run on the Builder" in planner_results[0]                      # the planner is told at once
    upd = [e for e in c.of("step_update") if e["status"] == "done"][0]
    assert upd["agent_display"] == "Builder" and upd["agent_fallback"] is True
    md = c.of("run_finished")[0]["markdown"]
    assert "Builder (fallback: gone-agent not available)" in md and "does not exist in this folder" in md
    step = hub.current.folder.read(hub.current.folder.step_path(1))
    assert "ran on the Builder instead" in step


def test_broken_agent_file_also_falls_back(harness, project):
    agent_file(project, "csv-maker", purpose="building")
    h = harness()
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    plan = {**ONE, "steps": [{**ONE["steps"][0], "agent": "csv-maker"}]}
    fake.script("launchpad-planner", [[fake.call("write_plan", plan)]])
    script_orchestrator_sequential(1)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        (project / ".claude" / "agents" / "csv-maker.md").write_text("---\nname: csv-maker\nmodel: gpt-9\n---\nx\n",
                                                                     encoding="utf-8")       # broken after the draft
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        return c
    c = asyncio.run(go())
    assert "broken file" in c.of("run_finished")[0]["markdown"]


def test_reviewing_and_exploring_agents_are_read_only(harness, project):
    agent_file(project, "copy-reviewer", purpose="reviewing", tools="Read, Write, Edit, Bash, Grep")
    agent_file(project, "code-finder", purpose="exploring", tools=None)
    for name in ("copy-reviewer", "code-finder"):
        entry = next(e for e in crew.registry(project) if e["name"] == name)
        r = crew.load_step_worker(entry, engine="fake", project=project, tools=[]).resolved_tools()
        assert not set(r.builtin_names) & set(crew.WRITE_SHELL) and r.gated == []
    h = harness()
    got = []

    def reviewer(msg):
        got.append(msg)
        return [fake.call("Read", {"file_path": "CLAUDE.md"}),
                fake.call("Write", {"file_path": "x.md", "content": "x"}),
                fake.call("Edit", {"file_path": "CLAUDE.md", "old_string": "be", "new_string": "is"}),
                fake.call("Bash", {"command": "ls"}),
                fake.call("submit_report", report())]
    fake.script("copy-reviewer", [reviewer])
    plan = {**ONE, "steps": [{**ONE["steps"][0], "agent": "copy-reviewer"}]}
    hub, c = run_plan(h, plan)
    assert c.of("plan_draft")[0]["steps"][0]["agent_purpose"] == "reviewing"
    assert c.of("run_started")[0]["steps"][0]["agent_purpose"] == "reviewing"
    assert {e["agent_purpose"] for e in c.of("step_update")} == {"reviewing"}
    calls = {n: e for n, _r, e in h.tool_results()}
    assert calls["Read"] is False and calls["Write"] and calls["Edit"] and calls["Bash"]      # all three refused
    assert not c.of("queue_item")                                                # no card: refused in code
    assert "read-only" in got[0]
    assert (project / "CLAUDE.md").read_text(encoding="utf-8") == "# Rules\n- be nice\n"


def test_read_only_permission_hook_refuses_without_a_card(harness, project):
    """Belt and braces: even if a write reached the permission hook, a read-only agent is refused in code."""
    from agentlib import PermissionRequest
    from app.agents.builder.builder import StepContext
    agent_file(project, "copy-reviewer", purpose="reviewing")
    h = harness()
    fake.script("launchpad-planner", [[fake.call("write_plan", ONE)]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        from app.agents.orchestrator.run import Run
        run = Run(hub.current)
        entry = next(e for e in crew.registry(project) if e["name"] == "copy-reviewer")
        ctx = StepContext(run, 1, entry)
        d = await ctx.permission(PermissionRequest(agent="copy-reviewer", tool="Bash", input={"command": "ls"}))
        return c, ctx, d
    c, ctx, d = asyncio.run(go())
    assert d.decision == "deny" and "read-only" in d.message and ctx.refused and not c.of("queue_item")


# ------------------------------------------------------------------ use counter
def test_use_counter_survives_a_restart(tmp_path):
    path = tmp_path / "home" / "settings.json"
    s = Store(path)
    s.add(tmp_path)
    assert s.add_use("launchpad-builder") == 1 and s.add_use("launchpad-builder") == 2
    s.add_use("copy-reviewer")
    again = Store(path)                                                          # a new launch
    assert again.uses() == {"launchpad-builder": 2, "copy-reviewer": 1}
    assert again.add_use("launchpad-builder") == 3
    assert Store(path).directories()                                             # other data untouched


def test_counts_for_planner_explore_steps_run_and_chat(harness, project):
    h = harness()
    fake.script("launchpad-planner", [[fake.call("explore", {"question": "q"}), fake.call("write_plan", ONE)]])
    fake.script("launchpad-astronaut", [[fake.output({"links": []})]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])
    fake.script("launchpad-pilot", [[fake.say("hi")]] * 3)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "a"})
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "b"})
        await hub.activity({"type": "activity", "id": "x", "session_id": hub.current.id, "chat_id": None,
                            "agent_id": "visual-1", "role": "visual", "name": "Visualizer", "step": None,
                            "tool": "render", "summary": "v1/o1", "status": "started", "ts": "t"})
        await hub.handle({"type": "get_crew"})
        return hub, c
    hub, c = asyncio.run(go())
    last = {}
    for e in c.of("agent_uses"):
        last[e["name"]] = e["uses"]
    assert last == {"launchpad-planner": 1, "launchpad-astronaut": 1, "launchpad-orchestrator": 1,
                    "launchpad-builder": 1, "launchpad-pilot": 1, "launchpad-visual": 1}
    uses = {a["name"]: a["uses"] for a in c.of("crew_list")[-1]["agents"]}
    assert uses == last


# ------------------------------------------------------------------ draft / create / remove
def test_agent_draft_returns_a_clean_form(harness, project):
    h = harness()
    fake.script("launchpad-drafter", [[fake.output({
        "name": "Copy Reviewer!", "description": "Checks copy.", "purpose": "reviewing", "model": "haiku",
        "tools": ["Read", "Write", "Grep"], "instructions": "- Check the copy."})]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "an agent that reviews copy"})
        fake.script("launchpad-drafter", [[fake.say("not json at all")]])
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "again"})
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "  "})
        return c
    c = asyncio.run(go())
    ok, bad, empty = c.of("agent_drafted")
    assert ok["ok"] is True and ok["fields"] == {"name": "copy-reviewer", "description": "Checks copy.",
                                                 "purpose": "reviewing", "model": "haiku", "tools": ["Read", "Grep"],
                                                 "instructions": "- Check the copy."}    # Write dropped: read-only
    assert bad["ok"] is False and bad["error"] and empty["ok"] is False
    drafter_usage = [e for e in c.of("agent_usage") if e["role"] == "drafter"]
    assert drafter_usage and drafter_usage[-1]["session_id"] is None and drafter_usage[-1]["chat_id"] is None


def test_drafter_is_lean_haiku_and_tool_free(project):
    a = crew.load("drafter", engine="claude", project=project, output_schema=drafter.DRAFT_SCHEMA,
                  save_conversation=False)
    r = a.resolved_tools()
    assert a.setup == "lean" and a.model == "haiku" and r.builtin_rules == [] and r.custom == []
    assert len(a.instructions) < 1500


def test_agent_create_validates_and_writes_the_file(harness, project):
    h = harness()
    good = {"name": "csv-maker", "description": "Makes CSV files: one per table.", "purpose": "building",
            "model": "sonnet", "tools": ["Read", "Write", "Bash"], "instructions": "- Write the CSV.\n- Say where."}

    async def go():
        hub, c = await h.start()
        did = hub.default_dir
        for fields in (good, {**good, "name": "launchpad-builder"}, good, {**good, "name": "x2", "purpose": "planning"},
                       {**good, "name": "Bad Name", "model": "gpt-9", "tools": ["Telnet"]},
                       {**good, "name": "peek", "purpose": "reviewing", "tools": ["Read", "Write"]},
                       {**good, "name": "empty", "instructions": "", "description": ""}):
            await hub.handle({"type": "agent_create", "dir_id": did, "fields": fields})
        await hub.handle({"type": "agent_create", "dir_id": "dnope", "fields": good})
        return hub, c
    hub, c = asyncio.run(go())
    saved = c.of("agent_saved")
    assert saved[0] == {"type": "agent_saved", "ok": True, "dir_id": hub.default_dir, "name": "csv-maker"}
    text = (project / ".claude" / "agents" / "csv-maker.md").read_text(encoding="utf-8")
    assert "purpose: building" in text and "tools: Read, Write, Bash" in text and "model: sonnet" in text
    from app.files import agent_problems
    assert agent_problems(text) == []
    refused = saved[1:]
    assert all(e["ok"] is False and isinstance(e["problems"], list) for e in refused)
    assert "built-in" in refused[0]["problems"][0]
    assert "already has an agent" in refused[1]["problems"][0]
    assert "planning agents cannot be added" in refused[2]["problems"][0]
    assert {p.split(":")[0] for p in refused[3]["problems"]} == {"name", "model", "tools"}
    assert "read-only" in refused[4]["problems"][0]
    assert {p.split(":")[0] for p in refused[5]["problems"]} == {"description", "instructions"}
    assert refused[6]["error"] == "that folder is not connected"
    crew_after = [e for e in c.of("crew_list") if any(a["name"] == "csv-maker" for a in e["agents"])]
    assert crew_after and crew_after[0]["dir_id"] == hub.default_dir


def test_agent_remove_keeps_a_backup_and_refuses_builtins(harness, project):
    agent_file(project, "copy-reviewer", purpose="reviewing")
    h = harness()

    async def go():
        hub, c = await h.start()
        did = hub.default_dir
        await hub.handle({"type": "agent_remove", "dir_id": did, "name": "launchpad-builder"})
        await hub.handle({"type": "agent_remove", "dir_id": did, "name": "nobody"})
        await hub.handle({"type": "agent_remove", "dir_id": did, "name": "copy-reviewer"})
        await hub.handle({"type": "list_backups", "root": did, "path": ".claude/agents/copy-reviewer.md"})
        bid = c.of("backups")[-1]["items"][0]["backup_id"]
        await hub.handle({"type": "restore_backup", "root": did, "path": ".claude/agents/copy-reviewer.md",
                          "backup_id": bid})
        return hub, c
    hub, c = asyncio.run(go())
    builtin, unknown, ok = c.of("agent_removed")
    assert builtin["ok"] is False and "built-in" in builtin["error"] and unknown["ok"] is False
    assert ok == {"type": "agent_removed", "ok": True, "dir_id": hub.default_dir, "name": "copy-reviewer"}
    after_remove = c.of("crew_list")[-2] if len(c.of("crew_list")) > 1 else c.of("crew_list")[-1]
    assert not any(a["name"] == "copy-reviewer" for a in after_remove["agents"])
    backups = Path(os.environ["LAUNCHPAD_HOME"]) / "backups" / hub.default_dir
    assert backups.is_dir()
    assert (project / ".claude" / "agents" / "copy-reviewer.md").is_file()          # restored from the backup
    assert any(a["name"] == "copy-reviewer" for a in c.of("crew_list")[-1]["agents"])   # folder save -> fresh list


def test_editing_a_folder_agent_refreshes_crew_list(harness, project):
    agent_file(project, "copy-reviewer", purpose="reviewing")
    h = harness()

    async def go():
        hub, c = await h.start()
        did = hub.default_dir
        rel = ".claude/agents/copy-reviewer.md"
        await hub.handle({"type": "read_file", "root": did, "path": rel})
        fc = c.of("file_content")[-1]
        await hub.handle({"type": "save_file", "root": did, "path": rel, "base_version": fc["version"],
                          "text": fc["text"].replace("purpose: reviewing", "purpose: exploring")})
        bad = c.of("file_saved")[-1]
        await hub.handle({"type": "read_file", "root": did, "path": rel})
        fc = c.of("file_content")[-1]
        await hub.handle({"type": "save_file", "root": did, "path": rel, "base_version": fc["version"],
                          "text": fc["text"].replace("purpose: exploring", "purpose: wandering")})
        return c, bad
    c, saved = asyncio.run(go())
    card = next(a for a in c.of("crew_list")[-1]["agents"] if a["name"] == "copy-reviewer")
    assert card["purpose"] == "exploring" and saved["applies"] == "new_sessions"
    assert c.of("file_error")[-1]["code"] == "invalid" and "purpose" in c.of("file_error")[-1]["message"]


# ------------------------------------------------------------------ chat_from_plan
def test_chat_from_plan_opens_claude_code_in_plan_mode_with_the_plan(harness, project):
    h = harness()
    fake.script("launchpad-planner", [[fake.call("write_plan", ONE)]])
    got = []
    fake.script("launchpad-pilot", [lambda m: got.append(m) or [fake.say("Let me look first.")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "chat_from_plan", "session_id": hub.current.id})       # no draft yet
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "chat_from_plan", "session_id": hub.current.id})
        late = Client(hub)                                                        # a reload afterwards
        await hub.connect(late)
        return hub, c, late
    hub, c, late = asyncio.run(go())
    assert any("no plan draft" in e["text"] for e in c.of("system"))
    # the plan shows as the user's first message, live and on reconnect
    user_msgs = [e for e in c.of("chat_message") if e["role"] == "user"]
    assert len(user_msgs) == 1 and "# Test plan" in user_msgs[0]["markdown"]
    kinds = [e["type"] for e in c.events if e.get("chat_id") == user_msgs[0]["chat_id"]
             and e["type"] in ("chat_started", "chat_message")]
    assert kinds[:2] == ["chat_started", "chat_message"]                         # before the assistant's reply
    replay = next(x for x in late.events[0]["chats"] if x["id"] == user_msgs[0]["chat_id"])
    assert replay["history"][0] == {"role": "user", "markdown": user_msgs[0]["markdown"]}
    started = c.of("chat_started")[-1]
    assert started["mode"] == "plan" and started["from_session_id"] == hub.current.id
    assert started["dir_id"] == hub.current.dir_id
    chat = hub.chats[started["chat_id"]]
    assert chat.agent.permission_mode == "plan" and chat.session.permission_mode == "plan"
    assert got and "# Test plan" in got[0] and "plan.md" in got[0]
    assert chat.history[0]["role"] == "user" and "# Test plan" in chat.history[0]["markdown"]
    assert c.of("chat_done")[-1]["status"] == "ok"
    assert hub.current.draft_pending                                              # still approvable
    assert [e["name"] for e in c.of("agent_uses") if e["name"] == "launchpad-pilot"] == ["launchpad-pilot"]


def test_folder_agent_name_cannot_clash_with_a_builtin_file_name(project):
    with pytest.raises(folder_agents.AgentFormError):
        folder_agents.create(None, "d", project, {"name": "launchpad-drafter", "description": "x", "purpose": "building",
                                                 "tools": [], "instructions": "y"})
