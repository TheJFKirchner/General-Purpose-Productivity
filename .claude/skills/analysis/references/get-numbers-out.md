# Get a section's numbers out

What this does
1. Runs one section's calculation and prints one of its tables, or its metrics, as CSV or JSON.
2. With `--out`, writes it to a file instead: CSV, JSON, or an Excel workbook (one sheet per table).
3. Separately, a section can save its full table as a CSV beside the report on every build (`EXPORT`).
   Nothing else is saved.

Step 1: see what a section returns (in the report folder)
  python run.py list
  -> each section's file, then its tables with their columns, and its metric names

Step 2: get it out
  python run.py data paid_by_region by_region --out exports/paid_by_region.xlsx

  | Part | Where it comes from |
  | --- | --- |
  | `paid_by_region` | the section's name (from its file name `sN_<name>.py`, or `list`) |
  | `by_region` | one of its tables, as `list` prints them; `metrics` for its figures; left out, every table |
  | `--out exports/...xlsx` | where to write; `.csv` or `.json` work too; left out, it prints |
  | `--json` | JSON instead of CSV when printing |

  Files handed to people go in the project's `exports/` folder. An Excel file needs the `openpyxl` package.
  A full list every build: in the section file add  EXPORT = ["by_region"]  ; the report links the CSV.

If a part is missing
  No section of that name: it prints the sections and their tables, then stops.
  A section with several tables and none named: it lists them; name one, or use `--out` with `.xlsx`.
  No `openpyxl`: it says how to install it, or use `.csv`.

Step 3: check it
  Open the file, or read what printed: the columns match the section's table and the rows its data.
  For a deck or dashboard, use these numbers; do not retype them.
