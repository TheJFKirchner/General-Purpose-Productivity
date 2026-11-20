# Change a section

What this does
1. Nothing runs until you build: you edit one file, `sections/sN_<name>.py`, in the report folder.
2. `python run.py list` names each section's file. Everything about a section is in that file.
3. On every build the visual's data lists are refilled from the calculation's table; all else is kept as you wrote it.

Step 1: open the file and find its parts (shortened example)
```
DESCRIPTION = "Paid amount by month, CT-35 plain-line"   # 1  what `list` shows
USE = "CT-35 plain-line"                                  # 2  the library item it came from: leave it
DATA = "by_month"                                         # 3  the table that feeds the visual
SLOTS = {"label": "month", "value": ["paid", "allowed"]}  # 4  which column fills which slot
NAMES = {"paid": "Paid amount"}                           # 5  words the reader sees for a column
FORMAT = {"paid": "$short", "allowed": "$short"}          # 6  number format per column
def monthly(src, params): ...                             # 7  the calculation: returns tables and metrics
TITLE = "Paid peaked at {largest:$short} in {largest_label}"  # 8  figures are {metric} placeholders
BULLETS = ["**Latest:** {latest_label}, {latest:$short}."]    # 9  up to 3
LAYOUT = "above"                                          # 10 side, flip, above or below the text
CHART = {"series": [{"slot": "value", "type": "line", "data": []}, ...]}   # 11 the copied chart, one series a line
BASIS = "Paid by month of service, Jan 2025 to Aug 2026"  # 12 the line under the chart
```
  A table or hero card has `HTML = """..."""` in place of `CHART`.

Step 2: three worked edits
  Add a third line: in the calculation, after the line that makes `t` and before `return`, add the column:
      t["plan"] = t["paid"] * 1.05
    then  SLOTS: "value": ["paid", "allowed", "plan"]   NAMES: "plan": "Plan"   FORMAT: "plan": "$short"
    and copy one series line in CHART, e.g. a dashed one:
    {"slot": "value", "type": "line", "lineStyle": {"type": "dashed", "color": "var(--orange)"},
     "itemStyle": {"color": "var(--orange)"}, "data": []},
  Rename an axis: in CHART, the axis line:  "yAxis": {"type": "value", "name": "Paid per month"},
  Change a format: two places, for two kinds of text.
    The chart (its axis numbers, labels, tooltips) and table cells follow `FORMAT`, one entry per column:
      FORMAT = {"paid": "$,.0f"}   gives $1,234 on the axis and labels ("$short" $1.2M, ".0%" 62%, "," 1,234).
    A figure in the title or bullets has its own format inside its placeholder; change it there:
      TITLE = "Paid peaked at {largest:$short} in {largest_label}"  ->  "{largest:$,.0f}" shows $291,666.
      "+" in front shows the sign: "{change:+$short}" gives +$4.2M.

  | Part | Where it comes from |
  | --- | --- |
  | column names (`paid`, `plan`) | the calculation's table; `python run.py <section name>` prints its columns |
  | metric names (`largest`, `latest`) | the calculation's `m` dict; the same command prints them |
  | colours | theme tokens: `"var(--blue)"`, `"var(--orange)"`, `"var(--chart-muted)"` |

  Python, not JSON: write `True`, `False`, `None`. Never type data into `"data": []`.

If a part is missing
  A slot with no column: its series is left out and the build prints a `check:` line naming it.
  A placeholder marked `MANUAL` is still there: the build prints a `check:` line with its line number.
  A key the item does not use: ignored by the chart.

Step 3: build and look
  python run.py report
  python run.py shot
  -> `check:` lines are things to fix; `STOP:` names the file and the fix. Open the screenshot and look at the section.
