# Add generated commentary

What this does
1. `npm run tables` writes small summary tables for chosen sections, one set per filter value (a "scenario"),
   with the notes the reader already sees, to a new file in `Data/.tables/`.
2. The commentary skill hands that file to the `commentary-generator` agent, which writes `commentary.json` in the
   dashboard folder: items with an id (C1, C2 ...), the bullets, their source, and the filter values they are for.
3. A section shows an item when its `meta` names that id; the page picks the item matching the current filters
   and shows nothing when none matches.
Only for text across many filter values or on every refresh. Text like "cost was $X, up Y%" belongs in the
section's own `note` (live figures), not here. Run commands in the dashboard folder.

Step 1: make the tables
  npm run tables -- --sections s2_paid_by_month,s3_provider_table --by line_of_business
  -> the path of the tables file (a new name each run)
  | Part | Where it comes from |
  | --- | --- |
  | `--sections` | section ids from `npm run status` |
  | `--by` | a filter's column from `dashboard.config.json`; one scenario per value, plus "all" |

Step 2: generate the text
  Use the commentary skill with that file's path; it writes `commentary.json`.

Step 3: show it on the section
  In the section file's `meta`, add the item's id:
    id: 's2_paid_by_month', title: '...', tab: 'overview', use: 'CT-35', commentary: 'C1',
  An item in `commentary.json` looks like:
    { "id": "C1", "filters": { "line_of_business": "Medicare" }, "commentary": ["...", "..."], "source": "..." }
  Hand edits go straight into `commentary.json`.

If something is missing
  - `meta.commentary` names an id that is not in `commentary.json`: check warns; nothing shows until it is.
  - A filter column in an item that is not a filter's column: check warns; that item only shows at "All".

Step 4: check and look
  npm run check
  npm run shot -- s2_paid_by_month lob=Medicare   -> the commentary box under the section (`lob`: the filter's name in dashboard.config.json)
  After each data refresh, regenerate (steps 1 and 2) and check again. Add "Commentary: C1 on <section>" to the
  `dashboard/` row of the project's map.
