# A slide file

Each slide is one file, `slides/NN-<name>.html`; the number orders the slides. `deck.js list <deck>` shows them in order with their headlines. Change a slide by editing its file, then `deck.js build <deck>`. `presentation.html` is rebuilt from these files every time: never edit it.

```html
<section id="paid-by-month" data-section="Results" data-from="CH-01 CT-35">
  <p class="kicker" data-spot="kicker">Results</p>
  <h2 data-spot="headline">Paid claims have eased since October</h2>
  <div class="content">
    <div data-place="left" style="... grid-template-columns: 3fr 2fr; gap: var(--split-gap); ...">
      <div data-item="CT-35" data-source="../reports/claims::monthly_trend" data-format="$short" data-spot="chart">
        ...the chart's options in <script type="application/json">...
      </div>
      <div class="commentary"> <h3 data-spot="text">...</h3> <ul data-spot="bullets"><li>...</li></ul> </div>
    </div>
  </div>
  <div class="footnote" data-spot="footnote">What is measured, the period. Source: ...</div>
</section>
<style>...the item's own CSS, if it has any...</style>
```

| Part | What |
| --- | --- |
| `id` | A unique name, not a position |
| `data-section` | The section in the bottom bar. Leave it off to continue the previous section; the title slide has none |
| `data-from` | The library ids it was copied from (for reference) |
| `data-spot` | Each piece of text and the chart: `kicker`, `headline`, `chart`, `bullets`, `text`, `figure`, `table`, `footnote` (`text-2` for a second one) |
| `data-item` | A copied chart, table or hero card. `data-source`: where its data comes from, read from the deck folder (a file, or `<report folder>::<section>::<table>`). `data-shape`: how raw rows were summed. `data-format`: the number format. `data-cols`: for tables and cards, which column fills which slot |
| `data-sample` | The library's sample values are still in it; the build flags it until you fill or replace them and delete the attribute |
| `data-place` | Where the chart sits; `deck.js place` sets it |

## What refill changes

- In a chart, only the `data` of objects carrying `"col"` (the column they show), lines tied to a `"figure"`, and `"highlight"` bars. Series names, colours, axis names and ranges, formats stay as you left them.
- In a table or cards, the rows (the first `top` of them, from `data-shape`); the headings and the highlighted row are kept.
- Never the words. Refill prints the facts for every series and lists each figure in a headline, bullet or footnote that matched the old data and no longer does. Figures worked out by hand (ratios, differences) are yours to check.
- `--data <file>` (or `--from`) on refill points every item that used a file (or a report) at the new one; with a slide named, only that slide.
- Raw rows (a label repeats) are summed by the label column and many dates become months; `--agg mean` averages instead.

## Words

- Headline: the point as a sentence, with its number. Two lines of about 60 characters at most; never ends on one word. Read the headlines alone: they tell the story.
- Bullets: up to 3, about 18 words, each pointing at something on the visual, with its number, and saying what it means. None repeats the headline.
- Chart heading (`text` above the bullets): what is measured and the period.
- Footnote: one line: what is measured, the period, the source.
- Every number has a unit, a period and something to compare it to. One name per measure across the deck.
- No lead-ins ("Here's what we found"), no filler (robust, key, leverage, unlock, crucial), no sentence explaining colours, no column names or codes.
- No real company names or logos in the deck's own wording (titles, theme, footers). Names that are in the data (providers, plans) may show.
- A decision close names owner, timing and cost; missing ones go on one line: "To agree today: owner, cost".

## Layout and classes

- Visible text sits in `<p>`, `<li>`, `<h1>` to `<h3>`, `<td>` or `<th>`, never bare in a `<div>`. No controls (buttons, inputs, tabs); a slide shows one fixed cut.
- Columns: an inline CSS grid. A grid holding a chart needs `min-height: 0; min-width: 0;`. Never set a height on a chart.
- Classes: `.commentary` (`h3`, `ul`, `p.so-what`), `.callout`, `.card`, `.stat` with `.stat-value`, `.stat-label`, `.stat-note`, `table.data` (`tr.is-key` highlights a row), `.rows`, `.steps`, `.text-lg` to `.text-4xl`. Library kit classes (`lib-panel`, `lib-cards`, `lib-card`, `lib-big`, `lib-table`) also work.
- A slide with little on it: make the content bigger, do not add content.

## Showing and sending

- Keys: arrows or space to move, F full screen, S speaker notes (`<aside class="notes">`), Esc overview. PDF: open `presentation.html?print-pdf` and print.
- To send: `presentation.html` and `styles.css` (and the font licence file, if the theme copied one). `shots/` holds the screenshots; it is for looking, not sending. It needs internet to open (reveal.js and ECharts load from a CDN).

Adapted from github.com/ryanbbrown/revealjs-skill (MIT).
