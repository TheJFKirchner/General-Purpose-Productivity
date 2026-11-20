"""Run a report section's analytic (the analysis skill's shape) live inside a dashboard section.

    from Shared.reuse import from_report

    @section("s4_paid_by_month", tables=["claims"])     # the report's SOURCES names, loaded as they are
    def paid_by_month(t):
        r = from_report("../reports/claims-review","s1_paid_by_month", t)   # report folder, section file (or function name)
        return {"data": {"rows": r["tables"]["by_month"]}, "metrics": r["metrics"]}

A report keeps one file per section: <report>/sections/sN_<name>.py with one fn(src, params), and DEFAULTS in
<report>/sections/_shared.py. One function, both places: the report runs it on the whole source, the dashboard on
the section's already-filtered tables (src(name) = t.<name>). Params = DEFAULTS, then "analyticsDefaults" in
dashboard.config.json, then any keyword given here. A thin slice raises NoData, shown as "Not enough data for this
selection". (A path to a single .py file still works: its own DEFAULTS, and the function named.)
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


def _load(path: Path):
    """Import a file by path (again after it changes). Its folder goes on the import path, so `from _shared import`
    works; a `_shared` from another report is dropped first."""
    stamp = path.stat().st_mtime
    if _modules.get(path, (None, None))[1] != stamp:
        if str(path.parent) in sys.path:
            sys.path.remove(str(path.parent))
        sys.path.insert(0, str(path.parent))
        shared = sys.modules.get("_shared")
        if shared is not None and Path(getattr(shared, "__file__", "")).resolve().parent != path.parent:
            del sys.modules["_shared"]
        spec = importlib.util.spec_from_file_location(f"report_{path.parent.parent.name}_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _modules[path] = (mod, stamp)
    return _modules[path][0]


def _own_functions(mod) -> list[str]:
    return [n for n, v in vars(mod).items() if callable(v) and not n.startswith("_") and getattr(v, "__module__", "") == mod.__name__]


def _find(report: str, name: str | None):
    """(module, function name, DEFAULTS) for a report folder + section file or function name, or a single file."""
    where = (ROOT / report).resolve()
    if where.is_file():
        mod = _load(where)
        fn = name or (_own_functions(mod)[0] if len(_own_functions(mod)) == 1 else None)
        return mod, fn, getattr(mod, "DEFAULTS", None) or {}
    folder = where / "sections"
    if not folder.is_dir():
        raise FileNotFoundError(f"no report sections in {folder} (from_report takes the report folder, relative to the dashboard folder)")
    files = sorted(folder.glob("s*.py"))
    hit = folder / f"{name}.py" if name else None
    if hit is not None and hit.exists():
        mod = _load(hit)
        own = _own_functions(mod)
        if len(own) != 1:
            raise AttributeError(f"{hit.name} has {len(own)} functions ({', '.join(own)}); give the function name instead")
        fn = own[0]
    else:
        mod = next((m for m in (_load(f) for f in files) if name in _own_functions(m)), None)
        if mod is None:
            raise AttributeError(f"no section file or function '{name}' in {folder} (files: {', '.join(f.stem for f in files) or 'none'})")
        fn = name
    shared = folder / "_shared.py"
    defaults = getattr(_load(shared), "DEFAULTS", None) if shared.exists() else None
    return mod, fn, defaults if isinstance(defaults, dict) else {}


def from_report(report: str, section: str | None, t, **overrides) -> dict:
    """{params, question, tables (lists of records), metrics, notes} from a report section's analytic, run on the
    dashboard section's filtered tables. report = the report folder; section = its file name (s1_paid_by_month)
    or function name. A keyword (e.g. material=0.3) overrides one param for this call only."""
    mod, function, defaults = _find(report, section)
    fn = getattr(mod, function or "", None)
    if fn is None:
        raise AttributeError(f"no function '{function}' to run in {report}")
    params = {**defaults, **(tables.config().get("analyticsDefaults") or {}), **overrides}

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
