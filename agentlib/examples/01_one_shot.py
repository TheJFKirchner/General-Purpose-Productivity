"""01 - One-shot ask: the smallest working agent.

Run:  python examples/01_one_shot.py           (fake engine, free, no login needed)
      python examples/01_one_shot.py --live    (LIVE: uses your Claude login, costs tokens; haiku, ~$0.01)

Raw SDK equivalent: claude_agent_sdk.query(prompt, options=ClaudeAgentOptions(...)) and reading ResultMessage.
"""
import sys

from agentlib import Agent

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

if not LIVE:
    # The fake engine registers itself as engine "fake" when agentlib.fake is imported.
    # script(agent_name, turns): each turn is a list of steps the "model" will perform.
    from agentlib import fake
    fake.script("geo", [[fake.say("Paris.")]])

# Optional, live only: make sure the Claude Code login (subscription) is used rather than any
# ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL in the environment.
#   from agentlib import use_login_only; use_login_only()

agent = Agent(
    "geo",                                   # name (also the key the fake script is looked up by)
    instructions="Answer in one short sentence.",
    engine=ENGINE,                           # "claude" (default) | "fake" | "cursor" (stub, not runnable yet)
    model="haiku",                           # alias or full model id; None = engine default
    # setup="lean" is the default: no CLAUDE.md, no folder settings, no built-in tools unless listed.
)

# ask_sync() = asyncio.run(agent.ask(...)). Each ask() is a NEW conversation (no memory between calls).
# Inside async code use:  reply = await agent.ask("...")
reply = agent.ask_sync("What is the capital of France?")

print("status:  ", reply.status)             # done | needs_input | error
print("text:    ", reply.text)
print("tokens:  ", reply.usage.input_tokens, "in /", reply.usage.output_tokens, "out")
print("cost:    ", f"${reply.cost_usd:.6f} this turn, ${reply.total_cost_usd:.6f} conversation total")
print("session: ", reply.session_id)         # save this to resume the conversation later (see 02)
print("engine:  ", reply.engine, "| model:", reply.model)
