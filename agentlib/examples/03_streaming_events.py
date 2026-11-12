"""03 - Streaming: watch a turn live as engine-neutral events.

Run:  python examples/03_streaming_events.py          (fake engine, free)
      python examples/03_streaming_events.py --live   (LIVE: uses your Claude login, costs tokens; haiku)

Raw SDK equivalent: include_partial_messages=True + iterating StreamEvent / AssistantMessage (TextBlock,
ToolUseBlock) / UserMessage (ToolResultBlock) / RateLimitEvent / ResultMessage. agentlib maps them to six
events (agentlib/events.py); every event has .type and .to_dict() (JSON-ready for a web UI).
"""
import asyncio
import json
import sys

from agentlib import Agent, Done, RateLimit, Text, TextDelta, ToolCall, ToolResult, tool

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"


@tool(read_only=True)
def add_numbers(a: float, b: float) -> str:
    """Add two numbers and return the sum."""
    return str(a + b)


if not LIVE:
    from agentlib import fake
    fake.script("calc", [[
        fake.rate_limit("allowed_warning", 0.9),       # engines report usage-limit status as an event
        fake.say("Let me add those."),
        fake.call("add_numbers", {"a": 2, "b": 3}),    # runs the REAL add_numbers above
        fake.say("2 + 3 = 5."),
    ]])

agent = Agent("calc", instructions="Use add_numbers for any arithmetic. Be brief.",
              engine=ENGINE, model="haiku", tools=[add_numbers])


async def main() -> None:
    async with agent.session() as s:
        async for ev in s.stream("What is 2 + 3?"):
            if isinstance(ev, TextDelta):              # live typing (top-level agent only)
                print(ev.text, end="", flush=True)
            elif isinstance(ev, Text):                 # a finished text block (arrives after its deltas)
                print(f"\n[text block finished, {len(ev.text)} chars]")
            elif isinstance(ev, ToolCall):             # short tool name: "add_numbers", not "mcp__..."
                print(f"[tool_call] {ev.name}({ev.input})")
            elif isinstance(ev, ToolResult):
                print(f"[tool_result] {ev.name} -> {ev.text!r} error={ev.is_error}")
            elif isinstance(ev, RateLimit):
                print(f"[rate_limit] {ev.status} utilization={ev.utilization} type={ev.limit_type}")
            elif isinstance(ev, Done):                 # always last; carries the same Reply send() returns
                r = ev.reply
                print(f"[done] status={r.status} tools={[c.name for c in r.tool_calls]} cost=${r.cost_usd:.6f}")
                print("as JSON for a UI:", json.dumps(ev.to_dict())[:120], "...")
        # After streaming, s.last_reply holds the Reply and s.pending_questions any ask_user questions.
        # To stream the answer to ask_user questions use s.answer_stream(answers) (see 05).


asyncio.run(main())
