"""Settings for this analysis. The only file to change for a rerun."""
from pathlib import Path

ROOT = Path(__file__).parent

TITLE = "__TITLE__"
QUESTION = "__QUESTION__"
AUDIENCE = "TODO who reads the report and what they know, e.g. claims operations leads who have not seen these tables"

# name -> file. Sections ask for a source by name: src("claims_a")
#   "inputs/<file>"  a file someone handed over (.csv, .tsv, .parquet, .xlsx)
#   "sql/<file>.sql" a query; needs run_query below; its result is saved in data/sources/
SOURCES = {
}

# Dates, thresholds, tolerances. Sections read params["x"]; SQL files use {x}.
PARAMS = {
}

# Sections in the report, in order, e.g. ["s1", "s3"]. Leave empty until the answer is agreed;
# no report can be built while it is empty.
REPORT = []


# Only needed when a source is a .sql file. Must return a pandas DataFrame.
# def run_query(sql):
#     import pandas as pd
#     ...
#     return pd.read_sql_query(sql, connection)
