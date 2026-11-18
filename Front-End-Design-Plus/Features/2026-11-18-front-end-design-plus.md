# Front-end design plus

Status: built
Date: 2026-11-18

A user-invoked skill that opens a small local "whiteboard" page for designing charts and tables. The skill writes the table behind the current visual to a temp file and launches the page. In the page the user chats with an agent that sees only column names, types and a few sample rows, and asks it for several ID'd visuals, then iterations of the ones they like. The page draws every visual on the full real data. Saved visuals are written as small recipe files to a temp folder, and the main conversation merges them into the deliverable.

## Assumptions

1. The pop-up is a local browser page. The agent runs through `agentlib`, has no file or shell access, and sees only its prompt, column names and types, about three sample rows and an optional style note.
2. The skill writes the table behind the current graph to a temp file. The page loads the full data and runs the agent's recipes on it.
3. One library per session. The skill names it, or when the user is tweaking an existing visual it is that visual's library. If there is none yet, ECharts.
4. Supported: ECharts (default), Plotly, Chart.js, Vega-Lite, D3, plain HTML/SVG. Anything else (for example matplotlib) means the skill does not launch and says why.
5. When tweaking an existing visual, its current code is passed in and appears as card G1.
6. Plain HTML tables are available in every session, whatever the library.
7. Only the reference file for the session's library goes into the agent's prompt.
8. Cards are sealed mini-pages with IDs G1, G2, ...; an iteration gets a new ID and shows its parent. Cards can be deleted, and one or several saved. Done closes the page and ends the agent.
9. A recipe that fails shows its error on the card and goes back to the agent once to fix.
10. Each saved visual is one small file (ID, title, library, recipe; no data) in a system temp folder. The skill reports the path to the main conversation for merging.
11. Library files are local copies in the skill folder, so the page works offline.
12. The skill lives in `Front-End-Design-Plus/` in this repo, is linked into the user skills folder, and is user-invoked only (`disable-model-invocation: true`).
13. The board is kept in the temp folder as the user works, so relaunching on the same output folder resumes it.

## Decisions

- **Recipes, not data, go to the agent.** The agent writes a function that takes the rows and draws; the page runs it on the real data. This gives real graphs with a near-empty agent context. Rejected: passing the data, or a summary only (the user would not see the real graph).
- **Library-neutral cards.** The first design fixed the recipe as an ECharts description, which tied the page, the prompt and the saved file to ECharts. A recipe is now the body of `render(el, rows, lib)` drawing into a box, inside a sealed mini-page that loads the session's library. Any browser library fits; Python-only libraries do not, because the server would have to run agent-written Python.
- **One library per session.** Chosen to keep it simple to test and to keep the prompt light. Rejected: choosing a library per card.
- **No translation on merge.** The session uses the deliverable's own library, so the saved recipe merges directly. An unsupported library stops the launch instead of designing in one library and translating.
- **Recipe-only output.** Rejected: a standalone HTML file with the data embedded, which is larger and harder to merge.
- **Tables included in version one**, since plain HTML cards come with the design.
- **Local library copies**, because a work network may block outside sites.
- **Testing**: fake-engine tests, then sample data with one subagent running the skill end to end and a separate reviewer.

## Shared interface

- Launch: `python -m whiteboard --data <file> --library <name> --out <folder> [--style <text>] [--existing <file>]`. Exits with a clear message and a non-zero code on an unsupported library. `<name>` is one of `echarts`, `plotly`, `chartjs`, `vegalite`, `d3`, `html`.
- Recipe: `{id, parent, title, library, kind, code}`. `kind` is `chart` or `table`. `code` is the body of `render(el, rows, lib)`: `el` is the empty box, `rows` is an array of row objects, `lib` is the session library's global (absent for `html`). A table recipe always has `library: "html"`.
- Routes (server to page, JSON):
  - `GET /api/session`: library, columns, style note, existing cards.
  - `GET /api/data`: the full rows.
  - `POST /api/chat` `{message}`: streamed reply as server-sent events: `text` (delta), `card` (a recipe), `done`, `error`.
  - `POST /api/card-error` `{id, error}`: a card failed to render.
  - `POST /api/save` `{id}`, `POST /api/delete` `{id}`, `POST /api/done`.
- Output: `<out>/<id>.json` per saved visual (the recipe), `<out>/result.json` listing saved IDs, titles and the library, and `<out>/board.json` holding every card for resume.

## What was built differently from the plan

- Extra launch flags: `--fake` (scripted agent, no tokens), `--no-open`, `--port`. The launcher's last output line is `RESULT: <path to result.json>`.
- Extra routes: `POST /api/heartbeat` (the page posts every 15 seconds; the server stops itself after 90 seconds of silence, with `done: false`), and `POST /api/unsave {id}`.
- `/api/session` also returns `chat`, the visible conversation, so a reload or resume shows it. `/api/card-error` replies with JSON `{ok, fixed, card, cards, text}`.
- Sealed cards make no network request: the page fetches each library file once and passes its text into the card. A library that fails to load is shown as a page problem and never sent to the agent.
- Deleting a saved card also unsaves it. Relaunching an output folder with a different library is refused.
- The agent's prompt also includes the row count.

## Known issues after the fix round

Fixed in a follow-up on the same day: scrollbars inside chart cards; a correct recipe once being reported as failed (only an exception thrown by the recipe itself, or from the promise it returns, now counts, and a recipe never runs in a zero-size frame); and a new board from `--existing` saying "Resumed".

- A recipe error that happens later and outside the returned promise (for example in a timer) is no longer shown on the card or reported.
- Not yet tried: the chartjs, vegalite, d3 and plotly libraries with the real agent (only with hand-written and starter recipes).

## Tasks

### 1. Server and agent
- Goal: the launcher, the local server, and the `agentlib` chat session whose only tool adds a card.
- Builder: factory-builder, Opus (agent design).
- Owns: `Front-End-Design-Plus/whiteboard/*.py`, `Front-End-Design-Plus/tests/`.
- Reads: `agentlib/README.md`, examples 02, 03, 04, 09, 11; `Smart-HTML-Editor/editor/server.py` for the pop-up pattern.
- Done: fake-engine tests pass for a multi-card request, iteration by ID, save, resume, and refusal of an unsupported library; no direct SDK import.
- Runs with: tasks 2 and 3.

### 2. The page
- Goal: chat box, card grid with sealed cards, IDs, save, delete, Done; local copies of the five libraries.
- Builder: factory-builder, Sonnet (UI).
- Owns: `Front-End-Design-Plus/whiteboard/ui/`, `Front-End-Design-Plus/whiteboard/vendor/`.
- Done: a hand-written recipe renders on real data in each of the six modes; a broken recipe shows its error on the card and reports it; conservative blue look.
- Runs with: tasks 1 and 3.

### 3. Skill and reference files
- Goal: a short `SKILL.md`, one reference with a starter recipe per library, a merge reference, sample data, README rows, and the link into the user skills folder.
- Builder: factory-builder, Opus (agent design).
- Owns: `Front-End-Design-Plus/SKILL.md`, `references/`, `sample/`, `README.md`, and the root `README.md` skill table.
- Done: each starter recipe is valid against the shared interface; `SKILL.md` is lists and tables, under a page.
- Runs with: tasks 1 and 2.
