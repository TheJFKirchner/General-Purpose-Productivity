# Building the deck

## Wording a slide: the short rules

Enough to word a slide that `add-slide.js` made, or to change one slide. **Stop here** unless you are building a new deck, need a layout `add-slide.js` does not make, are copying a library pattern, or need a chart rule not below (then `references/charts.md`).

| Part | Rule |
| --- | --- |
| Headline | The slide's point as a sentence, with its number. 2 lines of at most 60 characters; never ends on one word. States the date basis (paid month, month of care) when the project uses more than one |
| Numbers | From a `findings.md` row, the report's own chart series, or `python run.py data <analytic> <table>` (what `--from` runs). Never from memory; never a script of your own |
| Ratios | "13 times" is allowed when both numbers are on the slide or in its cited findings rows. Round down; give the sum in the speaker notes. Otherwise add a findings row first |
| Chart | Value labels carry units. One item in `var(--blue)`, the rest grey. Draw any line the text cites (`markLine`). A report chart keeps its kind, period and measure name |
| Chart heading | Names what is measured and the period: "Hospital-stay claims paid, by month of care, Jan 25 to Jun 26" |
| Bullets | 2 or 3, about 18 words each. Each points at something on the visual, with its number, and says what it means. None repeats the headline |
| Footnote | One line: what is measured, the period, the source as finding n; report folder, section, table |
| Description | `data-desc` on the `<section>`: what the slide is for, 8 to 10 words. Set it with `slides.js <deck> --desc <id> "..."` |
| Section | The neighbour's. Never reopen an earlier section: the bottom bar must read in order |
| Close | A decision close names owner, timing and cost; missing ones go on one line: "To agree today: owner, cost". Never repeat the close |
| Text | No lead-ins ("Here's what we found"), no filler (robust, key, leverage, unlock, crucial), no sentence explaining colours |

Then one command: `slides.js <deck>` (nothing flagged TO WORD, no section reopened, no missing description), `check-charts.js <deck>`, `screenshot.js <deck>` (writes to the system temp folder). Read `sheet.png` only. One fix pass, one re-shot, stop.

Never opened on an edit: the deck HTML as a whole, anything below `SLIDES:END`, `styles.css` below `:root`, library slide files, the scripts.

---

The rest of this page is for building a new deck.

For whoever builds: you in quick mode, the builder subagent in full mode. A deck is one reveal.js HTML file plus `styles.css`. No build step; open the HTML in a browser.

## Scaffold

```bash
node <skill>/scripts/create-presentation.js --title "Short deck title" -o <deck folder>/presentation.html
```

- Writes `presentation.html` (a BRIEF comment and one `NEW SLIDES` line) and copies the base theme to `styles.css`.
- **A new deck is filled in one Edit:** Read the file down to `SLIDES:END`, then replace the BRIEF facts and the `NEW SLIDES` line with the filled facts and every slide. Leave the BRIEF `Slides:` line: `slides.js <deck> --sync` writes the list from each slide's `data-desc`.
- Later changes: one slide per Edit, by id. Never rewrite the file with Write.
- `<title>` (the `--title`) shows in the bottom bar: 30 characters at most. The full title goes on the title slide.

## Slide HTML

- Slides sit between `<!-- SLIDES:START -->` and `<!-- SLIDES:END -->`. Never read or edit below; it is the engine.

```html
<section id="s03-west-kept-most" data-section="Results" data-desc="Shows the West region retained the most new customers">
  <p class="kicker">Results</p>
  <h2>The West region kept the most new customers after the change</h2>
  <div class="content"> ... </div>
  <div class="footnote">What is measured, the period, the source.</div>
</section>
```

| Part | Rule |
| --- | --- |
| `id` | A unique name, not a position: `paid-by-month`. `add-slide.js` makes one when `--id` is left out |
| `data-section` | Section name for the bottom bar. Leave off to continue the previous section |
| `data-desc` | What the slide is for, 8 to 10 words. The BRIEF slide list is written from it by `slides.js --sync` |
| `.kicker` | The section name, exactly as in the bar |
| `<h2>` | The headline: the slide's point as a sentence. 2 lines of at most 60 characters; never ends on one word |
| `.content` | Everything below the headline. `middle` centres it: only for a statement or quote |
| `.footnote` | One line: what is measured, the period, the source |
| `<aside class="notes">` | Speaker notes (S opens the speaker view) |

- All visible text sits in `<p>`, `<li>`, `<h1>` to `<h6>`, `<td>` or `<th>`, never bare in a `<div>`.
- Layout (columns, rows): inline CSS grid on a `<div>`. Anything visual (colour, border, size) comes from a class in `styles.css`; no colours on slides.
- A grid that holds a chart needs `flex: 1; min-height: 0; min-width: 0;`. Never set a height on a chart.
- No controls: no `<select>`, `<input>`, `<button>`, `<details>`, tabs or `<iframe>`. No icons or decorative images.
- A slide with little on it: make the content bigger (`.text-lg` to `.text-4xl`), do not add content.

## Layouts

The fallback when there is no design library. With one, use the pattern each slide names (see "Library patterns").

| Layout | Use for |
| --- | --- |
| `title` | First slide: the answer (or the subject) as the headline |
| `figures` | One to three figures that make one point, with one sentence |
| `chart-commentary` | A chart and 2 to 3 bullets beside it. The workhorse |
| `chart-callout` | One sentence over a full-width chart. Lean, for senior rooms |
| `table-commentary` | Exact figures that will be read, with bullets |
| `rows` | Findings, next steps, or an ask with owners and dates |

```html
<!-- title -->
<section id="title" class="section-divider" data-state="is-section-divider">
  <p class="kicker">Results readout</p>
  <h1>Guided setup cut early churn from 5.1% to 3.1%</h1>
  <p>Onboarding team, November 2026</p>
</section>

<!-- figures: inside .content. Fills the slide; one figure alone uses .hero -->
<div class="figures">
  <div class="stats">
    <div class="stat edge is-key"><p class="stat-value">3.1%</p><p class="stat-label">early churn, October</p><p class="stat-note">5.1% before the change</p></div>
    <div class="stat edge"><p class="stat-value plain">9 days</p><p class="stat-label">to finish setup</p><p class="stat-note">14 on the old checklist</p></div>
    <div class="stat edge"><p class="stat-value plain">91%</p><p class="stat-label">kept in the West</p><p class="stat-note">7 points above the rest</p></div>
  </div>
  <div class="callout"><p class="text-lg">The one sentence that ties the figures to this audience.</p></div>
</div>

<!-- chart-commentary: inside .content -->
<div style="flex: 1; display: grid; grid-template-columns: 3fr 2fr; gap: 44px; min-height: 0; min-width: 0;">
  <div class="chart" data-echart><script type="application/json">{ ... }</script></div>
  <div class="commentary">
    <h3>New-customer retention by region, Q3</h3>
    <ul><li>What to look at, with its number.</li><li>What it means.</li></ul>
    <p class="so-what">Why it matters to this audience.</p>
  </div>
</div>

<!-- chart-callout: inside .content -->
<div style="flex: 1; display: grid; grid-template-rows: auto 1fr; gap: 22px; min-height: 0; min-width: 0;">
  <div class="callout"><p class="text-lg">The one sentence the chart proves.</p></div>
  <div class="chart" data-echart><script type="application/json">{ ... }</script></div>
</div>

<!-- table-commentary: inside .content -->
<div style="flex: 1; display: grid; grid-template-columns: 3fr 2fr; gap: 44px; align-items: center;">
  <table class="data">
    <thead><tr><th>Region</th><th>Before</th><th>After</th></tr></thead>
    <tbody><tr class="is-key"><td>West</td><td>84%</td><td>91%</td></tr><tr><td>East</td><td>82%</td><td>84%</td></tr></tbody>
  </table>
  <div class="commentary"><ul><li>...</li></ul></div>
</div>

<!-- rows: straight inside .content, so the rows fill the slide. --rows-cols sets the column widths -->
<div class="rows" style="--rows-cols: 170px 1fr 200px;">
  <div><p class="row-key small">January</p><p>Roll guided setup out to North</p><p class="text-muted">Onboarding lead</p></div>
  <div><p class="row-key small">March</p><p>Shorten setup from 9 days to 5</p><p class="text-muted">Product team</p></div>
</div>
```

- `chart-commentary` with 4 bars or fewer: give the chart the smaller share (`2fr 3fr`).
- Numbered findings: `rows` with `<p class="row-key">1</p>`.

## Not a template

Each of these would have changed a slide in a real test deck.

- No two slides with the same layout back to back, other than chart slides.
- Supporting figures for one point go on one slide (`figures`), not one slide each.
- The visual shows the headline's own number.
- A heading names what is measured ("Paid claims by month, 2025"); never "What this shows" or "Reading the chart".
- Label series and periods on the chart; never explain colours in a sentence.
- No dead bands: rows and figures fill the slide (above); never centre a small block with `middle`.
- A decision slide argues approve against wait (DE-05) or sets the ask beside its actions (DE-06), never identical boxes. Missing owner, timing or cost go on one line under the ask: "To agree today: owner, cost".
- The headline states the date basis (paid month, month of care) when the project uses more than one.

## Library patterns

With a design library, each slide names a pattern by its id, such as CP-01 (the library's `index.md` lists them).

- Fetch every pattern the deck uses in one call: `node <skill>/scripts/patterns.js <library> <name> <name> ...` prints each named slide whole. Copy each structure and replace every word and number; the sample's subject matter is placeholder.
- Do not copy the `data-component` attribute or the COMPONENT comment.
- A pattern that does not fit its content: stop and say so (full mode: report it). Do not invent a layout.
- An ask with actions: every row has an owner and a date; without them, show the ask alone. A backup slide: the headline states the answer; the question sits above.

## Classes

- `.stat` with `.stat-value` (`.hero` very large, `.compact` in small cards, `.plain` navy), `.stat-label`, `.stat-note`.
- `.card` (white, hairline), `.callout` (wash panel, blue edge), `.compact` on either for tight spaces.
- `.commentary` with an optional `<h3>`, a `<ul>`, an optional `p.so-what`. `.so-what` works only inside `.commentary`; `.row-key` only inside `.rows`.
- `table.data`: `tr.is-key` (the highlighted row), `tr.is-total`, `td.text`. 5 rows by 4 columns at most.
- `<span class="status-dot good|bad">` (plain = watch). `.steps` with `.step-when`, `.step-detail`, `.is-current`. `blockquote` with `cite`. `h3.chart-title` above each chart when a slide holds two.
- Two stacked blocks of unequal size: rows `auto 1fr`, not `1fr 1fr`.
- A pattern used on 3 or more slides with no class: add a class to that deck's `styles.css`.

## Text

Full mode uses `references/writing.md`. Quick mode, these:

- Headline: the finding as a full sentence, with the number. Not a topic ("Churn overview"). Read the headlines alone: they tell the story.
- Bullets: 2 or 3 per visual, about 18 words, each pointing at something the visual shows and saying what it means. None repeats the headline.
- Every number has a unit, a period and something to compare it to. One name per measure across the deck.
- No lead-ins ("Here's what we found"), no filler (robust, key, leverage, unlock, crucial), no closing one-liner that repeats the point.

## The bottom bar

- Built from `data-section`: the deck title, each section with its progress, the slide count. Hidden on the title slide and on any slide with `data-bar="hide"`.
- 2 to 5 sections, two words each at most. Clicking a section jumps to it.

## Changing the look

- The whole look is the `:root` block of the deck's `styles.css`. Charts and the bar read the same tokens.
- Dark dividers: `--section-divider-bg: var(--navy)` and `--divider-text: var(--paper)`.
- Never change `references/base-styles.css` for one deck. Never name a company in a theme.

## Check

1. `node <skill>/scripts/check-charts.js <deck>/presentation.html`
2. `node <skill>/scripts/screenshot.js <deck>/presentation.html` (images go to the system temp folder's `deck-shots/<deck folder>/`, for looking, not kept). Read only `sheet.png`, the contact sheet of every slide; open one slide's image only if the sheet cannot settle a doubt. Never write images into the deck folder.
3. Look for: headlines over two lines or ending on one word, empty bands, value labels without units, colliding or clipped labels, text overflowing, the bar's sections in order on every slide after the title.
4. One fix pass covering everything found, one re-shot, read the new sheet, stop. About 22 calls for a seven-slide deck.

Then give the user the path to `presentation.html`. Keys: arrows or space to move, F full screen, S speaker view, Esc overview. PDF: open `presentation.html?print-pdf` and print. To send: `presentation.html` and `styles.css` together.

Adapted from github.com/ryanbbrown/revealjs-skill (MIT).
