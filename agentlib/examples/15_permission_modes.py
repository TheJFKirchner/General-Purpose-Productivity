"""15 - Permission modes like Claude Code: plan first, approve the plan, switch modes mid-session.

Run:  python examples/15_permission_modes.py          (fake engine, free)
      python examples/15_permission_modes.py --live   (LIVE: uses your Claude login, costs tokens; haiku,
                                                       project setup in a temp folder, roughly $0.05-0.20)

Raw SDK equivalent: ClaudeAgentOptions(permission_mode="plan" | "acceptEdits" | ...), client.set_permission_mode(),
can_use_tool answering ExitPlanMode with PermissionResultAllow(updated_permissions=[PermissionUpdate(setMode)]),
ToolPermissionContext.suggestions, PermissionUpdate(destination="localSettings").

agentlib:
- Agent(permission_mode="default" | "never_ask" | "accept_edits" | "plan"); s.permission_mode;
  await s.set_permission_mode(mode) at any time (the next tool call uses it)
- In plan mode the agent proposes its plan through on_permission: req.kind == "plan", req.plan = the text.
  Return PermissionDecision("allow", mode="accept_edits") to approve and continue in that mode (plain "allow"
  continues in "default"), or PermissionDecision("deny", message="what to change") to keep planning
- Every request has req.suggestions (engine's "always allow" options, engine-neutral) and req.mode.
  PermissionDecision("always_allow", remember="project_local") keeps the rule in the project's local settings
  (Claude: .claude/settings.local.json), so later setup="project" sessions in that folder do not ask again
"""
import asyncio
import sys
import tempfile

from agentlib import Agent, PermissionDecision, PermissionRequest

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"
FOLDER = tempfile.mkdtemp(prefix="agentlib-15-")


def decide(req: PermissionRequest):
    if req.kind == "plan":                                  # show req.plan to the user; they approve it
        print(f"  [plan proposed]\n    " + (req.plan or "").replace("\n", "\n    "))
        return PermissionDecision("allow", mode="accept_edits")     # approve; edits now run without asking
    print(f"  [asked] {req.tool} in mode {req.mode}; suggestions: {[s.rules or s.mode for s in req.suggestions]}")
    return "deny"                                           # or "allow", "always_allow", PermissionDecision(...)


if not LIVE:
    from agentlib import fake
    fake.script("planner", [
        [fake.say("Plan: write hello.txt with 'hi'."), fake.plan("1. Create hello.txt containing 'hi'."),
         fake.call("Write", {"file_path": "hello.txt", "content": "hi"}), fake.say("Created hello.txt.")],
        [fake.call("Write", {"file_path": "hello.txt", "content": "bye"}), fake.say("The edit was denied.")],
    ])

# gated_tools: the fake engine's project setup approves every built-in (it cannot read your settings files);
# gating Write/Edit makes it ask like Claude does. On Claude it changes nothing here (nothing is pre-approved).
agent = Agent("planner", engine=ENGINE, model="haiku", setup="project", cwd=FOLDER, permission_mode="plan",
              gated_tools=["Write", "Edit"], on_permission=decide)


async def main():
    async with agent.session() as s:
        print("mode:", s.permission_mode)
        r = await s.send("Create hello.txt containing 'hi'. Present a one-line plan with ExitPlanMode first, "
                         "without exploring; once approved, create the file.")
        print("turn 1:", [(c.name, c.is_error) for c in r.tool_calls], "| mode now:", s.permission_mode)

        await s.set_permission_mode("default")              # back to "ask before edits"
        r = await s.send("Overwrite hello.txt with 'bye' using one Write call. If denied, do not retry.")
        print("turn 2:", [(c.name, c.is_error) for c in r.tool_calls], "| mode now:", s.permission_mode)


asyncio.run(main())
