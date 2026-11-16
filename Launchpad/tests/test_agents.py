"""The built-in agent files (app/agents/<folder>/agent.md): standard format, minimum tools, one folder per agent;
the planner cannot read code, write or run anything."""
import asyncio

import pytest

from agentlib import fake
from agentlib.loaders import frontmatter

from app.agents import crew
from app.agents.builder.builder import builder_tools
from app.agents.orchestrator.run import orchestrator_tools
from app.agents.planner.planner import planner_tools, read_markdown_file

STANDARD = {"name", "description", "tools", "model"}


@pytest.mark.parametrize("role,model", [("planner", "opus"), ("astronaut", "haiku"),
                                        ("orchestrator", "sonnet"), ("builder", "sonnet"), ("pilot", "sonnet"),
                                        ("visual", "haiku"), ("drafter", "haiku")])
def test_agent_files_are_standard(role, model):
    path = crew.agent_file(role)
    meta, body = frontmatter.read(path)
    assert set(meta) <= STANDARD and meta["model"] == model and meta["name"].startswith("launchpad-")
    if role == "pilot":
        assert body.strip() == "" and "tools" not in meta            # Claude Code's own prompt and tools
    else:
        assert body.strip() and len(body) < 2500                   # lean prompt


FOLDERS = {"planner": "planner", "astronaut": "explorer", "orchestrator": "orchestrator", "builder": "builder",
           "visual": "visualizer", "pilot": "claude_code", "drafter": "drafter"}


def test_each_builtin_has_its_own_folder_with_definition_code_and_readme():
    """Shared layout: app/agents/<folder>/ holds agent.md, the agent's Python code and a README; no .claude/agents."""
    assert {r: e["folder"] for r, e in {**crew.ROLES, **crew.HELPERS}.items()} == FOLDERS
    for role, folder in FOLDERS.items():
        d = crew.ROOT / "app" / "agents" / folder
        assert crew.agent_file(role) == d / "agent.md" and crew.definition_rel(role) == f"app/agents/{folder}/agent.md"
        assert (d / "agent.md").is_file() and (d / "README.md").is_file()
        assert [p for p in d.glob("*.py") if p.name != "__init__.py"], f"{folder} has no Python code"
    assert crew.CRITERIA_REL == "app/agents/planner/promotion.md" and (crew.ROOT / crew.CRITERIA_REL).is_file()
    assert not (crew.ROOT / ".claude" / "agents").exists()
    assert set(crew.editable_files()) == {f"app/agents/{f}/agent.md" for f in FOLDERS.values()} | {crew.CRITERIA_REL}


def test_visual_agent_has_no_tools_and_its_own_prompt(project):
    a = crew.load("visual", engine="claude", project=project, save_conversation=False)
    r = a.resolved_tools()
    assert a.setup == "lean" and r.builtin_rules == [] and r.custom == [] and not r.all_builtins
    assert "echarts" in a.instructions and a.model == "haiku"


def test_pilot_runs_like_claude_code(project):
    from app.agents.claude_code.pilot import pilot_overrides
    a = crew.load("pilot", engine="claude", project=project, **pilot_overrides("claude"))
    r = a.resolved_tools()
    assert a.setup == "project" and r.all_builtins and r.custom == []     # all built-ins, no ask_user added
    assert a.instructions == "" and a.gated_tools == [] and a.permission_mode == "default"
    assert a.timeout_s is None


def _tools(agent):
    r = agent.resolved_tools()
    return sorted(t.name for t in r.custom), list(r.builtin_rules), list(r.approved_rules)


def test_planner_has_only_its_tools(project):
    a = crew.load("planner", engine="fake", project=project, tools=planner_tools(None))
    custom, builtin, approved = _tools(a)
    assert custom == ["ask_user", "edit_plan", "explore", "read_markdown", "show_visuals", "write_plan"]
    assert builtin == [] and approved == []                        # no Read, Bash, Write, Edit, ...


def test_astronaut_orchestrator_builder_tools(project):
    a = crew.load("astronaut", engine="fake", project=project)
    assert _tools(a) == ([], ["Read", "Grep", "Glob"], ["Read", "Grep", "Glob"])
    o = crew.load("orchestrator", engine="fake", project=project, tools=orchestrator_tools(None))
    assert _tools(o) == (["run_builder", "write_report"], [], [])
    b = crew.load("builder", engine="fake", project=project, tools=builder_tools(None),
                  gated_tools=["Write", "Edit", "Bash"])
    custom, builtin, approved = _tools(b)
    assert custom == ["add_to_flight_log", "ask_question", "submit_report"]
    assert builtin == ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
    assert approved == ["Read", "Grep", "Glob"]                    # writes and shell always reach code


def test_read_markdown_only_md_inside_project(project):
    assert "be nice" in read_markdown_file(project, "CLAUDE.md")
    assert "Notes" in read_markdown_file(project, "docs/notes.md")
    for bad in ("app/main.py", "../outside.md", "docs/../../outside.md", str(project.parent / "outside.md"),
                "missing.md", ""):
        with pytest.raises(ValueError):
            read_markdown_file(project, bad)


def test_planner_tool_refusals_reach_the_model(harness):
    h = harness()
    fake.script("launchpad-planner", [[fake.call("read_markdown", {"path": "app/main.py"}),
                                       fake.call("read_markdown", {"path": "../outside.md"}),
                                       fake.call("read_markdown", {"path": "CLAUDE.md"}),
                                       fake.call("Bash", {"command": "ls"}),
                                       fake.call("Write", {"file_path": "x.md", "content": "x"})]])
    results = []

    async def go():
        hub, _ = await h.start()
        chat = hub.current.chat
        chat.session = chat.agent.session()
        await chat.session.__aenter__()
        reply = await chat.session.send("hi")
        results.extend((c.name, c.is_error) for c in reply.tool_calls)

    asyncio.run(go())
    assert results == [("read_markdown", True), ("read_markdown", True), ("read_markdown", False),
                       ("Bash", True), ("Write", True)]


def test_crew_list_shape(project):
    ev = crew.crew_list("fake", project)
    assert ev["type"] == "crew_list" and len(ev["agents"]) == 6
    keys = {"name", "display_name", "role", "description", "model", "source_path", "instructions",
            "builtin_tools", "custom_tools", "mcp_servers", "disallowed_tools", "warnings"}
    keys |= {"setup", "prompt_note"}
    for a in ev["agents"]:
        assert keys <= set(a)
        if a["role"] != "pilot":
            assert a["warnings"] == [] and a["setup"] == "lean"
        assert all(set(t) == {"name", "description"} for t in a["custom_tools"])
    assert {a["display_name"] for a in ev["agents"]} == {"Planner", "Explorer", "Orchestrator", "Builder",
                                                         "CLI", "Visualizer"}
    visual = next(a for a in ev["agents"] if a["role"] == "visual")
    assert visual["builtin_tools"] == [] and visual["custom_tools"] == [] and visual["model"] == "haiku"
    pilot = next(a for a in ev["agents"] if a["role"] == "pilot")
    assert pilot["setup"] == "project" and "CLI harness's own system prompt" in pilot["prompt_note"]
    assert pilot["gated_tools"] == []                              # fake-only gating is not shown


def test_planner_runs_on_its_own_prompt_without_the_claude_code_preset(project):
    """Lean setup: the file body is the whole system prompt (no Claude Code preset, no built-in tools)."""
    from agentlib.engines import get_engine
    a = crew.load("planner", engine="claude", project=project, tools=planner_tools(None))
    assert a.setup == "lean"
    prompt = get_engine("claude").open(a, resume=None, fork=False, cost_base=0)._system_prompt()
    assert isinstance(prompt, str) and prompt == a.instructions.strip()      # a preset would be a dict
    assert prompt.startswith("You plan work with the user.")
    for role in ("astronaut", "orchestrator", "visual"):                      # own prompt only
        assert crew.load(role, engine="claude", project=project).setup == "lean"


def test_preset_users_are_exactly_the_builder_and_the_pilot(project):
    """Builder: Claude Code prompt + its file text, still lean (no settings). CLI chat: the full harness."""
    from agentlib.engines import get_engine
    ev = crew.crew_list("claude", project)
    assert {a["role"] for a in ev["agents"] if a["engine_prompt"]} == {"builder", "pilot"}
    b = crew.load("builder", engine="claude", project=project, tools=builder_tools(None),
                  gated_tools=["Write", "Edit", "Bash"], engine_prompt=True)
    s = get_engine("claude").open(b, resume=None, fork=False, cost_base=0)
    assert s._system_prompt() == {"type": "preset", "preset": "claude_code", "append": b.instructions.strip()}
    opts = s.options(resume=None)
    assert opts.setting_sources == [] and sorted(opts.tools) == ["Bash", "Edit", "Glob", "Grep", "Read", "Write"]
