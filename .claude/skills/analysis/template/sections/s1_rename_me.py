"""Section starter. Rename to s1_<short_name>.py and copy for s2, s3 ..."""

TITLE = "TODO short label in plain words"
QUESTION = "TODO the one question this section answers. Plain words, no numbers, no answer"
NOTES = ""    # after seeing the results: causes and context no table shows
EXPORT = []   # tables to save in full beside the report, e.g. ["differences"]


def compute(src, params):
    df = src("source_name")          # a name from config.py SOURCES
    chart_table = df
    summary = df.head(10)            # at most 50 rows x 15 columns, plain names
    return {"chart_table": chart_table, "summary": summary}


# Only needed once this section is listed in config.py REPORT.
def charts(data):
    d = data["chart_table"]
    return [
        {"title": "What the reader should see",
         "option": {"xAxis": {"type": "category", "data": d.iloc[:, 0]},
                    "yAxis": {"type": "value", "name": "Unit"},
                    "series": [{"type": "bar", "data": d.iloc[:, 1]}]}},
    ]
