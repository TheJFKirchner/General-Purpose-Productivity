---
name: presentation
description: Build or change a slide deck (reveal.js HTML) from existing work - findings, an analysis report, a dashboard, a plan - by copying slides, charts, tables and animations from the design library and filling them with real data. Use for "make a deck / slides / presentation / readout on ...", or to change, restyle or refresh a deck. Not for .pptx, and not for a written report (that is the analysis skill).
---

# Presentation

This skill makes slide decks to present or to send: one HTML file that opens in a browser, with real charts. Every slide starts as a copy of a slide, chart, table, hero card or animation from the design library, is filled from a data file or an analysis report, and is then reworded by hand. The deck keeps a snapshot of its data and refreshes it with one command.

## A deck on disk

```
decks/<name>/
  slides/             one file per slide (01-<name>.html, 02-...), in order    edit these
  styles.css          spacing and size settings at the top, then the theme     edit the settings only
  presentation.html   the deck itself, rebuilt from slides/ every time         open and send it; never edit
  host-runtime.js     the library's chart engine, copied in                    never edit
  host-motion.js      the library's animation engine (decks with animations)   never edit
  <font>-OFL.txt      the licence of a theme's font (themes TH-04 to TH-07)    send it with the deck
  shots/              screenshots from the last look; sheet.png shows them all not sent
```

To send a deck: `presentation.html` and `styles.css` (and the licence file, if there is one). It needs internet to open.

## How it works

1. Pick each slide, chart, table or animation by its id from the design library's lists.
2. Copy it in: one command writes it into the deck as its own slide file.
3. Point it at data: the same command fills it from a data file or a report table and records where the data came from.
4. Edit that one file: reword the lines marked WORD; change the chart if needed.
5. Build, check and look at the contact sheet of every slide.
6. When the data changes, one command refills every chart and lists figures in the words that went out of date.
7. A slide you like can be saved back to the library as a new item.

## Where decks go

- By default in `decks/<name>/`, beside the project's `CLAUDE.md` (or in the current folder when there is none).
- The map can override this. The map is the `## Map` section the toolbox skill writes into a project's `CLAUDE.md`; a row whose "Holds" cell starts with "Decks", or a line `Decks: <folder>`, names the decks folder.

## Rules

- Before building, agree in one message: the audience, the one message, and the slide list (each slide's headline and library id). Told "just do it": list what you assumed.
- One point per slide, stated in its headline as a sentence with its number.
- Every figure comes from data named in the slide's footnote, never from memory.
- A missing part never blocks: the slide goes in and a `MANUAL:` line says what to finish by hand.
- Edit slide files only; never `presentation.html` or the scripts.
- No real company names or logos in the deck's own words; names that are in the data may show.

## To do this | Read this

| To do this | Read this |
| --- | --- |
| Start a new deck | `references/make-a-deck.md` |
| Add a slide, chart, table or hero card, with or without data | `references/add-a-slide.md` |
| Add an animation | `references/add-an-animation.md` |
| Reword a slide or change its chart | `references/change-a-slide.md` |
| Make a slide the library does not have | `references/make-your-own-slide.md` |
| Refresh the figures after the data changed | `references/refresh-the-data.md` |
| Change the theme, spacing, title or where the chart sits | `references/change-theme-or-layout.md` |
| Save a slide you like to the library | `references/save-a-visual-to-the-library.md` |
| Work on a deck made before slides were separate files | `references/older-decks.md` |

Deck engine adapted from github.com/ryanbbrown/revealjs-skill (MIT, see `LICENSE-revealjs-skill`).
