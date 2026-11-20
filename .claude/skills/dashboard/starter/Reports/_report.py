"""Shared helper for report scripts. Mechanical only: load the report's JSON, let the script fill it, build it.

A report is two files in Reports/ with the same name:
    <name>.json   what it needs: title, sections, filters, output name (and the script that runs it)
    <name>.py     how it runs: python Reports/<name>.py

    from _report import build, load, metrics
    report = load(__file__)                         # Reports/<name>.json as a dict
    m = metrics("s1_summary")                       # a section's metrics, from its analytic (optional)
    report["notice"] = f"Data through {m['latest_month']}"   # fill anything that changes per run
    build(report)                                   # -> Exports/<output>_<date>.html, one offline file

build() hands the filled report to Tools/export.mjs, which precomputes every allowed filter combination and
writes one self-contained HTML file. The JSON file itself is never changed.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # the dashboard folder


def load(script: str | Path) -> dict:
    """The report's JSON (same name as the script, in Reports/)."""
    path = Path(script).resolve().with_suffix(".json")
    if not path.exists():
        sys.exit(f"report: {path.name} not found next to {Path(script).name}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))   # also as Windows tools save it (BOM, CRLF)
    except json.JSONDecodeError as e:
        sys.exit(f"report: {path.name} is not valid JSON at line {e.lineno}: {e.msg}")


def metrics(section_id: str, **filters) -> dict:
    """One section's metrics from its analytic, for these fast filter values (others at "All"). A date metric
    also comes as <name>_label ("Jun 2026"), for text."""
    if str(ROOT / "Analysis") not in sys.path:
        sys.path.insert(0, str(ROOT / "Analysis"))
    from Shared import engine  # noqa: E402 - the dashboard's own analytics
    result = engine.run(section_id, {k: str(v) for k, v in filters.items()})
    if "error" in result:
        raise RuntimeError(f"{section_id}: {result['error']}")
    out = dict(result["metrics"])
    for k, v in result["metrics"].items():   # dates also as words: latest_month "2026-06-01" -> latest_month_label "Jun 2026"
        if isinstance(v, str) and re.match(r"^\d{4}-\d{2}(-\d{2})?$", v):
            out[f"{k}_label"] = dt.date(int(v[:4]), int(v[5:7]), 1).strftime("%b %Y")
    return out


def build(report: dict, name: str | None = None) -> int:
    """Build the filled report into Exports/. name defaults to the running script's name."""
    name = name or Path(sys.argv[0]).stem
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / f"{name}.json"
        spec.write_text(json.dumps(report, indent=2), encoding="utf-8")
        code = subprocess.run(["node", str(ROOT / "Tools" / "export.mjs"), name, "--spec", str(spec)], cwd=ROOT).returncode
    if code:
        sys.exit(code)
    return 0
