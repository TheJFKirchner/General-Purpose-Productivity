# Undefined roles: tally, independent review, define as an agent; Auto answers for builders only; one place for cost totals

Status: built
Date: 2026-11-17

When a plan step has no defined agent, the planner now gives it a role name. Launchpad keeps a record of each role's uses, and the Crew tab lists roles that have been used but have no definition. Pressing Review has an independent reviewer agent read the history and write a case for or against giving the role its own agent definition, judged on five fixed tests; the user decides. The same request corrects Auto answers (builders only, every question answered) and makes the server the one place where cost totals are added up.

Interviewed with the grilling skill on 2026-11-17; James confirmed the design.

## Why

A similar product records subagents that were used without a predefined definition and offers to convert them. James wants that, but not as a one-click convert: an agent has to earn its definition, because the default alternative, a skill plus the generic Builder, is usually enough.

## Assumptions (shown to James; none corrected)

Tally

1. Only plan-step workers are tracked. Subagents the CLI launches by itself are out of this version.
2. A step that uses a registered agent is not tracked.
3. The tally is per user, in its own file beside the existing settings. Each entry holds: role name, base agent, skills, purpose, times used, last used, folders used in, up to three sample step instructions, and the last 20 uses.
4. The Crew tab gets a "Used but not defined" section. A role appears once it has been used twice.
5. Each entry has Review, Merge (into another entry) and Dismiss. A dismissed role stays hidden unless it is used again.
6. Once a role is defined as an agent, its tally entry is removed and the planner assigns the agent by name.
7. The zero-token demo never writes to the real tally; it gets sample entries.
8. Built on the branch of request 25, which is not merged yet, because it depends on the "Other" purpose.
14. A plan step gets an optional `role` field, shown as a chip on the plan card. The planner sets it only when the step needs a recognisable specialism; plain steps get none.
15. The role name is the tally key. Skills are evidence under it, so one role used with different skills is one entry.
16. The planner sees the role names already in the tally, capped at the 20 most recently used, so it reuses them.
17. A step that names an agent which no longer exists is tallied under that name.
18. Tally writes re-read the file first, so two Launchpad windows do not overwrite each other.
19. The tally spans all folders. A defined agent is saved to the folder selected on the Crew tab, as the add-agent flow does today.

Review

9. Five fixed tests, each addressed in the case: clear value; logic the agent needs beyond the skill; clear usage history; mistakes or issues it fixes; an independent view that a subagent is the right fix.
10. The independent view comes from a new read-only built-in agent that sees only the evidence. It is not the planner and not a builder.
11. The default answer is "skill plus Builder is enough". The review needs positive evidence to say otherwise.
12. With thin history the reviewer says so and should lean to "not yet".
13. The written case is saved with the agent when one is created.
20. The review opens in the Crew tab: progress while the reviewer reads, then the case, the verdict and any question cards.
23. Each review shows its cost in tokens and dollars on the case screen and in the case file. The drafting call for a defined agent shows its cost the same way.
25. A review's cost counts in the app-wide total, not in any session's total, like the drafter.

Auto answers

21. Applies to every builder question, including blocking ones. Each is saved as a question file marked as the builder's own decision and listed in the run's report.
22. Permission cards stay with Autopilot and are not affected.

Cost

24. One cost path: agentlib reports usage and cost for every run from one module; Launchpad has one place that produces every figure shown.

## Decisions from the interview

- Q1 Auto mechanism: the builder's question tool always requires a recommended answer and a reason; with Auto on the question resolves at once with it. Rejected: disabling the tool (no record of the question), a "decide yourself" reply (decision arrives in a second step), a swapped-in record-assumption tool (tools are fixed when a builder starts, so a mid-run switch would not take effect). Fact found after: `recommended` is already a required string on `ask_question`, so the work is removing the planner and CLI paths and rejecting an empty recommendation.
- Auto answers scope (James): builders only. Never the planner, never CLI chats.
- Q2 Who names the role: the planner, reusing tally names. Rejected: grouping afterwards with a cheap model. Near-duplicate names are handled by Merge.
- Q3 What Review does: not a quick convert. It is a justification of why the role earns a definition over skill plus Builder, on the five tests (James's list).
- Q4 Shape: evidence first. The reviewer writes the case from the records, asks question cards only for what the evidence cannot answer, and the decision is always the user's. Rejected: a pure interview on all five tests every time.
- Q5 Evidence per use: session and step, how the step ended (done, failed, blocked), number of questions the builder asked, assumptions logged and questions that timed out, whether the plan was sent back after that run. Last 20 uses per role.
- Q6 Verdicts: define an agent (the drafter writes the file from the case; the user edits and saves); keep as skill plus Builder (the case notes what the skill should cover; Launchpad does not write skills in this version); not yet (keep counting).
- Q7 Reviewer model: Sonnet by default, on the planner's CLI, changeable in Settings.
- Q8 After "keep" or "not yet": the role leaves the list but keeps being counted, and returns after five more uses or a new failed, blocked or sent-back step.
- Q9 Auto answers switch: beside the Autopilot switch wherever that appears (plan card before launch, running row, each running mission); removed from the row under the planner's chat box.
- Q10 Reading depth: the tally line for every recorded use; session records opened only for the five most recent uses plus every failed, blocked or sent-back use; the activity log only for those problem uses.
- Q11 Cost: the engine's own per-turn cost through `agentlib/reply.py` and Launchpad's `Meter` is already the single source, so nothing drastic. The server becomes the only place totals are summed, the front end only displays them, and there is one formatting helper on each side.

## What the reviewer reads

1. The tally entry: one line per use.
2. For the uses it opens: the step's section of plan.md (title, instructions, done-when), the step's own file, that step's question files, the assumptions logged for it, and the run's report. Never the code the builders wrote.
3. The SKILL.md of each skill the role used, to compare against instructions the planner kept adding.
4. The generic Builder's definition and the list of defined agents, to see whether something already covers the role.

Session folders live inside each project folder. When one is gone, the reviewer has only the tally line and the saved samples for that use, and the case says so.

## Shared interfaces

- Plan step: optional `role` (short slug, letters, digits, hyphens).
- Tally file: per user, beside settings.json, written with re-read-then-replace.
- Reviewer: built-in agent in its own folder under `app/agents/`, read-only, metered with the same `Meter` as every agent, model setting beside the other model settings.
- Websocket messages for the tally list, starting a review, review progress, the case, a verdict, merge and dismiss are named by the back-end builder in the `app/server.py` header and mirrored in `frontend/src/contract.ts`; the front-end builder builds to them.
- The drafter's message gains optional context (sample instructions, skills, the case) without changing its output fields.

## As built (2026-11-17)

Built on branch `feature/cli-picker-other-questions` (the branch of request 25) by three builders in sequence, one UI review and one fix round. Where this section differs from the sections above, this section is what the code does.

Names

- Plan step field `role` (slug, up to 40 characters), carried on `plan_draft`, `run_started` and `step_update`.
- Tally: `app/tally.py`, stored as `roles.json` beside settings.json; cases in `role-cases/` beside it. On define, a copy of the case goes to `<folder>/.claude/agent-cases/<name>.md`, a sibling of the agents folder so no CLI reads it as an agent.
- Reviewer: `app/agents/role_reviewer/`, role id `role_reviewer`, display name "Role Reviewer", meter role `reviewer`, setting `reviewer_model` (default sonnet), launch option `--reviewer-model`.
- Websocket, page to server: `roles_get`, `role_dismiss`, `role_merge`, `review_start`, `review_decide`; on define, `agent_draft` and `agent_create` take `role`. Server to page: `roles_list`, `review_started`, `review_progress`, `review_case`, `review_failed`, `review_refused`, `review_decided`. Reviewer questions are `queue_item`s with `review_id`, `role` and `test`. `agent_drafted` gains `usage` and `role`; `agent_saved` gains `role` and `case_path`.
- Cost: `app/costs.py` is the only place totals are summed and formatted on the server; `usage` events gain `session` and `chat` scopes and `by_role`; the front end's one formatter is `usd()`.
- Front end: `views/Crew/UsedRoles.tsx`, `views/Crew/RoleReview.tsx`, `store/roles.ts`.

Differences and choices

- "Sent back" is recorded when the planner writes a revised draft after a run.
- The planner's instructions grew to 2,655 characters; the test's limit was raised from 2,500 to 2,800.
- The reviewer finds a role's skills in the primary and the additional folders.
- A reviewer question that nobody answers before the normal question timeout resolves as "No answer" and the reviewer carries on.
- Starting a define on an Add an agent form that already holds unsaved text replaces that text.
- Auto answers: each decided question shows in Incoming as a settled line marked "Auto" (the last 200 are replayed on reconnect), not in the planner chat. `auto_answer` lost `round_id`. A folder agent that brings its own question tool is not covered.
- Cost: the "agents and tokens in the session" and "builders on a step" figures also moved to the server, so the rule for which agents count exists only there. Values on screen were checked in the UI review and agreed (header total = planner + session + CLI chat + reviews and drafting).
- Settings: both CLI settings are drop-downs showing the CLI's display label ("Planner CLI (new plans)", "CLI chat: CLI (new chats)").
- Activity entries never show absolute paths, for any agent.

Checks

- Launchpad: 265 passed, 2 failed (the same two that predate request 24). agentlib untouched. Front end: typecheck clean, 77 tests passed, build fresh in `dist/`.
- UI review ran once in a browser on the fake demo, before the fix round: all three verdict paths, Merge, Dismiss, the empty section, Auto answers during a run, no console errors, no sideways scroll at 1000 or 1440 px.
- Not seen in a browser: the fix round (the role chip's size, the two switches on one row at about 768 px height, the "Reviewer's recommendation" tag). Not exercised at all: blocked and sent-back markers (the demo has no such uses); a live review on a real engine, so the real cost per review is not yet known.

Open suggestions (not built)

- A longer, separate timeout for reviewer questions.
- Header writes small amounts as "~$0.01", the review as "<$0.01".
- "Session total" leaves out the planner (its tooltip says so), so it can read lower than the planner's share.
- Dismiss has no toast and no undo.
- "Back to Crew" opens the list mid-scroll; focus falls to the page after a decision.
- The Auto answers knob is hard to see when on.
- The CLI chat shows "$0.00 · 0 tool calls" until its turn ends.

## Tasks

In sequence: all three touch the hub, the contract and the built front end.

### 1. Auto answers for builders only; cost totals summed in one place

- Builder: factory-builder, Sonnet.
- Area: `app/hub.py`, `app/incoming.py`, `app/agents/planner/planner.py`, `app/agents/builder/`, `app/agents/claude_code/`, report and session files, `frontend/src` (AutoAnswersSwitch placement, PlannerPicker, PlanLog, Orbit, Missions, selectors, cost formatting), tests, docs.
- Done when: assumptions 21 and 22 and decisions Q1, Q9 and Q11 hold; planner rounds and CLI chat questions are never auto-answered (tests); an empty recommendation is rejected; cost figures on screen are unchanged in value; all suites and the build pass with no new failures.

### 2. Role field, tally, reviewer agent, review flow (back end)

- Builder: factory-builder, Opus (agent design).
- Area: `app/agents/planner/` (schemas, prompt), `app/plan.py`, new tally module, new reviewer agent folder, `app/agents/drafter/`, `app/agents/crew.py`, `app/hub.py`, `app/server.py` header, `frontend/src/contract.ts` (types only), settings, demo data, tests, docs.
- Done when: assumptions 1 to 3, 6 to 19, 23, 25 and decisions Q2 to Q8 and Q10 hold on the fake engine, with tests for: a role recorded from a run with its evidence; the two-use threshold; resurfacing; merge; dismiss; concurrent writes; a review producing a case with five sections, a verdict and a cost; the define path feeding the drafter; all suites pass with no new failures.

### 3. Crew screens for roles and reviews (front end)

- Builder: factory-builder, Sonnet.
- Area: `frontend/src/views/Crew/`, plan card role chip, Settings (reviewer model), store, demo, tests, docs, build.
- Done when: assumptions 4, 5, 14 (chip), 20 and 23 hold in the fake demo; the three verdict paths can be walked end to end; typecheck, tests and build pass.
