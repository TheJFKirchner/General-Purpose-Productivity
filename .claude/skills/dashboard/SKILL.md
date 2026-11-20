---
name: dashboard
description: Make a new dashboard (tabs, filters and charts on live data) or change an existing one (a folder with dashboard.config.json), with every chart, table and hero card copied from the design library by its id, pointed at a table and then edited. Also loading data, filters, themes, offline report files, hosting, porting older work and saving a visual back to the library.
---

# Dashboard

A dashboard is a small web page that reads tables of data and shows them in tabs of sections, with filters. Python works out the numbers; the page draws them with the design library's charts, tables and hero cards. Each section is one file holding a copy of a library item, which columns feed it, and its words.

## What a dashboard folder holds

```
<dashboard>/
  dashboard.config.json   title, theme, filters, the library's folder           edit
  PLAN.md                 who it is for, the questions, tabs and sections        edit
  Pipeline/sources.py     one line per input file that loads it as a table      edit
  Pipeline/<table>.py     a script for a table that needs preparing             edit
  Data/Current/           the loaded tables                                     never edit
  Analysis/<tab>.py       hand-written number functions, when a section needs one  edit
  Src/Sections/index.js   the tabs and the order of the sections                edit
  Src/Sections/sN_*.jsx   one section each: item copy, columns, title, note     edit
  Src/custom.css          page width, spacing, chart height, small looks        edit
  Themes/<TH id>/         the theme taken from the library                      never edit
  Reports/<name>.json/.py offline report files                                  edit
  Src/Lib, Src/Components, Tools, Analysis/Shared   the machinery              never edit
```

## How it works

1. Data in: each input file becomes a table.
2. Pick an item from the library by the claim the section makes.
3. Copy it in: one command writes one section file.
4. Point it at a table: each of the item's parts (slots) gets a column.
5. Edit that file: words, names, formats, colours, extra series.
6. Check, then look at a screenshot.
7. A visual the user likes goes back to the library.

## Where it goes

- Default: a `dashboard` folder inside the project's folder.
- Never inside OneDrive or another synced folder: when the project is in one, the dashboard goes in the workspace's dashboards folder, under the project's name (ask where that is if it is not known), and reads the input files by their full path.
- The map (the `## Map` section the toolbox skill writes into a project's `CLAUDE.md`) may name another place in its `dashboard/` row; when it does, that wins.

## Rules

- Agree who it is for, the questions it answers and the sections (one message, one yes) before building.
- Every section is a library item, or a blank one made by the tool; never a chart written from nothing.
- Titles say what is shown. Notes use live figures, never typed numbers.
- No column names, codes or company names where readers see them.
- Never change the user's own files.
- A part the tool could not fill is marked MANUAL: fix it before showing the user.

## To do this, read this

| To do this | Read this |
| --- | --- |
| Make a new dashboard | `references/make-a-dashboard.md` |
| Load data, refresh it, add filters | `references/add-data-and-filters.md` |
| Add a chart, table or hero card | `references/add-a-section.md` |
| Change a section | `references/change-a-section.md` |
| Make a section with no library item to start from | `references/make-your-own-section.md` |
| Change the theme, spacing, widths or order | `references/change-theme-or-layout.md` |
| Make an offline report file | `references/export-an-offline-report.md` |
| Put it on a server | `references/host-it.md` |
| Move notebooks, scripts, a report or an old dashboard into one | `references/port-existing-work.md` |
| Add generated commentary | `references/add-generated-commentary.md` |
| Save a visual to the library | `references/save-a-visual-to-the-library.md` |
| Work on a dashboard made before library items | `references/older-dashboards.md` |
