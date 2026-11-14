# Claude Code (role `pilot`)

- What: the regular session. A plain Claude Code chat in a connected folder: no plan, no orchestrator, none of Launchpad's builder guards. Permission prompts, plan proposals and Claude's own questions become queue cards tied to the chat; modes default / accept_edits / plan; interrupt.
- Model: `sonnet` (from the file); `--pilot-model` overrides it.
- Tools: no tools line and an empty body: every Claude Code built-in and Claude Code's own system prompt. Loaded with `setup="project"` (the folder's CLAUDE.md, user + project settings, skills, hooks); permissions are Claude Code's own.
- Files:
  - `agent.md`: definition (front-matter name `launchpad-pilot`)
  - `pilot.py`: `PilotChat`, `pilot_overrides` (load-time settings), permission "always allow" offers
- Called by: `app/hub.py` (`chat_new`, `chat_from_plan` "Send plan to Claude Code"; chat messages, mode changes, stop).
