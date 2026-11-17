# Planner (role `planner`)

- What: plans work with the user in short question rounds, then writes a step-by-step plan draft (plan.md). Never reads code or runs anything; the user's Approve starts the run.
- Model and harness: the file says `opus`; Launchpad starts every session on the start model (`sonnet`) and may promote once to the top model (`opus`): by itself when auto-promote is on (criteria in `promotion.md`, first 2 turns), or by hand. The user picks harness, start model and auto-promote in the picker under the chat box (`choices.py`; settings `planner_harness`, `planner_start_model`, `planner_auto_promote`, per user). `--model` pins one model; `--planner-start` / `--planner-top` / `--planner-harness` / `--no-auto-promote` / `--promotion-window` / `--promotion-criteria` override for one launch. `--fake` always runs it on the fake engine.
- Questions: every answered question of a round is saved as its own file in the session's `questions/` folder. The Auto answers switch never touches planner rounds (it is for builders only): every round waits for the user.
- Tools: `ask_user` (file) + Launchpad tools added at load time: `explore`, `read_markdown` (.md inside the project or an additional folder), `write_plan`, `edit_plan`, `show_visuals`, `promote_planner` (only when start and top differ and auto-promote is on).
- Skills: its first message lists the session's skills (`app/skills.py` `note`); a plan step may name some (`skills`), and that step's worker gets them. The planner itself runs with its own allowlist (default: all skills) through agentlib.
- Roles: a step with no fitting listed agent that needs a recognisable specialism may get a `role` slug (`write_plan` / `edit_plan`; never with `agent`; plain steps get none). Its first message lists the tally's role names, the 20 most recently used (`app/tally.py` `role_note`), so it reuses them. The step runs on the Builder and is tallied under the role.

- Files:
  - `agent.md`: definition (front-matter name `launchpad-planner`)
  - `planner.py`: `PlannerChat` (one session per Launchpad session), `planner_tools`, plan schemas, promotion (`planner_models`, `promotion_criteria`, `CRITERIA_FILE`)
  - `choices.py`: the picker's harness-and-model table (harness -> agentlib engine; availability from agentlib), the engine a new planner runs on, the `planner_choice` event; `harness_options` / `engine_for` / `launch_harness` are shared with the CLI chat's picker (`app/agents/claude_code/choices.py`)
  - `promotion.md`: editable promotion criteria (shown and editable in the Crew tab / File Explorer)
- Called by: `app/hub.py` (`LaunchSession.chat = PlannerChat(...)`; user messages and question-round answers; `planner_choose` and planner settings changes reload a planner nobody has written to yet with `configure()`). It calls the Explorer (`explore`) and the Visualizer (`show_visuals`).
