# Step 2: create the folder and connect sources

## Create the folder

```
python <this skill>/scripts/new_analysis.py <parent folder> <name> --title "<report title>" --question "<the question>"
```

- Creates `<parent>/<yyyy-mm>-<name>/` from the template.
- Adds a row to `<parent>/README.md`, the index of analyses in that parent.
- Then: copy the approved brief into the new folder's `README.md`.

## config.py

| Setting | What |
| --- | --- |
| `TITLE` | Report title |
| `QUESTION` | The brief's question, same words |
| `AUDIENCE` | The brief's "For whom"; passed to the commentary writer |
| `SOURCES` | `name -> file`. Names lower_snake_case |
| `PARAMS` | Dates, thresholds, tolerances. Sections read `params["x"]`; SQL files use `{x}` |
| `run_query(sql)` | Only if a source is a `.sql` file. Returns a DataFrame |

A rerun changes `config.py` only.

## Where each source goes

| Source | Put it | In `SOURCES` |
| --- | --- | --- |
| File handed over | `inputs/` | `"claims_a": "inputs/claims_a.csv"` |
| File the user pointed at on disk | Copy into `inputs/` | As above |
| Same, but over about 200 MB or replaced regularly | Leave where it is | The full path |
| File in the project's shared `data/` folder (in a project) | Leave where it is. Never copy: every deliverable reads the one file, so a refresh reaches all of them | The path from the analysis folder: `"claims": "../../data/claims.csv"`. Never a full path |
| Database file in the project's `data/` | Leave where it is | Not listed. `run_query` opens `ROOT.parent.parent / "data" / "warehouse.db"` |
| Query | `sql/<name>.sql`, one query per file | `"claims_b": "sql/claims_b.sql"` |
| Database file handed over (SQLite, DuckDB) | `inputs/` | Not listed. Query it with `.sql` files; `run_query` opens it |
| Reference documents (specs, emails) | `inputs/` | Not listed |

- File types: `.csv`, `.tsv`, `.parquet`, `.xlsx`, `.sql`.
- `inputs/` and `sql/` are not in the template. Create them when first needed.

## SQL

- All SQL in `sql/`. None in section files or `config.py`.
- Query: heavy filtering and joining. Sections: the analysis.
- First run saves the result as `data/sources/<name>.parquet`. Later runs reuse it.
- Pull again: `python run.py --refresh` (or `python run.py report --refresh`).
- `{x}` is replaced with `PARAMS["x"]` as plain text. Write the quotes in the SQL: `where paid_dt >= '{start}'`.
- `run_query` holds the connection. Credentials stay out of the folder (environment variables or the team's usual method).

```python
# config.py, for a database file in inputs/
def run_query(sql):
    import sqlite3
    import pandas as pd
    with sqlite3.connect(ROOT / "inputs" / "warehouse.db") as con:
        return pd.read_sql_query(sql, con)
```

## Checklist

- [ ] Every source the brief names is in `SOURCES`
- [ ] Paths only in `config.py`; queries only in `sql/`
