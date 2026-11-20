# Change the theme, spacing, widths or order

What this does
1. Theme: `npm run theme` takes a theme from the design library by its id, writes it to `Themes/<id>/` and sets
   `"theme"` in `dashboard.config.json`. Every section, copied items included, takes its colours and fonts.
2. Spacing and sizes: four settings at the top of `Src/custom.css`.
3. Width: `size: 'half'` in a section's `meta`. Order: the list in `Src/Sections/index.js`.
Run commands in the dashboard folder.

Step 1: switch the theme
  npm run theme
  -> the library's themes, one line each: TH-01 light, TH-02 dark, TH-03 print-grey ...
  npm run theme -- TH-02
  -> "theme: TH-02 dark (Themes/TH-02/), now the dashboard's theme"
  | Part | Where it comes from |
  | --- | --- |
  | `TH-02` | an id from the list above (the library's `index/themes.md`) |

Step 2: spacing and sizes
  In `Src/custom.css`, change the numbers:
  :root {
    --page-width: 1200px;    the widest the page gets
    --section-gap: 16px;     space between sections
    --section-pad: 16px;     space inside a section's border
    --chart-height: 340px;   every library chart
  }
  One chart's height only: add `height={300}` to the `<Item ... />` line at the end of its section file.

Step 3: widths
  In a section file's `meta`, add `size: 'half'` (or delete it for full width):
    id: 's1_paid_by_lob', title: '...', tab: 'overview', use: 'CT-34', size: 'half',
  Two neighbouring sections that are both half share a row, at one height (a shorter chart grows to match).
  A half section with no half neighbour is shown full width.

Step 4: order and tabs
  In `Src/Sections/index.js`, the `export default [ ... ]` list is the order on the page; move a line up or down.
  `export const tabs = [ { id: 'overview', label: 'Overview' } ]` lists the tabs; a section's `meta.tab` names its tab.
  A new tab: add `{ id: 'trend', label: 'Trend' }` there, or add a section with `--page trend --new-tab`.

If something is missing
  - `npm run theme` says no library found: run it once with `--library <the design-library folder>`; it remembers.
  - An unknown theme id: the library says so; nothing changes.

Step 5: check and look
  npm run check   -> "check OK"
  npm run shot -- overview   -> open the picture: the colours, the gaps and the widths as set.
