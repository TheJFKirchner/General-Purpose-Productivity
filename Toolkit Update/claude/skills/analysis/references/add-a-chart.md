# Add a chart, table or hero card

What this does
1. Copies one item from the design library into a new file, `sections/sN_<name>.py`, in the report folder.
2. Writes a calculation in that file that turns the source into the table the item needs.
3. Wires the item's parts (its slots) to that table's columns, and adds the section to `SECTIONS` in `report.py`.
4. Prints the lines to reword. Every later build refills the item from the data.

Step 1: find the library and pick an item
  The library is the first that exists: the folder named on the project map's `Design library:` line;
  `design-library` beside the `.claude` folder; `Toolkit Update/design-library`.
  Read its list for one kind: `index/charts.md`, `index/tables.md` or `index/hero-cards.md`. Pick by the point
  the section must prove. Each line starts with an id (CT-34, TB-09, HC-15).

Step 2: see what the item has (run in the report folder)
  python run.py show CT-34
  -> its parts (each item has its own), which are required, the source columns that fit each, and a ready command

Step 3: add it
  python run.py add-section paid_by_region --use CT-34 --source claims --slot label=region --slot value=paid_amount

  | Part | Where it comes from |
  | --- | --- |
  | `paid_by_region` | your name for the section, lower_snake_case |
  | `CT-34` | the id from the library's list |
  | `claims` | a source name in `report.py` SOURCES (`python run.py list` shows them) |
  | `label`, `value` | the item's slot names, as `show` prints them |
  | `region`, `paid_amount` | columns of that source (`python run.py list` shows them) |

  A slot that takes "one or more" columns takes a list: `--slot value=paid_amount,allowed_amount`.
  The design library not found: add `--library <folder>` once; it is remembered.

When the data needs shaping first
  | Option | Use it when |
  | --- | --- |
  | `--period quarter` (or `year`) | a date column labels the rows; default is month |
  | `--top 10` | there are many groups; keeps the largest |
  | `--by product` | one series per group of another column |
  | `--agg mean` (or `count`) | the number is an average or a count, not a sum |
  | `--where status=paid` | only some rows count (`>=`, `<=` also work) |
  | `--compare paid_date=2026-04,2026-05` | two months, years or values side by side; builds a waterfall's columns |

When the item needs columns worked out first
  How to tell: `show` marks a part "worked out for you" or "work this out first", and quotes the recipe.
  Never give a raw column for those parts. Give the parts it is worked out from.
  Worked out for you: the tool writes the line in the calculation. Example, the dumbbell CT-08
  (recipe "low: the smaller of start and end; gap: the difference between them"):
    python run.py add-section paid_vs_allowed --use CT-08 --source claims --slot label=region --slot start=paid_amount --slot end=allowed_amount
    -> the section's calculation gets  t["low"] = t[["paid_amount", "allowed_amount"]].min(axis=1)  and the gap line
  Work this out first: the item goes in with that part on placeholder data, and prints for example
    MANUAL: range not filled - edit sections/s6_ranges.py:21: work it out: high minus low
    Open that line (it reads  t["range"] = 1   # MANUAL: range - ...) and replace the 1 with the recipe's sum, e.g.
    t["range"] = t["high_amount"] - t["low_amount"]   (the columns it needs must be in `t`: add them to the
    groupby line above). Build again: the `check:` line for it goes away.
  Covered automatically: CT-08 (low, gap), CT-22 (running), CT-24 (share), TB-08 (incurred), and CT-06 with `--compare`.

If a part is missing
  Required slot not given, or its column absent: the item goes in on placeholder data and a `MANUAL:` line says which line to edit.
  Optional slot not given: left out, with an `info:` line.
  A slot the item does not have: ignored, with a `note:` line.

Step 4: build and look
  python run.py report
  python run.py shot
  -> `Report:` the page; `check:` lines are things to fix (sample words left, placeholders, typed numbers, a % or $
     label on numbers that do not suit it: set that column's `FORMAT`);
     `STOP:` names a file and the fix. Open the screenshot it names and look at the new section.
  `check: report.py ANSWER ...` repeats until `ANSWER` in `report.py` has a `headline` (the answer in one sentence)
  and a `basis` (which date, against what, data through when).
  Then reword the lines `add-section` printed (title, bullets, the line under the chart) in the section file.
