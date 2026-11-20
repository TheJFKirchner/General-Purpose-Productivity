# Add an animation

What this does
1. Copies a library animation into the deck: as a new slide file of its own, or into a spot of a slide that is already there (it replaces what that spot held).
2. With data, fills it like a chart and records where the data came from, so a refresh works later.
3. Marks it to play each time its slide shows; it has a Replay button and shows its finished state in screenshots, print and PDF.
4. Copies the library's animation engine (`host-motion.js`) into the deck and rebuilds `presentation.html`.

`<skill>` = this skill's folder, `.claude/skills/presentation`. `<deck>` = the deck's name (from `decks/`) or its folder.

Step 1: pick the animation and see its parts
  Ids are in the library's `index/animations.md` (library: the project map's `Design library:` line; else `design-library`
  beside `.claude`; else `Toolkit Update/design-library`). AN-09 does not fit a deck.
  node <skill>/scripts/deck.js show AN-10 may-claims --data data/trend_parts.csv
  -> what it moves (figure, chart, table, blocks), its data slots with kind and required or optional, the columns that fit, a ready command
  Each animation has its own slots: run `show` on it.

Step 2a: as a slide of its own
  node <skill>/scripts/deck.js animate may-claims AN-06 --data data/claims.csv --slot label=line_of_business --slot value=paid_amount --headline "Medicare stands out"

Step 2b: into a slide that is already there
  node <skill>/scripts/deck.js animate may-claims plan-figures AN-10 --data data/trend_parts.csv --slot part=part --slot share=share --slot points=points --slot "value=+7.0%" --slot value-number=7

  | Part | Where it comes from |
  | --- | --- |
  | `may-claims` | the deck's name |
  | `plan-figures` | the slide's id or number, from `deck.js list may-claims`; leave it out for a slide of its own |
  | `AN-06`, `AN-10` | animation ids from `index/animations.md` |
  | `--data data/trend_parts.csv` | your data file; or `--from "<report folder>::<section>::<table>"` |
  | `part`, `share`, `points`, `value`, `value-number` | slot names `show AN-10` printed; after `=` a column of the data |
  | `"value=+7.0%"` | a slot of kind "one value" takes text typed as is (commas allowed) |
  | `--spot chart-2` | optional: which spot of the slide; by default the spot that holds what it moves (a figure or hero card, a chart, a table) |
  `--headline`, `--after`, `--id`, `--format`, `--top`, `--by` work as for `add`.

If a part is missing
  - A required slot with no column: placeholder data marked `MANUAL <slot>` and a `MANUAL:` line; `build` and `check` list it until fixed.
  - A slide with no fitting spot: the animation goes on a slide of its own right after it, with a `MANUAL:` line.
  - Its heading, caption and any text inside its script are the library sample's; the add and `build` list them to reword.
  - It stops only for an unknown id, a missing data file or report, or AN-09.

Step 3: build and look
  node <skill>/scripts/deck.js build may-claims    -> what is left to word or fix
  node <skill>/scripts/deck.js check may-claims    -> draws every slide; exits 1 until clean
  node <skill>/scripts/screenshot.js may-claims    -> decks/may-claims/shots/sheet.png shows each animation finished
  Open presentation.html and move to the slide: it plays; going back and forward plays it again; Replay replays it.
  With "reduce motion" set on the computer, it waits for Replay.
