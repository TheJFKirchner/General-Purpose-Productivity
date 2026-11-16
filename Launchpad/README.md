# Launchpad

A local desktop app for planning and running work with AI agents. You chat with a planner, approve the plan it drafts, and an orchestrator hands each step to a builder agent and writes a report. It runs on your own computer only.

It is built on `agentlib`, the shared agent library in this repo, so keep the `Launchpad` and `agentlib` folders side by side.

## Set up

1. Do the one-time sign-in setup in [agentlib/setup/claude-setup.md](../agentlib/setup/claude-setup.md).
2. From this folder, install what the app needs: `pip install -r app/requirements.txt`

## Run

- Windows: double-click `Launchpad.bat`.
- Mac: double-click `Launchpad.command`.
- Zero-token demo, no sign-in needed: `python -m app.launch --fake`

Running the app needs Python only. The built front end is included in `frontend/dist/`.

## Test

`python -m pytest` runs the test suite on the fake engine and uses no tokens.

## Where things are

| Item | What it is |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Rules, current state and a file map for anyone (or any AI) changing the app |
| [docs/](docs/README.md) | [architecture.md](docs/architecture.md) (start here), library notes, background |
| [Features/](Features/README.md) | One file per conversation or feature request (decisions and specs), listed in its README |
| [app/](app/README.md) | The Python app: server, hub, plan and session files |
| [app/agents/](app/agents/README.md) | The built-in agents, one folder each (definition, code, README) |
| [frontend/](frontend/README.md) | The React front end; run `npm run build` there after changing it |
| [tests/](tests/README.md) | The fake-engine test suite and the live (token-spending) scripts |
