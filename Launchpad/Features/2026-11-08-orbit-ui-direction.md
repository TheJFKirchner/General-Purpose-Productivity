# Orbit UI direction and prototype

Status: decided
Date: 2026-11-08

Picks the "Orbit" look from three concepts and sets the window layout: planner chat on the left, crew status and an Incoming request queue on the right. It describes the queue's three kinds of item, how planner question rounds render, and the vanilla HTML prototype with its draft event contract.

Later changed by: [2026-11-13-react-port](2026-11-13-react-port.md) (the vanilla prototype is replaced by the React front end and no longer updated)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## UI direction (2026-11-08)
- Chosen look: "Orbit" (picked from 3 concepts: Mission Control / Orbit / Flight Manual)
- Light lavender-grey ground #F4F3FA, white rounded cards, indigo #3B3FB6 primary, coral #E8664A = waiting on you, green #4BAE7F = done; Sora headings, Inter body; big pill buttons
- Layout: planner chat (left) + side panel (right): "Crew in orbit" status graphic + "Incoming" request queue
- Queue holds 3 kinds:
  - permission: tool + command, Allow / Deny / Always allow
  - question: options, worker's suggestion highlighted, Other… free text
  - info/done: view summary, dismiss
- Planner question rounds render as cards in chat: Yes / Change per question, Accept all, Skip (skipped stays open)
- Prototype: prototype/launchpad-orbit.html — vanilla HTML/JS, still being refined before React port
  - Bridge object: websocket to 127.0.0.1 when ?port=&code= in URL, else demo mode with scripted fake planner
  - Event contract in the file header — DRAFT, to be grilled:
    - in: planner_message, typing, question_round, queue_item, queue_resolved, crew, usage, plan_meta, system
    - out: user_message, round_answer, queue_response, queue_dismiss
- Concept canvas (all 3 looks): https://claude.ai/artifact/XpsWhXKF2rw8pLzur1VkE3
