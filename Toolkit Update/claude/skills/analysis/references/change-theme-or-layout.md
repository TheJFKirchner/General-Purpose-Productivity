# Change the theme, spacing or where a visual sits

What this does
1. Theme: copies a design-library theme's colours and fonts into `page.html` in the report folder (needs Node.js).
   A theme with its own font also copies the font's licence file beside the report; another theme removes it.
2. Spacing and widths: you edit the settings block at the top of `page.html`.
3. Where a visual sits: you edit `LAYOUT` (and optionally `HEIGHT`) in that section's file.

Step 1: see the themes
  The library is the first that exists: the folder named on the project map's `Design library:` line;
  `design-library` beside the `.claude` folder; `Toolkit Update/design-library`.
  Its `index/themes.md` lists them: TH-01 light (the default), TH-02 dark, TH-03 print grey, and more.

Step 2: change it (in the report folder)
  Theme:      python run.py theme TH-02
  New report: add  --theme TH-02  to the `new_report.py` command.
  Spacing:    in `page.html`, the block marked "Page settings":
                --section-gap: 40px;   space between sections
                --text-share: 5fr;  --visual-share: 7fr;   widths when text and visual sit side by side
                --page-width: 1120px;  --chart-height: 340px;
  Placement:  in `sections/sN_<name>.py`:  LAYOUT = "above"
                side  = text left, visual right    flip  = visual left, text right
                above = visual above the text       below = text above the visual
              One chart taller:  HEIGHT = 420
              What a section uses now: its `LAYOUT = ...` line; no such line means side.
              The add command writes one: tables below, hero cards, animations and charts over dates above,
              other charts side.
              No visible change? A section with no bullets has nothing to sit beside: its visual takes the full width
              whatever `LAYOUT` says. Side and flip also stack on a narrow window.

  | Part | Where it comes from |
  | --- | --- |
  | `TH-02` | the id from the library's `index/themes.md` |
  | the settings names | the "Page settings" block at the top of `page.html` |
  | the section file | `python run.py list` names each section's file |

If a part is missing
  An id that is not a theme: the command stops and says so; nothing changes.
  The library not found: add `--library <folder>` once; it is remembered.
  A report made before themes existed (no theme block in `page.html`): edit its colours by hand.

Step 3: build and look
  python run.py report
  python run.py shot
  -> open the screenshot: check the colours, the gaps between sections and where each visual now sits.
