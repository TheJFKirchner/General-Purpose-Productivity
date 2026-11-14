"""gated_tools: built-ins offered to the model but never pre-approved (every call goes to on_permission)."""
import pytest

from agentlib import Agent, fake
from agentlib.tools import resolve_tools


@pytest.fixture(autouse=True)
def _clean():
    fake.reset()
    yield
    fake.reset()


def test_resolve_offers_gated_but_does_not_approve_them():
    r = resolve_tools(["Read", "Write", "Bash(ls:*)"], gated=["Write", "Bash", "Edit"])
    assert r.builtin_names == ["Read", "Write", "Bash", "Edit"]      # offered
    assert r.approved_rules == ["Read"]                               # pre-approved
    assert r.builtin_rules == ["Read", "Write", "Bash(ls:*)"]         # what the file listed (describe shows it)


def test_gated_calls_reach_on_permission_on_fake_engine():
    seen = []

    def decide(req):
        seen.append((req.tool, dict(req.input)))
        return "allow" if req.input.get("file_path", "").startswith("ok/") else "deny"

    fake.script("w", [[fake.call("Write", {"file_path": "ok/a.txt", "content": "x"}),
                       fake.call("Write", {"file_path": "../b.txt", "content": "x"}),
                       fake.call("Read", {"file_path": "a.txt"})]])
    a = Agent("w", instructions="write", engine="fake", tools=["Read", "Write"], gated_tools=["Write"],
              on_permission=decide)
    r = a.ask_sync("go")
    assert [c.is_error for c in r.tool_calls] == [False, True, False]
    assert [t for t, _ in seen] == ["Write", "Write"]                  # Read stayed pre-approved


def test_gated_without_hook_is_denied_and_never_ask_rejected():
    fake.script("w", [[fake.call("Bash", {"command": "ls"})]])
    r = Agent("w", instructions="x", engine="fake", tools=["Bash"], gated_tools=["Bash"]).ask_sync("go")
    assert r.tool_calls[0].is_error
    with pytest.raises(ValueError):
        Agent("w", instructions="x", tools=["Bash"], gated_tools=["Bash"], permission_mode="never_ask")


def test_allow_with_changed_input_reaches_the_tool():
    from agentlib import PermissionDecision
    fake.script("q", [[fake.call("AskUserQuestion", {"questions": [{"question": "Colour?", "header": "c",
                                                                   "options": [{"label": "Red"}, {"label": "Blue"}]}]})]])

    def decide(req):
        return PermissionDecision("allow", input={**req.input, "answers": {"Colour?": "Blue"}})

    r = Agent("q", instructions="x", engine="fake", tools=["AskUserQuestion"], gated_tools=["AskUserQuestion"],
              on_permission=decide).ask_sync("go")
    assert not r.tool_calls[0].is_error and '"answers": {"Colour?": "Blue"}' in r.tool_calls[0].result
    with pytest.raises(ValueError):
        PermissionDecision("allow", input="nope")
