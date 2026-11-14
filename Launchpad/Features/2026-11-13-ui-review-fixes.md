# UI review fix round

Status: built
Date: 2026-11-13

Fixes from a review of the running UI: queue items carry the agent, one Explorer meter per session, a snapshot on reconnect, a favicon and one consistent session total. Permission cards no longer show a recommended choice.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## UI review fix round (2026-11-13)
- queue_item carries agent_id; agent / name fields are the plain display name ("Flight Engineer"); the page adds the step
- One Astronaut per session: a single meter with cumulative usage, working during a lookup, idle between lookups (never "done")
- Reconnect: first event is `snapshot {current_session_id, sessions:[{session_id, chat, report_sent, ...}], chats:[...]}`; planner chat history kept per session
- /favicon.ico served (small SVG)
- One session total everywhere (run_finished, snapshot, report.md): orchestrator + builders + astronauts; planner separate as planner_cost_usd / "Planner (separate, not in the session total)"
- Permission cards carry rec null (no recommended choice); questions keep their recommendation
