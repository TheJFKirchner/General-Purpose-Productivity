# Usage screen: cost and session monitoring

Status: built
Date: 2026-11-17

Clicking the app-wide cost total in the header opens a full Usage screen (also in the sidebar) for monitoring cost and sessions. A bar chart shows spend by day or by week, split by CLI, by model or by agent, measured as total cost or as input, output, cache read or cache write tokens. Under it, a table lists every session across all connected folders. To make this possible Launchpad starts keeping a per-user log of every agent call, because until now costs were held in memory only and lost when the app closed.

Feature branch: `feature/usage-monitor`, created from `feature/workflows` (request 30). Merge order: requests 27, 29, 30, then this.

## What was built, and where it differs from the plan

- Built as planned: the usage log (`app/usagelog.py`, written from `Meter.add_reply` in `app/meter.py`, saved as `<home>/.launchpad/usage/<YYYY-MM>.jsonl`, one file per month), the `usage_get` / `usage_stop` / `usage_data` messages, and the Usage view (`frontend/src/views/Usage/`, chart helpers in `frontend/src/lib/usageChart.ts`) with the sidebar entry and the clickable header total. ECharts is loaded only when the Usage screen opens.
- Choices the back-end builder made where the plan was open, raised with the user: agents inside workflow runs are their own groups when split by agent ("Workflow: Builder"); "Other" is the smallest groups ranked by cost whatever measure is shown, with at most six named series; each review or agent-drafting call counts as its own session; a session's start time is its first recorded call; a call that used several models is one line with a per-model split; in `--fake` the demo's own calls show as a second CLI, "Fake engine (demo)".
- The page opens split by CLI; the server's own default is agent.
- Checked: fake-engine tests (including that the log's sum for a session, a chat and the whole app equals the totals the app already shows), front-end tests and build, a 38,000-line log read in under a second, and one UI review of the running demo in which bar sums were checked by hand against bucket and period totals, followed by one fix round (two series sharing a colour, the two largest models drawn in two shades of one hue).
- Not checked: the fix-round colours were not looked at again in the running app; running sessions listed first (the demo has no running session with spend); the CSV file save inside the app's own window (its contents were checked); the "nothing recorded yet" state; nothing has been recorded from a real agent yet.
- Known limit: the first "all" view slows as the log grows over years (about 3 s at 200,000 lines); a saved summary per finished month is the remedy.

## Assumptions (shown to the user, uncorrected)

1. Clicking the app-wide cost total in the header opens a full Usage screen, which also has a sidebar entry. The hover tooltip stays.
2. A bar chart over time, by day or by week (weeks start on Monday), with a period choice of the last 7, 30 or 90 days or everything.
3. Bars are split by CLI, by model or by agent (planner, builder, explorer, the user's own agents, CLI chat, reviewer, visualizer, workflow stages). When there are many, the largest few are shown and the rest grouped as "Other".
4. The measure is total cost, input tokens, output tokens, cache read tokens or cache write tokens. Totals for the period sit above the chart, and hovering shows exact figures.
5. Under the chart, a sessions table: start time, folder, kind (plan, CLI chat, workflow run, review), running or finished, cost and tokens, running ones first. Clicking a row narrows the chart to that session, and the narrowing can be cleared.
6. From now on Launchpad writes one line per agent call to a log in `<home>/.launchpad/`: time, session, kind, folder, agent, model, CLI, cost and the four token counts. Earlier spend is not reconstructed. The log is kept indefinitely and never leaves the computer.
7. Costs are the figures each CLI reports. On a subscription these are equivalent costs, not a bill; the screen says so.
8. The chart uses ECharts, added to the app itself (the library the Visualizer already uses in its sealed frames).
9. A "Download CSV" button exports what the chart is showing.
10. The zero-token demo shows a few weeks of made-up history so the screen can be reviewed.
11. It covers the user's own use across all connected folders.

## Decisions from the interview

- **Full screen, not a pop-up (Q1).** A chart with three controls and a sessions table needs room and is something to come back to; the header total is a shortcut to it, not the only way in.
- **Sessions table under the chart (Q2).** The chart shows trends; the table shows the individual sessions behind a tall bar.
- **Start a log now, no reconstruction (Q3).** A reader confirmed there is no history to rebuild: costs live only in in-memory meters, and the only traces on disk are cost figures written as text inside individual session reports, without a time per call.
- **Run folders stay where they are (Q4).** The user asked whether the home `.launchpad` should also hold the per-run folders that agents pass files through. Decision: not in this build. Only the usage log goes in the home folder, and each log line records which folder and run it came from, so the Usage screen can list every session across folders and point to its run folder. Moving run folders was kept as a possible separate request, because it changes how every agent is allowed to read and write its run folder, stops a run's record travelling with its project, and is unrelated to charting spend.

## Facts about today's code that the build rests on

- `agentlib.Reply` reports per call: `cost_usd`, `usage` (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` separately; input is uncached only), `engine`, `model`, `usage_by_model`.
- `Meter.add_reply` (`app/meter.py`) adds these into running totals and drops `engine`, `model` and any per-call row; meters have no time stamp. `hub.meters` is in memory only.
- A CLI chat is role `pilot` with a `chat_id` and no session id; reviewer and drafter calls have no session and count only in the app-wide total; workflow runs are sessions named `wf-<run id>`.
- The header pill (`frontend/src/components/Header.tsx`) shows the app-wide total with a hover tooltip and no click handler.
- The React app has no chart library; `app/vendor/` holds ECharts for the Visualizer's frames only.
- There is no index of past sessions across folders.

## Shared interface (websocket)

| Sent by the page | Reply |
|---|---|
| `usage_get {period, bucket, split, session?}` | `usage_data {buckets, series, totals, sessions}` |

- `period`: last 7, 30 or 90 days, or all. `bucket`: day or week. `split`: cli, model or agent. `session`: optional, narrows to one session.
- Each series carries all five measures per bucket, so switching the measure needs no new request.
- `usage_data` is sent again when new spend is recorded while the screen is open.
- The back-end builder writes the full contract into the `app/server.py` header first (exact field names, how sessions are identified and labelled, how "Other" is formed, what the CSV contains) and the front-end builder builds to that.

Contract as written (full text: "Usage screen" section of the `app/server.py` header, authoritative):

- `usage_get {period?: 7d|30d|90d|all (30d), bucket?: day|week (day), split?: cli|model|agent (agent), session?: id|null}` -> `usage_data`. The server remembers the latest request and pushes `usage_data` (with `pushed: true`) again when new spend is recorded, at most once every 2 s, until `usage_stop {}` (screen closed). Unknown values fall back to their defaults; `request` echoes what was used.
- `usage_data {request, range: {start, end}|null, buckets, series, totals, sessions, sessions_total, measures, skipped_lines, pushed, error?}`. `range` null = nothing recorded yet (all lists empty).
- `bucket {key, label, start, end, partial}`: every day or week of the range, empty ones included; local time; weeks start Monday; day label "17 Nov", week label "Week of 16 Nov" (year added when not the current year); a week cut by the range is `partial`.
- `series {key, label, values: {cost[], input_tokens[], output_tokens[], cache_read_tokens[], cache_write_tokens[]}, totals, members}`: arrays aligned with buckets. Ordered by cost; more than 7 groups -> 6 named + one `{key: "__other__", label: "Other", members: [...]}`. Split cli: harness id / "Claude"; model: readable name ("Sonnet 4.5"); agent: display name, workflow calls as "Workflow: <agent>".
- `totals {cost, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, calls, sessions}` for the request (range and narrowing).
- `session {id, kind: plan|chat|workflow|review|other, kind_label, label, folder: {dir_id, name, path}|null, run_folder, started_at, last_at, running, cost, planner_cost, the four token counts, calls, agents, models, clis}`: every session with a call in the range (not affected by the narrowing), running first then latest; at most 500. Cost includes the planner; `cost - planner_cost` = the app's own session total.
- `measures [{key, label, unit}]`: the five measures in order.
- Errors: a damaged log line is skipped and counted in `skipped_lines`; a log that cannot be read gives empty lists and `error`.
- CSV is built by the page from the last `usage_data`: one row per bucket and series; columns period start, period end, group, cost_usd, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens.

## Tasks

### Task A: back end

- **Goal:** keep the detail of every agent call in the usage log, and answer the page's requests for chart data and the sessions list.
- **Builder:** factory-builder, Opus (touches how every agent's cost is recorded).
- **Owns:** `app/`, `tests/`, Launchpad docs (CLAUDE.md, `app/README.md`, `docs/architecture.md`, `tests/README.md`).
- **Read first:** `app/meter.py`, `app/costs.py`, `app/hub.py` (`emit_totals`), `app/store.py` (`launchpad_home`), `app/workflows/runner.py`, `../agentlib/README.md`.
- **Done when:** every kind of agent call (planner, builder, explorer, folder agents, CLI chat, reviewer, drafter, visualizer, workflow stages) writes a line with its model and CLI; totals from the log match the totals the app already shows for the same session; chart data can be grouped by day or week and split by CLI, model or agent for each measure; the sessions list covers all connected folders with kind, folder, start time and running or finished; a damaged line in the log is skipped, not fatal; concurrent runs cannot corrupt the log; `--fake` shows a few weeks of made-up history in its temp home only; `python -m pytest` passes on the fake engine.
- **Runs with:** Task B, in parallel, after writing the contract first.

### Task B: front end

- **Goal:** the Usage screen: the chart with its three controls, the totals row, the sessions table, the CSV button, the sidebar entry and the click on the header total.
- **Builder:** factory-builder, Sonnet, UI.
- **Owns:** `frontend/`.
- **Read first:** `frontend/README.md`, `frontend/src/components/Header.tsx`, `Sidebar.tsx`, `Tooltip.tsx`, `contract.ts`, the store's totals fields.
- **Done when:** every combination of split, measure and period draws correctly; an empty log shows a plain "nothing recorded yet" message; clicking a session narrows the chart and can be cleared; the chart is readable in a narrow window and with the sidebar open or collapsed; the subscription note is shown; demo data covers the screen; `npx vitest run` passes and `npm run build` succeeds.
- **Runs with:** Task A, in parallel.
