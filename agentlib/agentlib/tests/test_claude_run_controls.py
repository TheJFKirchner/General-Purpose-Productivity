"""Claude engine: spending cap, never_ask, output_schema, save_conversation, model list (no process, no tokens)."""
import asyncio

from agentlib import Agent
from agentlib.engines import claude as ce          # SDK types via the engine module (no direct SDK import)
from agentlib.engines.claude import ClaudeSession, parse_models

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}


def _opts(agent):
    return ClaudeSession(agent, resume=None, fork=False, cost_base=0).options(resume=None)


def test_defaults_unchanged():
    o = _opts(Agent("a", include_ask_user=False))
    assert o.permission_mode == "default" and o.can_use_tool is not None
    assert o.max_budget_usd is None and o.output_format is None
    assert o.extra_args == {"disable-slash-commands": None}


def test_run_controls_map_to_sdk_options():
    o = _opts(Agent("a", include_ask_user=False, max_budget_usd=0.5, permission_mode="never_ask",
                    output_schema=SCHEMA, save_conversation=False))
    assert o.max_budget_usd == 0.5
    assert o.permission_mode == "dontAsk" and o.can_use_tool is None
    assert o.output_format == {"type": "json_schema", "schema": SCHEMA}
    assert o.extra_args == {"disable-slash-commands": None, "no-session-persistence": None}


def test_project_setup_unsaved_keeps_only_its_flag():
    o = _opts(Agent("a", setup="project", save_conversation=False))
    assert o.extra_args == {"no-session-persistence": None}


class _Client:
    def __init__(self, messages):
        self.messages = messages

    async def query(self, message):
        return None

    async def receive_response(self):
        for m in self.messages:
            yield m

    async def disconnect(self):
        return None

    async def interrupt(self):
        return None


def _result(subtype="success", is_error=False, result=None, structured=None, cost=0.01):
    return ce.ResultMessage(subtype=subtype, duration_ms=1, duration_api_ms=1, is_error=is_error, num_turns=1,
                            session_id="sid", total_cost_usd=cost, usage={"input_tokens": 5, "output_tokens": 3},
                            result=result, structured_output=structured)


def _run(agent, messages):
    s = ClaudeSession(agent, resume=None, fork=False, cost_base=0)
    s._client = _Client(messages)

    async def go():
        q = asyncio.Queue()
        await s._turn("hi", q)
        out = []
        while not q.empty():
            out.append(q.get_nowait())
        return out
    events = asyncio.run(go())
    return events[-1].reply, events, s


def test_budget_stop_is_error_kind_budget():
    r, _, s = _run(Agent("a", include_ask_user=False, max_budget_usd=0.01),
                   [_result("error_max_budget_usd", is_error=True, cost=0.02)])
    assert r.status == "error" and r.error_kind == "budget" and "spending cap" in r.error
    assert r.cost_usd == 0.02 and r.usage.output_tokens == 3
    assert s._client is None                      # dropped: the next turn reconnects with resume


def test_max_turns_and_other_errors():
    r, _, _ = _run(Agent("a", include_ask_user=False, max_turns=2), [_result("error_max_turns", is_error=True)])
    assert (r.status, r.error_kind) == ("error", "max_turns")
    r, _, _ = _run(Agent("a", include_ask_user=False), [_result(is_error=True, result="API Error: 500")])
    assert (r.error_kind, r.error) == ("other", "API Error: 500")
    r, _, _ = _run(Agent("a", include_ask_user=False), [_result()])
    assert r.status == "done" and r.error_kind is None


def test_structured_output_native_value_and_hidden_tool():
    use = ce.AssistantMessage(content=[ce.ToolUseBlock("t1", "StructuredOutput", {"title": "Hi"})],
                              model="claude-haiku", message_id="m1")
    done = ce.UserMessage(content=[ce.ToolResultBlock("t1", "Structured output provided successfully")])
    r, events, _ = _run(Agent("a", tools=[], include_ask_user=False, output_schema=SCHEMA),
                        [use, done, _result(structured={"title": "Hi"})])
    assert r.status == "done" and r.data == {"title": "Hi"}
    assert r.tool_calls == [] and [e.type for e in events] == ["done"]


def test_structured_output_falls_back_to_tool_input_then_text():
    use = ce.AssistantMessage(content=[ce.ToolUseBlock("t1", "StructuredOutput", {"title": "From tool"})],
                              model="claude-haiku", message_id="m1")
    r, _, _ = _run(Agent("a", tools=[], include_ask_user=False, output_schema=SCHEMA), [use, _result()])
    assert r.data == {"title": "From tool"}
    r, _, _ = _run(Agent("a", tools=[], include_ask_user=False, output_schema=SCHEMA),
                   [_result(result='```json\n{"title": "From text"}\n```')])
    assert r.data == {"title": "From text"}


def test_malformed_structured_reply_is_output_shape_error():
    r, _, _ = _run(Agent("a", tools=[], include_ask_user=False, output_schema=SCHEMA),
                   [_result(structured={"name": "x"})])
    assert r.status == "error" and r.error_kind == "output_shape" and "title" in r.error and r.data is None
    r, _, _ = _run(Agent("a", tools=[], include_ask_user=False, output_schema=SCHEMA),
                   [_result("error_max_structured_output_retries", is_error=True)])
    assert r.error_kind == "output_shape"


def test_parse_models_merges_aliases():
    info = {"models": [
        {"value": "default", "resolvedModel": "claude-opus-5-5", "displayName": "Default (recommended)",
         "description": "Opus 5.5 · Best for everyday tasks", "supportedEffortLevels": ["low", "high"]},
        {"value": "opus", "resolvedModel": "claude-opus-5-5", "displayName": "Opus",
         "description": "Opus 5.5 · Best for everyday tasks"},
        {"value": "haiku", "resolvedModel": "claude-haiku-5-5", "displayName": "Haiku",
         "description": "Haiku 5.5 · Fastest for quick answers"},
        {"value": "custom-model", "displayName": "Custom"},
    ]}
    ms = parse_models(info)
    assert [m.id for m in ms] == ["claude-opus-5-5", "claude-haiku-5-5", "custom-model"]
    opus = ms[0]
    assert (opus.name, opus.description, opus.aliases, opus.is_default, opus.effort_levels) == \
        ("Opus 5.5", "Best for everyday tasks", ["default", "opus"], True, ["low", "high"])
    assert ms[1].aliases == ["haiku"] and not ms[1].is_default
    assert ms[2].name == "Custom" and ms[2].aliases == []
    assert parse_models(None) == [] and parse_models({}) == []
