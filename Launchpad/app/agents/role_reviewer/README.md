# Role Reviewer (helper `role_reviewer`)

- What: an independent, read-only judge of one undefined role (a `role` the planner gave to plan steps that ran on the Builder, recorded in the per-user tally, `app/tally.py`). It weighs the recorded evidence on five fixed tests (clear value; logic beyond the skill; clear usage history; mistakes or issues it would fix; its own view on whether a subagent is the right fix) and returns a case with a verdict: define / keep / not_yet. Default position: a skill plus the Builder is enough. The user decides. A helper, not a crew card and not in the registry; its definition is editable in the File Explorer. Display name "Role Reviewer" (not to be confused with the folder-agent purpose "reviewing").
- Model: the setting `reviewer_model` (default `sonnet`; launch option `--reviewer-model`), on the planner's chosen CLI (`choices.planner_engine`; `--fake` forces the fake engine).
- Tools: `Read`, `Grep`, `Glob` only, each call checked in code against the paths in its brief (`path_guard`); no write, edit, shell or `ask_user`. Structured output `REVIEW_SCHEMA`.
- Reads (brief built by `build_brief`): every tally line; session records (plan.md step section, step report, that step's question files, assumptions, the run's report) only for the 5 most recent uses plus every failed / blocked / sent-back use; `activity.log` only for those problem uses; the SKILL.md of each skill the role used (found like a session finds skills, app/skills.py: each use's primary folder, then the additional folders it ran with, recorded on the use as `extra_projects`); the Builder's `agent.md` and the defined agents. A session folder that is gone is named in the brief and the case.
- Questions: at most 3, shown as question cards (`Incoming.ask`, no session; never auto-answered; "No answer" after the question timeout), then a second turn finalises the case.
- Cost: the standard `Meter` (role `reviewer`, no session): app-wide total only; the case carries its tokens and cost.
- Files:
  - `agent.md`: definition (front-matter name `launchpad-role-reviewer`)
  - `reviewer.py`: `REVIEW_SCHEMA`, `build_brief`, `path_guard`, `run_review`, case markdown, `draft_context` (define path), `Reviews` (the hub's side: one review per role at a time, latest case per role)
- Case files: `<home>/.launchpad/role-cases/<role>-<stamp>.md` (cost, date, the user's decision); after define + create, a copy at `<folder>/.claude/agent-cases/<agent>.md` (outside `.claude/agents/`, never loaded as an agent).
- Called by: `app/hub.py` on `review_start` / `review_decide` (Crew tab).
