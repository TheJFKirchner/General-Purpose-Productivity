# CLI (role `pilot`; folder name kept from its old display name, Claude Code)

- What: the regular session. A plain chat in the CLI harness (today Claude Code, through agentlib), in a connected folder: no plan, no orchestrator, none of Launchpad's builder guards. Permission prompts, plan proposals and Claude's own questions become queue cards tied to the chat; modes default / accept_edits / plan; interrupt.
- Model: `sonnet` (from the file); `--pilot-model` overrides it.
- Tools: no tools line and an empty body: every built-in tool of the harness and its own system prompt. Loaded with `setup="project"` (the folder's CLAUDE.md, user + project settings, skills, hooks); permissions are the harness's own.
- Folders and skills: cwd = the primary folder; folders ticked as additional go in as `add_dirs`. Skills are the harness's own discovery; Launchpad's per-agent skill settings do not apply (Crew shows "All (handled by the CLI)").

- Files:
  - `agent.md`: definition (front-matter name `launchpad-pilot`)
  - `pilot.py`: `PilotChat`, `pilot_overrides` (load-time settings), permission "always allow" offers
- Called by: `app/hub.py` (`chat_new`, `chat_from_plan` "Send plan to CLI"; chat messages, mode changes, stop).
