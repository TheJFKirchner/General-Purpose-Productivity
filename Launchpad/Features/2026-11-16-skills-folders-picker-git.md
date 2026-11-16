# Skills, primary and additional folders, CLI naming, model picker, Git repos panel

Status: built
Date: 2026-11-16

Five changes asked for in one message. Agents get skills, found in the working folders and scoped per agent from the Crew tab. A session works in one primary folder plus any additional folders. The "Claude Code" chat is renamed "CLI" so the app reads as harness-neutral. The planner's model controls move under the chat box into one harness-and-model picker. The right-hand panel shows Git repos while the Files tab is open, with status, changed files and commit / push.

James gave the request and left before an interview could happen, so nothing below was confirmed by him. Every point in "Assumptions" is the orchestrating session's choice and is open to correction.

## Background

- Asked first, as a question: should skills be visible to every agent, or assigned by the planner? Recommendation given: a fixed allowlist per agent, the agent chooses within it from the descriptions, and the planner names a skill only when a step must follow it.
- Research on Cursor (2026-11-16, from Cursor's docs, not verified by hand): Cursor supports the same SKILL.md standard since 2.4, picks skills from descriptions, and reads `.agents/skills`, `.cursor/skills` and `.claude/skills`. It has no per-agent skills allowlist. So scoping has to be enforced by Launchpad / agentlib, not by a harness setting.

## Assumptions

Skills

1. Skills are discovered only from the session's working folders (primary first, then additional), not from the user's home folder.
2. Per folder: if the folder contains a `.claude` folder, skills come from `.claude/skills` and `.agents` is ignored for that folder, even when `.claude/skills` is missing or empty. Only when there is no `.claude` folder is `.agents/skills` used. Never both for one folder.
3. A skill is a folder holding a `SKILL.md` with `name` and `description` front matter. When two folders have a skill of the same name, the primary folder wins, then the additional folders in order; the others are listed as shadowed.
4. Each agent in the crew has a skills setting: "All skills" or a checklist. Default: Planner = all; every other agent (built-in and folder agents) = none ticked.
5. The setting is stored per user in settings, keyed by agent, as "all" or a list of skill names. Names that do not exist in the current folders are ignored at run time and shown greyed in the checklist.
6. The planner sees the list of discovered skills (name and description) and may name skills on a plan step, the same way it may name an agent. The worker for that step gets its own allowlist plus the skills named on the step. This is James's first design; his simpler alternative (everything visible to everyone) was not taken, because scoping keeps each agent's list short and works the same on a harness with no allowlist.
7. The plan draft shows the skills named on each step, so they are approved with the plan.
8. An agent given no skills behaves exactly as today.
9. The CLI chat (was "Claude Code") keeps the harness's own skill discovery, since it is meant to behave exactly as the harness does. The Crew tab shows it as "All (handled by the CLI)" with no checklist.

Folders

10. The existing connected-folders list stays. One folder is the primary (the existing default folder); any of the others can be ticked as "additional".
11. A new session or CLI chat runs with the primary folder as its working directory and the ticked folders as additional directories (agentlib `add_dirs`). The set is fixed when the session starts.
12. Builder write guards treat the additional folders as inside the project.
13. The existing folder menu still picks the primary for a new session; the additional ticks are a global setting, minus whichever folder is primary.

Naming

14. The display name "Claude Code" becomes "CLI" everywhere a user reads it ("Planner / CLI" switch, "Send plan to CLI", "CLI model", tooltips, feed, crew). Internal ids stay (`pilot`, `chat_*`, `app/agents/claude_code/`), as they did in the last rename.

Model picker

15. "New plan", the model chip and the promote button leave the top of the Plan view. A control row under the planner's chat box holds one picker button showing the current choice, for example "Claude · Sonnet".
16. The picker's menu lists harness-and-model pairs: Claude · Sonnet (default), Claude · Opus, and Cursor entries shown but disabled with "not available yet", because agentlib's Cursor engine is still a stub. The list comes from the back end, so a new engine appears without front-end changes.
17. Below the pairs the menu has: an "Auto-promote to Opus" toggle with a link that shows the promotion rules, and "New plan".
18. Picking Opus on a Sonnet session is the existing promote-by-hand. A choice the running session cannot take (a step down, or another harness) applies to the next new plan, and the picker says so.
19. The choice is remembered per user as the planner's start model and harness.
20. The CLI chat's own model control is unchanged in this request.

Git repos

21. Repos are detected in every connected folder: the folder itself when it is a repo, and repos up to two levels below it, skipping `.git`, `node_modules`, virtual environments and `.launchpad`.
22. While the Files tab is open, the right-hand panel shows "Repos" instead of "In orbit" and "Incoming". A small "N waiting" line stays visible when there are queue items, because permission cards time out and must not be hidden. Other tabs keep the panel as it is.
23. Each repo shows: name, branch, remote, ahead / behind its upstream, clean or changed, and the changed files with lines added and removed. "Refresh" re-reads status; "Check remote" runs a fetch.
24. "Chat box" is read as a message box: type the commit message, then "Commit" or "Commit and push". Files have tick boxes, all ticked by default.
25. Git runs as subprocess calls with argument lists (no shell), only on detected repos. No force push, no pull, no branch switching, no history rewriting.
26. A repo with no remote or no upstream shows "not linked to GitHub" and offers commit only.
27. Git here is a back-end utility, not an agent, so agentlib is not involved.

## Decisions for James to confirm

- Assumption 2 is the literal reading. The alternative is to fall back to `.agents/skills` when `.claude` exists but has no `skills` folder.
- Assumption 6 against his "maybe just visible to everyone" alternative.
- Assumption 24: a message box, not an agent that commits from a typed instruction.
- Commit and push from the app skip the security review that the desktop workflow runs before every commit. Suggested follow-up: a quick secrets check before an in-app push.

## As built (2026-11-16)

Built on branch `feature/skills-folders-picker-git` by three builders in sequence, one UI review and one fix round. Where this section differs from the assumptions, this section is what the code does.

Names

- Settings: `additional_dir_ids`, `agent_skills` (`"all"` or a list of names), `planner_harness`, `planner_auto_promote`, alongside the existing `planner_start_model`. Folder entries carry `is_additional`.
- Launch options: `--planner-harness`, `--no-auto-promote`.
- Websocket: `set_agent_skills`; `crew_list` gains `skills` and a per-agent `skill_setting` (`"all"`, a list, or `"cli"`); `session_started` and `chat_started` gain `additional_dir_ids`; `planner_choose` and `planner_choice`; `planner_model` gains harness, labels and `switchable_to`; `git_scan`, `git_refresh`, `git_fetch`, `git_commit` (with a `push` flag), `git_push`, answered by `git_repos` and `git_result`.
- Plan step: `skills` (list); events also carry `skills_unknown` for names not found.
- agentlib: `Agent(skill_dirs=[...])` and `agentlib.skills.list_skills(folder)`.
- Code: `app/skills.py`, `app/agents/planner/choices.py`, `app/gitrepos.py`, `frontend/src/views/Plan/PlannerPicker.tsx`, `frontend/src/views/Aside/Repos.tsx`.

Differences from the assumptions

- Folders: "Default" / "Make default" now read "Primary" / "Make primary". The Builder may write in additional folders without asking.
- Picker: picking the top model on a running plan promotes that plan only and does not change what new plans start on. A plan nobody has written to yet takes any choice at once. Turning auto-promote off also stops running planners from promoting themselves; turning it on affects new plans only. The Cursor entries are placeholders (Sonnet, Opus) until its engine exists.
- Naming: the `/classic` page still says "Claude Code"; it is no longer updated.
- Repos: a separate "Push N commits" button covers push with nothing to commit. "Commit and push" is hidden on a repo that is not linked. A failed commit restores the staging area to how it was. A missing git name and email gives a short plain message instead of git's raw text. The panel rescans when the Files tab opens and has a "Rescan" button. "N waiting" opens the Plan tab with Incoming showing.
- The agentlib fake engine does not look skills up.

Checks

- agentlib: 234 passed. Launchpad: 209 passed, 2 failed (`test_agents.py::test_each_builtin_has_its_own_folder_with_definition_code_and_readme`, tripped by an empty `Launchpad/.claude/agents` folder on disk, and `test_files_settings.py::test_edited_agent_file_reaches_crew_list_and_new_sessions`, a forward-slash path check that fails on Windows). Both were reported as failing before this work; that was not re-run against `main`.
- Front end: typecheck clean, 50 tests passed, build fresh in `dist/`.
- UI review ran once on the fake demo, before the fix round. Not seen in a browser: the fixes themselves, "Commit and push", and skill chips on plan steps.

Open suggestions (not built)

- A secrets check before an in-app push; git also runs each repo's own hooks, so the panel is for trusted repos.
- "New plan" confirm state lasts only 4 seconds.
- The changed-files total ignores which files are unticked.
- The folder menu sits at the window's bottom-left, away from the picker.
- No feedback when the picked model matches the current start model.
- Crew > CLI shows contradictory tool and guard text.
- The model picker could also sit under the CLI chat box.
- Delete the empty `Launchpad/.claude/agents` folder to clear one failing test.

## Shared interfaces

- Settings: `additional_dir_ids` (list of dir ids), `agent_skills` (`{agent key: "all" | [skill names]}`), planner harness and auto-promote flag. Exact names are recorded in the `app/server.py` header, which stays the authoritative websocket contract, mirrored in `frontend/src/contract.ts`.
- A session's folders: `[primary, *additional]`, used for `cwd` + `add_dirs`, for skill discovery and for the write guards.
- Skill discovery lives in one back-end module that returns, per skill: name, description, the folder it came from, whether from `.claude` or `.agents`, and whether it is shadowed.
- Plan steps gain an optional `skills` list of names.
- agentlib gains an engine-neutral way to pass explicit skill folders (so `.agents/skills` and additional folders work in lean setup), documented in its README table.

## Tasks

Run in sequence, because all three touch the websocket contract, the store and the built front end.

### 1. Folders and skills

- Goal: primary + additional folders for sessions; skill discovery; per-agent skill scoping in the Crew tab; planner can name skills per step; workers receive them.
- Builder: factory-builder, Opus (agent design).
- Area: `../agentlib/` (skills option, README, tests), `app/` (store, settings, server, crew, planner, orchestrator, new skills module, builder guard), `frontend/src/` (Crew, Settings, DirMenu, plan draft, store, contract), tests, docs.
- Done when:
  - Discovery follows assumptions 1 to 3, with tests for `.claude` present, `.agents` only, both present, and a name clash.
  - Crew tab shows a Skills section per agent with "All skills" or a checklist, defaults as in assumption 4, saved per user.
  - Settings shows which folder is primary and lets others be ticked as additional; a new session passes them to the agents and the builder guard allows writes there.
  - Planner prompt lists discovered skills; a plan step can carry skill names; the draft shows them; the step's worker is loaded with allowlist plus step skills (fake-engine test).
  - `python -m pytest` passes in Launchpad and in agentlib; `npm run typecheck`, `npx vitest run` and `npm run build` pass.

### 2. CLI naming and model picker

- Goal: "Claude Code" reads "CLI" everywhere; planner controls move under the chat box into the harness-and-model picker.
- Builder: factory-builder, Opus.
- Area: `frontend/src/` (Chat, Plan, Code, labels, selectors, tooltips, new picker component), `app/` (display names, planner model / harness options, settings), tests, docs.
- Done when:
  - No user-visible "Claude Code" remains in the app (docs and internal ids excepted).
  - The top of the Plan view no longer has New plan, the model chip or the promote button; the picker under the chat box behaves as in assumptions 15 to 19.
  - Back end sends the harness-and-model options with an availability flag; Cursor entries are disabled.
  - Tests and build pass as in task 1.

### 3. Git repos panel

- Goal: repo detection, status and commit / push in the right-hand panel while Files is open.
- Builder: factory-builder, Sonnet.
- Area: new back-end git module and its websocket messages, `frontend/src/views/Aside/` and a new Repos view, store, contract, tests, docs.
- Done when:
  - Assumptions 21 to 26 hold, with back-end tests that build temporary repos (clean, changed, untracked, no remote).
  - Commit with a message and ticked files works; "Commit and push" pushes to the upstream; errors from git are shown in the panel.
  - The "N waiting" line appears on the Files tab when the queue has items.
  - Tests and build pass as in task 1.
