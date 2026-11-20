# Change the theme or layout

What this does
1. Theme: rewrites the THEME block in the deck's `styles.css` with a library theme's colours and fonts; a theme with its own font (TH-04 to TH-07) copies its licence file beside the deck, and switching away removes it.
2. Spacing and sizes: you edit the settings at the top of `styles.css`; every slide uses them.
3. Where the chart sits: rewrites one slide file so its chart is on the left, on the right, or full width with the commentary under it.
4. Title: changes the title in the bottom bar. Each command rebuilds `presentation.html` (a theme needs no build).

`<skill>` = this skill's folder, `.claude/skills/presentation`. `<deck>` = the deck's name (from `decks/`) or its folder.

Step 1: switch the theme
  node <skill>/scripts/deck.js theme may-claims TH-04
  -> Theme TH-04 (...) is in .../styles.css. Its embedded font's licence is beside it (barlow-OFL.txt); send it with the deck.

  | Part | Where it comes from |
  | --- | --- |
  | `may-claims` | the deck's name |
  | `TH-04` | a theme id from the library's `index/themes.md` (library: the project map's `Design library:` line; else `design-library` beside `.claude`; else `Toolkit Update/design-library`) |

Step 2: spacing and sizes
  Open the deck's `styles.css`; the first block is the settings. Change a value, save, open presentation.html again.
  | Setting | What it spaces |
  | --- | --- |
  | `--slide-padding` | left and right edges of every slide |
  | `--slide-padding-top`, `--slide-padding-bottom` | above the headline; below the content (room for the bottom bar) |
  | `--content-gap` | between the headline and the body |
  | `--split-gap` | between a chart and its commentary |
  | `--text-size`, `--h2-size`, `--footnote-size` | body text, headlines, footnotes (in pt) |
  Never edit the THEME block by hand; the theme command rewrites it.

Step 3: where the chart sits on one slide
  See where each chart sits now:
  node <skill>/scripts/deck.js list may-claims
  -> 2  slides/02-paid-by-lob.html  [LV-05 CT-34]  (has data, chart left)
  Move it:
  node <skill>/scripts/deck.js place may-claims paid-by-lob right
  | Part | Where it comes from |
  | --- | --- |
  | `paid-by-lob` | the slide's id or number, from `deck.js list may-claims` |
  | `right` | `left`, `right`, or `full` (chart across the slide, bullets side by side under it) |

Step 4: the title in the bottom bar
  node <skill>/scripts/deck.js build may-claims --title "June claims review"   (30 characters at most)

If a part is missing
  - `place` works on slides whose chart and commentary sit side by side in a grid; otherwise it says so,
    and you swap the two blocks and the two widths in that slide's `grid-template-columns` line by hand.
  - A theme id the library does not have: it stops and names the themes page.
  - Order of slides: change the number in a file name (`03b-` sits between `03-` and `04-`).

Step 5: build and look
  node <skill>/scripts/deck.js build may-claims    -> what is left to word or fix
  node <skill>/scripts/deck.js check may-claims    -> draws every slide: overflow, cut-off labels; exits 1 until clean
  node <skill>/scripts/screenshot.js may-claims    -> open decks/may-claims/shots/sheet.png and look
