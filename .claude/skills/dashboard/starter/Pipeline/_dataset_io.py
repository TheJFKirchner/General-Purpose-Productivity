"""Shared writer for pipeline scripts. The only code that writes Data/.

A pipeline run pulls source data ONCE (slow) into local parquet tables; the Analysis server reads them on
every request (fast). One set of tables exists at a time: Data/Current/.

Usage from a dataset script:
    from _dataset_io import params, write_dataset
    p = params()                     # {"as_of": date(2026, 10, 31), ...}: the run's slow parameters
    write_dataset("sales_monthly", rows_or_dataframe,
                  grain="month x region",
                  source="Sales ledger - through Oct 2026",
                  description="Revenue by month and region")  # optional

Outside the dashboard folder:
    write_source("claims", "../inputs/claims.csv")             # a report's source, as it is (for from_report)
    df = outside("../analytics/prep.py", "claims_monthly")     # heavy prep returning a table with filter columns
    write_dataset("claims_monthly", df, grain="month x region", source="analytics/prep.py")
The result is cached in Data/Current like any other table; npm run pipeline refreshes it.

Slow filters (dashboard.config.json "parameters") are passed by run_all.py to every script on its command line
(--dash-params '<json>'), with the folder to write to (--dash-out <folder>). Run on its own, a script writes to
Data/Current with the default values. No environment variables are used.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import inspect
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # the dashboard folder, worked out from this file's place
DATA = ROOT / "Data"
CURRENT = DATA / "Current"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _arg(name: str) -> str | None:
    """The value after --<name> on this script's command line (run_all.py adds them), or None."""
    flag = f"--{name}"
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


OUT = Path(_arg("dash-out") or CURRENT)   # run_all.py points this at a staging folder


def read_json(path: Path):
    """A JSON file as Windows tools write it too (byte-order mark, CRLF); a clear message when it is broken."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{Path(path).name} is not valid JSON at line {e.lineno}: {e.msg}") from None


def load_config() -> dict:
    return read_json(ROOT / "dashboard.config.json")


def param_specs() -> dict:
    """dashboard.config.json "parameters", without "_note"-style keys."""
    return {k: v for k, v in (load_config().get("parameters") or {}).items() if not k.startswith("_")}


def last_month_end(today: dt.date | None = None) -> dt.date:
    return (today or dt.date.today()).replace(day=1) - dt.timedelta(days=1)


def default_params() -> dict:
    """Each slow parameter's default value (as strings, like the API sends them)."""
    out = {}
    for name, spec in param_specs().items():
        if spec.get("type") == "month_end":
            d = spec.get("default", "latest")
            d = last_month_end().isoformat() if d == "latest" else d
        else:   # a fixed list: its "default", else the first option
            opts = spec.get("options") if isinstance(spec.get("options"), list) else []
            d = spec.get("default", opts[0] if opts else "")
        out[name] = str(d)
    return out


def params() -> dict:
    """This run's slow parameters: defaults, overridden by run_all.py (--dash-params). Dates become date objects."""
    values = default_params()
    values.update(json.loads(_arg("dash-params") or "{}"))
    spec = param_specs()
    return {k: (dt.date.fromisoformat(v) if spec.get(k, {}).get("type") == "month_end" else v) for k, v in values.items()}


def _report_source(report: str | Path, name: str) -> Path:
    """The file a report's SOURCES names (report.py read as text, never run), from the dashboard folder."""
    import ast

    folder = (ROOT / report).resolve()
    tree = ast.parse((folder / "report.py").read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SOURCES" for t in node.targets):
            sources = ast.literal_eval(node.value)
            if name not in sources or not isinstance(sources[name], str):
                raise KeyError(f"{folder.name}/report.py SOURCES has no file for '{name}' ({', '.join(sources)})")
            return (folder / sources[name]).resolve()
    raise KeyError(f"no SOURCES in {folder / 'report.py'}")


def write_source(name: str, path: str | Path | None = None, *, report: str | Path | None = None,
                 as_of_from: str | None = None, as_of: str | None = None, source: str | None = None) -> Path:
    """Save a source file as it is, as table <name> (.csv .tsv .parquet .xlsx; path from the dashboard folder).
    Every input file gets one line like this in Pipeline/sources.py. A report's source: write_source("claims",
    report="../reports/claims-review") takes the file its report.py SOURCES names, under the same name.
    as_of_from: a date column; "Data as of" becomes its latest date (a month start counts as that month's end),
    so it moves on by itself when new data arrives."""
    import pandas as pd

    if path is None:
        if report is None:
            raise ValueError(f"{name}: give a file path, or report=<report folder>")
        path = _report_source(report, name)

    f = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)
    readers = {".csv": pd.read_csv, ".tsv": lambda x: pd.read_csv(x, sep="\t"), ".parquet": pd.read_parquet,
               ".xlsx": pd.read_excel, ".xls": pd.read_excel}
    if f.suffix.lower() not in readers:
        raise ValueError(f"{name}: unsupported file type {f.suffix} (.csv .tsv .parquet .xlsx)")
    if not f.exists():
        raise FileNotFoundError(f"{name}: {f} not found (paths are relative to the dashboard folder)")
    df = readers[f.suffix.lower()](f)
    if as_of_from:
        if as_of_from not in df.columns:
            raise KeyError(f"{name}: as_of_from column '{as_of_from}' not in {f.name} ({', '.join(map(str, df.columns))})")
        last = pd.to_datetime(df[as_of_from], errors="coerce").max()
        if pd.notna(last):
            as_of = (last + pd.offsets.MonthEnd(0) if last.day == 1 else last).strftime("%Y-%m-%d")
    return write_dataset(name, df, grain="as in the source", source=source or Path(os.path.relpath(f, ROOT)).as_posix(), as_of=as_of,
                         script=Path(inspect.stack()[1].filename).name)


def outside(script: str | Path, function: str | None = None, **kwargs):
    """Run a prep function that lives outside the dashboard folder and return what it returns (e.g. a DataFrame).

    For heavy prep, or a data asset cached at a grain that still has the filter columns. Not for report analytics:
    those are called live by sections (Analysis/Shared/reuse.py, from_report), so filters act on them.
    script: a path relative to the dashboard folder (e.g. "../analytics/prep.py") or absolute. Its own folder is
    put on the import path, so its imports work. Without a function, the script just runs and its module is returned."""
    path = (ROOT / script).resolve() if not Path(script).is_absolute() else Path(script)
    if not path.exists():
        raise FileNotFoundError(f"outside script not found: {path} (paths are relative to the dashboard folder)")
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"outside_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if function is None:
        return module
    if not hasattr(module, function):
        raise AttributeError(f"{path.name} has no function {function}()")
    return getattr(module, function)(**kwargs)


def _clean(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):  # numpy scalar
        value = value.item()
    if isinstance(value, float) and value != value:  # NaN -> null
        return None
    return value


def _frame(rows):
    import pandas as pd

    if hasattr(rows, "to_parquet"):
        df = rows.copy()
    else:
        df = pd.DataFrame([{k: _clean(v) for k, v in r.items()} for r in rows])
    for col in df.columns:
        if str(df[col].dtype).startswith("datetime"):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    return df


def _col_type(series) -> str:
    kind = str(series.dtype)
    if kind == "bool":
        return "boolean"
    if kind.startswith(("int", "float", "Int", "Float")):
        return "number"
    vals = series.dropna().astype(str)
    if len(vals) and vals.str.match(_DATE.pattern).all():
        return "date"
    return "string"


def read_manifest(folder: Path = OUT) -> dict:
    f = folder / "manifest.json"
    if f.exists():
        return read_json(f)
    return {"generated_at": None, "params": {}, "tables": {}}


def write_manifest(manifest: dict, folder: Path = OUT) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    manifest["generated_at"] = dt.datetime.now().replace(microsecond=0).isoformat()
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_dataset(name: str, rows, *, grain: str, source: str, description: str | None = None, as_of: str | None = None,
                  script: str | None = None) -> Path:
    """Write one table as Data/.../<name>.parquet and record it in the manifest.

    as_of: the table's data completeness date; defaults to the run's "as_of" parameter."""
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        raise ValueError(f"dataset name must be snake_case: {name!r}")
    df = _frame(rows)
    if df.empty:
        raise ValueError(f"{name}: no rows")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.parquet"
    df.to_parquet(path, index=False)

    run = params()
    manifest = read_manifest()
    manifest["params"] = {k: _clean(v) for k, v in run.items()}
    manifest["tables"][name] = {
        "path": path.name,
        "grain": grain,
        "columns": {c: _col_type(df[c]) for c in df.columns},
        "rows": int(len(df)),
        "as_of": str(as_of or _clean(run.get("as_of")) or ""),
        "source": source,
        "script": script or Path(inspect.stack()[1].filename).name,   # which pipeline script wrote it
    }
    if description:
        manifest["tables"][name]["description"] = description
    write_manifest(manifest)
    print(f"  wrote {name}.parquet: {len(df):,} rows, {path.stat().st_size / 1e6:.2f} MB", flush=True)
    return path
