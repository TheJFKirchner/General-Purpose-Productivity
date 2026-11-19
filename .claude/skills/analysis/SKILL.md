---
name: analysis
description: Data analysis in two modes. Explore (the default) tests things in the conversation, creating and saving nothing. Report, only when asked, builds a quick templated HTML readout, one file per section (an analytic returning tables and metrics, its chart, and author-written bullets whose figures are pulled from those metrics). Use for "can you tell me if / where / why ..." questions on data, and to rerun or change an existing report folder. Not for standing weekly or monthly views; that is a dashboard.
---

# Analysis

Explore by default. Build a report only when asked.

## First

- Read the project's `CLAUDE.md` map. Open the project plan and findings it lists when they bear on the question.

## Explore

- Test however suits the question: Python or SQL in the session, counts, cuts, comparisons. No required file format.
- Results go in the conversation: a small table or a few figures, each with one line on what it shows.
- Create no folders and save no files unless asked.
- Open question ("why is X high?"): name the few things you will test, likeliest first. Ask before chasing something off that list.
- Data with more than one date (paid, service, received): check the answer on each. If they disagree, say so.
- Say when a result looks worth a report. The person decides.

## Report

Only when asked ("write it up", "make a report").

| Request | Before building |
| --- | --- |
| Small: one question, one or two sections | One message: the question, who reads it, the answer and the sections you will show. One yes covers it |
| Larger, or an open question | 1. Brief: question, reader, what they must be able to say or do after, sources, things to test. Yes. 2. The answer in two sentences, one line per section (its claim, its chart). Yes |

Told "just do it": skip the yes and list what you assumed at hand-over.

A caveat from exploring that changes the size or reading of the answer goes in the headline, `basis` or an answer bullet, never only in a note.

1. **Where.** The map's folder for reports or outputs. No fitting folder, or no map: ask where.
2. **Create.** `python <this skill>/scripts/new_report.py <parent> <name> --title "..." --question "..." --for "<reader>" --source <name>=<file> --map <project CLAUDE.md>`. It adds the map line.
3. **Sections.** `python run.py list` shows the sources and columns. Per section: `python run.py add-section NAME --source SRC --chart bar|line|table --x COL [--y COL] [--agg sum|count|mean] [--where COL=VALUE] --bullets N --desc "8 to 10 words"` (no `--y`: counts rows; `--y`: sums; `--where` limits rows; quote `"COL>=VALUE"` and `<=`). It writes a working `sections/sN_NAME.py`; reword the lines it prints. It notes a section that seems to repeat one already there: tell the user or ask which they meant. Other shapes: edit that file (`references/section.md`).
4. **Answer.** In `report.py`: the brief (docstring) and `ANSWER`. `python run.py report`. Fix every `STOP:` and `check:` line.
5. **Look at it.** `python run.py shot` saves a screenshot to read: charts drawn, nothing overlapping, plain words throughout.
6. **Hand over.** The report path, the answer, anything assumed or unverified. Offer a cold read (`references/cold-read.md`); run it only if accepted.

## Bullets

- You write them from the results and the project's findings. No commentary step.
- Every figure is a placeholder pulling a metric: `{metric:.0%}`, `{section_name.metric:$short}`. Never type a result: a typed number is flagged, so make it a metric. Years, and thresholds that match `DEFAULTS` or `PARAMS`, may be typed.
- A comparison word (normal, in line, flat, up) needs both sides as metrics on one basis.
- Section title: the finding as a sentence. Up to 3 bullets, about 25 words each, point first.
- The answer is a headline and `basis` (a chart note is not enough). Bullets and key figures are optional. A named size gets exactly that: one chart and three bullets means no more.

## Rules

- The report answers the question, nothing else. One to five sections, each proving one claim the answer needs. No overview or profiling section.
- One chart per section, proving its claim. Reads the same without it: cut it.
- Reader does not know the data: no column names, codes or unexplained abbreviations anywhere.
- Nothing saved by default: sources and tables live in memory for each run. `KEEP` saves a slow source; a section's `export` writes a table as CSV.
- Never read or edit `run.py`. `page.html` only for a restyle the user asks for, and then only its `:root` block.
- No company names or logos.
- User likes a visual, or says save it: launch `design-librarian` with the files and the library folder (the map's `Design library:` line, else `design-library` beside `.claude`, else `Toolkit Update/design-library`); it saves them there.

## Existing report folder

- Add or change a section: `python run.py list` (the registry), then `add-section` or the one file it names; reword the bullets; `python run.py report`; `python run.py shot`.
- Open `report.py` only for the brief, the answer or the order. Open a section file only when you just added it or the user points at it.
- Rerun: compare the new file's date range and row count with the old one and update `DEFAULTS` (or `PARAMS`, if only this report differs). `python run.py report`, then reread the headline, `basis`, titles and bullets; placeholders update, words do not. A section that changes the answer means rewriting `ANSWER`.
- A deck or dashboard needs a section's numbers: `python run.py data NAME [TABLE] [--json] [--out FILE]`. No script needed.
- New question: new folder.

`python run.py --help` lists the commands. A `STOP:` line names the file and the fix.
