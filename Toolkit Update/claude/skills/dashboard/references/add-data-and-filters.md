# Load data, refresh it, add filters

What this does
1. `Pipeline/sources.py` lists the input files; each line loads one file as a table.
2. `npm run pipeline` runs that file and any `Pipeline/<table>.py` scripts and swaps the result into
   `Data/Current/` only if every one worked (one file per table, `claims.csv` becomes table `claims`).
3. Filters are written in `dashboard.config.json`; each narrows the sections whose table has its column.
Run every command in the dashboard folder.

Step 1: load an input file as it is
  Add one line to `Pipeline/sources.py`:
  write_source("claims", "../inputs/claims.csv", as_of_from="service_date")

  | Part | Where it comes from |
  | --- | --- |
  | `"claims"` | the table's name, the word sections use; lowercase |
  | `"../inputs/claims.csv"` | the file, from the dashboard folder (a full path when the dashboard sits outside the project) |
  | `as_of_from` | the date column that says how current the file is: the paid date for paid claims, the posting date
    for ledger rows. The header shows "Data as of" its latest date, and the page warns when that gets old |

  Then: npm run pipeline
  -> "OK: 1 script(s), 1 table(s)" and "Swapped in as Data/Current"

Step 2 (only when a table needs preparing): a pipeline script
  Write `Pipeline/claims_monthly.py`:
  ```python
  from _dataset_io import write_dataset
  df = ...   # the query or prep code
  write_dataset("claims_monthly", df, grain="month x region", as_of="2026-10-31", source="Claims warehouse")
  ```
  Try it alone: npm run pipeline -- --try claims_monthly.py  -> its columns and row count.
  Build paths from the script's place (`Path(__file__).parent.parent`); never put files in `Data/Current` by hand.

Step 3: add a filter
  In `dashboard.config.json`, under "filters":
  "lob": { "label": "Line of business", "column": "line_of_business" }
  | Part | Where it comes from |
  | --- | --- |
  | `"lob"` | any short name |
  | `"label"` | the words readers see |
  | `"column"` | a column of the tables, as `npm run status` lists them |
  Add `"tab": "<tab id>"` for one tab only, or `"section": "<section id>"` for one section.
  Filters and sections: a filter narrows every section whose table has its column, except a section that compares
  that column's values (bars per line of business), where new-section writes `ignore: ['lob']` into the meta. If
  check warns "filter ... narrows no section", every section ignores it or lacks its column: delete the name from
  one section's `ignore` if it should follow, or delete the filter.

Step 4 (rare): a slow filter, whose data must be pulled again for each value
  "parameters": { "as_of": { "label": "Data as of", "type": "month_end", "default": "latest", "options": { "month_ends": 12 } } }
  A pipeline script reads it with `params()["as_of"]`. The page asks before re-pulling, for everyone.

New data later
  Replace the input files (same names), then: npm run pipeline, npm run check, npm run status.
  status lists, under "Changed since the last status", each section whose note now reads differently: tell the user.

Step 5: check and look
  npm run check  -> "check OK"; npm run status  -> each table with its columns, type and a sample.
  npm run shot   -> a picture of the page in Data/.shots/; open it: the header shows the source file's name and
                    "Data as of"; with sections, a filter appears above them.
