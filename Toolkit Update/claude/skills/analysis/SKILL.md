---
name: analysis
description: Data analysis in two modes. Explore (the default) tests in the conversation and saves nothing. Report, only when asked, builds an HTML readout: one file per section with its calculation, a design-library chart, table or hero card, and bullets whose figures come from the data. Use for "can you tell me if / where / why ..." questions on data, and to change or rerun a report. Not for standing weekly or monthly views; that is a dashboard.
---

# Analysis

Explore by default; build a report only when asked ("write it up").

## Explore
- First read the project's `CLAUDE.md` map and any findings it lists.
- Test in the session (Python, SQL); results in the chat, a line each.
- Save nothing unless asked (an asked-for file goes in `exports/`).
- Open question: name what you will test, likeliest first.
- Several dates (paid, service): check each; say if they disagree. Say when a result looks worth a report.

## Before building
One message, one yes: the question, the reader, the answer, one line per section (its claim, its visual). Told "just do it": skip it; list what you assumed.

## Make a new report
1. Folder: the map's reports folder, else ask.
2. `python <skill>/scripts/new_report.py <parent> <name> --title "..." --question "..." --for "<reader>" --source <name>=<file> [--map <project CLAUDE.md, if any>]`
3. In it: `python run.py list` (sources, columns); `report` builds even with no sections.

## Add from the library
1. Library: the map's `Design library:` line; else `design-library` beside `.claude`; else `Toolkit Update/design-library`. Not found: `--library DIR` once (saved).
2. Read one index there (`index/charts.md`, `tables.md`, `hero-cards.md`); pick by the claim; note its `data:` line.
3. `python run.py add-section NAME --use CT-34 --source SRC --slot label=region --slot value=paid,allowed`
4. Shapes: `--period quarter|year` (dates; default month), `--top 10`, `--where COL=VALUE`, `--agg mean|count`, `--by COL`.
5. `--compare COL=A,B` (months `2026-04,2026-05`, years or values): a waterfall (CT-06 `--slot step=COL --slot total=AMOUNT`), cards for A, B and the change, or A and B side by side.
6. It writes `sections/sN_NAME.py` and prints the lines to reword. Any other column the source lacks: a TODO (see `recipe:`).

## Change a section
- One file holds it all: calculation, `SLOTS`, `NAMES`, `FORMAT`, title, bullets, `LAYOUT`, the copied `CHART` or `HTML`.
- Edit by hand. A third line: its column in the calculation and `SLOTS`, a series line in `CHART`.
- Axis names, colours (`"var(--orange)"`), `FORMAT` the same way.
- Data lists refill at every build: new data needs no edits.
- Then `python run.py report` and `shot`; fix every `STOP:` and `check:`; look at the image.

## Make your own
`python run.py add-section NAME --own chart` (or `html`; `--source` optional): a working blank section. Change it as above (parts: `references/section.md`).

## Page-level changes
- Theme: `python run.py theme TH-02` (ids: `index/themes.md`). New report: `--theme TH-02`.
- Spacing, widths: the settings atop `page.html` (`--section-gap` ...).
- Where the visual sits: `LAYOUT` in the section file (`side`, `flip`, `above`, `below`).

## Words
- Title: the finding as a sentence. Up to 3 bullets, about 25 words, point first.
- Every figure is a placeholder: `{metric:$short}`, `{other_section.metric:.0%}`. A typed result is flagged.
- A comparison word (up, normal) needs both sides as metrics.
- `report.py`: `ANSWER` headline and `basis` (which date, against what, data through when).

## Rules
- One visual per section, proving one claim of the answer.
- No column names, codes or company names in what the reader sees. Never read or edit `run.py`.
- User likes a visual, or says save it: launch `design-librarian` with the files and the library folder.

## Elsewhere
- Reruns, settings, SQL, numbers for a deck or Excel (`run.py data`): `references/build.md`.
