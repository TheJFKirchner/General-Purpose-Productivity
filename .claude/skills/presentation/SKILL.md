---
name: presentation
description: Build a slide deck (reveal.js HTML with ECharts charts) from work that already exists - findings, an analysis, a dashboard, a project plan. Two modes. Quick, the default for decks under about eight slides - one confirmed brief, one confirmed slide list, built in the conversation. Full, for a real readout or when asked - interviews, a hard-questions reviewer and a builder subagent. Use for "make a deck / slides / presentation / readout on ...", or to change an existing deck. Not for .pptx, and not for a written report (that is the analysis skill).
---

# Presentation

Existing work in, one HTML deck out. Slide text comes from the findings and results; this skill does no new analysis.

## Start

1. Read the project's `CLAUDE.md` map: the project plan, findings, existing decks. Follow links one level; do not survey the project.
2. Find the design library: the map's `Design library:` line if there is one, else `design-library/` three folders up from this skill (`<skill>/../../../design-library`), unless the user says no. Neither: use the basic layouts in `references/slides.md`.
3. Ask one question: quick or full, with your pick (quick under about eight slides; full for a decision meeting or a senior room). The user's answer wins. In quick mode, put the drafted brief in the same message.

## Where the deck goes

- In the folder the map's deck rows use; none yet, `deck/<yyyy-mm-short-name>/`.
- Add one map row per deck: `` | `deck/<name>/` | Deck: <title>, for <audience>, <ask> | ``.
- No map, or no map table: ask where, in one line. Then write `## Map`, the header `` | Folder or file | Holds | ``, the separator `` | --- | --- | ``, then the row.
- The folder holds `presentation.html` and `styles.css`; full mode adds `plan.md`. Sources are pointed to, never copied.

## Quick mode

| # | Step | Gate | Read |
| --- | --- | --- | --- |
| 1 | Draft the brief: audience, what we want from them, minutes, the answer in one sentence, basis (date basis, comparison period), sources | **User confirms** | |
| 2 | Slide list: per slide its headline (the point as a sentence), layout or library code, visual, source, and the first question the room will ask with where the deck answers it | **User confirms** | `references/slides.md`; the library `index.md` |
| 3 | `patterns.js` fetches every library pattern in one call. Scaffold, then one Edit fills the BRIEF and every slide. Run the chart check | | `references/slides.md`; `references/charts.md` for a chart with no library pattern |
| 4 | Screenshot, read the contact sheet, one fix pass, one re-shot, stop (about 22 calls for seven slides). Give the user the path | | |

- No subagents and no `plan.md`. Shape: title (the answer as headline), one slide per finding, a close.
- Bullets come from findings and results: 2 or 3 per visual, each pointing at something on it.
- A decision meeting: the close names owner, timing and cost, or shows "to agree today" for each one missing.
- A source contradicts a finding: raise it with the user before building. Never put it on a slide as "unexplained".
- The user is away: state the brief and slide list in your reply and carry on.

## Full mode

Open `references/full-mode.md` and follow it: facts, interview 1, storyboard, hard-questions reviewer, interview 2, builder subagent, walk-through. Uses the grilling skill.

## Existing deck

- `grep -n SLIDES:END presentation.html`, then Read with that line as the limit. The BRIEF says who it is for and why.
- A change: no mode question and no gates, unless it adds more than two slides. New slide ids: any unused `s<nn>-<name>`; ids are names, not positions.
- A new slide takes its neighbour's section; never reopen a section. Do not repeat the close; a changed close follows the decision rule above.
- Update the BRIEF slide list and the map row, then re-shoot every slide.

## Look

- The base theme carries the toolbox Look tokens (`--blue`, `--navy`, `--ink` ...) at the top of `styles.css`. Light, readout level, sharp: blue highlight, grey context.
- Colours only through the tokens. No company name, no logo. Light hover only; nothing moves; no controls on a slide.

## Rules

- One point per slide, in its headline. The visual shows the headline's own number, one fixed cut.
- Every number traces to a source named in the slide's footnote (and in `plan.md` in full mode).
- The user's picks (a visual, a cut, wording) stand. Raise a concern once, only when it cannot work as asked.
- Changing a chart's period or series: update its heading, its footnote period and any bullet citing what was removed, in the same pass.
- A new deck in one Edit; later changes one slide per Edit, by id. Never rewrite `presentation.html` whole; never read below `<!-- SLIDES:END -->`.

## Scripts

All in `scripts/`, run with Node. Mechanical only.

| Script | Does |
| --- | --- |
| `create-presentation.js --title "<t>" -o <deck>/presentation.html` | Scaffold plus `styles.css`. `--plan-only` writes `plan.md` (full mode). `--refresh <file>` updates an old deck's engine |
| `screenshot.js <html> <temp-dir> [slide-id ...]` | One image per slide plus `sheet.png`, a contact sheet of them all (Edge or Chrome; `--browser <path>` if not found) |
| `patterns.js <library> <name> ...` | Prints the named library slides, whole, in one call |
| `check-charts.js <html>` | Chart JSON, limits, one item highlighted, no controls |
| `check-overflow.js <html>`, `edit-html.js <html>` | Overflow measure (needs `puppeteer`); browser editor for wording |

Needs: Node.js; internet when a deck opens (reveal.js and ECharts from a CDN); Edge or Chrome for screenshots.

Deck engine, scripts and parts of the references adapted from github.com/ryanbbrown/revealjs-skill (MIT, see `LICENSE-revealjs-skill`).
