# Cost audit, thinking / effort facts and planner cost study

Status: decided
Date: 2026-11-13

Audits where every dollar figure comes from and what the fixed cost floors are, checks how thinking effort is set for each agent, and measures where a live planner conversation spends its money. It lists candidate savings, some of which later requests built.

Later changed by: [2026-11-14-code-organisation](2026-11-14-code-organisation.md) (tests/live_planner_study.py is now tests/live/live_planner_study.py)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Costs (audit 2026-11-13)
- One source: every dollar figure is the engine's own per-turn cost (Claude Code's total_cost_usd, turned into a per-turn delta in agentlib); no local price table. Per-turn token counts are the turn's own (not cumulative); verified live against published prices (Haiku 5.5, Sonnet 5.5, 1-hour cache writes) to the cent
- The app-wide `usage` event is the plain sum of all agent_usage (all sessions, chats, planner) and now carries the same four token counts; most "tokens" are cache reads, which are cheap
- Floors (1-hour cache writes, 2x base input): Claude Code system prompt + tools (Pilot) is about 30K tokens: about $0.12 to write cold on Sonnet 5.5 ($0.24 Opus 5.5, $0.006 Haiku 5.5), then about $0.003 per model call to read; a lean builder step about 7K tokens cold (about $0.03 on Sonnet 5.5), paid again every step (fresh session); output tokens are $10/M on Sonnet 5.5, so a 5K-token file costs about $0.05 to write plus its later cache write and reads
- Candidate savings (not built): 5-minute instead of 1-hour cache writes (-37.5% on writes, if Claude Code allows choosing), one builder session per run instead of per step, planner on Sonnet instead of Opus, cheaper Pilot model, trimmed tool lists

## Thinking / effort (facts, 2026-11-13)
- No agent sets effort: agent files cannot hold it, agentlib passes none by default, lean agents do not read the user's settings (their modelSettings effort "high" for Opus 5.5 does not apply), and CLAUDE_CODE_EFFORT_LEVEL is not set; so every agent runs its model's Claude Code default: medium for Opus 5.5 / Sonnet 5.5 / Haiku 5.5, with adaptive thinking (cannot be turned off on these models). The Pilot reads the user's settings, so it gets "high" on Opus 5.5 if it ever runs Opus
- agentlib already sets effort per agent at load time (`Agent(effort=...)`, levels low | medium | high | xhigh | max); not used yet
- Live: planner at effort low, conversation A turns 1-2: $0.0447 vs $0.0540 at default (-17%), same tool use and 3-question round, shorter plan

## Planner cost study (2026-11-13, live, Opus 5.5 planner as it runs; tests/live_planner_study.py)
- Short conversation A (3 turns): $0.096; longer conversation B (8 turns, 3 rounds incl. typed push-back, 2 lookups, a visual set + pick, draft + 2 revisions): $0.405; both reconcile to published prices exactly
- Where it goes (B): visible output 38%, cache writes (1-hour) 30%, thinking ~24% (inferred), cache reads 6%, sub-agents 2%, uncached input ~0%. The three plan-draft turns cost $0.267 (66% of the planner): each revision rewrites the whole plan (~6K characters) as tool input, then caches it
- Candidate savings (not built): revise plans by edits, effort low, Sonnet planner, shorter replies after a draft, tighter plan text; 5-minute cache only if replies come within 5 minutes (gaps would rewrite the whole context), tool definitions and lookup results are minor
