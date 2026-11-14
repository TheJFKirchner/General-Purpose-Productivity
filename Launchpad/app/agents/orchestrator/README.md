# Orchestrator (role `orchestrator`)

- What: runs an approved plan. Hands steps, one at a time, to a fresh step agent (the Builder, or the folder agent the plan names), receives only a capped result per step, then writes the final summary. Never reads project code or asks the user anything.
- Model: `sonnet` (from the file).
- Tools: none from the file (`tools: []`); Launchpad tools `run_builder` and `write_report`, both end its turn.
- Files:
  - `agent.md`: definition (front-matter name `launchpad-orchestrator`)
  - `run.py`: `Run` (the run's state, the orchestrator loop, step / run events), `orchestrator_tools`, `REPORT_SCHEMA`
  - `report.py`: `render_report` (report.md: summary, steps table, assumptions, autopilot approvals, issues, costs per agent)
- Called by: `app/hub.py` (`Hub.approve` creates `Run(ls)` and starts `run.go()`). Each step goes to `app/agents/builder/builder.py` `run_step`.
