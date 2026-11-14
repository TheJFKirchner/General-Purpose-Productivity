# Connected folders, settings store, File Explorer and hand-editing

Status: built
Date: 2026-11-13

Sessions now run in one of several connected folders, and launch options became per-user settings kept in a store under the home folder. A File Explorer browses those folders and allows safe hand-editing of markdown files, with validation and backups.

Later changed by: [2026-11-13-agents-crew-visualizer](2026-11-13-agents-crew-visualizer.md) (the separate Free Flight tab became a Planner / Claude Code switch)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Connected folders, settings store, File Explorer and hand-editing (2026-11-13, decided with the user)
- Per-user store `<home>/.launchpad/settings.json` (env LAUNCHPAD_HOME moves the folder; outside every project and out of git): connected folders + the settings that were launch options
- Connected folders: the File Explorer shows them all; each new planning session or Free Flight chat picks one (default = the last used, saved). A session's agents, write guard, permission rules and `.launchpad/<id>/` folder live in its own folder; sessions in different folders run at once. `--cwd` adds its folder and makes it this launch's default. Add by typed path, or the native picker in the window; removing never deletes anything and is refused while a session is busy there; the last folder cannot be removed
- Settings from the page: question_timeout_s, permission_timeout_s, visual_model apply now; autopilot_default, planner_start_model, planner_top_model, promotion_window_turns, promotion_criteria_path, pilot_model apply to new sessions. A launch option overrides for that launch (flagged) until the setting is changed from the page
- File browsing: roots = connected folders + "app" (Launchpad's agent files and the promotion criteria only); every path resolved (symlinks, "..") and kept inside its root; .launchpad session folders included; binary files and files over 1 MB are listed but never sent; behind the existing local-only + access code + origin checks
- Hand-editing: .md only; conflict-safe (the page sends the version it opened; changed on disk -> conflict with the current content); agent files (.claude/agents/*.md) and plan files are validated, a broken one is refused with the reason; every save keeps the previous version as a backup in `<home>/.launchpad/backups/<root>/<path>/<timestamp>.md` with list and restore (restore is itself a backed-up save)
- Agent files and the criteria apply to NEW sessions (file_content / file_saved say so); crew_list is re-sent after a save of an app file
- Fake demo: its own store in the temp folder and two scratch folders ("Demo shop", "Demo clinic")
