"""Fake engine: spending cap, never_ask, structured one-shot replies, unsaved conversations, model list."""
import asyncio

import pytest

from agentlib import (Agent, AgentError, ConversationMissing, ModelInfo, ask_structured, ask_structured_sync,
                      list_models, list_models_sync)
from agentlib import fake

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "tags": {"type": "array",
          "items": {"type": "string"}}}, "required": ["title", "tags"], "additionalProperties": False}


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()
    yield
    fake.reset()


def run(coro):
    return asyncio.run(coro)


# --- spending cap ---------------------------------------------------------------------------------------
def test_cap_stop_is_distinct_and_keeps_partial_turn():
    fake.script("a", [[fake.say("Step one"), fake.spend(0.04), fake.say("Step two"), fake.spend(0.04),
                       fake.say("never said")]])
    r = Agent("a", engine="fake", max_budget_usd=0.05).ask_sync("go")
    assert r.status == "error" and r.error_kind == "budget"
    assert r.error == "stopped at the spending cap (max_budget_usd=0.05)"
    assert r.text == "Step one\n\nStep two"           # stopped right after the step that crossed the cap
    assert r.cost_usd > 0.08 and r.usage.input_tokens > 0


def test_under_cap_or_no_cap_finishes():
    fake.script("a", [[fake.spend(0.04), fake.say("ok")]])
    assert Agent("a", engine="fake", max_budget_usd=0.05).ask_sync("go").status == "done"
    fake.script("a", [[fake.spend(10), fake.say("ok")]])
    r = Agent("a", engine="fake").ask_sync("go")
    assert r.status == "done" and r.error_kind is None and r.cost_usd > 10


def test_cap_counts_the_whole_session():
    fake.script("a", [[fake.spend(0.03), fake.say("one")], [fake.spend(0.03), fake.say("two")]])

    async def go():
        async with Agent("a", engine="fake", max_budget_usd=0.05).session() as s:
            return await s.send("1"), await s.send("2")
    r1, r2 = run(go())
    assert r1.status == "done" and (r2.status, r2.error_kind) == ("error", "budget")


def test_bad_cap_rejected():
    with pytest.raises(ValueError):
        Agent("a", engine="fake", max_budget_usd=0)


# --- never ask -----------------------------------------------------------------------------------------
def test_never_ask_denies_unapproved_tool_and_allows_listed():
    fake.script("a", [[fake.call("Bash", {"command": "echo hi"}), fake.call("Bash", {"command": "mkdir x"}),
                       fake.say("done")]])
    r = Agent("a", engine="fake", tools=["Bash(echo:*)"], permission_mode="never_ask").ask_sync("go")
    assert [c.is_error for c in r.tool_calls] == [False, True]
    assert "never_ask" in r.tool_calls[1].result and "not allowed" in r.tool_calls[1].result
    assert r.status == "done"                          # a denial is a tool error, not a failed run


def test_never_ask_rejects_permission_hook_and_bad_mode():
    with pytest.raises(ValueError, match="never_ask"):
        Agent("a", engine="fake", permission_mode="never_ask", on_permission=lambda req: "allow")
    with pytest.raises(ValueError, match="permission_mode"):
        Agent("a", engine="fake", permission_mode="dontAsk")


# --- structured output ---------------------------------------------------------------------------------
def test_structured_reply_from_output_step():
    fake.script("structured", [[fake.output({"title": "Jupiter review", "tags": ["sales"]})]])
    r = ask_structured_sync("Summarise", SCHEMA, engine="fake", model="fake-small")
    assert r.status == "done" and r.data == {"title": "Jupiter review", "tags": ["sales"]}
    assert r.usage.output_tokens > 0 and r.cost_usd > 0 and r.model == "fake-small" and r.tool_calls == []


def test_structured_reply_parsed_from_text():
    fake.script("summ", [[fake.say('Here: ```json\n{"title": "T", "tags": []}\n```')]])
    r = run(ask_structured("Summarise", SCHEMA, engine="fake", name="summ"))
    assert r.data == {"title": "T", "tags": []}


@pytest.mark.parametrize("steps, needle", [
    ([fake.output({"title": "T"})], "tags"),                        # missing required field
    ([fake.output({"title": 3, "tags": []})], "title"),             # wrong type
    ([fake.say("no json here")], "no JSON"),                        # not JSON at all
    ([fake.say("")], "empty"),
])
def test_malformed_structured_reply_is_clear_error(steps, needle):
    fake.script("structured", [steps])
    r = ask_structured_sync("Summarise", SCHEMA, engine="fake")
    assert r.status == "error" and r.error_kind == "output_shape" and r.data is None
    assert r.error.startswith("reply did not match the output schema") and needle in r.error
    assert r.usage.input_tokens > 0                    # usage is kept for the failed call


def test_structured_one_shot_is_not_saved():
    fake.script("structured", [[fake.output({"title": "T", "tags": []})]])
    r = ask_structured_sync("x", SCHEMA, engine="fake")
    with pytest.raises(ConversationMissing):
        Agent("structured", engine="fake").session(resume=r.session_id)


def test_output_schema_must_be_valid_schema():
    with pytest.raises(ValueError, match="not a valid JSON Schema"):
        Agent("a", engine="fake", output_schema={"type": "nonsense"})


def test_output_schema_on_a_normal_agent():
    fake.script("a", [[fake.say("thinking"), fake.output({"title": "T", "tags": ["x"]})]])
    r = Agent("a", engine="fake", output_schema=SCHEMA).ask_sync("go")
    assert r.data == {"title": "T", "tags": ["x"]} and r.text == "thinking"


# --- unsaved conversations -----------------------------------------------------------------------------
def test_unsaved_conversation_cannot_be_resumed_and_saved_one_is_untouched():
    fake.script("a", [[fake.say("one")], [fake.say("two")]])
    saved = Agent("a", engine="fake").ask_sync("1")
    r = run(_resume_unsaved(saved.session_id))
    assert r.text == "two"
    async def again():                                  # the saved conversation did not advance
        async with Agent("a", engine="fake").session(resume=saved.session_id) as s:
            return await s.send("2 again")
    assert run(again()).text == "two"


async def _resume_unsaved(sid):
    async with Agent("a", engine="fake", save_conversation=False).session(resume=sid) as s:
        return await s.send("2")


# --- model list ----------------------------------------------------------------------------------------
def test_default_model_list():
    ms = list_models_sync("fake")
    assert [m.id for m in ms] == ["fake-large", "fake-small"]
    assert ms[0].is_default and "default" in ms[0].aliases and ms[0].name == "Fake Large"


def test_scripted_model_list_and_failure():
    fake.models(["m-1", {"id": "m-2", "name": "Model Two", "description": "Quick", "is_default": True},
                 ModelInfo(id="m-3")])
    ms = run(list_models("fake"))
    assert [(m.id, m.name, m.is_default) for m in ms] == [("m-1", "m-1", False), ("m-2", "Model Two", True),
                                                           ("m-3", "", False)]
    assert ms[1].to_dict()["description"] == "Quick"
    fake.models(fail="Claude Code not signed in")
    with pytest.raises(AgentError, match="not signed in"):
        list_models_sync("fake")
