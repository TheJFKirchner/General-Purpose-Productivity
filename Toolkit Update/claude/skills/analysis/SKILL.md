---
name: analysis
description: Data analysis in two modes. Explore (the default) answers a question about data in the conversation and saves nothing. Report, only when asked, builds a one-file HTML readout whose sections each hold a calculation, a chart, table, hero card or animation copied from the design library, and words whose figures come from the data. Use for "can you tell me if / where / why ..." questions on data, and to change or rerun a report. Not for standing weekly or monthly views; that is a dashboard.
---

# Analysis

The skill answers questions about data. By default it explores: it tests things in the conversation and saves nothing. When asked for a report, it builds a single HTML page: a headline answer, then one to a few sections, each proving one point with one visual taken from the design library.

## A finished report folder

```
reports/claims-review/
  report.py              the brief, the sources, the answer and the order of sections   edit
  sections/s1_<name>.py  one section: its calculation, wiring, words and copied visual  edit
  sections/_shared.py    thresholds and helpers shared by the sections                  edit
  page.html              the page shell: theme, spacing settings, library runtime       edit the settings only
  run.py                 the tool that builds the report                                never edit
  claims-review.html     the report itself, rebuilt every time                          never edit
  claims-review_shot.png the latest screenshot                                          never edit
```

## How it works

1. Pick a visual from the design library (its lists of charts, tables, hero cards and animations).
2. Copy it into the report: the tool writes one section file holding the visual and a calculation.
3. Point it at the data: the section's wiring says which column fills which part of the visual.
4. Edit that one file to change words, series, axes, formats or colours.
5. Build the report and look at its screenshot; data changes need no edits, only a rebuild.
6. A visual you like can be saved back to the library.

## Where reports go

- By default in `reports/<name>/` under the folder the work starts from.
- A project's map (the `## Map` section the toolbox skill writes into a project's `CLAUDE.md`) may name a reports folder; that overrides the default. A project without a map works fine.

## Rules

- Every figure in the text is a placeholder filled from the data; a typed number is flagged.
- One visual per section, proving one claim the answer needs.
- No column names, codes or company names where the reader sees them.
- Never edit `run.py`.

## To do this | Read this

| To do this | Read this |
| --- | --- |
| Answer a question without making anything | `references/explore-a-question.md` |
| Start a new report | `references/make-a-report.md` |
| Add a chart, table or hero card | `references/add-a-chart.md` |
| Add an animation | `references/add-an-animation.md` |
| Change a section (words, series, axes, formats) | `references/change-a-section.md` |
| Draw a visual the library does not have | `references/make-your-own-section.md` |
| Change the theme, spacing or where a visual sits | `references/change-theme-or-layout.md` |
| Rebuild with new data | `references/rerun-with-new-data.md` |
| Get a section's numbers out (CSV, Excel) | `references/get-numbers-out.md` |
| Save a visual to the design library | `references/save-a-visual-to-the-library.md` |
