# CLI-then-model picker, CLI choice for the CLI chat, "Other" agents, smaller activity feed, question files

Status: built
Date: 2026-11-17

A follow-up to request 24. The model picker becomes two levels: pick a CLI, then one of that CLI's models. The CLI chat gets the same picker, so the user can switch CLIs there too. Agents get a fifth purpose, "Other". The activity feed on the Missions tab takes less room. Every answered question is saved as its own markdown file in the session folder. A design for recording undefined subagents is written down but not built.

James gave the request and left before an interview could happen. Every point under "Assumptions" is the orchestrating session's choice and is open to correction.

## Assumptions

Picker (planner)

1. "CLI" is the user-facing word for a harness (Claude, Cursor).
2. The picker menu under the planner's chat box shows a CLI dropdown first, then only the chosen CLI's models as the list. The button still reads "CLI · Model", for example "Claude · Sonnet".
3. A CLI that is not available (Cursor today) is listed in the dropdown, marked "not available yet", and cannot be chosen.
4. Changing the CLI selects that CLI's first model. The rules from request 24 for when a choice applies stay as built: an untouched plan takes it at once, a running plan takes only a promotion, anything else applies to the next new plan.
5. Auto-promote, the Rules link and New plan stay in the menu below the models.
6. The back end keeps sending the flat list of options; the front end groups it by harness.

CLI chat

7. The CLI chat gets the same picker under its chat box, without the auto-promote and New plan items. The read-only model chip it replaces is removed.
8. The CLI and model for the chat are remembered per user (`pilot_harness`, and the existing `pilot_model`). `--pilot-model` keeps working; the launch engine is the default CLI; `--fake` still forces the fake engine for everything.
9. A chat's CLI and model are fixed when its first message is sent. A chat nobody has written to takes a new choice at once; for a chat in progress the choice applies to the next new chat, and the picker says so.
10. The CLI chat's choice is independent of the planner's.

"Other" agents

11. A fifth purpose, `other`, labelled "Other", for agents that are not planning, exploring, building or reviewing. It can be chosen when adding an agent and gets its own section in the Crew tab.
12. At run time an "other" agent is treated like a building agent: gated tools, permission cards and the Builder guards. The planner may assign it to plan steps.
13. A folder agent with a missing or unknown `purpose` is now grouped under "Other" instead of silently becoming "building". Its run-time treatment does not change, because "other" and "building" are guarded the same way.

Activity feed

14. "The activity section in Missions" is the activity feed in the right-hand panel on the Missions tab. "Smaller" is read as less height: the feed is capped at about a third of the panel and Incoming gets the room. Text size and rows are unchanged.

Question files

15. Every question that gets an answer is saved as one markdown file in `<session folder>/questions/`, named with a running number that is unique within the session and a short slug of the question, for example `003-which-chart-library.md`.
16. Each file holds: the question, who asked (Planner, Builder, CLI) and when, the step it belongs to when there is one, the options offered, the answer given, and the justification.
17. "Justification" is the agent's own reason for asking plus its recommended answer, and any text the user typed with their answer. The user is not asked for a reason.
18. A question that timed out is saved too, with the answer "No answer (timed out)" and the assumption the agent went on with.
19. Planner question rounds write one file per question in the round, not one per round.
20. Files stay in the session's `questions/` folder across runs; they are not moved into `run-<k>/`.
21. The report lists the question files of that run with links.

Auto answers

James's clarification: "auto" means questions are approved automatically so all the answers are collected and work carries on while he is away; he answers or corrects them separately later.

24. An "Auto answers" switch sits in the control row under the planner's chat box. It is per session and off by default. It is separate from Autopilot, which approves permission requests.
25. While it is on, any question from any agent in that session (planner rounds, builder questions) is answered at once with the agent's recommended answer, and the agent carries on.
26. A question with no recommended answer is not guessed: it waits as a normal card.
27. Each auto-answered question shows in the chat as a compact line with the question and the answer taken, and its question file is marked "Answered automatically (recommended)".
28. To change an auto answer later, the user tells the planner in the chat (or sends the plan back); there is no separate editing screen.
29. Permission cards are not affected by this switch.

Left out on purpose

22. (Superseded: James clarified "the auto tab" on 2026-11-17; see "Auto answers" below.)
23. Recording undefined subagents is not built. The design is below.

## Decided design, not built: undefined subagents

Asked as "how could this work". Design given:

- A plan step that names no registered agent runs as a generic Builder with that step's instructions and skills. That combination is the ad-hoc agent.
- The planner gives such a step a short role name (for example `echarts-visual-builder`), reusing names from the tally where one fits. No extra model call.
- Launchpad keeps a per-user tally next to the existing use counts: role name, base agent, skills, purpose, times used, last used, two or three sample step instructions.
- The Crew tab shows "Used but not defined" for roles used twice or more, with Review, Merge and Dismiss. Review feeds the samples to the existing drafter, and the result is saved through the existing add-agent flow.
- CLI-mode subagents are out of a first version: the calls are visible in the activity feed, but grouping free-text descriptions is unreliable.
- Rejected: letting the orchestrator launch arbitrary subagents, because it cuts across the Builders.

What exists today that this builds on: steps carry `agent` and `skills` but no free-text role; use counts are in the per-user store under `agent_uses`.

## Questions for James

- Auto answers: is taking the recommended answer right (assumption 25), and is "tell the planner" enough for changing one later (assumption 28)?
- Should the undefined-subagents feature be built next (assumption 23)?
- Is "smaller" for the activity feed about height (assumption 14), or about text and row size too?
- Should an "other" agent be guarded like a builder (assumption 12), or be read-only until told otherwise?

## As built (2026-11-17)

Built on branch `feature/cli-picker-other-questions` by two builders in sequence, one UI review and one fix round. Where this section differs from the assumptions, this section is what the code does.

Names

- Settings: `pilot_harness` (empty means the launch engine's CLI). Launch option `--pilot-harness` (not asked for).
- Websocket: `cli_choose`, answered by `cli_choice` and `chat_model`; `chat_started` and snapshot chats gain `harness`, `label`, `option_id`, `started`. `set_auto_answers`, answered by `auto_answers` and `auto_answer`; snapshot field `auto_answers`; `queue_resolved` carries `by: "auto"`.
- Code: `frontend/src/components/ModelPicker.tsx` (shared by both chats), `app/agents/claude_code/choices.py`, `tests/test_cli_picker.py`.

Differences from the assumptions

- Picker: the CLI dropdown is a list inside the menu, not a native select.
- Auto answers: a planner round is answered automatically only when every question in it has a recommendation; otherwise the whole round waits. It does not apply to CLI chats.
- Question files: a CLI chat has no session folder, so its questions go in `<chat-id>/questions/`. Skipped planner questions get no file. The run is named as the app names it ("A", or "A (launch 2)"), and a question asked before launch says "Before launch". An archived report's links are rewritten to `../questions/`.
- Activity feed: capped at 34% of the panel.
- "Other": green token, Shapes icon.
- Crew: the CLI card shows "This chat: …" while a chat runs, otherwise "New chats: …". The CLI definition now says the harness's own tools apply.
- CLI chat: the app's own wording no longer names a brand (placeholder, deny box, working label). Below 1200 px wide or 800 px tall the shortcut line is hidden.

Checks

- Launchpad: 231 passed, 2 failed (the same two that predate request 24). Front end: typecheck clean, 63 tests passed, build fresh in `dist/`.
- UI review ran once on the fake demo, before the fix round, with no console errors. Not seen in a browser: the fix round, including the two narrow-window layout fixes; a planner question with no recommendation; Auto answers and Autopilot on together.

Open suggestions (not built)

- Auto answers and Autopilot look alike; an icon on Auto answers would tell them apart.
- A blocking builder question that is auto-answered briefly flips its step to blocked and back.
- The planner card on Crew shows "Opus" while the CLI card shows "Claude · Opus".
- The Other colour is close to the green used for success.
- At a 700 px window height the activity feed shows about two rows.

## Tasks

Run in sequence: both touch the websocket contract, the store and the built front end.

### 1. CLI-then-model picker, and the picker in the CLI chat

- Builder: factory-builder, Opus.
- Area: `frontend/src/views/Plan/PlannerPicker.tsx` and its selector, `frontend/src/views/Code/`, `app/agents/claude_code/`, `app/agents/planner/choices.py`, `app/hub.py` (chat start), settings, server header, contract, tests, docs.
- Done when: assumptions 1 to 10 hold; the CLI chat loads on the chosen engine and model (fake-engine test); settings persist; all test suites and the build pass with no new failures.

### 2. "Other" purpose, activity feed size, question files, Auto answers

- Builder: factory-builder, Sonnet.
- Area: `app/agents/crew.py`, `folder_agents.py`, `app/files.py`, `frontend/src/` labels, Purpose and Crew grouping, `frontend/src/views/Aside/Aside.css`, `app/agents/planner/`, `app/incoming.py`, `app/agents/builder/`, `app/sessionfiles.py`, report writing, tests, docs.
- Done when: assumptions 11 to 21 and 24 to 29 hold, with tests for Auto answers (a planner round and a builder question answered with the recommendation; a question with no recommendation left waiting), and tests for an "other" agent taking a plan step, an unknown purpose landing in "Other", and question files for a planner round, a builder question, and a timed-out question; all test suites and the build pass with no new failures.
