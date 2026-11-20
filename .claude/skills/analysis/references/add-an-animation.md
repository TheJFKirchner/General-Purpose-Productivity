# Add an animation

What this does
1. Copies one animation from the design library into a new file, `sections/sN_<name>.py`, in the report folder.
2. Writes a calculation for the table it needs and wires its parts to that table's columns, as for a chart.
3. Adds the section to `SECTIONS` in `report.py`; the next build switches on the page's motion player.
4. In the report each animation plays once when it scrolls into view and gets a Replay button. Before that,
   in print and in screenshots it shows its end state. With reduced motion nothing plays by itself.

Step 1: find the library and pick an animation
  The library is the first that exists: the folder named on the project map's `Design library:` line;
  `design-library` beside the `.claude` folder; `Toolkit Update/design-library`.
  Read `index/animations.md` there. Each line says what it moves and where it fits; use only ones that fit a report
  (AN-09 does not).

Step 2: see what it has (run in the report folder)
  python run.py show AN-06
  -> its parts, what it moves, the source columns that fit each part, and a ready command

Step 3: add it
  python run.py add-section focus_region --use AN-06 --source claims --slot label=region --slot value=paid_amount

  | Part | Where it comes from |
  | --- | --- |
  | `focus_region` | your name for the section, lower_snake_case |
  | `AN-06` | the id from `index/animations.md` |
  | `claims` | a source name in `report.py` SOURCES (`python run.py list`) |
  | `label`, `value` | the animation's slot names, as `show` prints them |
  | `region`, `paid_amount` | columns of that source (`python run.py list`) |

  The shaping options of a chart work here too (`--period`, `--top`, `--by`, `--agg`, `--where`, `--compare`).

Count up the figures of a section you already have
  Open its file and add the line  MOTION = "count-up"
  Its big figures then count up when they come into view, ending on the value they show.

If a part is missing
  Required slot not given, or its column absent: it goes in on placeholder data and a `MANUAL:` line says which line to edit.
  Optional slot not given: left out, with an `info:` line.
  A slot the animation does not have: ignored, with a `note:` line.

Step 4: build and look
  python run.py report
  python run.py shot
  -> the screenshot shows each animation's end state; `check: the page had script errors` means something broke.
     Open the report in a browser to see it play; Replay plays it again.
