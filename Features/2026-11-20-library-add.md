# Library-only adding and simpler skills

Status: built
Date: 2026-11-20

The analysis, presentation and dashboard skills are rewritten around one idea: copy an item from the design library into a section or slide file, point it at the data, then edit that file. The fixed bar, line and table lists in the add commands go away, and each skill shrinks to about 60 short lines covering four plain actions (make a new one, add from the library, change it, make your own) plus page-level changes (theme, spacing, position). The aim is fewer tokens per chart (a library chart file is about 25 KB, of which about 4 KB is the item itself) and skills a person can read.

## Why

- Measured on a sample five-chart, ten-bullet report: the page is about 23 KB, of which 34% is CSS, 29% chart script, 16% chart data and options, 11% tags and 9% visible words. The report builder already writes all of that; the model writes under 1,000 tokens.
- The cost was in the library: every chart file repeats an identical 17.7 KB engine script, and the index is 31 KB. There was no route from a library chart into a report other than hand-copying.
- The add commands only knew a few simple chart types, so they were rarely the chart wanted.
- Every added chart gets edited afterwards, so the design favours a small editable copy over a live link.

## Assumptions

1. Order of work: library, then analysis, then decks and dashboards, in this one request.
2. Each chart, table and hero card has one header line saying what data it needs; the index shows it; the index check fails without it.
3. One library script returns only an item's own block and its data note. All three skills use it.
4. Adding copies the item into a section or slide file. It is never a live link back to the library.
5. Each shell (report page, dashboard starter, deck) carries colour-token, theme and tooltip handling once, so a copied item draws unchanged.
6. The fixed bar, line, table and kpi lists are removed from the add commands.
7. Figures in report text stay as placeholders pulled from the data, so a data change needs no text edit.
8. Decks can take real data into a library slide (previously refused).
9. Existing report, dashboard and deck folders keep working.
10. Saved library items carry the data note and a short shaping recipe instead of "recreate" commands (this replaces that part of request 3).
11. "60 lines" also means short lines: at most about 4 KB per SKILL.md.
12. The `Toolkit Update` copies are refreshed at the end.
13. Each section or slide is one file holding the copied item, its data wiring and its words. Editing is changing that file, then build and look at the screenshot.
14. "Make your own" starts from a blank template created by one command.
15. A script stays in a skill only if making, editing or building calls it. The fake-data test helper is removed from the skill.
16. The build's error lines and the screenshot stay, one line each.
17. The add command reads the same in all three skills: an item id plus which columns fill its slots.

## Decisions

- **Library-only adding.** Chosen over keeping the simple built-in chart types beside the library. Six plain items (bar, line, stacked bar, scatter, table, figure tiles) return to the library so the basics are covered.
- **Copy, not link.** A report can change its chart without affecting the library or other reports. Cost accepted: improving a library item does not update old reports.
- **One dashboard skill.** `dashboard-new` and `dashboard-work` merge into `dashboard`, so there are three skills of the same shape.
- **What the skills hold.** Four actions and page-level changes, in plain words. No explanations of script internals. Presentation full mode (interviews, hard-questions reviewer, builder subagent) and the report cold read are dropped. Anything that is not a core action (exports, hosting, generated commentary, reruns) is left as it is and reached by one pointer line; it is not rewritten now.
- **Slides take chart ids by swap.** Library slides keep their sample chart but mark the spot it sits in; adding a slide with a chart id replaces what is in that spot. Rebuilding every slide to reference a chart id was rejected as too much rework. A chart, table or hero card id can also be added to a deck directly and lands in a plain chart-and-commentary slide.
- **Tighter library rules.** (1) Every chart, table and hero card states the data it needs in fixed wording the add command can read. (2) A chart's block is only its options, key and basis line. (3) A slide marks its chart spot and text spots. (4) An item that needs data reshaped first carries a short recipe. (5) The index check fails when any of these is missing, and the librarian fills them in when saving.
- **No picker subagent for now.** The index is split by type, so reading one section costs about the same. Revisit if the library grows a lot.
- **Pause after analysis.** Agreed in the interview; at approval the user asked for the work to continue while away, so agent-run tests and one fix round stand in for the pause before decks and dashboards are built.

## Tests

Run for each of the three skills on made-up data, by an agent that has only the skill to go on, with screenshots:

1. Make a new one.
2. Add a library item to it.
3. Add an item, then change it (for example a third line on a line chart).
4. Make a custom item from the blank template.
5. Change things outside the items: switch theme, change spacing, move a chart.

One fix round on what the tests report.

## What was built

- **Library.** Every chart, table and hero card has a `data:` line and marked slots; every slide has marked spots; six plain items were added (CT-34 bars, CT-35 line, CT-36 stacked bars, CT-37 scatter, TB-09 table, HC-15 figure tiles). `item.js` returns one item's block (largest chart about 5.9 KB), fills slots, swaps a chart into a slide and prints a theme. `host-runtime.js` and `host.css` are what a page embeds once. `index/` holds one small index per type. The index check enforces the five rules.
- **Analysis.** `run.py add-section NAME --use ID --source SRC --slot name=col`, with `--period`, `--top`, `--by`, `--compare COL=A,B` for common shapes; `--own chart|html` for a blank section; `run.py theme TH-xx`. The fill was ported to Python so a build needs only Python; Node is needed to add an item or change theme. `SKILL.md` is 60 lines.
- **Presentation.** A deck is now a folder with one file per slide. `scripts/deck.js` does `new`, `add`, `refill`, `own`, `theme`, `place`, `build`, `check`. Refill keeps hand edits, can switch the data file, and stops when a typed figure no longer matches the data. Full mode and seven old scripts were deleted. `SKILL.md` is 56 lines.
- **Dashboard.** `dashboard-new` and `dashboard-work` are merged into `dashboard`. `npm run new-section -- NAME --use ID --page TAB --tables T --slot name=col` with the same shape flags; `--own`; `npm run theme -- TH-xx`. Sections refill on every data or filter change and keep hand edits. `SKILL.md` is 60 lines.
- **Tests.** Each skill was built, then tested cold by an agent with only the skill to go on (the five tests above plus a data change), then given one fix round. All five tasks completed for each skill without the tester reading script source.

### Differences from the plan

- The pause after analysis was replaced by the agent-run tests and fix round, at the user's request.
- To fit the size cap, CT-13 went from 4 panels to 3 and CT-32 from 6 to 4; CT-28's legend became a key under the chart. Table CSV buttons export text as shown.
- Decks changed format (one file per slide). Decks made with the old scripts still open and can be edited by hand, themed, checked and screenshotted, but `add`, `own`, `place`, `refill` and `build` do not work on them.
- Dashboards made from the old starter keep running on their own tools; they get the new commands only if files are copied in (listed in the dashboard skill's `references/sections.md`).

### Left open

- About 20 charts still style individual bars by sample position; a highlight can land on the wrong row after the data reorders (CT-06 and CT-29 are fixed).
- Inner repeated details of some hero cards and tables (strip segments, rank dots, heat shading) are edited by hand after adding.
- Sample captions copied from library items stay until reworded; the checks flag them.
- Deck refill does not check figures worked out by hand (ratios, differences).
- A generated compare section does not name which date column it compares in its title.
- The fill logic exists three times (Python in analysis, Python in the dashboard starter, JavaScript in the library). A shared module was suggested and not built.
- The second-round fixes were verified by the builders and by the orchestrator looking at screenshots, not by a second cold test.

## Tasks

### 1. Library
- Goal: data note on every chart, table and hero card; chart and text spots marked on slides; six plain items; one script returning a single item's block and data note; index split by type and showing data needs.
- Builder: factory-builder, Opus.
- Owns: `Toolkit Update/design-library/`, `.claude/agents/design-librarian.md`.
- Done: the index check fails on a missing data note or spot marker and passes on the full library; the script returns under 6 KB for any chart id; the index page still previews every item; `AUTHORING.md` states the data-note wording and the script's output, which tasks 2 to 4 build to.
- Runs: first.

### 2. Analysis
- Goal: `add-section` takes any library chart, table or hero card id and writes a working section file; a blank-template command for custom sections; theme by library id; the skill rewritten.
- Builder: factory-builder, Opus.
- Owns: `.claude/skills/analysis/`.
- Done: the five tests pass on made-up data; changing the data and rebuilding needs no edits; `SKILL.md` at most 60 lines and 4 KB; an older report folder still builds.
- Runs: after 1.

### 3. Presentation
- Goal: the same add path in the deck scripts; real data into library slides; chart id swap; blank slide template; the skill rewritten without full mode.
- Builder: factory-builder, Opus.
- Owns: `.claude/skills/presentation/`.
- Done: the five tests pass; `SKILL.md` at most 60 lines and 4 KB.
- Runs: after 2 is tested, in parallel with 4.

### 4. Dashboard
- Goal: the same add path in the dashboard starter; `dashboard-new` and `dashboard-work` merged into `dashboard`; blank section template; the skill rewritten.
- Builder: factory-builder, Opus.
- Owns: `.claude/skills/dashboard*/`.
- Done: the five tests pass with filters working; `SKILL.md` at most 60 lines and 4 KB.
- Runs: in parallel with 3.

### 5. Tidy up
- Goal: the toolbox skill, repo README, CLAUDE.md and install pages name the skills correctly; `Toolkit Update` refreshed.
- Builder: factory-builder, Sonnet.
- Runs: last.
