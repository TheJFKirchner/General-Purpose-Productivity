# Design library expansion

> Note, 2026-11-19: the design library now lives only in `Toolkit Update/design-library/`. Paths in the text below refer to its old location.

Status: built
Date: 2026-11-19

The design library grew from slides, simple charts and themes into a library for actuarial reporting: tables, hero cards, animations and layout pieces were added as item types, the whole `james-themes` kit was imported, advanced charts were added, near-duplicate simple charts were retired, and the index page gained a theme dropdown, a popup preview and hover tooltips. It holds 122 items.

## Decisions

- **No separate report-section and dashboard-section types.** They are the same visual; only the frame and the recreate command differ. A liked visual is saved as what it is (a chart, a table or a hero card) and carries both recreate commands (`python run.py add-section`, `npm run new-section`). Rejected: keeping two types that differ only in layout.
- **Item types and id prefixes.** Chart `CT`, table `TB`, hero card `HC`, animation `AN`, layout `LY`, theme `TH`; slides keep their group codes. Layout was added to hold the page pieces and controls from `james-themes` (console band, menu, panels, filter chips, buttons).
- **`james-themes` is imported in full**, rewritten from React into self-contained items: its four themes, its cards, tables, charts, layout pieces, controls and motion. The four themes keep their company names, by the owner's explicit decision; the library's no-company-name check allows those four items only and still applies to anything saved from a project. The `james-themes/` folder itself is unchanged. Not imported: `BodyLens`, which the kit marks as explicit-request-only, and five charts identical to charts the library already had.
- **Separate subagents per type**, each briefed as a health actuarial analyst (PMPM and trend, paid against incurred, completion and IBNR, loss ratio against target, actual against expected, large claims, rate build-up, seasonality, splits by product and category). A separate actuarial reviewer then judged every item and recomputed the sample figures; wrong arithmetic and implausible values were corrected.
- **Tokens were extended** with good, bad and neutral status colours, a meter track, a tint, a shadow, band and menu colours and a corner radius, so cards, deltas and meters follow a theme. All seven themes carry them.
- **Near-duplicate simple charts were retired by a separate subagent**, proposing first: `CT-01`, `CT-03`, `CT-05` and `CT-09`, replaced by `CT-02`, `CT-20`, `CT-07` and `CT-19`. Imports from the kit were kept unless a true duplicate, with two exceptions the owner chose to drop: `CT-25` rank bump (the reviewer judged that it hides the size of the gaps and invites league-tabling small segments; `CT-08` dumbbell covers change between two points) and `CT-26` flow ribbon (decorative for a two-way split; `CT-19` mix-shift columns covers composition). Retired ids are listed in `retired-ids.txt` and never reused.
- **Animations and reduced motion.** An item must opt in to move. With reduced motion set on the device, nothing autoplays, but an explicit action (Replay, an item's own control, opening the popup) always plays, and a note says why nothing moved by itself. Rejected: honouring reduced motion by never playing, which left every animation dead on a machine with system animation effects turned off.
- **Hover.** Every chart has a one-line tooltip and a light highlight, added once in the shared engine: nothing moves, fades or redraws, and nothing shows in print.
- **Index page.** Themes are a dropdown in the top bar. Clicking an item opens a popup in the same window, with previous and next, and an "open by itself" link.
- **Hand-made items** are created with `save-item.js new <type>` and listed in `original-samples.txt`; they are exempt from the size cap and project-word checks that apply to items saved from a project. `AUTHORING.md` is the contract for writing one.
- **The librarian writes each purpose from the save script's printed description**, not by opening the saved item, which had tripled its cost.

## Checked

- Motion was verified by measurement, not screenshots: an independent subagent sampled every animation over time with reduced motion forced on. All ten play on Replay and on their own controls and end in the right state. Screenshots had missed the earlier failure because they show only an end state.
- Hover was verified by moving a pointer over charts and reading the tooltip text.
- `design-librarian` was retested cold on Haiku with the new types: a table section saved as a table, a tile row as a hero card, chart sections as charts.

## Open

- The default theme's teal has low contrast as a chart colour (about 2.9 to 1 on white). Left as it is pending the owner's choice.
- Phone-width behaviour of the popup was checked only down to 560 pixels.
- The reviewer listed further exhibits an actuarial team would use (a utilisation and unit-cost table, an IBNR run-off test, a membership bridge). Not built, to keep the number of tables small as the owner asked.
