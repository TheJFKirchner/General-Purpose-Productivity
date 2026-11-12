"""02 - Multi-turn session, resume by id, fork.

Run:  python examples/02_multi_turn_session.py          (fake engine, free)
      python examples/02_multi_turn_session.py --live   (LIVE: uses your Claude login, costs tokens; haiku)

Raw SDK equivalent: ClaudeSDKClient (connect / query / receive_response / disconnect),
ClaudeAgentOptions(resume=..., fork_session=True).
"""
import asyncio
import sys

from agentlib import Agent

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

if not LIVE:
    from agentlib import fake
    # One entry per turn, counted per conversation. Resume continues the count; fork copies it.
    fake.script("memo", [
        [fake.say("Nice to meet you, Sam.")],          # turn 1
        [fake.say("Your name is Sam.")],               # turn 2
        [fake.say("You told me your name is Sam.")],   # turn 3 (after resume)
        [fake.say("Sam, this is the forked branch.")], # turn 4 (fork of the 3-turn conversation)
    ])

agent = Agent("memo", instructions="Be brief: one sentence per reply.", engine=ENGINE, model="haiku")


async def main() -> None:
    # One session = one conversation (one `claude` process on the claude engine). Close it with `async with`.
    async with agent.session() as s:
        r1 = await s.send("Hi, my name is Sam.")
        print("1:", r1.text)
        r2 = await s.send("What is my name?")
        print("2:", r2.text)
        saved_id = s.session_id                  # persist this (DB / JSON) to continue later
        spent = r2.total_cost_usd                # running total so far

    # Later, even after a restart (claude engine: same cwd; fake engine: same Python process only):
    # cost_base = total already spent, so Reply.cost_usd is exactly this turn's cost.
    async with agent.session(resume=saved_id, cost_base=spent) as s:
        r3 = await s.send("Remind me what my name is.")
        print("3 (resumed):", r3.text, f"| turn ${r3.cost_usd:.6f}, total ${r3.total_cost_usd:.6f}")

    # fork=True: branch a copy of the saved conversation; the original stays as it was.
    # Engines without fork (engine.capabilities.fork False) raise CapabilityError here.
    async with agent.session(resume=saved_id, fork=True) as s:
        r4 = await s.send("Say my name once more.")
        print("4 (fork):", r4.text, "| new session id differs:", s.session_id != saved_id)

    # s.interrupt() stops a running turn (e.g. from a UI "Stop" button running in another task).


asyncio.run(main())
