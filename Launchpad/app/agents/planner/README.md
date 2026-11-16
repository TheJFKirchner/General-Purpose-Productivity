# Planner (role `planner`)

- What: plans work with the user in short question rounds, then writes a step-by-step plan draft (plan.md). Never reads code or runs anything; the user's Approve starts the run.
- Model: the file says `opus`; Launchpad starts every session on `sonnet` and may promote once to `opus` (criteria in `promotion.md`, first 2 turns, or by hand). `--model` pins one model; `--planner-start` / `--planner-top` / `--promotion-window` / `--promotion-criteria` change the rest.
- Tools: `ask_user` (file) + Launchpad tools added at load time: `explore`, `read_markdown` (.md inside the project only), `write_plan`, `edit_plan`, `show_visuals`, `promote_planner` (only when promotion is on).
- Files:
  - `agent.md`: definition (front-matter name `launchpad-planner`)
  - `planner.py`: `PlannerChat` (one session per Launchpad session), `planner_tools`, plan schemas, promotion (`planner_models`, `promotion_criteria`, `CRITERIA_FILE`)
  - `promotion.md`: editable promotion criteria (shown and editable in the Crew tab / File Explorer)
- Called by: `app/hub.py` (`LaunchSession.chat = PlannerChat(...)`; user messages and question-round answers). It calls the Explorer (`explore`) and the Visualizer (`show_visuals`).
