---
name: presentation
description: Build or change a slide deck (reveal.js HTML) from work that already exists - findings, an analysis report, a dashboard, a plan. Slides and charts are copied from the design library by id and filled with real data. Use for "make a deck / slides / presentation / readout on ...", or to change, restyle or refresh a deck. Not for .pptx, and not for a written report (that is the analysis skill).
---

# Presentation

A deck is a folder: `slides/` (one file per slide), `styles.css`, and `presentation.html`, built from them. Commands: `node <skill>/scripts/deck.js <command> <deck folder> ...`.

## Gather first
- Read the project's `CLAUDE.md` map: findings, reports, decks.
- One message, one yes: the audience, the one message, the slide list (per slide: headline, library id). Told "just do it": list what you assumed.

## The design library
- First that exists: the map's `Design library:` line; `design-library` beside `.claude`; `Toolkit Update/design-library`.
- Pick ids from its `index/slides.md`, `index/charts.md`, `index/tables.md`, `index/hero-cards.md`; themes: `index/themes.md`.

## Make a new deck
`deck.js new <deck> --title "Short title" --theme TH-01`. Folder: the map's deck folder, else `deck/<yyyy-mm-name>/`. Add a map row.

## Add from the library
- `add <deck> LV-05`: that slide. `add <deck> LV-05 CT-35`: the chart in its chart spot. `add <deck> CT-35` (or TB, HC): a plain chart-and-commentary slide.
- A slide's own chart shows sample values; data needs a chart, table or card id after the slide id.
- Data: `--from "<report folder>::<section>::<table>"` or `--data <file.csv>`, with `--slot label=region --slot value=paid,allowed` (slots: the item's `data:` line). `--from "<report folder>"` alone lists its tables.
- Raw rows are summed by the label column; many dates become months. `--by <column>`: one line or bar per group. `--top N`: first N rows (tables keep 8).
- Also: `--headline "..."`, `--section Results`, `--after <slide>`, `--id <name>`, `--format $short|$0|0|,|%` ($0: whole dollars).
- It prints the lines to reword (WORD). Edit only those.

## Change a slide
- `deck.js list <deck>` gives each slide's file. Edit that one file only.
- A third line: copy a series line, set its `"name"` and `"col"`, then `refill <deck> <slide>`. One line per group on a slide already added: `refill <deck> <slide> --by <column>`.
- Axes, colours, a highlight by name, a line at an average: `references/charts.md`.
- Reorder: renumber the file. Remove: delete it.

## The data changed
- `refill <deck>` (or `<deck> <slide>`): new figures from each item's source; hand edits stay. A new file: `refill <deck> --data <new.csv>` (or `--from`).
- It prints facts for every series and lists typed figures that went stale. Reword those.

## Make your own
`deck.js own <deck> --headline "..."`: headline, empty chart, bullets. Write the chart options, or put a table or cards in the chart spot.

## Deck-level changes
- Theme: `deck.js theme <deck> TH-02`. Spacing and sizes: the settings at the top of `styles.css`.
- Where the chart sits: `deck.js place <deck> <slide> left|right|full`.

## Build, check, look
- Build: `deck.js build <deck>`; fix every line it lists.
- Check: `deck.js check <deck>`: overflow, undrawn charts, cut-off or overlapping labels; exits 1 until clean.
- Look: `node <skill>/scripts/screenshot.js <deck>`; read `<deck>/shots/sheet.png`. One fix pass, one re-shot.

## Rules
- One point per slide, in its headline; the visual shows that number. Words: `references/slides.md`.
- Every figure from a source named in the footnote. No real company names or logos in the deck's own words; names in the data may show.
- Never edit `presentation.html` or the scripts.
- User likes a visual or says save it: launch `design-librarian` with the slide file and the library folder.
- A deck without `slides/` (older): edit `presentation.html` by hand; check, theme, screenshot work.
