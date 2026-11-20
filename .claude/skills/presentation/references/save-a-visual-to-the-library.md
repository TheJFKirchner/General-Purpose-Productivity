# Save a visual to the library

What this does
1. The `design-librarian` agent copies one slide (or just its chart) from the deck into the design library as a new item with the next free id.
2. It turns the copy into the library's item shape: its data note and slots, made-up sample values, no project words, a one-sentence purpose.
3. It rebuilds the library's index and checks the new item draws like the slide. The deck itself is never changed.

When: the person says they like a slide or a chart, or asks to save it. Never by hand.

Step 1: see which slide it is
  node .claude/skills/presentation/scripts/deck.js list may-claims
  -> 3  slides/03-paid-by-lob.html  [LV-05 CT-34]  (has data)
  Note the deck folder (`decks/may-claims`) and the slide's id (`paid-by-lob`) or number.

Step 2: find the library folder
  The first that exists: the folder on the project map's `Design library:` line; `design-library` beside `.claude`;
  `Toolkit Update/design-library`.

Step 3: launch the agent
  Launch the `design-librarian` agent with:
    library folder: Toolkit Update/design-library
    visuals: slide paid-by-lob from deck folder decks/may-claims (the whole slide)
  For only the chart: "the chart of slide paid-by-lob from deck folder decks/may-claims".

  | Part | Where it comes from |
  | --- | --- |
  | `Toolkit Update/design-library` | the library folder found in step 2 |
  | `paid-by-lob` | the slide's id or number, from `list` |
  | `decks/may-claims` | the deck folder (the one holding `slides/` and `presentation.html`) |
  | whole slide or chart | what the person liked |

If a part is missing
  - The agent stops and reports if a project word (a name, a product) cannot be taken out of the item.
  - It never edits the deck or any other library item.

Step 4: check the result
  The agent replies with the new id and its picture. Give the person the id; it now shows in the library's index
  and `deck.js show <new id>` prints its parts.
