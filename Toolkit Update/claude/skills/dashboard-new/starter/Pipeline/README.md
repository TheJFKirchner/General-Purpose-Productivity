# Pipeline/ (optional)

Scripts that pull source data into `Data/Current/`. Use them when data has to be queried or prepared, refreshed
on a schedule, re-pulled when a reader changes a slow filter, or worked out by an analysis script outside this
folder. If you already have the files, drop the `.parquet` / `.csv` straight into `Data/Current/` instead.

- One script per table: `sales_monthly.py` ends with `write_dataset("sales_monthly", df, ...)` (from
  `_dataset_io.py`), which also records a description and as-of date for "About this data".
- A report's source, as it is: `write_source("claims", "../inputs/claims.csv")` (sections call the report's analytics live).
- Heavy prep outside this folder: `df = outside("../analytics/prep.py", "fn")`, then `write_dataset(...)`.
  The result is cached in `Data/Current/`; `npm run pipeline` refreshes it.
- `params()` gives the run's slow filter values (`parameters` in the config), if the project has any.
- `npm run pipeline` runs every script (not files starting with `_`) into a staging folder and swaps it in only
  if all succeed. `--defaults` resets slow filter values picked earlier.
- `npm run pipeline -- --try sales_monthly.py` runs ONE script into `Data/.try/` and shows what it wrote,
  without touching `Data/Current`.
