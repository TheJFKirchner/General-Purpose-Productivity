# app: the Python back end

Entry point: `python -m app.launch` (options in the `launch.py` docstring). Overview of the flow: [docs/architecture.md](../docs/architecture.md). Install: `pip install -r app/requirements.txt`.

| File | What it does |
|---|---|
| `launch.py` | entry point: store + launch options, server thread, pywebview window |
| `server.py` | FastAPI: page, assets, vendor files, websocket; localhost + access code + origin check; header = websocket contract |
| `hub.py` | all sessions and chats, event broadcast, reconnect snapshot, UI message dispatch, approve / stop / new session, the planner picker (`planner_choose`, `planner_choice`), the CLI chat's picker (`cli_choose`, `cli_choice`; unstarted chats reloaded, `chat_model`) |
| `plan.py` | plan.md render, parse, validate, status updates, targeted edits |
| `sessionfiles.py` | the files in `<folder>/.launchpad/<session-id>/`, incl. one `questions/NNN-<slug>.md` per answered question (`add_question`; numbering from disk) |
| `incoming.py` | question / permission / plan queue with server-side timers; the per-session Auto answers switch answers questions that have a recommendation at once (`set_auto_answers` in `hub.py`) |
| `meter.py` | per-agent tokens, cost and tool-call counts |
| `activity.py` | one-line summaries for the live activity feed and `activity.log` |
| `settings.py` | active settings for this launch |
| `store.py` | per-user store: connected folders (+ which are ticked as additional), settings (incl. the planner picker's `planner_harness`, `planner_start_model`, `planner_auto_promote`, and the CLI chat picker's `pilot_harness`, `pilot_model`), agent use counts, per-agent skill settings (`<home>/.launchpad/settings.json`) |
| `skills.py` | skill discovery in a session's folders (`.claude/skills`, else `.agents/skills`; primary wins a name clash), per-agent allowlists, the planner's skill list |

| `files.py` | File Explorer back end: roots, safe paths, conflict-safe `.md` saves, backups |
| `gitrepos.py` | Repos panel back end (Files tab): finds git repos in the connected folders (folder itself + two levels down), reads status (branch, ahead / behind, changed files with +/- counts), commit / push / fetch through `git` argument-list subprocesses (no shell, timeouts, no prompts, no force push / pull / branch switch); the hub runs it off-thread (`git_scan`, `git_refresh`, `git_fetch`, `git_commit`, `git_push`) |
| `demo.py` | fake-engine scripts for `--fake` |
| `requirements.txt` | Python dependencies |

Other folders:
- [agents/](agents/README.md): the built-in agents (one folder each) plus the shared `crew.py` and `folder_agents.py`; the harness-and-model table is `agents/planner/choices.py` (the planner's picker), shared by `agents/claude_code/choices.py` (the CLI chat's picker)
- `vendor/`: bundled chart libraries (ECharts, Chart.js, D3) served at `/vendor/lib/<key>.js`; versions and hashes in [vendor/README.md](vendor/README.md)
