# Activity feed

Status: built
Date: 2026-11-13

Adds a live activity event for every tool call of every agent, with a short one-line summary. Recent events replay on reconnect and every finished call is appended to the session's activity.log.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Activity feed (2026-11-13)
- `activity` event per tool call of every agent: `started`, then the same id with done | denied | failed; one-line summary (command / path / pattern / short label, max 140 chars, never file contents)
- Recent events replayed on reconnect; every finished call also appended to `<session folder>/activity.log` (pairs with operations-manual.md)
