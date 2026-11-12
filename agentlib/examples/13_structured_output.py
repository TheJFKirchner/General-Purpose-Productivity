"""13 - Structured output: a one-shot call with no tools that replies in a fixed JSON shape.

Run:  python examples/13_structured_output.py          (fake engine, free)
      python examples/13_structured_output.py --live   (LIVE: uses your Claude login, costs tokens; haiku, ~$0.01)

Raw SDK equivalent: ClaudeAgentOptions(output_format={"type": "json_schema", "schema": S}) and reading
ResultMessage.structured_output (or `claude -p --json-schema ... --tools "" --no-session-persistence`).

agentlib, two ways:
- ask_structured(message, schema, instructions=, model=, engine=, name=, effort=, max_budget_usd=, timeout_s=,
  env=, cwd=) -> Reply. No tools, never asks for permission, nothing saved (cannot be resumed, not in the
  engine's session list). ask_structured_sync(...) outside async code.
- Or on any agent: Agent(output_schema=S) (works with tools too).

The reply:
- reply.data = the parsed JSON, already checked against the schema (jsonschema)
- a malformed reply -> reply.status == "error", reply.error_kind == "output_shape", reply.error says what is
  wrong (e.g. "reply did not match the output schema: 'tags' is a required property"); usage is kept
- reply.usage / reply.cost_usd / reply.model = this call's tokens, cost and the model that answered
Fake engine: fake.output(data) is the model's structured reply; fake.say("...json...") is parsed instead.
"""
import sys

from agentlib import ask_structured_sync

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "tags"],
    "additionalProperties": False,
}

if not LIVE:
    from agentlib import fake
    # The fake script is looked up by name; ask_structured's default name is "structured".
    fake.script("structured", [[fake.output({"title": "Jupiter quarterly review", "tags": ["sales", "risks"]})]])

reply = ask_structured_sync("Text: 'Quarterly sales review of the Jupiter project, with risks.'", SCHEMA,
                            instructions="Turn the text into a short title and a few tags.",
                            engine=ENGINE, model="haiku")

if reply.status == "error":
    print("failed:", reply.error_kind, "-", reply.error)
else:
    print("data:  ", reply.data)
print("tokens:", reply.usage.total_input_tokens, "in /", reply.usage.output_tokens, "out",
      f"| cost ${reply.cost_usd:.6f} | model {reply.model}")
