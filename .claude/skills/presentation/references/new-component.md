# Adding a component to the slide library

A component is one sample slide in `library/<folder>/slides.html`: a visual and commentary combination that decks reuse. Add one only when the user asks, or when a storyboard needs a pattern the library lacks and the user agrees.

## Before adding

1. Read `library/index.md`. Look for the same combination of visual and commentary layout.
2. One exists: use it. Do not add a second for a different subject; components are subject-neutral.
3. A close one exists (same chart, different commentary layout, or the reverse): add the new one and list the close one under Related.

| Same component | New component |
| --- | --- |
| Same chart kind, same layout, different data or subject | Different chart kind |
| Bullets reworded, or one more bullet | Commentary in a different place or form (beside, under, callout, none) |
| Different number of bars or lines | A different supporting element (figure cards, table, option cards) |

## What a component must include

| Part | Rule |
| --- | --- |
| Code | `<group prefix>-<nn>`, the next free number in its group. Never reused, never renumbered, even if a component is later removed |
| Name | Describes the visual and the commentary, not the subject: `paired-bars-commentary`, not `actual-vs-expected-claims`. Lowercase, hyphens, unique across the library |
| Looks like | One sentence: the visual, then where the commentary sits |
| Good for | 2 or 3 uses, separated by `;`. What the slide accomplishes, at a level any subject fits |
| Related | Codes and names of components with a similar visual, or `none` |
| Sample content | Realistic invented content that shows the pattern at its best. No real company, product or person |

Good for, right and wrong:

| Write | Not |
| --- | --- |
| Showing a change against an expectation | Showing 2025 trend against 2024 |
| Showing which driver accounts for most of a change | Showing commercial auto reserve movement |
| A comparison meant to be read without a presenter | Benchmark slide for the pricing committee |

Groups and prefixes:

| Prefix | Folder | Purpose |
| --- | --- | --- |
| FR | `frame` | Open and frame |
| EX | `explain` | Explain how the work was done |
| LV | `level` | Show where a number stands |
| CH | `change` | Show change over time |
| CP | `compare` | Compare two things |
| BD | `breakdown` | Break a total or a change into its parts |
| UN | `uncertainty` | Show range and risk |
| DE | `decide` | Summarise and ask |
| BK | `backup` | Back up the detail |

Choose the group by what the slide does for the audience, not by its chart. A new group needs the user's agreement: a new folder, a new two-letter prefix, and a `GROUP` comment.

## Structure

Add the component at the end of its group's `slides.html`, just above `<!-- SLIDES:END -->`, with Edit. Find the last one with a search for `COMPONENT: <prefix>-`; do not read the file whole.

```html
      <!-- COMPONENT: CP-09 · slope-lines-callout
           Looks like: Full-width slope chart (one line per item between two points), one sentence under it.
           Good for: Showing which items rose and which fell between two points; Showing a change in rank order
           Related: CP-05 dumbbell-callout, CP-01 paired-bars-commentary -->
      <section id="slope-lines-callout" data-section="Compare two things" data-component="CP-09">
        <p class="kicker">Section name</p>
        <h2>Headline that states the finding as a sentence</h2>
        <div class="content">
          <!-- the visual and the commentary -->
        </div>
        <div class="footnote">What is measured, the period, the source.</div>
      </section>
```

| Must match | With |
| --- | --- |
| The name in the comment | The section's `id` |
| The code in the comment | The section's `data-component` |
| `data-section` | The group's title, as on the other slides in the file |

Inside the slide:

- Follow `references/slides.md` (HTML rules, classes) and `references/charts.md` (all of it, if there is a chart) and `references/writing.md`.
- One point, in the headline. One visual showing one thing, one item highlighted.
- Commentary: 2 to 4 bullets in `<div class="commentary">`, or a one-sentence `.callout`, unless the component is deliberately lean. The Looks like line says which.
- Existing classes and theme variables only. No `<style>` blocks, no colours on the slide. A pattern that needs a new class: add the class to `references/base-styles.css`, copy that file over `library/styles.css`, and note it in `references/slides.md`, "Patterns".
- Related visual exists: read that one component first (search its `id`) and keep the shared parts the same (chart set-up, spacing, label style), so the family looks like one.

A new group folder is scaffolded with:

```bash
node <skill>/scripts/create-presentation.js --slides 1 --title "Slide library" --styles ../styles.css --back ../index.html -o <skill>/library/<folder>/slides.html
```

Then delete the `plan.md` it writes, replace the placeholder slide, and add `<!-- GROUP: <prefix> · <title> · <one-line description> -->` on the line after `<!-- SLIDES:START -->`.

## After adding

1. Add the new code to the Related line of each component it names, so the link runs both ways.
2. `node <skill>/scripts/check-charts.js <skill>/library/<folder>/slides.html`
3. `node <skill>/scripts/screenshot.js <skill>/library/<folder>/slides.html <temp-dir> <name>` and look at the image. Fix overflow, clipped labels, empty areas.
4. `node <skill>/scripts/build-library-index.js`. It rebuilds `library/index.md` and `library/index.html` from the slide files and lists anything inconsistent (a code used twice, a name that does not match its id, a missing related component, the wrong number of Good for items). Fix what it lists.

Never edit `library/index.md` or `library/index.html` by hand.

## Changing or removing one

- Change the look: edit the slide, update its Looks like line, run steps 2 to 4.
- Remove: delete the comment and the section, remove its code from other components' Related lines, rebuild the index. Its code is retired.
- Existing presentations are not affected; they hold their own copy of the pattern.
