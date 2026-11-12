"""10 - Spending cap: stop a run once it has cost a set amount, and tell that apart from other endings.

Run:  python examples/10_spending_cap.py          (fake engine, free)
      python examples/10_spending_cap.py --live   (LIVE: uses your Claude login, costs tokens; haiku, ~$0.01)

Raw SDK equivalent: ClaudeAgentOptions(max_budget_usd=0.05) and checking
ResultMessage.subtype == "error_max_budget_usd". agentlib: Agent(max_budget_usd=0.05); a cap stop comes back as
Reply.status == "error" with Reply.error_kind == "budget" (max_turns -> "max_turns"; anything else -> "other").

Rules:
- The cap covers one opened session (one agent.ask() is one run). A resumed session starts a new cap.
- It is checked between model calls, so a run can go a little over before it stops.
- The reply still carries the text, tool calls, usage and cost so far.
- Engines without it (capabilities.budget False, e.g. cursor today) raise CapabilityError when the session opens.
"""
import sys

from agentlib import Agent

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"
CAP = 0.00001 if LIVE else 0.05          # live: a tiny cap so even one Haiku call crosses it

if not LIVE:
    from agentlib import fake
    # fake.spend(usd) = "this step cost that much". The fake checks the cap after every step.
    fake.script("counter", [[fake.say("One."), fake.spend(0.03), fake.say("Two."), fake.spend(0.03),
                             fake.say("Three.")]])

agent = Agent("counter", instructions="Count from one to three, one number per line.",
              engine=ENGINE, model="haiku", tools=[], include_ask_user=False, max_budget_usd=CAP)

reply = agent.ask_sync("Count, please.")
print("status:    ", reply.status)
print("error_kind:", reply.error_kind)             # "budget" -> show "hit its cost limit"
print("error:     ", reply.error)
print("text so far:", repr(reply.text))
print("cost:      ", f"${reply.cost_usd:.6f}")
if reply.error_kind == "budget":
    print("-> The run hit its cost limit before finishing.")
