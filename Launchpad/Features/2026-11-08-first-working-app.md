# First working app

Status: built
Date: 2026-11-08

The first running app: the Orbit page served by FastAPI on 127.0.0.1 in a pywebview window, with a planner chat built on agentlib whose ask_user questions show up as question cards. It also records what was paused next (front-end refinement, then the orchestrator).

Later changed by: [2026-11-12-v1-loop](2026-11-12-v1-loop.md) (the planner becomes Navigator with its own tool set in the V1 loop)
Later changed by: [2026-11-14-code-organisation](2026-11-14-code-organisation.md) (app/agents/planner.md is now app/agents/planner/agent.md)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## First working app (2026-11-08)
- app/launch.py + app/server.py: Orbit page served by FastAPI on 127.0.0.1; websocket checks access code + Origin; pywebview window (or --browser)
- Planner chat = agentlib agent from app/agents/planner.md: Opus, lean, tools: ask_user only
- ask_user questions → question_round cards (why, options, pick; Yes / Change / option buttons; Accept all; Skip) → round_answer → session.answer()
- Chat window header shows that agent's own prompt-cache tokens (read / written, conversation totals; tooltip = last turn + uncached input/output) via `agent_usage` event; header pill stays app-wide total
- Planner text rendered with a minimal escape-first markdown subset (stand-in for D66 DOMPurify renderer)
- Verified: security rejects bad code/origin; chat → question round → answers → reply, in the browser pane

## Next up (paused 2026-11-08)
- James refining the Orbit front end first
- Then: orchestrator branch — lean = planner is the front door, starts the orchestration loop; orchestrator reaches user only via the queue; general agent beside planner
