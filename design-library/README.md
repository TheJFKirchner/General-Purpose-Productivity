# Design library

Reusable design items for the analysis toolbox: slides, charts, dashboard sections, report blocks and themes. All share one look (`themes/look.css`). Skills work without it on their plain default look; with it, decks and dashboards reuse patterns that already work.

| Path | Holds |
| --- | --- |
| [index.md](index.md) | Every item by type: code, name, looks like, good for. Planners read only this |
| [index.html](index.html) | The same index as a page to browse; slide names open the sample slide |
| `slides/<group>/slides.html` | 47 sample slides (reveal.js), grouped by what a slide has to do. Look: `slides/styles.css` |
| `charts/` | ECharts option recipes, one small file each |
| `themes/` | The Look tokens (`look.css`) and the matching ECharts theme (`echarts-theme.json`) |
| `dashboard-sections/`, `report-blocks/` | None yet; created with the first item |
| [build-index.js](build-index.js) | Rebuilds both index files from the items |
| [new-component.md](new-component.md) | Adding or changing a sample slide |

## Using it from a project

Add one line to the project's `CLAUDE.md` map, with the path to this folder from the project:

```markdown
- Design library: ../General-Purpose-Productivity/design-library
```

- A skill that sees the line plans from `index.md` and links each part of its plan to an item: `CP-01 slides/compare/slides.html#/paired-bars-commentary`, relative to this folder.
- The builder or design subagent opens only the linked items. Slides: `node .claude/skills/presentation/scripts/patterns.js design-library <name> ...` prints the named slides in one call.
- Chart recipes use the theme tokens as `"var(--blue)"` strings. A deck resolves them; elsewhere use the hex values in `themes/look.css`.

## Adding an item

1. Check `index.md` for one that already does the job. Items are subject-neutral; a new subject is not a new item.
2. Slides: follow `new-component.md`.
3. Anything else: one file in the type's folder (create the folder with the first item), starting with this header. Markdown uses the heading; a code file puts the same lines in a comment, with `ITEM:` in front of the code.

   ```markdown
   # CT-12 · slope-lines

   - Looks like: One line per item between two points, the item that matters in blue.
   - Good for: Showing which items rose and which fell; Showing a change in rank order
   - Related: CT-08
   ```

   | Type | Folder | Code |
   | --- | --- | --- |
   | Chart | `charts/` | `CT-` |
   | Dashboard section | `dashboard-sections/` | `DS-` |
   | Report block | `report-blocks/` | `RB-` |
   | Theme | `themes/` | `TH-` |

   - Code: the next free number of its type, never reused. Name: lowercase with hyphens, describes the visual, not the subject.
   - Good for: 2 or 3 uses separated by `;`. Related: codes, or `none`. An item made of several files lists them on a `Files:` line.
   - Colours come from the Look tokens only. Sample content is invented; no real company, product or person, no logos.
4. `node build-index.js` from this folder. It rewrites `index.md` and `index.html` and lists anything inconsistent (a code used twice, a missing related item, the wrong number of "Good for" items). Never edit the index files by hand.
