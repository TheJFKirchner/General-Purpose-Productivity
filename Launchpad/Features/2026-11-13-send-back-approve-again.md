# Send-back and approve again

Status: built
Date: 2026-11-13

From the first live use: every draft gets a revision number and a revised draft can be approved again, also after a finished run. A reload now replays a pending draft, and the planner is told deliverables never go under .launchpad/.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Send-back and approve again (2026-11-13, from the first live use)
- Every saved draft has a revision number; any draft written after the last approval can be approved, also after a finished run (send-back -> revise -> approve starts run k+1; the old steps/ and report.md move to run-<k>/). Approving again with no new draft is refused with a system message
- A reconnect or reload replays a pending draft after the finished run's events (before: a revised draft written after a run was never replayed, so a reloaded page had nothing to approve)
- plan_draft carries revision + previous_runs; run_started carries run, revision, autopilot; errors handled by the hub are also printed to the console
- Planner prompt: deliverables go in the project folder, never under .launchpad/ (the first live plan put the dashboard in the session folder, so the write was refused)
