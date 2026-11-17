# Agent drafter (helper `drafter`)

- What: turns a sentence or two about a wanted helper agent into a filled "new agent" form (name, description, purpose, model, tools, instructions). Nothing is saved: the user edits the form, then creating the file goes through `app/agents/folder_agents.py`. A helper, not a crew card and not in the registry; its definition is still editable in the File Explorer.
- Model: `haiku` (from the file).
- Tools: none (`tools: []`); one one-shot call with structured output `DRAFT_SCHEMA`.
- Files:
  - `agent.md`: definition (front-matter name `launchpad-drafter`)
  - `drafter.py`: `draft(hub, folder, text, context="")`, `draft_with_usage(...)` (fields + the call's tokens and cost), `DRAFT_SCHEMA`
- Called by: `app/hub.py` on the page's `agent_draft` message (Crew tab). Define path (undefined roles): `agent_draft {role}` adds the role's samples, skills and the Role Reviewer's case as context (`app/agents/role_reviewer/reviewer.py draft_context`); the output fields are unchanged. `agent_drafted` carries the call's `usage`.
