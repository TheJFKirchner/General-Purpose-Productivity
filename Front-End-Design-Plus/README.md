# Front-end design plus

A Claude Code skill for designing charts and tables on real data without putting the data in front of an AI model.

You invoke it while working on a deliverable (a dashboard, a report page, an app screen). It writes the table behind the visual to a temp file and opens a local "whiteboard" page in your browser. In the page you chat with a design agent: ask for several visuals, iterate on the ones you like by ID ("G3 but stacked", "G2 as a table"), save some, and press Done. Claude Code then merges the saved visuals into the deliverable.

- **The agent never sees the data.** It gets column names, simple types and about three sample rows. It writes a small recipe (a JavaScript function that draws), and the page runs that recipe on the full table.
- **Real graphs.** Every card is drawn on all the rows, in the deliverable's own charting library, so what you save is what you get.
- **Small output.** Each saved visual is one short JSON file with its ID, title, library and recipe. No data.
- **Offline.** The chart libraries are local copies in `whiteboard/vendor/`.

In the page:
- **Current visual pinned at the top.** When you are changing a visual that already exists, the skill always passes it in, redrawn as it looks today, as "Current visual" (G1).
- **A tidy board.** After each round, earlier cards fold away behind "Show earlier cards"; saved cards stay visible.
- **Cost in view.** A bar at the bottom shows the model, the tokens used and an estimated cost.

## Install

1. Python 3.10 or later.
2. Install `agentlib` from this repo and do its one-time sign-in setup: `pip install -e agentlib` from the repo folder, then follow [agentlib/setup/claude-setup.md](../agentlib/setup/claude-setup.md) and run `python -m agentlib.check`.
3. Link the skill into your user skills folder (Windows, from a Command Prompt; replace the second path with where this repo is cloned):

   ```
   mklink /J "%USERPROFILE%\.claude\skills\front-end-design-plus" "<repo folder>\Front-End-Design-Plus"
   ```

   On Mac or Linux: `ln -s "<repo folder>/Front-End-Design-Plus" ~/.claude/skills/front-end-design-plus`.

The skill is user-invoked only: type `/front-end-design-plus` in Claude Code. It does not start by itself.

## Run

- **Through Claude Code (normal use):** invoke the skill while working on a visual. [SKILL.md](SKILL.md) holds the steps Claude Code follows.
- **By hand, on the sample data (from this folder):**

  ```
  python -m whiteboard --data sample/orders.csv --library echarts --out <a new, empty temp folder>
  ```

  Other flags: `--style "<note>"` (colours, font, light or dark), `--existing <file>` (the visual as it is today, as a `render` body or a recipe JSON; it is pinned as "Current visual", G1; the skill always passes it when the visual exists), `--no-open` (do not open a browser), `--port N`, and `--fake` (or `WHITEBOARD_FAKE=1`) for the scripted fake engine: no sign-in and no tokens. `python -m whiteboard --help` lists every flag.
- **Finish:** press Done. The launcher exits and its last line is `RESULT: <path to result.json>`. If the tab is closed without Done, it stops by itself after about 90 seconds and `result.json` has `done: false`, still listing what was saved.
- **No resuming:** every launch is a fresh board, and the output folder must be new or empty (a folder that already holds files is refused). To carry on from a visual saved last time, pass its `<id>.json` as `--existing`; it opens as the "Current visual".

The output folder ends up with `result.json` (the saved IDs) and one `<id>.json` per saved visual. These are the only record of a session; unsaved cards and the chat are not kept.

## The six libraries

One library per session: the existing visual's library when tweaking one, otherwise the deliverable's, otherwise ECharts. Plain HTML tables are available in every session.

| Library | `--library` | Notes for the agent |
|---|---|---|
| ECharts (default) | `echarts` | [references/echarts.md](references/echarts.md) |
| Plotly (JavaScript) | `plotly` | [references/plotly.md](references/plotly.md) |
| Chart.js | `chartjs` | [references/chartjs.md](references/chartjs.md) |
| Vega-Lite | `vegalite` | [references/vegalite.md](references/vegalite.md) |
| D3 | `d3` | [references/d3.md](references/d3.md) |
| Plain HTML and SVG, tables | `html` | [references/html.md](references/html.md) |

Python-only libraries (matplotlib, seaborn and so on) are not supported: the page would have to run agent-written Python. The skill says so and does not launch.

## What is in this folder

| Path | What it is |
|---|---|
| [SKILL.md](SKILL.md) | The steps Claude Code follows when you invoke the skill. |
| [references/](references) | `launch.md` and `merge.md` for Claude Code; one notes file per library, which goes into the design agent's prompt (only the session's library, plus `html.md`). Each has the recipe contract, conventions (including room for the title, and tables that fit a 520 px card), a blue-led default palette and a starter recipe. |
| [sample/](sample) | `orders.csv`, an invented dataset of 360 orders (date, region, product line, channel, units, price, discount, revenue, cost, satisfaction, delivery days), and `recipes/<library>.json`, the starter recipe for each library as a saved-recipe file, for testing. |
| `whiteboard/` | The launcher, local server and agent (`*.py`), the page (`ui/`) and the local library copies (`vendor/`). |
| `tests/` | Fake-engine tests. |
| [Features/](Features) | The requests and agreed design for this skill. |

## A recipe

`{id, parent, title, library, kind, code}`. `kind` is `chart` or `table` (a table always has `library: "html"`). `code` is the body of `render(el, rows, lib)`: `el` is an empty sized box, `rows` the full table as row objects, `lib` the library's global (`echarts`, `Plotly`, `Chart`, `vegaEmbed`, `d3`; absent for `html`). How to merge one into a deliverable is in [references/merge.md](references/merge.md).

## Adding a library

It must draw in the browser from JavaScript.

1. Put a local copy of its minified file(s) in `whiteboard/vendor/`.
2. Register it with the page (which files to load and which global becomes `lib`) in `whiteboard/ui/`, and add its name to the launcher's list of supported libraries in `whiteboard/`.
3. Write `references/<name>.md` in the style of the others: contract, conventions (including how to reserve room for the title), palette, one starter recipe written against `sample/orders.csv`. Keep it to about 40 to 70 lines; it goes into the agent's prompt.
4. Add `sample/recipes/<name>.json` with the same starter code, and a row to the tables in this README, [SKILL.md](SKILL.md) and [references/launch.md](references/launch.md).

## Tests

From this folder: `python -m pytest tests -q`. They run on the fake engine, so they need no sign-in and spend no tokens.
