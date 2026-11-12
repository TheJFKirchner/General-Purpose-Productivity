"""04 - Custom tools with @tool.

Run:  python examples/04_custom_tools.py          (fake engine, free)
      python examples/04_custom_tools.py --live   (LIVE: uses your Claude login, costs tokens; haiku)

Raw SDK equivalent: @claude_agent_sdk.tool + create_sdk_mcp_server + allowed_tools=["mcp__srv__name"].
agentlib builds the in-process MCP server for you. The model sees the tools as
mcp__<Agent.tool_server>__<name>; tool_server defaults to DEFAULT_SERVER in agentlib/tools.py.
Events, Reply.tool_calls and on_permission always use the short name.
"""
import sys
from typing import Literal

from agentlib import Agent, tool

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

PRICES = {"A-1": 12.5, "B-2": 40.0}


# Plain function -> Tool. Input schema from type hints (str/int/float/bool/list/dict/Literal/Optional),
# description from the docstring, parameters without a default are required.
# Return str; dict/list are sent as JSON; None is sent as "ok".
@tool(read_only=True)                     # read_only=True: safe to run in parallel (a hint to the engine)
def lookup_price(sku: str, currency: Literal["USD", "EUR"] = "USD") -> dict:
    """Look up the unit price of a product by SKU."""
    if sku not in PRICES:
        raise KeyError(f"unknown sku {sku}")   # an exception becomes an error result; the turn goes on
    return {"sku": sku, "price": PRICES[sku], "currency": currency}


# Async handlers work too. ends_turn=True: the agent stops right after a successful call
# (no extra model call; useful for "submit"/"finish" tools).
@tool(name="submit_order", ends_turn=True)
async def submit(sku: str, quantity: int) -> str:
    """Submit an order. Call this last."""
    return f"order placed: {quantity} x {sku}"


if not LIVE:
    from agentlib import fake
    fake.script("shop", [[
        fake.call("lookup_price", {"sku": "Z-9"}),               # raises -> is_error result, turn continues
        fake.call("lookup_price", {"sku": "A-1"}),
        fake.call("submit_order", {"sku": "A-1", "quantity": 2}),
        fake.say("never reached: submit_order ended the turn"),
    ]])

agent = Agent(
    "shop",
    instructions=("Look up prices with lookup_price, then place the order with submit_order. "
                  "If a SKU is unknown, try A-1."),
    engine=ENGINE, model="haiku",
    # One mixed list: Tool objects, built-in names/rules ("Read", "Bash(git status:*)"), "ask_user",
    # external MCP names ("mcp__db__query"). Listed tools are pre-approved.
    tools=[lookup_price, submit],
    # Alternative: tools=["lookup_price", "submit_order"], available_tools=[lookup_price, submit]
    # (names in the list, implementations alongside; this is what agent files use, see 08).
)

print("schema the model sees for lookup_price:", lookup_price.schema)
reply = agent.ask_sync("Order 2 units of SKU Z-9.")
for c in reply.tool_calls:
    print(f"  {c.name}({c.input}) -> {c.result!r} error={c.is_error}")
print("status:", reply.status, "| text:", repr(reply.text))
