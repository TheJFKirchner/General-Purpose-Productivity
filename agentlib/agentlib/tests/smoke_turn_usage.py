"""Live check of Reply.turn_usage against real Claude (Haiku, about 1 cent). Run by hand:

    python -m agentlib.tests.smoke_turn_usage

Not collected by pytest. Two short sends in one session:
1. a request that makes the model call a tool twice in ONE reply, then answer (at least two model replies)
2. a one-line follow-up (one more reply; its model_turn must carry on from the first send)

For each send it prints, per model reply: the usage agentlib reports (Reply.turn_usage), what the raw messages
said (AssistantMessage usage per content block, stream message_start / message_delta), then the sum over the
replies against the turn's total from the engine (Reply.usage, from ResultMessage.usage) field by field, and
whether the parallel calls share a model_turn. Ends with the cost. Nothing is asserted beyond "it ran": the
point is to read the figures.
"""
from __future__ import annotations

import asyncio
from functools import reduce

from agentlib import Agent, Usage, tool
from agentlib.engines import claude as ce
from agentlib.engines.claude import sdk_version

FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
RAW: list[tuple] = []                      # (kind, message_id, Usage) seen by the engine, in order


@tool(read_only=True)
def get_weather(city: str) -> str:
    """Current temperature in a city (test data)."""
    return {"paris": "14 C, cloudy", "tokyo": "21 C, sunny"}.get(city.strip().lower(), "18 C, clear")


INSTRUCTIONS = ("You are a test agent. When you need several independent tool results, call the tools in parallel "
                "in a single reply. Keep answers to one short sentence.")


def _spy() -> None:
    """Record raw per-message usage as the Claude engine sees it (diagnostics only)."""
    orig = ce.ClaudeSession._map
    current = {"mid": None}

    def spy(self, m, state):
        if isinstance(m, ce.StreamEvent) and not m.parent_tool_use_id:
            e = m.event or {}
            if e.get("type") == "message_start":
                msg = e.get("message") or {}
                current["mid"] = msg.get("id")
                RAW.append(("stream start", current["mid"], ce.normalize_usage(msg.get("usage"))))
            elif e.get("type") == "message_delta":
                RAW.append(("stream delta", current["mid"], ce.normalize_usage(e.get("usage"))))
        elif isinstance(m, ce.AssistantMessage) and not m.parent_tool_use_id:
            kinds = ",".join(type(b).__name__.replace("Block", "") for b in m.content)
            RAW.append((f"block {kinds}", m.message_id, ce.normalize_usage(m.usage) if isinstance(m.usage, dict)
                        else None))
        return orig(self, m, state)
    ce.ClaudeSession._map = spy


def _fmt(u: Usage | None) -> str:
    if u is None:
        return "(no usage)"
    return (f"in={u.input_tokens} out={u.output_tokens} cache_read={u.cache_read_tokens} "
            f"cache_write={u.cache_write_tokens}")


def _report(label: str, reply) -> dict:
    print(f"\n=== {label}: status={reply.status} api_calls={reply.api_calls} cost=${reply.cost_usd:.5f}")
    print("tool calls:", [(c.name, c.input, c.model_turn) for c in reply.tool_calls])
    print("raw messages seen:")
    for kind, mid, u in RAW:
        print(f"  {kind:<22} {str(mid)[-10:]:<11} {_fmt(u)}")
    RAW.clear()
    print("Reply.turn_usage:")
    for t in reply.turn_usage:
        print(f"  model_turn {t.model_turn}: {_fmt(t.usage)}  ({t.model})")
    total = reduce(lambda a, b: a + b, (t.usage for t in reply.turn_usage), Usage())
    print(f"sum of replies : {_fmt(total)}")
    print(f"Reply.usage    : {_fmt(reply.usage)}")
    print(f"usage_by_model : { {m: _fmt(v['usage']) for m, v in reply.usage_by_model.items()} }")
    verdict = {}
    for f in FIELDS:
        a, b = getattr(total, f), getattr(reply.usage, f)
        verdict[f] = "exact" if a == b else f"off by {a - b:+d} ({(a - b) / b * 100 if b else float('inf'):+.1f}%)"
        print(f"  {f:<20} {verdict[f]}")
    return verdict


async def main() -> None:
    print(sdk_version())
    _spy()
    agent = Agent("turn-usage-smoke", instructions=INSTRUCTIONS, model="haiku", tools=[get_weather],
                  include_ask_user=False, timeout_s=180)
    async with agent.session() as s:
        r1 = await s.send("What is the weather in Paris and in Tokyo right now? Call get_weather for both "
                          "cities at once, in the same reply, then tell me which is warmer.")
        v1 = _report("send 1", r1)
        r2 = await s.send("In one word: which of the two was colder?")
        v2 = _report("send 2", r2)

    turns = [c.model_turn for c in r1.tool_calls]
    print("\n=== findings")
    print(f"parallel calls share a model_turn: {len(turns) >= 2 and len(set(turns)) == 1} (calls' turns {turns})")
    print(f"send 2 numbers carry on: {[t.model_turn for t in r2.turn_usage]} after {[t.model_turn for t in r1.turn_usage]}")
    print(f"per-field match send 1: {v1}")
    print(f"per-field match send 2: {v2}")
    print(f"cost of this check: ${r2.total_cost_usd:.5f}")


if __name__ == "__main__":
    asyncio.run(main())
