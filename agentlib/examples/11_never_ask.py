"""11 - Never ask for permission: non-interactive runs where anything not pre-approved is simply denied.

Run:  python examples/11_never_ask.py          (fake engine, free)
      python examples/11_never_ask.py --live   (LIVE: uses your Claude login, costs tokens; haiku, ~$0.01)

Raw SDK equivalent: ClaudeAgentOptions(permission_mode="dontAsk"). agentlib: Agent(permission_mode="never_ask").

Rules:
- Tools listed in tools= are pre-approved and run. Anything else is denied on the spot: the model gets an error
  tool result and carries on (the run is not an error). Nothing is ever asked.
- on_permission cannot be combined with it (ValueError when the Agent is built).
- The default, permission_mode="default", is unchanged: unlisted tools go to on_permission, or are denied.
- Claude Code lets some read-only shell commands run without any rule (e.g. `python --version`); the fake
  engine does not model that, so the demo uses a command that writes.
"""
import sys
import tempfile

from agentlib import Agent

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

if not LIVE:
    from agentlib import fake
    fake.script("ops", [[
        fake.call("Bash", {"command": "echo hello"}),          # matches Bash(echo:*) -> runs
        fake.call("Bash", {"command": "mkdir build"}),         # not pre-approved -> denied, nobody asked
        fake.say("echo ran; mkdir was denied."),
    ]])

agent = Agent("ops", instructions="Run `echo hello`, then `mkdir build`, one Bash call each. Do not retry. "
                                  "Then say in one line what happened.",
              engine=ENGINE, model="haiku", tools=["Bash(echo:*)"], include_ask_user=False,
              permission_mode="never_ask", cwd=tempfile.mkdtemp(prefix="agentlib-11-"))

reply = agent.ask_sync("Go.")
for c in reply.tool_calls:
    print(f"  {c.name}({c.input.get('command')}) error={c.is_error} -> {(c.result or '')[:70]!r}")
print("status:", reply.status, "| text:", reply.text)
