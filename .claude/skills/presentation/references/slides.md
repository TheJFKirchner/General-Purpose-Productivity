# Steps 6 and 7: build and walk through

The build (scaffold, fill, check) is done by a builder subagent given this page. The main conversation does the walk-through.

A deck is a reveal.js HTML file plus one CSS file. No build step; open the HTML in a browser.

## Scaffold

After gate 2, with the structure from the storyboard:

```bash
node <skill>/scripts/create-presentation.js --structure 1,1,d,1,1,1,d,1,1 --title "Deck title" -o <folder>/presentation.html
```

| Value | Makes |
| --- | --- |
| `1` | One slide |
| `d` | Section divider slide |
| `N` above 1 | Vertical stack of N slides (drill-down; avoid unless asked) |

- Writes `presentation.html` and `styles.css`. `plan.md` is kept if it exists.
- `--slides N` instead of `--structure` for N plain slides.

## Fill the slides

- **Use Edit, one slide at a time.** Each placeholder is unique (`Slide 4 Title Here`). Never rewrite the file with Write.
- Slides sit between `<!-- SLIDES:START -->` and `<!-- SLIDES:END -->`. Never read or edit below that; it is the engine.
- For each storyboard block: follow its Pattern link (see "Patterns" below), copy that slide's structure, and fill it from the block.

```html
<section id="s04-churn-after-launch" data-section="Results">
  <p class="kicker">Results</p>
  <h2>Churn fell in the first month after launch and stayed down</h2>
  <div class="content">
    <!-- Content here -->
  </div>
  <div class="footnote">What is measured, the period, the source.</div>
</section>
```

| Part | Rule |
| --- | --- |
| `id` | Unique: `s<nn>-<short-name>`, matching the storyboard row |
| `data-section` | The storyboard's Section. Builds the bottom bar. Leave off to continue the previous section |
| `<h2>` | The headline: the slide's point as a sentence |
| `<div class="content">` | Wraps everything below the headline. Add `middle` to centre it vertically |
| `<div class="footnote">` | Source line |
| `class="section-divider" data-state="is-section-divider"` | Title and divider slides |
| `<aside class="notes">` | Speaker notes (S opens the speaker view) |

HTML rules:

- All visible text sits in `<p>`, `<li>`, `<h1>` to `<h6>`, `<td>` or `<th>`. Never bare in a `<div>` or `<span>`; it will not pick up the styles.
- Layout (columns, rows): inline CSS grid on a `<div>`, since it varies per slide.

```html
<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 26px;"> ... </div>
<div style="display: grid; grid-template-columns: 1fr 2fr; gap: 30px;"> ... </div>
```

- Anything visual (colour, border, type size) comes from a class in `styles.css`. No colours on slides.
- A pattern used on 3 or more slides that has no class: add a class to that deck's `styles.css`.
- Font sizes in `pt`, only in `styles.css`. On a slide, use `.text-lg` to `.text-4xl` to scale text up.
- A slide with little on it: make the content bigger. Do not add content to fill it.
- Commentary bullets go in `<div class="commentary">` beside or under the visual: an optional `<h3>` label, a `<ul>`, and an optional `<p class="so-what">`. How many: the storyboard block's "On the page" line.
- No icons or images as decoration.
- Light hover is built into `styles.css`: cards and callouts lift slightly, rows and table rows tint, a step's line turns to the accent colour, a big figure grows a touch. Add no other hover, animation or click behaviour to a slide. It is off in `?export`.
- No controls on a slide: no `<select>`, `<input>`, `<button>`, `<details>`, tabs or `<iframe>`. Every visual is one hard-coded cut (`references/charts.md`, "Visuals from an analysis or dashboard").
- The kicker is the slide's section name, exactly as in the bottom bar.

## Patterns

Every storyboard block in `plan.md` has a "Pattern" line: a component code and a link into the slide library, such as CP-01 `library/compare/slides.html#/paired-bars-commentary`.

- Open that file, search `id="<the part after #/>"`, read that one slide, copy its structure, and replace the text and data with the block's content. Never read a library file whole.
- The sample's subject matter is placeholder. Keep the layout, classes and chart set-up; take every word and number from the storyboard block and its sources.
- Pattern links are relative to the skill folder.
- The comment above each library slide gives its code, what it looks like, what it is good for, and related components.
- Do not copy the `data-component` attribute or the COMPONENT comment into a deck.
- Per-pattern rules:
  - An ask with actions: every action row has an owner and a date; without them, show the ask alone. The ask is never repeated as a row.
  - A backup slide: the headline states the answer; the question sits above the text.
- Extra classes: `.stat-value.hero` (one very large figure) and `.compact` (inside small cards); `h3.chart-title` above a chart when a slide holds two; `tr.is-total` and `td.text` in tables; `<span class="status-dot good|bad">` (plain = watch) for scorecards; `.rows.compact`, `.card.compact`, `.callout.compact` for tight spaces.
- A `.rows` row can hold a `<div>` with an `<h3>` and a `<p>` in place of a bare `<p>`. `.row-key` works only inside `.rows`, `.so-what` only inside `.commentary`.
- Two stacked blocks of unequal size: size the rows `auto 1fr`, not `1fr 1fr`, or the taller one runs into the footnote.
- Tables: 5 rows by 4 columns at most; a scorecard may use 5 columns when the cells are short.
- A block with no Pattern line, or a pattern that does not fit its content: stop and report it. Do not invent a layout.
- Fix before returning, not just report: large empty areas (give a short chart or a short list the smaller share, or enlarge the text), a half-empty card, colliding labels.
- Charts: read `references/charts.md` in full first.
- Fragments, backgrounds, auto-animate, per-slide transitions: `references/advanced-features.md`. Only when the user asks.

## The bottom bar

- Built from `data-section`. Shows the deck title, each section with its progress, and the slide count.
- Hidden on slides before the first `data-section` (the title slide), and on any slide with `data-bar="hide"`.
- 3 to 5 sections, two words each at most. Appendix is its own section.
- The bar shows the deck's `<title>`. Keep it to 30 characters; a long title is cut off. The full title goes on the title slide.
- Clicking a section jumps to its first slide.

## Changing the look

- The whole look is the `:root` block at the top of the deck's `styles.css`: colours, fonts, sizes, corner radius, padding. Charts and the bar read the same variables.
- Dark dividers: set `--section-divider-bg` to `var(--navy)` and `--divider-text` to a light colour.
- Slide transition: `transition:` in `Reveal.initialize` (`slide`, `fade`, `none`). The only engine line that may change.
- Never change `references/base-styles.css` for one deck. Never name a company in a theme.

## Check

1. `node <skill>/scripts/check-charts.js <folder>/presentation.html`
2. Look at every slide, not a sample: `node <skill>/scripts/screenshot.js <folder>/presentation.html <temp-dir>` saves one image per slide (headless Edge or Chrome, nothing to install). Read each image. After a fix, pass the changed slide ids as extra arguments. Where `puppeteer` is installed, `check-overflow.js` also measures overflow.
3. Look for: text overflowing or wrapping unevenly across columns, unreadable text on tinted boxes, charts squeezed or empty, a headline over two lines, large empty areas (a short chart in a tall space, a tall box with one line in it), the bottom bar present on every slide after the title.
4. Writing pass: `references/writing.md`, "Check before gate 3".

Screenshots go to a temp folder, never into the presentation folder.

## Walk-through (step 7)

1. Give the user the path to `presentation.html`. Keys: arrows or space to move, F full screen, S speaker view, Esc overview.
2. Go section by section. Ask what is wrong, missing, or does not sound like them.
3. Fix slide by slide. Changes that alter the story also change the storyboard row in `plan.md`; note them under "Review notes".
4. Offer the browser editor for wording: `node <skill>/scripts/edit-html.js <folder>/presentation.html`. Click text to edit, Save, Ctrl+C to stop.
5. PDF to send: open `presentation.html?print-pdf` and print to PDF.

**Gate 3:** the user says it is ready.

Sending the deck: send the folder's `presentation.html` and `styles.css` together. It loads reveal.js and ECharts from the internet when opened.

Adapted from github.com/ryanbbrown/revealjs-skill (MIT).
