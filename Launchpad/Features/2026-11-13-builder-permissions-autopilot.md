# Builder permissions: timed cards and autopilot

Status: built
Date: 2026-11-13

Builder permission cards now have a timer and are denied when unanswered, and writes outside the project raise a card instead of being refused. A per-session autopilot approves every builder permission request with no exceptions, by the user's choice, and records each approval.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Builder permissions: timed cards and autopilot (2026-11-13, decided by the user)
- Builder permission requests are cards with a timer (setting `permission_timeout_s`, default 180 s, separate from the question timeout; `--permission-timeout`; 45 s in the fake demo); unanswered = DENIED, the builder is told in plain words, the step records it as an issue. No more builder cards that wait forever
- Writes outside the project folder (and into .launchpad/ or .git/) are no longer refused silently: they raise a card the user can allow
- Unchanged: edits inside the project and ordinary shell commands run without a card; the deny list (git commit/push, package installs, deletes outside the project) still raises cards; questions (timed / blocking) unchanged; the Pilot keeps Claude Code's own permissions
- Autopilot: per session, default off (`--autopilot` / setting `autopilot_default`), switchable before launch and while a run is in flight (set_autopilot). When on, EVERY builder permission request is approved without a card, including git push, package installs, deletes outside the project and writes outside the project: the user explicitly chose no exceptions. Turning it on approves the run's open cards. Each auto-approval goes to assumptions.md (tag autopilot), the report's "Approved by autopilot" section, and the activity feed (auto: true). Autopilot never answers questions
