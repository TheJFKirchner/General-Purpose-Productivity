"""Run a report analytic (the analysis skill's shape) live inside a dashboard section.

    from Shared.reuse import from_report

    @section("s4_cost_by_region", tables=["claims", "membership"])   # the report's SOURCES names, saved as they are
    def cost_by_region(t):
        r = from_report("../analytics/claims_cost.py", "region_cost", t)
        return {"data": {"rows": r["tables"]["by_region"]}, "metrics": r["metrics"]}

One function, both places: the report runs it on the whole source, the dashboard on the section's already-filtered
tables (src(name) = t.<name>). Params = the analytics file's DEFAULTS, then "analyticsDefaults" in
dashboard.config.json, then any keyword given here. A thin slice (empty table, a missing row) raises NoData, which
the section shows as "Not enough data for this selection".
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import tables

ROOT = Path(__file__).resolve().parents[2]   # the dashboard folder
_modules: dict = {}


class NoData(Exception):
    """The current filter choice leaves too little data for this analytic."""


def _module(script: str):
    path = (ROOT / script).resolve()
    if not path.exists():
        raise FileNotFoundError(f"report analytics not found: {path} (paths are relative to the dashboard folder)")
    stamp = path.stat().st_mtime
    if _modules.get(path, (None, None))[1] != stamp:   # reload after an edit to the analytics file
        if str(path.parent) not in sys.path:
            sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location(f"report_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _modules[path] = (mod, stamp)
    return _modules[path][0]


def from_report(script: str, function: str, t, **overrides) -> dict:
    """{params, question, tables (lists of records), metrics, notes} from a report analytic on the filtered tables.
    A keyword (e.g. material=0.3) overrides one param for this call only."""
    mod = _module(script)
    fn = getattr(mod, function, None)
    if fn is None:
        raise AttributeError(f"{Path(script).name} has no function {function}()")
    params = {**getattr(mod, "DEFAULTS", {}), **(tables.config().get("analyticsDefaults") or {}), **overrides}

    def src(name: str):
        df = getattr(t, name)
        if df.empty:
            raise NoData(f"no {name} rows for this selection")
        return df.copy()

    try:
        out = fn(src, params)
    except NoData:
        raise
    except (KeyError, IndexError, ZeroDivisionError) as e:   # the analytic needed a row this slice does not have
        raise NoData(f"not enough data for this selection ({type(e).__name__}: {e})") from e
    return {
        "params": params,
        "question": out.get("question"),
        "tables": {k: v.to_dict("records") for k, v in (out.get("tables") or {}).items()},
        "metrics": out.get("metrics") or {},
        "notes": out.get("notes"),
    }
