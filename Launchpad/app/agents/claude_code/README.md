# CLI (role `pilot`; folder name kept from its old display name, Claude Code)

- What: the regular session. A plain chat in the CLI harness (today Claude Code, through agentlib), in a connected folder: no plan, no orchestrator, none of Launchpad's builder guards. Permission prompts, plan proposals and Claude's own questions become queue cards tied to the chat; modes default / accept_edits / plan; interrupt.
- CLI and model: chosen in the picker under the chat box (CLI dropdown, then that CLI's models; same table as the planner's, `app/agents/planner/choices.py`). Per-user settings `pilot_harness` (default: the launch engine's CLI) and `pilot_model` (default `sonnet`, from the file); `--pilot-model` / `--pilot-harness` override them for one launch; `--fake` forces the fake engine. Fixed at the chat's first message: a chat nobody has written to is reloaded at once with a new choice, a chat in progress keeps its own and the choice is for the next new chat. Independent of the planner's choice.
- Tools: no tools line and an empty body: every built-in tool of the harness and its own system prompt. Loaded with `setup="project"` (the folder's CLAUDE.md, user + project settings, skills, hooks); permissions are the harness's own.
- Folders and skills: cwd = the primary folder; folders ticked as additional go in as `add_dirs`. Skills are the harness's own discovery; Launchpad's per-agent skill settings do not apply (Crew shows "All (handled by the CLI)").

- Files:
  - `agent.md`: definition (front-matter name `launchpad-pilot`)
  - `pilot.py`: `PilotChat` (`configure()` loads the agent on the chosen CLI's engine and model, `started`, `model_event()` = `chat_model`), `pilot_overrides` (load-time settings), permission "always allow" offers
  - `choices.py`: the CLI chat's choices (`cli_harness`, `cli_model`, `cli_engine`, options, the `cli_choice` event)
- Called by: `app/hub.py` (`chat_new`, `chat_from_plan` "Send plan to CLI", `cli_choose`; chat messages, mode changes, stop).
