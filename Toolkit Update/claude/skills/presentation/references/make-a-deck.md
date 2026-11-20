# Make a deck

What this does
1. Makes the deck folder `decks/<name>/` (beside the project's `CLAUDE.md`) with an empty `slides/` folder in it.
2. Writes `styles.css`: spacing and size settings at the top, then the chosen theme's colours and fonts.
3. Copies the library's chart engine (`host-runtime.js`) in and builds an empty `presentation.html`.
4. A theme with its own font (TH-04 to TH-07) also gets the font's licence file copied beside the deck.

`<skill>` below is this skill's folder, `.claude/skills/presentation`. Run commands from the project folder.

Step 1: agree the deck and find the library
  Agree in one message: who it is for, the one message, the slide list (each slide: its headline and a library id).
  The library is the first that exists: the folder on the project map's `Design library:` line;
  `design-library` beside `.claude`; `Toolkit Update/design-library`.
  Its lists: `index/slides.md` (slides), `index/charts.md`, `index/tables.md`, `index/hero-cards.md`, `index/animations.md`,
  and `index/themes.md` (themes). Each line reads
    - LV-05 | slide | bars-highlight-commentary | Vertical bars with one highlighted, commentary bullets ...
  that is: the id, its type, its name, what it is for (and, for charts, tables and cards, the data it needs).

Step 2: make the deck
  node <skill>/scripts/deck.js new may-claims --title "May claims review" --theme TH-01
  -> Made .../decks/may-claims: presentation.html (built), styles.css (... theme TH-01 light), slides/ (empty).
  -> Folder: the default: decks/ beside the project's CLAUDE.md.

  | Part | Where it comes from |
  | --- | --- |
  | `new` | the command that makes a deck |
  | `may-claims` | a short name you choose (lowercase, hyphens); the deck becomes `decks/may-claims/` and later commands use this name |
  | `--title "May claims review"` | the deck title; it shows in the bottom bar, so 30 characters at most |
  | `--theme TH-01` | a theme id from the library's `index/themes.md`; leave it out for TH-01 |

  A folder path in place of the name (`reports/q2/deck`) puts the deck exactly there; later commands then take that path.

If a part is missing
  - No `--title`: the name becomes the title (change it later with `build <deck> --title "..."`).
  - A `--theme` that is not a theme id: TH-01 is used, with a note.
  - A deck already in that folder: it stops; choose another name.
  - The folder used is printed. The project map can change the default: a map row whose "Holds" cell starts
    with "Decks", or a line `Decks: <folder>` in the project's `CLAUDE.md`.

Step 3: look
  node <skill>/scripts/screenshot.js may-claims
  -> writes decks/may-claims/shots/sheet.png (the empty page until slides are added)
  Next: add the slides (`add-a-slide.md`).
