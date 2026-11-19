# Lean agent on Claude Code

Status: built
Date: 2026-11-18

The first live sessions cost far more per turn than expected: one turn that made three cards used about 24,000 tokens and an estimated $0.089. The agent was stripped to the bare minimum and moved off `agentlib` onto Claude Code directly. The same kind of turn now uses one model call, about 6,300 tokens and an estimated $0.025.

## Decisions

- **No `agentlib` for now, by the owner's decision.** The agent runs on the Claude Agent SDK for Python. This is a deliberate exception to the workspace rule that agent code goes through `agentlib`. It makes the whiteboard Claude-only. All engine code is in `whiteboard/engine.py`, behind a small interface that the fake engine also implements, so moving back to `agentlib` changes that one file.
- **No tools.** The agent replies in a plain-text format (a header line per card, a code block, one chat line) that `whiteboard/reply.py` parses as it streams. This removed the tool definition, the wrapping of code in a tool call, and a second model call per turn that re-read everything. A reply that ignores the format is shown as plain text.
- **Nothing but our instructions.** Our prompt replaces Claude Code's own; no setting sources, CLAUDE.md, memory, skills, MCP servers or session saving; an empty temp working folder; lowest effort; a 5-minute prompt cache; no background title call.
- **Smaller prompt.** A short brief, compact samples, the session library's reference only, a few lines on tables unless the session library is `html`, and card code sent only when a session starts or restarts.
- **Flags**: `--model`, `--effort` and `--debug-usage` (per-turn model calls, tokens by type, cost and the size of each prompt part).

## Where the tokens had gone

- A second model call after the tool results, re-reading the whole prompt.
- The tool definition and tool-call wrapping.
- A background call per turn that generated a session title.
- A 1-hour prompt cache, priced higher than the 5-minute one.
- Our own prompt was larger than it looked: code and JSON take more tokens per character than prose.

## Known limits

- About 575 tokens per call remain that could not be removed (built-in subagent and plugin listings). The option that would remove them does not use the normal login.
- Reasoning cannot be switched off on the current models; lowest effort is the floor. Output is now most of the cost.
- The cost shown is Claude Code's estimate from token counts, not a bill.
- With no tool, a card naming a parent that does not exist is kept without a parent instead of being corrected.
- The system prompt (column names and sample rows) is written to a temp file and deleted on close; if the process is killed, the file stays in the system temp folder.
