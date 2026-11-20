# Save a visual to the library

What this does
1. The `design-librarian` agent copies a section the user likes into the design library as a new item: the chart,
   table or hero card it shows, with made-up sample values, its data note (which parts it takes) and its slots.
2. It never copies the dashboard's numbers, columns, names or calculation, and never changes the dashboard.
3. It checks the new item (the library's own check, a test fill, a picture) and reports the new id.
Only when the user likes a visual or asks to save it; never by hand.

Step 1: find the section's file and the library
  npm run status   (in the dashboard folder)   -> the section's id and file, e.g. s2_paid_by_month,
                                                   Src/Sections/s2_paid_by_month.jsx
  The library: the project map's `Design library:` line; else `design-library` beside `.claude`; else
  `Toolkit Update/design-library`.

Step 2: launch the agent
  Launch `design-librarian` with:
    Library: C:/work/Toolkit Update/design-library
    Visuals: dashboard section s2_paid_by_month in C:/work/claims/dashboard (Src/Sections/s2_paid_by_month.jsx)
    What it is for: monthly paid amount, one line per line of business, labelled at the line ends
  | Part | Where it comes from |
  | --- | --- |
  | Library | step 1 |
  | the section id and folder | `npm run status`, and the dashboard's own folder |
  | What it is for | one plain sentence from the user or the plan; no company or product names |

If something is missing
  - The section is a library item the user only re-coloured: say so; the library may already have it (its id is
    `meta.use` in the file); save only if it is really new.
  - The agent stops on a word from the project in the sample: it asks; give it a neutral word.

Step 3: check
  The agent reports the new id (e.g. CT-38) and a picture. Look at the picture; then the item can be added to any
  dashboard with `npm run show -- CT-38` and `add-a-section.md`.
