"""06 - Tool permissions with on_permission (live Allow / Deny for tools that are not pre-approved).

Run:  python examples/06_permissions.py          (fake engine, free)
      python examples/06_permissions.py --live   (LIVE: uses your Claude login, costs tokens; haiku)

Raw SDK equivalent: ClaudeAgentOptions(can_use_tool=fn) returning PermissionResultAllow / PermissionResultDeny
(+ PermissionUpdate for "always allow"). agentlib: on_permission(PermissionRequest) -> "allow" | "deny" |
"always_allow" (or True / False), sync or async. Engines without it (capabilities.permission_hook False,
e.g. cursor) raise CapabilityError when the session opens.

Rules:
- Everything listed in tools= is pre-approved and never asks.
- Anything else the model calls goes to on_permission; with no hook it is denied.
- In lean setup a built-in is only OFFERED to the model if it is listed. Listing a rule such as
  "Bash(echo:*)" offers Bash but pre-approves only matching commands; other Bash commands ask.
  ("Bash(echo:*)" = "Bash(echo *)": `echo` and `echo ...`; `echo hi && rm x` asks, since every part of a
  compound command must match.) disallowed_tools=["Bash(rm *)"] would deny without asking.
- The fake engine applies the same rule matching, so both engines use the same tools list.
"""
import sys

from agentlib import Agent, PermissionRequest

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"


def decide(req: PermissionRequest) -> str:
    # req.agent, req.tool (short name), req.input (tool arguments), req.reason (engine's reason, may be None)
    command = str(req.input.get("command", ""))
    verdict = "allow" if req.tool == "Bash" and command.startswith("python --version") else "deny"
    print(f"  [on_permission] {req.tool} {req.input} -> {verdict}")
    return verdict                  # "always_allow" = allow and stop asking for this tool this session


if not LIVE:
    from agentlib import fake
    fake.script("ops", [[
        fake.call("Bash", {"command": "echo hello"}),                # matches Bash(echo:*) -> runs, no question
        fake.call("Bash", {"command": "python --version"}),          # not pre-approved -> decide() -> allow
        fake.call("Bash", {"command": "rm -rf build"}),              # not pre-approved -> decide() -> deny
        fake.say("Done."),
    ]])

# Bash is offered; only `echo ...` is pre-approved, so `python --version` reaches decide().
agent = Agent("ops", instructions="Run the shell commands the user asks for, one at a time, then stop.",
              engine=ENGINE, model="haiku", tools=["Bash(echo:*)"], on_permission=decide)

reply = agent.ask_sync("Run `echo hello`, then run `python --version`.")
for c in reply.tool_calls:
    print(f"  {c.name}({c.input}) -> {(c.result or '')[:60]!r} error={c.is_error}")
print("status:", reply.status)
