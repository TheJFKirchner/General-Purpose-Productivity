# Offline HTML (report files)

One self-contained HTML file built from the dashboard: chosen sections, their notes and commentary, and every
filter choice it offers worked out in advance. It opens anywhere with no server.

## Two files each, in `Reports/`
| File | Says |
|---|---|
| `<name>.json` | What it needs: title, sections, filters, output name, the script that runs it |
| `<name>.py` | How it runs: loads the JSON, fills what changes per run, builds |

Run it: `python Reports/<name>.py`. The file lands in `Exports/<output>_<date>.html` (a same-day rebuild replaces it).

## The JSON
```json
{
  "title": "Cost trend: Commercial",
  "audience": "Finance leadership",
  "script": "finance.py",
  "output": "cost-trend-commercial",
  "sections": ["s1_summary", "s2_paid_trend"],
  "filters": {
    "line_of_business": { "value": "Commercial", "locked": true },
    "region": { "value": "All", "options": ["All", "East", "West"] }
  }
}
```
- `sections`: by id. Or `"tabs": ["overview"]` for whole tabs.
- `filters`: `locked` fixes a value and hides the filter; `options` lets the reader pick. Unlisted = "All".
- Optional: `notice` (a line under the title), `notes` (per section: `false` hides its note, text replaces it),
  `hide` (`footer`, `source`, `notes`, `commentary`, `filters`), `inspect: true` ("About this data" buttons),
  `parameters` (pin a slow filter, e.g. `{"as_of": "2026-07-31"}`; the data is pulled for it without touching the
  dashboard), `combinations` (`{"only": [...], "except": [...]}`), `theme`, `reportTabs`.

## The script
```python
"""Cost trend. Run: python Reports/finance.py"""
from _report import build, load, metrics

report = load(__file__)                      # finance.json
m = metrics("s2_paid_trend", line_of_business="Commercial")
report["notice"] = (f"Commercial, all regions; months are the month care was given; data through {m['latest_month_label']}. "
                    f"Paid in {m['latest_month_label']} was ${m['latest_paid'] / 1e3:,.1f}K, {m['yoy_change']:+.0%} on a year earlier.")
build(report)
```
- `metrics(section_id, **filters)` gives a section's metrics from its analytic, so filled text traces to code. A
  date metric also comes as `<name>_label` ("Jun 2026").
- Fill only what changes per run (title month, notice, notes, a pinned `as_of`). Never type numbers in.
- `build(report)` validates, precomputes every allowed combination and writes the single HTML file. The JSON file
  itself is not changed.
- Commentary comes from the dashboard's `commentary.json` at build time; refresh it first if it should be new.

Add a section to an existing report: `--report <name>` on `new-section`, or its id as one more line in
`"sections"`. `npm run status` lists each report's sections and those its locked filter does not narrow.

## Make one (a readout, not screenshots)
1. Ask: which sections, which filters the reader may change, what is fixed, the file name.
2. Write `<name>.json` and `<name>.py` (copy the two above):
   - a headline section first (2 to 3 KPI tiles);
   - a `notice` filled from metrics: scope, basis, data-through month, and 2 to 3 takeaways, as above;
   - leave out sections the locked filters don't narrow (a region comparison in a West file); check warns;
   - the source line is `dataSource` in `dashboard.config.json`: set it.
3. `npm run check` (it checks these too), then `python Reports/<name>.py`.
4. Open the file with no server running: sections show, filters update them, nothing loads from the internet.
5. Add the report (its name, what it locks, the command) to the map's `dashboard/` row.

A habit of "one file per region" is one file with a region choice, or one locked file per region if readers
mustn't see each other's numbers. Ask which.

## Size
The build says how many combinations it will work out and the rough size, and refuses above 500 combinations or
25 MB. Too big: lock filters the audience doesn't need, use `combinations`, or leave out heavy sections.

Quick look without saved files: `npm run export -- 1,3` (section numbers) or `npm run export -- tabs:overview`.
