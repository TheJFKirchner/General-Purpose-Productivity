"""project_rules: caller-supplied project rules text added after the instructions; the agent stays lean (no tokens)."""
import asyncio

import pytest

from agentlib import Agent, AgentError, CapabilityError, fake, load_claude_agent, prompt_files, register_engine
from agentlib.engines import get_engine
from agentlib.engines.base import requirements
from agentlib.engines.claude import ARGV_PROMPT_LIMIT

RULES = "# Repo rules\n- Run the tests before you finish.\n- Never edit generated files."
PRESET = {"type": "preset", "preset": "claude_code"}


def _session(agent):
    return get_engine("claude").open(agent, resume=None, fork=False, cost_base=0)


def _prompt(**kw):
    return _session(Agent("a", **kw))._system_prompt()


def _block(rules=RULES):
    return prompt_files.fill("project_rules", rules=rules)


@pytest.fixture(autouse=True)
def _clean():
    fake.reset()
    yield
    fake.reset()


@pytest.mark.parametrize("unset", [None, "", "  \n "])
def test_unset_or_blank_leaves_every_prompt_unchanged(unset):
    assert _prompt(instructions="Plan.", project_rules=unset) == "Plan."
    assert _prompt(project_rules=unset) == ""
    assert _prompt(instructions="Plan.", engine_prompt=True, project_rules=unset) == {**PRESET, "append": "Plan."}
    assert _prompt(engine_prompt=True, project_rules=unset) == PRESET
    assert _prompt(instructions="Plan.", setup="project", project_rules=unset) == {**PRESET, "append": "Plan."}
    long = "x" * (ARGV_PROMPT_LIMIT + 1)                     # long lean prompt still goes through a file, unchanged
    sp = _prompt(instructions=long, project_rules=unset)
    assert sp["type"] == "file" and open(sp["path"], encoding="utf-8").read() == long
    assert requirements(Agent("a", project_rules=unset))["project_rules"] is False


def test_lean_prompt_is_instructions_then_rules_under_a_heading():
    sp = _prompt(instructions="Plan.", project_rules=RULES)
    assert sp == "Plan.\n\n" + _block()
    assert _block().startswith("## Project rules\n") and _block().endswith(RULES)
    assert sp.index("Plan.") < sp.index("## Project rules") < sp.index("Run the tests")
    assert _prompt(project_rules=f"\n{RULES}\n\n") == _block()           # no instructions: just the block, trimmed


def test_engine_prompt_appends_instructions_then_rules_to_the_preset():
    sp = _prompt(instructions="Finish with submit_report.", engine_prompt=True, project_rules=RULES)
    assert sp == {**PRESET, "append": "Finish with submit_report.\n\n" + _block()}


def test_agent_stays_lean_with_rules():
    s = _session(Agent("a", instructions="x", tools=["Read"], engine_prompt=True, project_rules=RULES))
    opts = s.options(resume=None)
    assert opts.setting_sources == [] and opts.strict_mcp_config is True
    assert opts.env.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS") == "1"
    assert requirements(s.agent)["project_rules"] is True


def test_too_long_with_engine_prompt_fails_naming_project_rules():
    rules = "r" * ARGV_PROMPT_LIMIT
    with pytest.raises(AgentError, match="project rules") as ei:
        _prompt(instructions="x", engine_prompt=True, project_rules=rules)
    assert f"{ARGV_PROMPT_LIMIT:,}" in str(ei.value)
    with pytest.raises(AgentError) as ei:                                # without rules: no mention of them
        _prompt(instructions="x" * (ARGV_PROMPT_LIMIT + 1), engine_prompt=True)
    assert "project rules" not in str(ei.value)
    sp = _prompt(instructions="x", project_rules=rules)                  # plain lean: long prompts use a file
    assert sp["type"] == "file"


def test_project_setup_ignores_rules():
    a = Agent("a", instructions="Plan.", setup="project", project_rules=RULES)
    assert a.rules_text() is None and requirements(a)["project_rules"] is False
    assert _session(a)._system_prompt() == {**PRESET, "append": "Plan."}     # the CLI loads CLAUDE.md itself


def test_set_after_loading_applies_to_later_sessions(tmp_path):
    f = tmp_path / ".claude" / "agents" / "builder.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\nname: builder\n---\nBuild it.\n", encoding="utf-8")
    a = load_claude_agent(f, engine_prompt=True)
    assert _session(a)._system_prompt() == {**PRESET, "append": "Build it."}
    a.project_rules = RULES
    assert _session(a)._system_prompt() == {**PRESET, "append": "Build it.\n\n" + _block()}
    b = load_claude_agent(f, project_rules=RULES)                         # as a load override
    assert _session(b)._system_prompt() == "Build it.\n\n" + _block()


def test_capability_flags():
    assert get_engine("claude").capabilities.project_rules and get_engine("fake").capabilities.project_rules
    assert not get_engine("cursor").capabilities.project_rules


def test_engine_without_it_refuses():
    from dataclasses import replace

    from agentlib.fake import FakeEngine

    class NoRules(FakeEngine):
        name = "norules"
        capabilities = replace(FakeEngine.capabilities, project_rules=False)
    register_engine("norules", NoRules)
    with pytest.raises(CapabilityError, match="project_rules"):
        Agent("a", engine="norules", project_rules=RULES).session()
    Agent("a", engine="norules", project_rules=RULES, setup="project").session()   # ignored there: not needed


def test_fake_records_what_each_session_was_given():
    async def run():
        a = Agent("builder", engine="fake", instructions="Build.", project_rules=RULES)
        p = Agent("planner", engine="fake", instructions="Plan.")
        async with a.session() as s:
            assert s._es.project_rules == RULES                          # also on the engine session
            await s.send("go")
        await p.ask("plan")
        a.project_rules = None                                           # changed after loading: next session
        await a.ask("again")
        await Agent("proj", engine="fake", setup="project", project_rules=RULES).ask("x")
    asyncio.run(run())
    got = [(r["agent"], r["project_rules"]) for r in fake.opened()]
    assert got == [("builder", RULES), ("planner", None), ("builder", None), ("proj", None)]
    assert all(r["session_id"] for r in fake.opened())
    fake.reset()
    assert fake.opened() == []


def test_fake_mirrors_the_preset_size_limit():
    a = Agent("b", engine="fake", instructions="x", engine_prompt=True, project_rules="r" * 30_000)
    with pytest.raises(AgentError, match="project rules"):
        a.ask_sync("go")
    Agent("b", engine="fake", instructions="x", project_rules="r" * 30_000).ask_sync("go")   # plain lean: fine
