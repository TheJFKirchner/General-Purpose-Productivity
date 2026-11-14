"""Claude engine: permission modes, live switch, plan approval, suggestions, always_allow destinations.
No process, no tokens: options() is built directly and _can_use_tool is called with SDK context objects."""
import asyncio

from agentlib import Agent, PermissionDecision, tool
from agentlib.engines import claude as ce          # SDK types via the engine module (no direct SDK import)
from agentlib.engines.claude import ClaudeSession

PermissionUpdate = ce.PermissionUpdate
RuleValue = ce.PermissionRuleValue
Ctx = ce.sdk.ToolPermissionContext


@tool
def lookup(q: str) -> str:
    """Look up."""
    return q


def _session(agent):
    return ClaudeSession(agent, resume=None, fork=False, cost_base=0)


def _opts(agent):
    return _session(agent).options(resume=None)


def _ask(s, tool_name, inp, ctx=None):
    return asyncio.run(s._can_use_tool(tool_name, inp, ctx or Ctx()))


# --- options --------------------------------------------------------------------------------------------
def test_modes_map_to_sdk_modes():
    want = {"default": "default", "never_ask": "dontAsk", "accept_edits": "acceptEdits", "plan": "plan"}
    for mode, sdk_mode in want.items():
        o = _opts(Agent("a", include_ask_user=False, permission_mode=mode))
        assert o.permission_mode == sdk_mode
        assert (o.can_use_tool is None) == (mode == "never_ask")


def test_plan_mode_offers_exit_plan_tool_but_never_preapproves_it():
    o = _opts(Agent("a", include_ask_user=False, tools=["Read"], permission_mode="plan"))
    assert o.tools == ["Read", "ExitPlanMode"] and "ExitPlanMode" not in o.allowed_tools
    o = _opts(Agent("a", include_ask_user=False, tools=["Read", "ExitPlanMode"]))
    assert "ExitPlanMode" in o.tools and o.allowed_tools == ["Read"]
    o = _opts(Agent("a", include_ask_user=False, tools=["Read"]))            # lean default: unchanged
    assert o.tools == ["Read"]
    o = _opts(Agent("a", setup="project", permission_mode="plan"))           # preset already has it
    assert o.tools == {"type": "preset", "preset": "claude_code"}


def test_switched_mode_is_used_when_the_process_restarts():
    s = _session(Agent("a", include_ask_user=False, on_permission=lambda r: "allow"))
    asyncio.run(s.set_permission_mode("accept_edits"))      # no live process: just remembered
    o = s.options(resume="sid")
    assert s.permission_mode == "accept_edits" and o.permission_mode == "acceptEdits"
    asyncio.run(s.set_permission_mode("never_ask"))
    assert s.options(resume="sid").can_use_tool is not None   # hook kept: switching back still reaches it


# --- live switch ----------------------------------------------------------------------------------------
class _Client:
    def __init__(self):
        self.modes = []

    async def set_permission_mode(self, mode):
        self.modes.append(mode)

    async def disconnect(self):
        return None


def test_set_permission_mode_runs_on_worker_between_turns_and_directly_mid_turn():
    async def go():
        s = _session(Agent("a", include_ask_user=False))
        s._ensure_worker()
        s._client = c = _Client()
        await s.set_permission_mode("plan")                  # idle: through the worker's queue
        s._busy = True
        await s.set_permission_mode("accept_edits")          # mid-turn: direct control request
        s._busy = False
        await s.close()
        return c.modes, s.permission_mode
    modes, mode = asyncio.run(go())
    assert modes == ["plan", "acceptEdits"] and mode == "accept_edits"


def test_failed_switch_keeps_old_mode():
    class Broken(_Client):
        async def set_permission_mode(self, mode):
            raise RuntimeError("boom")

    async def go():
        s = _session(Agent("a", include_ask_user=False))
        s._ensure_worker()
        s._client = Broken()
        try:
            await s.set_permission_mode("plan")
        except ce.AgentError as e:
            err = e
        await s.close()
        return err, s.permission_mode
    err, mode = asyncio.run(go())
    assert "permission mode" in err.short and mode == "default"


def test_status_message_updates_mode():
    s = _session(Agent("a", include_ask_user=False))
    s._map(ce.SystemMessage(subtype="status", data={"permissionMode": "acceptEdits"}), None)
    assert s.permission_mode == "accept_edits"
    s._map(ce.SystemMessage(subtype="status", data={"permissionMode": "bypassPermissions"}), None)
    assert s.permission_mode == "accept_edits"                # unknown modes are ignored


# --- permission requests --------------------------------------------------------------------------------
SUGGESTIONS = [
    PermissionUpdate(type="addRules", rules=[RuleValue("Bash", "npm test:*")], behavior="allow",
                     destination="localSettings"),
    PermissionUpdate(type="setMode", mode="acceptEdits", destination="session"),
    PermissionUpdate(type="addDirectories", directories=["/tmp/x"], destination="session"),
]


def test_request_carries_suggestions_mode_call_id_title():
    seen = []
    s = _session(Agent("a", include_ask_user=False, on_permission=lambda r: seen.append(r) or "allow"))
    res = _ask(s, "Bash", {"command": "npm test"},
               Ctx(suggestions=SUGGESTIONS, tool_use_id="tu1", title="Claude wants to run npm test"))
    assert isinstance(res, ce.PermissionResultAllow) and res.updated_permissions is None   # plain allow unchanged
    req = seen[0]
    assert (req.kind, req.mode, req.call_id, req.title, req.plan) == \
        ("tool", "default", "tu1", "Claude wants to run npm test", None)
    a, b, c = req.suggestions
    assert (a.kind, a.rules, a.behavior, a.where) == ("add_rules", ["Bash(npm test:*)"], "allow", "project_local")
    assert (b.kind, b.mode, b.where) == ("set_mode", "accept_edits", "session")
    assert (c.kind, c.dirs) == ("add_dirs", ["/tmp/x"])


def test_always_allow_session_shape_unchanged():
    s = _session(Agent("a", include_ask_user=False, on_permission=lambda r: "always_allow"))
    res = _ask(s, "Bash", {"command": "npm test"}, Ctx(suggestions=SUGGESTIONS))
    (u,) = res.updated_permissions
    assert (u.type, u.behavior, u.destination) == ("addRules", "allow", "session")
    assert [(r.tool_name, r.rule_content) for r in u.rules] == [("Bash", None)]


def test_always_allow_project_local_uses_suggested_rules_else_whole_tool():
    s = _session(Agent("a", include_ask_user=False,
                       on_permission=lambda r: PermissionDecision("always_allow", remember="project_local")))
    (u,) = _ask(s, "Bash", {"command": "npm test"}, Ctx(suggestions=SUGGESTIONS)).updated_permissions
    assert (u.destination, [(r.tool_name, r.rule_content) for r in u.rules]) == \
        ("localSettings", [("Bash", "npm test:*")])
    (u,) = _ask(s, "Write", {"file_path": "a"}).updated_permissions
    assert (u.destination, [(r.tool_name, r.rule_content) for r in u.rules]) == ("localSettings", [("Write", None)])


def test_always_allow_explicit_rules_and_custom_tool_names():
    s = _session(Agent("a", tools=[lookup], include_ask_user=False, on_permission=lambda r: PermissionDecision(
        "always_allow", rules=["Bash(git status)", "lookup", "Read(*)"])))
    (u,) = _ask(s, "Bash", {"command": "git status"}).updated_permissions
    assert u.destination == "session"
    assert [(r.tool_name, r.rule_content) for r in u.rules] == \
        [("Bash", "git status"), ("mcp__agentlib__lookup", None), ("Read", None)]


def test_suggestions_show_custom_tools_by_short_name():
    seen = []
    s = _session(Agent("a", tools=[lookup], include_ask_user=False, on_permission=lambda r: seen.append(r)))
    _ask(s, "mcp__agentlib__lookup", {"q": "x"}, Ctx(suggestions=[PermissionUpdate(
        type="addRules", rules=[RuleValue("mcp__agentlib__lookup")], behavior="allow", destination="session")]))
    assert seen[0].tool == "lookup" and seen[0].suggestions[0].rules == ["lookup"]


def test_decision_mode_adds_set_mode_update():
    s = _session(Agent("a", include_ask_user=False,
                       on_permission=lambda r: PermissionDecision("allow", mode="accept_edits")))
    (u,) = _ask(s, "Edit", {"file_path": "a"}).updated_permissions
    assert (u.type, u.mode, u.destination) == ("setMode", "acceptEdits", "session")
    assert s.permission_mode == "accept_edits"


def test_deny_keeps_old_message_and_adds_feedback():
    s = _session(Agent("a", include_ask_user=False, on_permission=lambda r: "deny"))
    assert _ask(s, "Bash", {"command": "x"}).message == "The user denied Bash."
    s = _session(Agent("a", include_ask_user=False,
                       on_permission=lambda r: PermissionDecision("deny", message="Use git mv.")))
    assert _ask(s, "Bash", {"command": "x"}).message == "The user denied Bash. The user's feedback: Use git mv."


# --- plan approval --------------------------------------------------------------------------------------
def test_plan_request_approved_sets_chosen_mode():
    seen = []

    async def decide(req):
        seen.append(req)
        return PermissionDecision("allow", mode="accept_edits")
    s = _session(Agent("a", include_ask_user=False, permission_mode="plan", on_permission=decide))
    res = _ask(s, "ExitPlanMode", {"plan": "1. do it"}, Ctx(tool_use_id="p1"))
    assert (seen[0].kind, seen[0].plan, seen[0].mode, seen[0].call_id) == ("plan", "1. do it", "plan", "p1")
    (u,) = res.updated_permissions
    assert (u.type, u.mode, u.destination) == ("setMode", "acceptEdits", "session")
    assert s.permission_mode == "accept_edits"


def test_plan_plain_allow_goes_to_default_and_always_allow_adds_no_rule():
    for answer in ("allow", "always_allow", True):
        s = _session(Agent("a", include_ask_user=False, permission_mode="plan", on_permission=lambda r, a=answer: a))
        (u,) = _ask(s, "ExitPlanMode", {"plan": "p"}).updated_permissions
        assert (u.type, u.mode) == ("setMode", "default") and s.permission_mode == "default"


def test_plan_rejected_stays_in_plan_mode_with_feedback():
    s = _session(Agent("a", include_ask_user=False, permission_mode="plan",
                       on_permission=lambda r: PermissionDecision("deny", message="Split step 2.")))
    res = _ask(s, "ExitPlanMode", {"plan": "p"})
    assert isinstance(res, ce.PermissionResultDeny) and "plan mode" in res.message
    assert res.message.endswith("The user's feedback: Split step 2.") and s.permission_mode == "plan"


def test_plan_without_hook_is_denied():
    s = _session(Agent("a", include_ask_user=False, permission_mode="plan"))
    assert isinstance(_ask(s, "ExitPlanMode", {"plan": "p"}), ce.PermissionResultDeny)
