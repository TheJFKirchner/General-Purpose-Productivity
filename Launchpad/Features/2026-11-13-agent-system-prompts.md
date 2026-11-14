# Agent system prompts: planner without the Claude Code preset, builder on it

Status: built
Date: 2026-11-13

Confirms the planner and most agents run on their own short prompt rather than Claude Code's, and fills the planner's few gaps leanly. By the user's decision the builder now runs on Claude Code's own system prompt with its file text appended, still without folder settings.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Planner prompt: no Claude Code preset (2026-11-13)
- Checked: the planner already runs on its own file body only (lean setup, a plain-string system prompt); so do the Astronaut, orchestrator, builder and Cartographer. Only the Pilot uses the Claude Code preset (by design: "no difference from Claude Code"). A test now asserts the planner is built without the preset
- Planner gaps the preset would have covered, now filled leanly: today's date in the first-message context line (code, so the agent file stays standard); prompt lines "never say what a file contains unless explore / read_markdown showed it" and "short, plain, light markdown only"
- Live (Opus 5.5, same 3-turn exchange: ask_user round, answers, explore + write_plan): own prompt $0.113 (cold prompt 2.9K tokens) vs with the preset $0.147 (cold prompt 5.2K, built-in tools excluded); same tool use, rounds and format; the preset version was a little wordier
- Cold first-call sizes (Haiku tokenizer, incl. ~0.5K request framing): planner 2.8K (prompt 1.1K + tools 1.7K), Astronaut 3.7K (0.8K + 2.9K), orchestrator 1.7K (1.0K + 0.7K), builder 6.7K (1.0K + 5.7K), Pilot 29.9K (preset 3.7K + built-in tools 26.2K), Cartographer 0.9K (no tools)

## Builder on the Claude Code system prompt (2026-11-13, user decision)
- The builder runs on Claude Code's own system prompt with its file text appended (the Launchpad part: flight log, questions, approvals, submit_report, routing notes); the file was trimmed of what Claude Code covers and stays a standard agent definition
- Still lean: new agentlib option `Agent(engine_prompt=True)` = the engine's own agent prompt + instructions, with no folder settings. What loads: the Claude Code prompt (incl. its environment block), the file text, the same 6 built-ins + 3 Launchpad tools. What does not: project CLAUDE.md, user / project / local settings (so no user plugins, hooks or permission rules), skills, claude.ai connectors, auto memory
- Unchanged: fixed tool list, write / shell guard, timed permission cards, autopilot
- Cold start on Sonnet 5.5 (live): 6,654 tokens / $0.0267 before -> 8,128 tokens / $0.0325 now (+$0.006 per builder step)
- Agents on the Claude Code prompt: builder (lean, engine_prompt) and Pilot (full project setup); planner, Astronaut, orchestrator, Cartographer run on their own prompt only
