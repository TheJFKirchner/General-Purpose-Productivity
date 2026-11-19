# A section file

Each section of the report is one file, `sections/sN_<name>.py`, holding everything for that block. Changing a section means opening that file and nothing else; `python run.py list` says which file is which.

```python
"""Section s2_paid_by_month: one block of the report."""
DESCRIPTION = "Total paid amount by month of payment, bar chart"   # 8 to 10 words, shown by list


def paid_by_month(src, params):                 # named like the file; helpers start with _
    import pandas as pd
    df = src("claims")                           # a SOURCES name; rows may be filtered, may be empty
    df["month"] = pd.to_datetime(df["paid_date"]).dt.to_period("M")
    t = df.groupby("month", as_index=False)["paid_amount"].sum().sort_values("month")
    t["month"] = t["month"].dt.strftime("%b %Y")
    top = t.loc[t["paid_amount"].idxmax()] if len(t) else None
    return {"question": "How does paid amount vary by month paid?",
            "tables": {"by_month": t},
            "metrics": {"largest": None if top is None else top["paid_amount"],
                        "largest_label": None if top is None else top["month"]},
            "notes": "Months are when claims were paid."}


TITLE = "Paid amount peaked at {largest:$short} in {largest_label}"    # the finding, as a sentence
BULLETS = ["**Highest month.** {largest_label}, at {largest:$short}."]  # up to 3, about 25 words
CHART = {"type": "bar", "table": "by_month", "x": "month", "y": "paid_amount",
         "axis": "Paid amount", "format": "$short", "highlight": "{params.month}"}
LAYOUT = "wide"                                  # chart above bullets; default "side" (beside)
```

- Figures in text are placeholders: `{metric:format}`; another section's `{name.metric}`; a setting `{params.x}`. Formats: `$short` ($4.1M), `.0%`, `,`, `$,.0f`, `abs.0%` (drops the sign). Never type a result.
- Another figure: add a key to the metrics dict (`m["share"] = ...`) and use it in a bullet as `{share}`.
- A comparison word (normal, in line, up) needs both sides as metrics on one basis.
- Thresholds and periods come from `params` (`DEFAULTS` in `sections/_shared.py`), never literals. Empty input returns empty tables and `None` metrics. Plain column names and category values.

| `CHART` key | What |
| --- | --- |
| `type` | `bar`, `hbar` (long labels), `line`, `stack`, `scatter` |
| `table`, `x`, `y` | Table, category column, value column (a list, or `"*"` for every other column) |
| `axis`, `format` | Value-axis name with unit; `$short`, `.0%`, `,` |
| `highlight` | Category drawn orange; a band on lines and stacks |
| `ref` | Threshold line: `0.25` or `(0.25, "Material")` |
| `sort`, `top`, `names`, `title`, `height` | Sort by value; first N rows; legend names; caption; pixels |

Optional: `KPIS = [("Label", "{metric:$short}", "note")]` (not the bullets' figures), `TABLE = {"table": "top", "top": 10, "columns": {"provider": "Provider"}, "format": {"paid": "$,.0f"}}`, `NOTE = "..."` (line under the chart), `EXPORT = ["top"]` (full table as CSV beside the report).

Stop here. Only for report.py settings, sources and SQL, sharing with a dashboard, or every command: `build.md`. A chart the keys cannot draw: `charts.md`.
