# app: the Python back end

Entry point: `python -m app.launch` (options in the `launch.py` docstring). Overview of the flow: [docs/architecture.md](../docs/architecture.md). Install: `pip install -r app/requirements.txt`.

| File | What it does |
|---|---|
| `launch.py` | entry point: store + launch options, server thread, pywebview window |
| `server.py` | FastAPI: page, assets, vendor files, websocket; localhost + access code + origin check; header = websocket contract |
| `hub.py` | all sessions and chats, event broadcast, reconnect snapshot, UI message dispatch, approve / stop / new session |
| `plan.py` | plan.md render, parse, validate, status updates, targeted edits |
| `sessionfiles.py` | the files in `<folder>/.launchpad/<session-id>/` |
| `incoming.py` | question / permission / plan queue with server-side timers |
| `meter.py` | per-agent tokens, cost and tool-call counts |
| `activity.py` | one-line summaries for the live activity feed and `activity.log` |
| `settings.py` | active settings for this launch |
| `store.py` | per-user store: connected folders, settings, agent use counts (`<home>/.launchpad/settings.json`) |
| `files.py` | File Explorer back end: roots, safe paths, conflict-safe `.md` saves, backups |
| `demo.py` | fake-engine scripts for `--fake` |
| `requirements.txt` | Python dependencies |

Other folders:
- [agents/](agents/README.md): the built-in agents (one folder each) plus the shared `crew.py` and `folder_agents.py`
- `vendor/`: bundled chart libraries (ECharts, Chart.js, D3) served at `/vendor/lib/<key>.js`; versions and hashes in [vendor/README.md](vendor/README.md)
