# Getting data in

Sections read `Data/Current/`. Each `.parquet` or `.csv` there is one table, named after the file
(`Claims Monthly.csv` becomes `claims_monthly`).

## Ways to fill it
- **Input files as they are:** one line each in `Pipeline/sources.py`:
  `write_source("claims", "../inputs/claims.csv", as_of_from="service_month")`. `as_of_from` names the date column,
  so "Data as of" follows the data. Includes a report's `SOURCES`, under the same names.
- **A pipeline script** per table when data has to be fetched or prepared.
- `npm run pipeline` runs them all and replaces `Data/Current` only if every script worked. Never put files in
  `Data/Current` by hand. Refresh: replace the input files (same names), `npm run pipeline`.

## A pipeline script
```python
from _dataset_io import write_dataset

df = ...  # your query or prep code
write_dataset("claims_monthly", df, grain="month x region", as_of="2026-10-31",
              source="Claims warehouse; months are the month care was given",
              description="Paid claims by month and region")
```
- `source`, `grain`, `description` show in a report's "About this data"; `as_of` becomes "Data as of".
- Try one alone: `npm run pipeline -- --try claims_monthly.py` (writes to `Data/.try/`, shows columns and rows).
- Scripts run from inside `Pipeline/`; build file paths from the script's place: `Path(__file__).parent.parent`.

## A report's analytics
Sections call the report's section functions live (`from_report`, `sections.md`). The dashboard only needs the
tables the report reads, under the same names: `write_source("claims", report="../reports/claims-review",
as_of_from="service_month")` in `Pipeline/sources.py` takes the file the report's `SOURCES` names. Shared thresholds and periods live in the report's `sections/_shared.py` `DEFAULTS`; override one for the dashboard with
`"analyticsDefaults": {"material": 0.3}` in `dashboard.config.json`.

## Prep that lives outside the dashboard
For heavy prep, or a data asset cached at a grain that still has the filter columns:
`df = outside("../analytics/prep.py", "claims_monthly")`, then `write_dataset(...)`. Not for report analytics:
their finished tables have lost the filter columns, so filters could not act on them.

## Settings
Everything is in `dashboard.config.json`; nothing reads environment variables.

| Key | Holds |
|---|---|
| `title`, `dataSource` | Header title; source and basis line (check warns when empty) |
| `theme`, `staleDays` | Theme folder in `Themes/`; days before a "data is old" note |
| `python`, `server.port` | The Python command or path; the analysis server port (a busy one moves) |
| `filters`, `parameters`, `analyticsDefaults` | Fast filters; slow filters; report analytic overrides |

## Filters: fast or slow
One question: **does changing it mean querying the source again?**
- **Fast** (`filters`): every value is in a loaded table column. Instant; each reader has their own choice.
- **Slow** (`parameters`): one value's data is pulled on its own; changing it re-runs the pipeline for everyone.

### A fast filter
```json
"filters": {
  "region":     { "label": "Region", "column": "region" },
  "product":    { "label": "Product", "column": "product", "tab": "costs" },
  "claim_type": { "label": "Claim type", "column": "claim_type", "section": "s4_paid_by_type" }
}
```
- It narrows only sections in its reach whose tables have its column; use the same column name everywhere.
- A table without the column is not narrowed. Membership under a category filter keeps all member months, which is
  right for per-member rates.
- `"order": ["North", "South", "East", "West"]` sets the order of choices.

### A slow filter
```json
"parameters": {
  "as_of": { "label": "Data as of", "type": "month_end", "default": "latest", "options": { "month_ends": 12 } },
  "scenario": { "label": "Scenario", "default": "Base", "options": ["Base", "High"] }
}
```
- In a pipeline script `params()["as_of"]` gives the value (a date for `month_end`); in an analytic, `t.params`.
- The app asks before re-pulling; on failure nothing changes. `npm run pipeline -- --defaults` resets picked values.
