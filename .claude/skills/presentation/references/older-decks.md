# Older decks

Decks made before slides were separate files have `presentation.html` and `styles.css` but no `slides/` folder.

What still works
1. Opening, presenting and sending them, as before.
2. Theme: `node .claude/skills/presentation/scripts/deck.js theme <deck folder> TH-02` writes a THEME block after the tokens in `styles.css`.
3. Check: `node .claude/skills/presentation/scripts/deck.js check <deck folder>` lists WORD lines, chart problems, overflow and cut-off labels.
4. Look: `node .claude/skills/presentation/scripts/screenshot.js <deck folder>` writes `<deck folder>/shots/sheet.png`.

What does not
- `add`, `animate`, `own`, `place`, `refill` and `build` stop and say the deck is older.

How to change one
- Slides sit in `presentation.html` between `<!-- SLIDES:START -->` and `<!-- SLIDES:END -->`, one `<section>` each.
  Edit a section there by hand; never edit below `SLIDES:END` (the engine).
- To use the new commands, make a new deck (`make-a-deck.md`) and add its slides again from the library.
