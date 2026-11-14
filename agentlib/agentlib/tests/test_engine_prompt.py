"""engine_prompt: lean isolation, but the engine's own agent prompt with the agent's instructions appended."""
from agentlib import Agent
from agentlib.engines import get_engine
from agentlib.engines.base import requirements


def test_claude_lean_with_engine_prompt_uses_preset_but_no_settings():
    a = Agent("b", instructions="Finish with submit_report.", tools=["Read", "Bash"], engine_prompt=True)
    s = get_engine("claude").open(a, resume=None, fork=False, cost_base=0)
    assert s._system_prompt() == {"type": "preset", "preset": "claude_code", "append": "Finish with submit_report."}
    opts = s.options(resume=None)
    assert opts.setting_sources == [] and opts.strict_mcp_config is True          # still lean: no folder settings
    assert opts.env.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS") == "1"                    # no CLAUDE.md
    assert sorted(opts.tools) == ["Bash", "Read"]                                   # only the listed built-ins


def test_default_lean_keeps_own_prompt_and_capability_is_requested():
    a = Agent("p", instructions="Plan.", tools=[])
    assert get_engine("claude").open(a, resume=None, fork=False, cost_base=0)._system_prompt() == "Plan."
    assert requirements(a)["engine_prompt"] is False
    assert requirements(Agent("b", instructions="x", engine_prompt=True))["engine_prompt"] is True
    assert get_engine("fake").capabilities.engine_prompt and not get_engine("cursor").capabilities.engine_prompt
