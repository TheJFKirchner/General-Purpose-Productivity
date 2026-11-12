"""Live smoke test against real Claude (Haiku, ~1 cent). Run by hand: python -m agentlib.tests.smoke_claude

Checks: lean mode offers only our tools; ask_user parks -> needs_input; answer() resumes and the custom tool
runs; a fresh session resumes the conversation by id; usage + cost come back; live events stream.
"""
from __future__ import annotations

import asyncio
import sys

from agentlib import Agent, tool
from agentlib.engines.claude import sdk_version


@tool(read_only=True)
def add_numbers(a: float, b: float) -> str:
    """Add two numbers and return the sum."""
    return str(a + b)


INSTRUCTIONS = ("You are a test agent. Use add_numbers for any arithmetic. If the user has not said which "
                "numbers to add, ask them with ask_user (one question, id 'numbers') before doing anything.")


def check(cond: bool, label: str) -> None:
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        sys.exit(1)


async def main() -> None:
    print(sdk_version())
    agent = Agent("smoke", instructions=INSTRUCTIONS, model="haiku", tools=[add_numbers, "ask_user"],
                  timeout_s=180)
    async with agent.session() as s:
        types = []
        async for ev in s.stream("Please add two numbers for me."):
            types.append(ev.type)
        r1 = s.last_reply
        offered = s.info.tools                          # custom tools by short name
        print("tools offered:", offered, "| mcp servers:", s.info.mcp_servers)
        check(set(offered) == {"add_numbers", "ask_user"}, "lean: only our tools")
        check(s.info.mcp_servers.get("agentlib") == "connected", "custom tool server 'agentlib' connected")
        check(r1.status == "needs_input" and r1.questions, f"ask_user parked (status={r1.status})")
        check("text_delta" in types or "tool_call" in types, f"live events streamed ({sorted(set(types))})")
        qid = r1.questions[0].id
        r2 = await s.answer({qid: "2 and 3"})
        print("turn 2:", r2.text[:200].replace("\n", " "))
        print("tool calls:", [(c.name, c.input, c.result) for c in r2.tool_calls])
        check(any(c.name == "add_numbers" and c.result in ("5", "5.0") for c in r2.tool_calls), "custom tool ran")
        check(r2.usage.output_tokens > 0 and r2.total_cost_usd > 0, f"usage+cost ({r2.usage}, ${r2.cost_usd})")
        sid, total = s.session_id, r2.total_cost_usd

    async with agent.session(resume=sid, cost_base=total) as s2:
        r3 = await s2.send("What was the sum you computed? Reply with just the number.")
        print("resumed:", r3.text)
        check("5" in r3.text, "resume by session id")
        print(f"total cost ${r3.total_cost_usd:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
