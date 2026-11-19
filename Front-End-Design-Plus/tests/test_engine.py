"""The engine module without spending tokens: the options of the minimal Claude session, sign-in pass-through,
per-turn figures from the CLI's running totals, and the fake engine."""
import asyncio
import json
from types import SimpleNamespace

from whiteboard import engine as eng


def test_claude_session_options_are_minimal(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-config"))
    o = eng.ClaudeEngine(model="sonnet", effort="low", cache_ttl="5m").options(str(tmp_path / "p.md"), str(tmp_path))
    assert o.system_prompt == {"type": "file", "path": str(tmp_path / "p.md")}   # replaces the default prompt
    assert o.tools == [] and o.allowed_tools == [] and o.setting_sources == []
    assert o.strict_mcp_config is True and not o.mcp_servers and o.agents is None and o.skills is None
    assert o.plugins == [] and o.hooks is None and o.can_use_tool is None
    assert o.effort == "low" and o.model == "sonnet" and o.include_partial_messages is True
    assert o.extra_args == {"disable-slash-commands": None, "no-session-persistence": None}
    assert o.cwd == str(tmp_path) and o.settings is None
    for k, v in eng.LEAN_ENV.items():
        assert o.env[k] == v
    assert o.env["CLAUDE_CODE_PROMPT_CACHE_TTL"] == "5m"


def test_signin_parts_of_user_settings_pass_through_and_nothing_else(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.json").write_text(json.dumps({
        "apiKeyHelper": "get-key.sh", "hooks": {"x": 1}, "permissions": {"allow": ["Bash"]},
        "env": {"ANTHROPIC_BASE_URL": "https://gateway.example", "HTTPS_PROXY": "http://proxy:1",
                "MAX_THINKING_TOKENS": "9000", "CLAUDE_CODE_USE_BEDROCK": "1"}}), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    env, settings = eng.signin_from_user_settings()
    assert settings == {"apiKeyHelper": "get-key.sh"}
    assert env == {"ANTHROPIC_BASE_URL": "https://gateway.example", "HTTPS_PROXY": "http://proxy:1",
                   "CLAUDE_CODE_USE_BEDROCK": "1"}
    o = eng.ClaudeEngine().options("p.md", str(tmp_path))
    assert json.loads(o.settings) == {"apiKeyHelper": "get-key.sh"} and o.env["ANTHROPIC_BASE_URL"]


def result_msg(model_usage, total_cost, num_turns=1, is_error=False):
    return SimpleNamespace(model_usage=model_usage, total_cost_usd=total_cost, num_turns=num_turns,
                           is_error=is_error, errors=None, result=None, subtype="success", usage=None)


def mu(i, o, cr, cw, cost):
    return {"inputTokens": i, "outputTokens": o, "cacheReadInputTokens": cr, "cacheCreationInputTokens": cw,
            "costUSD": cost}


def test_per_turn_figures_from_running_totals():
    e = eng.ClaudeEngine()
    r1 = e._result(result_msg({"claude-sonnet-5-5": mu(4, 2000, 0, 5000, 0.05)}, 0.05), "a")
    assert r1.usage == {"input_tokens": 4, "output_tokens": 2000, "cache_read_tokens": 0, "cache_write_tokens": 5000}
    assert abs(r1.cost_usd - 0.05) < 1e-9 and r1.model == "claude-sonnet-5-5" and r1.api_calls == 1
    r2 = e._result(result_msg({"claude-sonnet-5-5": mu(7, 2600, 5000, 5800, 0.065),
                               "claude-haiku-5-5": mu(100, 5, 0, 0, 0.0001)}, 0.0651), "b")
    assert r2.usage == {"input_tokens": 103, "output_tokens": 605, "cache_read_tokens": 5000, "cache_write_tokens": 800}
    assert abs(r2.cost_usd - 0.0151) < 1e-9 and set(r2.by_model) == {"claude-sonnet-5-5", "claude-haiku-5-5"}


def test_fake_engine_streams_and_reports():
    async def go():
        f = eng.FakeEngine(["@say hello there, this reply is longer than forty characters in total\n"])
        await f.start("PROMPT" * 100)
        items = [x async for x in f.send("hi")]
        await f.close()
        return items

    items = asyncio.run(go())
    chunks, result = items[:-1], items[-1]
    assert len(chunks) > 1 and "".join(chunks) == result.text and result.model == "fake engine"
    assert result.api_calls == 1 and result.usage["cache_write_tokens"] == 150 and result.cost_usd > 0
