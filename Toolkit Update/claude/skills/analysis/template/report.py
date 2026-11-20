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
# Sections call src("name"). A .sql file needs run_query(sql) below.
SOURCES = {}
PARAMS = {}               # only where this report differs from DEFAULTS in sections/_shared.py
KEEP = []                 # sources to save in data/ and reuse until --refresh (slow queries only)
# The design library, for add-section --use and theme (searched for when empty or moved).
LIBRARY = ""

# The agreed answer. Every result is a placeholder: {section_name.metric:format}
ANSWER = {
    "headline": "",
    "basis": "",          # required: which date, compared with what, exclusions, data through when
    "bullets": [],       # optional
    "kpis": [],           # optional: ("Label", "{section_name.metric:$short}", "optional note")
}

# The order of the sections; each one is a file in sections/. `python run.py add-section` adds one.
# Page look: `python run.py theme TH-02`; spacing and widths: the settings block at the top of page.html.
SECTIONS = []


# Only when a source is a .sql file. Must return a pandas DataFrame.
# def run_query(sql):
#     import pandas as pd
#     ...
