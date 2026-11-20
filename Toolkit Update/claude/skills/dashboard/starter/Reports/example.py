"""EXAMPLE report: sales overview. Run: python Reports/example.py  (settings in Reports/example.json)"""
from _report import build, load, metrics

report = load(__file__)

# Fill what changes per run. Every number comes from an analytic, never typed in.
m = metrics("s1_summary")
report["notice"] = f"Data through {m['latest_month']}."

build(report)
