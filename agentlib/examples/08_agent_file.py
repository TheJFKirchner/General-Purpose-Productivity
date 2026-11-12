"""08 - Load an agent from a standard agent file (.claude/agents/*.md, .cursor/agents/*.md).

Run:  python examples/08_agent_file.py          (fake engine, free)
      python examples/08_agent_file.py --live   (LIVE: uses your Claude login, costs tokens; haiku)

Sample files: examples/.claude/agents/word_counter.md and examples/.cursor/agents/reviewer.md.

The file stays a normal Claude Code / Cursor subagent file (standard front matter, body = instructions),
so the same file also works inside the IDE. Library-only settings (engine, setup, cwd, tool functions,
timeouts, on_permission, ...) are passed to the loader, never written in the file.
Raw SDK equivalent: none (the SDK's AgentDefinition is for subagents, which agentlib does not expose yet).
"""
import sys
from pathlib import Path

from agentlib import load_claude_agent, load_cursor_agent, tool

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"
HERE = Path(__file__).resolve().parent          # the "project" folder holding .claude/ and .cursor/


@tool(read_only=True)
def count_words(text: str) -> int:
    """Count the words in a piece of text."""
    return len(text.split())


if not LIVE:
    from agentlib import fake
    # The script key is the agent's name from the file's front matter.
    fake.script("word_counter", [[fake.call("count_words", {"text": "the quick brown fox"}),
                                  fake.say("4 words.")]])

# Name lookup: <project>/.claude/agents/<name>.md, then ~/.claude/agents/<name>.md. A path also works.
# tools= gives Python implementations for custom names in the file's `tools:` line (missing -> AgentFileError).
# Any other Agent field can be passed as a keyword override (timeout_s=..., max_turns=..., on_permission=...).
agent = load_claude_agent("word_counter", project=HERE, engine=ENGINE, tools=[count_words], timeout_s=120)

print("name:     ", agent.name, "| model:", agent.model, "| setup:", agent.setup)
print("cwd:      ", agent.cwd)                  # defaults to the folder that holds .claude/
print("source:   ", agent.source)
print("tools:    ", agent.tools)                # as written in the file
print("extra:    ", agent.extra)                # unknown front-matter fields (color) are kept, not rejected
print("warnings: ", agent.warnings)             # e.g. body mentions files but the agent has no Read tool

reply = agent.ask_sync("How many words are in: the quick brown fox")
print("reply:    ", reply.text, [(c.name, c.result) for c in reply.tool_calls])

# Cursor format. Cursor files have no tools line: readonly: true -> Read, Grep, Glob (+ given tools, ask_user).
# Until the cursor engine exists these run on the claude engine; non-Claude model names fall back to the
# engine default with a warning. Loaded here only, not run.
reviewer = load_cursor_agent("reviewer", project=HERE, engine=ENGINE)
print("\ncursor file -> engine:", reviewer.engine, "| model:", reviewer.model, "| tools:", reviewer.tools)
print("cursor warnings:", reviewer.warnings)
