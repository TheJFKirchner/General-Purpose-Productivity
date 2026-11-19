"""Analytics: one function per question. Several per file is fine.
Each takes (src, params) and returns question, tables, metrics and notes.
Functions whose names start with _ are helpers, not analytics."""

# Thresholds, periods and cut-offs, each once, e.g. {"large_claim": 10000}. A report's PARAMS override.
DEFAULTS = {}


def rename_me(src, params):
    df = src("source_name")
    by_group = df.groupby("group", as_index=False)["amount"].sum()
    return {
        "question": "TODO one plain question, no numbers, no answer",
        "tables": {"by_group": by_group},
        "metrics": {"total": by_group["amount"].sum()},
        "notes": "",      # filters or adjustments the tables do not show
    }
