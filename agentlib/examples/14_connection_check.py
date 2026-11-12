"""14 - Show how an engine is set up for this user, and test the connection (e.g. an app's settings screen).

Run:  python examples/14_connection_check.py          (fake engine, free)
      python examples/14_connection_check.py --live   (Claude: LIVE, one tiny Haiku message, a fraction of a cent)

Command-line equivalent: python -m agentlib.check   (--status = setup only, sends nothing)

How each person signs in lives in ONE local file, setup/local.toml (ignored by git; copy it from
setup/local.example.toml). Guide: setup/claude-setup.md. Apps never deal with sign-in themselves:
- connection_status(engine) -> ConnectionStatus: ok, method ("login" | "settings-file" | "env"), summary,
  env_names (names only, never values), setup_file, setup_doc, problems, notes. Sends nothing
- check_connection_sync(engine) / await check_connection(engine) -> CheckResult: ok, model, cost_usd, error,
  fix, report() (the text the command prints). Never raises for a failed connection
"""
import sys

from agentlib import check_connection_sync, connection_status

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

if not LIVE:
    from agentlib import fake
    from agentlib.connection import CHECK_AGENT
    # The check sends one message as the agent CHECK_AGENT; script it to show the failure path for free:
    if "--fail" in sys.argv:
        fake.script(CHECK_AGENT, [[fake.fail("Not logged in - Please run /login")]])

# 1. A settings screen: show how the user is set up (free, instant)
st = connection_status(ENGINE)
print(f"[{'ok' if st.ok else 'needs attention'}] {ENGINE}: {st.summary}")
for p in st.problems:
    print("  problem:", p)

# 2. A "Test connection" button
result = check_connection_sync(ENGINE)
print()
print(result.report())
if not result.ok:
    print("\n(app view) error:", result.error, "| fix:", result.fix)
