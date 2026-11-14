# Regular session: Pilot (plain Claude Code chat)

Status: built
Date: 2026-11-13

Adds a fifth agent, Pilot: a plain Claude Code chat in the launch folder with no plan, no orchestrator and none of the builder guards. It covers its permission modes, how its prompts and questions become queue cards, interrupting, streaming, and known Claude Code behaviour seen live.

Later changed by: [2026-11-13-agents-crew-visualizer](2026-11-13-agents-crew-visualizer.md) (the Pilot is now shown as Claude Code, behind a Planner / Claude Code switch)
Later changed by: [2026-11-14-code-organisation](2026-11-14-code-organisation.md) (its agent file is now app/agents/claude_code/agent.md)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Regular session: Pilot (2026-11-13)
- Fifth agent `.claude/agents/launchpad-pilot.md` (display name Pilot): a plain Claude Code chat in the launch folder; no plan, no orchestrator
- Runs exactly as Claude Code does: setup="project" (Claude Code system prompt, all built-in tools, the folder's CLAUDE.md, user + project + local settings incl. the user's own permission rules, skills, hooks); empty agent body and no ask_user, so nothing is layered on top; model sonnet by default (`--pilot-model`)
- Deliberately has NONE of the builder guards: no Launchpad write check, no shell deny list, no gated tools on Claude; permissions are purely Claude Code's (rules, modes, prompts)
- Permission modes default | accept_edits | plan, switchable any time incl. mid-turn (chat_set_mode); starts in default; no bypass mode
- Permission prompts, plan proposals and Claude's own questions (AskUserQuestion) become queue items tied to the chat (chat_id, session_id null), no timer; "always allow" offers this session or the project's local settings (.claude/settings.local.json); for edits the session choice is Claude Code's "allow all edits" (switch to accept_edits)
- Plan mode: edits reach the permission callback (the engine does not hard-block them) and are denied without a card; plan approval picks the next mode (default or accept_edits); rejection keeps plan mode and sends the feedback
- AskUserQuestion answers go back as the tool input (new agentlib `PermissionDecision(input=...)`)
- Interrupt (chat_stop): open cards cleared, the engine interrupted, the turn cancelled if it does not end within 5 s (the next turn resumes the conversation)
- Streaming (chat_delta), activity feed + usage (role pilot, chat_id set, session_id null), activity.log in `.launchpad/<chat-id>/`; several chats and runs can coexist; listed in crew_list with setup + prompt_note
- Fake engine: Claude Code-style prompts are made visible by gating Write/Edit/NotebookEdit/Bash/WebFetch/AskUserQuestion on the fake only
- Known Claude Code behaviour (live 2026-11-13): allow rules in the checked-in `.claude/settings.json` are ignored until the folder is trusted in Claude Code (deny rules and `.claude/settings.local.json` apply regardless); file rules use `Edit(...)` (covers Write); in plan mode Claude Code writes its plan file under the user's `~/.claude/plans/` without asking
