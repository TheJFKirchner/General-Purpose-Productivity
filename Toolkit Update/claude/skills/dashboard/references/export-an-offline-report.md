# Make an offline report file

What this does
1. Builds one self-contained HTML file from chosen sections: their notes and commentary, and every filter choice it
   offers worked out in advance. It opens anywhere, with no server and nothing loaded from the internet.
2. A report is two files in `Reports/`: `<name>.json` (what is in it) and `<name>.py` (runs it, fills what changes
   per run). Running the `.py` writes `Exports/<output>_<date>.html` (a same-day rebuild replaces it).
Run commands in the dashboard folder.

Step 1: agree it
  Which sections, which filters the reader may change, which are fixed, the file name.
  A habit of "one file per region" is one file with a region choice, or one locked file per region if readers
  must not see each other's numbers. Ask which.

Step 2: write `Reports/finance.json`
  {
    "title": "Cost trend: Commercial", "audience": "Finance leadership",
    "script": "finance.py", "output": "cost-trend-commercial",
    "sections": ["s1_paid_by_lob", "s2_paid_by_month"],
    "filters": { "lob": { "value": "Commercial", "locked": true } }
  }
  | Part | Where it comes from |
  | --- | --- |
  | `sections` | section ids from `npm run status` (or `"tabs": ["overview"]` for whole tabs) |
  | `filters` | filter names from `dashboard.config.json`; `locked` fixes one value and hides it, `"options": [...]` lets the reader pick; unlisted = All |
  | `script`, `output` | the `.py` file's name; the start of the HTML file's name |
  Optional: `notice` (a line under the title), `notes` (per section: false hides it, text replaces it), `hide`
  (footer, source, notes, commentary, filters), `inspect: true` ("About this data" buttons), `parameters` (pin a slow
  filter), `combinations` (`{"only": [...], "except": [...]}`), `theme`.

Step 3: write `Reports/finance.py`
  from _report import build, load, metrics
  report = load(__file__)                                  # finance.json
  m = metrics("s2_paid_by_month", lob="Commercial")        # a section's metrics, so text traces to code
  report["notice"] = f"Commercial; data through {m['latest_label']}; paid {m['change']:+.0%} on the month before."
  build(report)
  Fill only what changes per run (the notice, notes, a pinned date); never type numbers in.

If something is missing
  - A section id or filter that does not exist: `npm run check` names it; the build refuses.
  - Too many filter combinations (over 500) or over 25 MB: lock filters the audience does not need, or use `combinations`.
  - A section a locked filter does not narrow (a region comparison in a West file): check warns; leave it out or say so in the notice.

Step 4: build and look
  npm run check               -> it checks the report files too
  python Reports/finance.py   -> the path of the HTML file
  Open it with no server running: sections show, the filters change them. Add the report (name, what it locks,
  the command) to the `dashboard/` row of the project's map.
  A quick look without saving report files: npm run export -- 1,3   (section numbers)   or   npm run export -- tabs:overview
