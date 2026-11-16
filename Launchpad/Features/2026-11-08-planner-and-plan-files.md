# Planner, plan files, runs and cost (first design)

Status: decided
Date: 2026-11-08

The first design for the planner (rounds of questions, a small tool set, playbooks, a done checklist) and for the plan files the orchestrator reads. It also sets where run records live, how settings and resume work, and how failures and costs are handled.

Later changed by: [2026-11-12-v1-loop](2026-11-12-v1-loop.md) (the V1 loop overrides the Planner, Runs and plan-file items where they conflict)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Planner
- Interviews in rounds (up to 5 questions, recommended answer + one-line reason); never decides on its own, incl. replans
- Tools only: ask user, explore (Haiku reader), save note, write plan. No bash/edit/write/general sub-agents
- Haiku reader = separate background session started by the app via the library (not SDK subagents); summary ≤300 words as bullets, full report in runs; picked up with next user message
- Playbooks/modes: list of questions + plan format; default playbook always available
- Done checklist: goal, audience, inputs, outputs, done criteria per step, sign-off points; user can say "draft now"

## Plan files (the orchestrator's input contract)
- plans folder per project; two files per plan:
  - plan.md — read by workers/other agents
  - interview notes — decisions + reasons, planner-only (replans, resume)
- Plan header data block: name, draft/approved status, date, link to notes, one line per step (number, title, skill, dependencies, status)
- Plain Python validates header before save
- Three tiers: project plan (big picture) → briefs (one piece, linked, propose approved changes) → tiny cosmetic changes in chat, nothing recorded
- Future router: tiny → worker/general agent; one piece → planner brief mode; big/new → planner project-plan mode

## Runs / state
- Top-level runs folder outside Git; retention a user setting, default 7 days; cleanup on launch
- Session scoreboard file in runs drives the live panel (display-only)
- Full transcripts kept in runs for retention window
- Settings per user, always persist; no project overrides in V1
- Resume only on explicit request = fresh session catching up from scoreboard + notes

## Failure / cost
- Gateway failure: one auto retry, then chat message + retry button
- Cost counter = local approximation from token counts (incl. cached); never poll gateway for spend
- Long-conversation warning offering fresh restart from notes
- Earlier intent: own Python hook system + kill-switch scripts for usage limits
