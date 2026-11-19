"""__TITLE__   (created __DATE__)

Brief
- Question: __QUESTION__
- For whom: __FOR__
- Success: what the reader must be able to say or do after reading
- Sources:
- Assumptions:
"""

TITLE = "__TITLE__"
QUESTION = "__QUESTION__"
FOR = "__FOR__"           # the reader, shown at the top: "For <reader> · <date>"

# name -> file, or a function returning a DataFrame. Paths are relative to this report folder.
# Analytics call src("name"). A .sql file needs run_query(sql) below.
SOURCES = {}
PARAMS = {}               # only where this report differs from the analytics' DEFAULTS
KEEP = []                 # sources to save in data/ and reuse until --refresh (slow queries only)
ANALYTICS = "__ANALYTICS__"

# The agreed answer. Every result is a placeholder: {analytic.metric:format}
ANSWER = {
    "headline": "",
    "basis": "",          # required: which date, compared with what, exclusions, data through when
    "bullets": [],
    "kpis": [],           # ("Label", "{analytic.metric:$short}", "optional note")
}

# One block per analytic, in reading order.
SECTIONS = []


# Only when a source is a .sql file. Must return a pandas DataFrame.
# def run_query(sql):
#     import pandas as pd
#     ...
