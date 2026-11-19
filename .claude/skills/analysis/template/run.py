#!/usr/bin/env python3
"""Run and build this report. Do not edit. Do not read unless a command ended in a Python
traceback (not a STOP: line) whose last lines are in this file.

  python run.py                  run every analytic; print its question, metrics and tables
  python run.py NAME [NAME ...]  run only those analytics
  python run.py report           run what the report uses and build <folder>.html
  python run.py text             print the report as plain text (for a cold read)
  python run.py shot [OUT.png]   screenshot the built report with Edge or Chrome
  python run.py data NAME [TABLE] [--json] [--out FILE]
                                 one table of an analytic (or TABLE=metrics) as CSV or JSON
  --refresh                      pull sources listed in KEEP again

Sources and tables are held in memory for one run. Nothing is written except the report,
CSV files a section exports, sources listed in KEEP (saved in data/), and a --out file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import html
import importlib.util
import json
import math
import re
import string
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEEP_DIR = ROOT / "data"
ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
NUM_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?[%KMB]?(?![\w])")
SECTION_KEYS = {"analytic", "title", "bullets", "chart", "table", "kpis", "layout", "note", "export"}
CHART_KEYS = {"type", "table", "x", "y", "axis", "x_axis", "format", "highlight", "sort", "top",
              "names", "height", "title", "labels", "ref"}
CHART_TYPES = ("bar", "hbar", "line", "stack", "scatter")
TABLE_KEYS = {"table", "columns", "format", "top", "title"}
TABLE_MAX_ROWS = 200


class Stop(Exception):
    """A problem the author must fix. Printed as one STOP: line, no traceback."""


# ------------------------------------------------------------------ loading

def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_report():
    p = ROOT / "report.py"
    if not p.exists():
        raise Stop("report.py is missing")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    r = _load(p, "report_settings")
    for f in ("TITLE", "QUESTION"):
        if not str(getattr(r, f, "") or "").strip():
            raise Stop(f"report.py: {f} is missing or empty")
        if "TODO" in str(getattr(r, f)):
            raise Stop(f"report.py: {f} still says TODO")
    r.SOURCES = getattr(r, "SOURCES", None) or {}
    r.PARAMS = getattr(r, "PARAMS", None) or {}
    r.KEEP = list(getattr(r, "KEEP", None) or [])
    r.ANSWER = getattr(r, "ANSWER", None) or {}
    r.SECTIONS = list(getattr(r, "SECTIONS", None) or [])
    r.ANALYTICS = str(getattr(r, "ANALYTICS", "analytics") or "analytics")
    if not isinstance(r.SOURCES, dict):
        raise Stop("report.py: SOURCES must be a dict of name -> file or function")
    for name in list(r.SOURCES) + r.KEEP:
        if not NAME_RE.match(str(name)):
            raise Stop(f"report.py: source name '{name}' must be lower_snake_case")
    for name in r.KEEP:
        if name not in r.SOURCES:
            raise Stop(f"report.py: KEEP names '{name}', which is not in SOURCES")
    return r


def load_analytics(rep) -> dict:
    """name -> (function, file shown in the report). Every public function in every .py file."""
    folder = (ROOT / rep.ANALYTICS).resolve()
    if not folder.is_dir():
        raise Stop(f"report.py: ANALYTICS folder '{rep.ANALYTICS}' does not exist")
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))  # so analytics can import a _helpers.py beside them
    found = {}
    for p in sorted(folder.glob("*.py")):
        if p.name.startswith("_"):
            continue
        mod = _load(p, f"analytics_{p.stem}")
        defaults = getattr(mod, "DEFAULTS", None) or {}   # shared thresholds and periods; PARAMS override
        if not isinstance(defaults, dict):
            raise Stop(f"{rep.ANALYTICS}/{p.name}: DEFAULTS must be a dict")
        for name, fn in vars(mod).items():
            if name.startswith("_") or not callable(fn) or getattr(fn, "__module__", None) != mod.__name__:
                continue
            if not isinstance(fn, type(_load)):
                continue
            if name in found:
                raise Stop(f"two analytics are named '{name}' ({found[name][1]} and {p.name})")
            found[name] = (fn, f"{rep.ANALYTICS.rstrip('/')}/{p.name}", defaults)
    if not found:
        raise Stop(f"no analytic functions in {rep.ANALYTICS}/")
    return found


# ------------------------------------------------------------------ sources

class Sources:
    """Analytics call src("name"). Each source is read once per run and held in memory."""

    def __init__(self, rep, refresh: bool):
        self.rep, self.refresh = rep, refresh
        self.cache: dict = {}
        self.used: dict = {}

    def __call__(self, name: str):
        import pandas as pd
        if name in self.cache:
            return self.cache[name].copy()
        if name not in self.rep.SOURCES:
            raise Stop(f"an analytic asked for source '{name}', but report.py SOURCES only has: "
                       f"{', '.join(self.rep.SOURCES) or 'nothing'}")
        spec = self.rep.SOURCES[name]
        kept = KEEP_DIR / f"{name}.parquet"
        note = ""
        if name in self.rep.KEEP and kept.exists() and not self.refresh:
            df = pd.read_parquet(kept)
            note = "kept copy from " + dt.datetime.fromtimestamp(kept.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {name}: using the {note} (--refresh to pull again)", file=sys.stderr, flush=True)
        else:
            df = self._read(name, spec)
            if name in self.rep.KEEP:
                KEEP_DIR.mkdir(exist_ok=True)
                df.to_parquet(kept, index=False)
                note = "kept copy from " + now()
        label = getattr(spec, "__name__", "function") + "()" if callable(spec) else Path(str(spec)).name
        self.cache[name] = df
        self.used[name] = {"from": label, "rows": int(len(df)), "note": note}
        return df.copy()

    def _read(self, name, spec):
        import pandas as pd
        if callable(spec):
            df = spec()
        else:
            path = Path(str(spec))
            path = path if path.is_absolute() else ROOT / path
            if not path.exists():
                raise Stop(f"source '{name}': file not found: {spec}")
            ext = path.suffix.lower()
            if ext == ".sql":
                run_query = getattr(self.rep, "run_query", None)
                if run_query is None:
                    raise Stop(f"source '{name}' is a .sql file, but report.py has no run_query(sql) function")
                sql = path.read_text(encoding="utf-8")
                for k, v in self.rep.PARAMS.items():
                    sql = sql.replace("{" + str(k) + "}", str(v))
                print(f"  pulling {name} ...", file=sys.stderr, flush=True)
                df = run_query(sql)
            elif ext == ".csv":
                df = pd.read_csv(path)
            elif ext in (".tsv", ".txt"):
                df = pd.read_csv(path, sep="\t")
            elif ext == ".parquet":
                df = pd.read_parquet(path)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(path)
            else:
                raise Stop(f"source '{name}': unsupported file type {ext} (.csv .tsv .parquet .xlsx .sql)")
        if not isinstance(df, pd.DataFrame):
            raise Stop(f"source '{name}' did not give a pandas DataFrame")
        return df


# ------------------------------------------------------------------ analytics

def scalar(v):
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
        except (ValueError, TypeError):
            pass
    if hasattr(v, "isoformat") and not isinstance(v, (str, int, float)):
        s = v.isoformat()
        return s[:10] if s.endswith("T00:00:00") or len(s) == 10 else s
    return v


class Runner:
    def __init__(self, rep, analytics: dict, refresh: bool):
        self.rep, self.analytics = rep, analytics
        self.src = Sources(rep, refresh)
        self.results: dict = {}

    def all_params(self) -> dict:
        """Every analytics file's DEFAULTS, then the report's PARAMS on top."""
        merged = {}
        for _, _, d in self.analytics.values():
            merged.update(d)
        return {**merged, **self.rep.PARAMS}

    def run(self, name: str) -> dict:
        import pandas as pd
        if name in self.results:
            return self.results[name]
        if name not in self.analytics:
            raise Stop(f"no analytic named '{name}'. Analytics: {', '.join(self.analytics)}")
        fn, where, defaults = self.analytics[name]
        print(f"  running {name} ...", file=sys.stderr, flush=True)
        try:
            out = fn(self.src, {**defaults, **self.rep.PARAMS})
        except Stop:
            raise
        except Exception:
            traceback.print_exc()
            raise Stop(f"{where}: {name}() failed (traceback above)")
        if not isinstance(out, dict):
            raise Stop(f"{where}: {name}() must return a dict with question, tables, metrics, notes")
        extra = set(out) - {"question", "tables", "metrics", "notes"}
        if extra:
            raise Stop(f"{where}: {name}() returned unknown keys {sorted(extra)}; "
                       "allowed: question, tables, metrics, notes")
        q = str(out.get("question") or "").strip()
        if not q or "TODO" in q:
            raise Stop(f"{where}: {name}() needs a 'question' (one plain sentence)")
        tables = out.get("tables") or {}
        metrics = out.get("metrics") or {}
        for t, df in tables.items():
            if not NAME_RE.match(str(t)):
                raise Stop(f"{where}: {name}() table name '{t}' must be lower_snake_case")
            if isinstance(df, pd.Series):
                df = tables[t] = df.reset_index()
            if not isinstance(df, pd.DataFrame):
                raise Stop(f"{where}: {name}() table '{t}' is not a DataFrame")
        clean = {}
        for m, v in metrics.items():
            if not NAME_RE.match(str(m)):
                raise Stop(f"{where}: {name}() metric name '{m}' must be lower_snake_case")
            v = scalar(v)
            if not (v is None or isinstance(v, (int, float, str, bool))):
                raise Stop(f"{where}: {name}() metric '{m}' must be one value, not {type(v).__name__}")
            clean[m] = v
        res = {"name": name, "where": where, "question": q, "tables": tables, "metrics": clean,
               "notes": str(out.get("notes") or "").strip()}
        self.results[name] = res
        return res


# ------------------------------------------------------------------ figures in text

def fmt_value(v, spec: str = "") -> str:
    """Python format specs, plus a leading $, 'short' (4.1M, 820K) and 'abs' (drop the sign)."""
    v = scalar(v)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return format(str(v), spec) if spec and not spec.startswith("$") else str(v)
    cur = spec.startswith("$")
    spec = spec[1:] if cur else spec
    if cur and "%" in spec:
        raise Stop(f"format '${spec}' mixes $ and %. Use one: '$short' or '.0%'")
    if "abs" in spec:
        v, spec = abs(v), spec.replace("abs", "")
    neg, a = v < 0, abs(v)
    if "short" in spec:
        unit = ""
        for size, u in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
            if a >= size:
                a, unit = a / size, u
                break
        s = f"{a:.1f}".removesuffix(".0") if a < 10 else f"{a:,.0f}"
        s += unit
    elif spec:
        s = format(a, spec)
    elif isinstance(v, int) and 1900 <= v <= 2099:
        s = str(v)                                   # a year: no thousands comma
    else:
        s = f"{a:,.0f}" if isinstance(a, int) or (float(a).is_integer() and a >= 1000) else f"{a:,.2f}"
    return ("-" if neg and s.strip("0.,%$KMB") else "") + ("$" if cur else "") + s


class _NS:
    def __init__(self, label: str, values: dict):
        self._label, self._values = label, values

    def get(self, key):
        if key not in self._values:
            raise Stop(f"{self._label} has no metric '{key}'. It has: {', '.join(self._values) or 'none'}")
        return self._values[key]


class Filler(string.Formatter):
    """Fills {analytic.metric:spec}, {params.x} and, inside a section, {metric} of its own analytic."""

    def __init__(self, runner: Runner):
        super().__init__()
        self.runner = runner
        self.own: dict = {}
        self.own_name = ""
        nums = [v for v in runner.all_params().values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        self.param_nums = [float(v) for v in nums]

    def get_field(self, field_name, args, kwargs):
        parts = field_name.split(".")
        if len(parts) == 1:
            if parts[0] in self.own:
                return self.own[parts[0]], field_name
            if not self.own_name:  # in ANSWER: name the analytic that has this metric
                names = [s.get("analytic") for s in self.runner.rep.SECTIONS if isinstance(s, dict)]
                has = [n for n in dict.fromkeys(names) if n in self.runner.analytics
                       and parts[0] in self.runner.run(n)["metrics"]]
                if has:
                    raise Stop(f"ANSWER needs the analytic name: write {{{has[0]}.{field_name}}}")
            hint = f" ({self.own_name} has: {', '.join(self.own) or 'none'})" if self.own_name else ""
            raise Stop(f"'{{{field_name}}}' is not a metric{hint}. Use {{analytic.metric}} for another analytic")
        if len(parts) != 2:
            raise Stop(f"'{{{field_name}}}': use {{analytic.metric}} or {{params.name}}")
        head, key = parts
        if head == "params":
            return _NS("PARAMS or DEFAULTS", self.runner.all_params()).get(key), field_name
        res = self.runner.run(head)
        return _NS(f"analytic '{head}'", res["metrics"]).get(key), field_name

    def format_field(self, value, format_spec):
        return fmt_value(value, format_spec)

    def fill(self, text: str, where: str, warns: list, check: bool = True) -> str:
        text = str(text)
        try:
            out = self.format(text)
        except Stop as e:
            raise Stop(f"{where}: {e}")
        except (ValueError, IndexError, KeyError) as e:
            raise Stop(f"{where}: cannot fill '{text}': {e}")
        if check:
            bad = [t for t in NUM_RE.findall(re.sub(r"\{[^{}]*\}", " ", text)) if not self._allowed(t)]
            if bad:
                warns.append(f"{where}: typed {', '.join(bad)}. Pull results from a metric; "
                             "a threshold must equal a PARAMS value")
        return out

    def _allowed(self, token: str) -> bool:
        """Years 1900-2099, and numbers equal to a PARAMS value (5000 = $5,000, 0.25 = 25%)."""
        t = token.replace("$", "").replace(",", "")
        if re.fullmatch(r"(19|20)\d\d", t):
            return True
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "%": 0.01}.get(t[-1:], 1)
        try:
            v = float(t.rstrip("KMB%")) * mult
        except ValueError:
            return False
        return any(math.isclose(v, p, rel_tol=1e-9, abs_tol=1e-12) for p in self.param_nums)

    def refs(self, text: str) -> list[str]:
        return [f for _, f, _, _ in string.Formatter().parse(str(text)) if f]


def rich(text: str) -> str:
    """Escape, then **bold** lead-ins."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))


# ------------------------------------------------------------------ charts and tables

def jsonable(o):
    import numpy as np
    import pandas as pd
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (pd.Series, pd.Index, np.ndarray)):
        return jsonable(o.tolist())
    if isinstance(o, pd.DataFrame):
        return jsonable(o.values.tolist())
    o = scalar(o)
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if o is None or isinstance(o, (str, bool, int, float)):
        return o
    try:
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    return str(o)


def pretty(col: str) -> str:
    s = str(col).replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def chart_option(spec: dict, res: dict, where: str) -> dict:
    """Shorthand chart -> ECharts option. Colours, fonts and axes are styled by page.html."""
    bad = set(spec) - CHART_KEYS
    if bad:
        raise Stop(f"{where}: chart has unknown keys {sorted(bad)}; allowed: {', '.join(sorted(CHART_KEYS))}")
    kind = spec.get("type", "bar")
    if kind not in CHART_TYPES:
        raise Stop(f"{where}: chart type '{kind}' is not one of {', '.join(CHART_TYPES)}. "
                   "Anything else: a function returning an ECharts option (references/charts.md)")
    df = table_of(res, spec.get("table"), where)
    x = spec.get("x") or df.columns[0]
    ys = spec.get("y") or [c for c in df.columns if c != x][:1]
    ys = [ys] if isinstance(ys, str) else list(ys)
    for c in [x, *ys]:
        if c not in df.columns:
            raise Stop(f"{where}: column '{c}' is not in table '{spec.get('table')}'. "
                       f"It has: {', '.join(map(str, df.columns))}")
    names = spec.get("names") or {}
    if spec.get("sort", kind == "hbar"):
        df = df.sort_values(ys[0], ascending=False)
    if spec.get("top"):
        df = df.head(int(spec["top"]))
    o: dict = {"format": spec.get("format", "")}
    if o["format"].startswith("$") and "%" in o["format"]:
        raise Stop(f"{where}: chart format '{o['format']}' mixes $ and %. Use one: '$short' or '.0%'")
    if kind == "scatter":
        o["xAxis"] = {"type": "value", "name": spec.get("x_axis", pretty(x)), "scale": True}
        o["yAxis"] = {"type": "value", "name": spec.get("axis", pretty(ys[0])), "scale": True}
        o["series"] = [{"type": "scatter", "name": names.get(y, pretty(y)), "symbolSize": 7,
                        "data": jsonable(df[[x, y]])} for y in ys]
        return o
    cats = jsonable(df[x].astype(str))
    hl = spec.get("highlight")
    hl = [str(h) for h in ([hl] if isinstance(hl, (str, int)) else (hl or []))]
    single = len(ys) == 1
    labels = spec.get("labels", single and kind in ("bar", "hbar") and len(df) <= 15)
    series = []
    for y in ys:
        vals = jsonable(df[y])
        if single and hl and kind in ("bar", "hbar"):
            vals = [{"value": v, "itemStyle": {"color": "@orange"}} if str(c) in hl else v
                    for c, v in zip(cats, vals)]
        s = {"type": "line" if kind == "line" else "bar", "name": names.get(y, pretty(y)), "data": vals}
        if kind == "stack":
            s["stack"] = "total"
        if labels:
            s["label"] = {"show": True, "position": "right" if kind == "hbar" else "top"}
        series.append(s)
    axis_key = "yAxis" if kind == "hbar" else "xAxis"
    lines = []
    hl = [h for h in hl if h in cats]
    if hl and kind == "line":            # a wide pale line marks the category
        lines += [{axis_key: h, "label": {"show": False},
                   "lineStyle": {"color": "@orange", "type": "solid", "width": 14, "opacity": 0.18}} for h in hl]
    elif hl and not single:              # stacks and several series: shade the band
        series[0]["markArea"] = {"silent": True, "itemStyle": {"color": "@orange", "opacity": 0.13},
                                 "data": [[{axis_key: h}, {axis_key: h}] for h in hl]}
    ref = spec.get("ref")
    if ref is not None:
        val, lab = (ref, "") if isinstance(ref, (int, float)) else (ref[0], ref[1] if len(ref) > 1 else "")
        text = (f"{lab} " if lab else "") + fmt_value(val, spec.get("format", ""))
        lines.append({("xAxis" if kind == "hbar" else "yAxis"): val,
                      "lineStyle": {"color": "@navy", "type": "dashed", "width": 1.5},
                      "label": {"formatter": text, "color": "@navy",
                                "position": "start" if kind == "hbar" else "insideEndTop"}})
    if lines:
        series[0]["markLine"] = {"silent": True, "symbol": "none", "data": lines}
    value_axis = {"type": "value", "name": spec.get("axis", pretty(ys[0]) if single else "")}
    cat_axis = {"type": "category", "data": cats}
    if kind == "hbar":
        cat_axis["inverse"] = True
        o["xAxis"], o["yAxis"] = value_axis, cat_axis
    else:
        o["xAxis"], o["yAxis"] = cat_axis, value_axis
    o["series"] = series
    return o


def table_of(res: dict, name, where: str):
    tables = res["tables"]
    if name is None:
        if len(tables) != 1:
            raise Stop(f"{where}: say which table ('table': one of {', '.join(tables) or 'none'})")
        name = next(iter(tables))
    if name not in tables:
        raise Stop(f"{where}: analytic '{res['name']}' has no table '{name}'. It has: {', '.join(tables) or 'none'}")
    return tables[name]


def table_spec(spec, res: dict, where: str):
    """-> (DataFrame with display headings, {heading: format})"""
    if isinstance(spec, str):
        spec = {"table": spec}
    bad = set(spec) - TABLE_KEYS
    if bad:
        raise Stop(f"{where}: table has unknown keys {sorted(bad)}; allowed: {', '.join(sorted(TABLE_KEYS))}")
    df = table_of(res, spec.get("table"), where)
    cols = spec.get("columns") or {c: pretty(c) for c in df.columns}
    if isinstance(cols, list):
        cols = {c: pretty(c) for c in cols}
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise Stop(f"{where}: table columns {missing} not found. It has: {', '.join(map(str, df.columns))}")
    df = df[list(cols)].rename(columns=cols)
    if spec.get("top"):
        df = df.head(int(spec["top"]))
    if len(df) > TABLE_MAX_ROWS:
        raise Stop(f"{where}: {len(df)} rows. Show the top rows ('top': 15) and export the full table")
    fmts = {cols[c]: f for c, f in (spec.get("format") or {}).items() if c in cols}
    return df, fmts


def render_table(df, fmts: dict) -> str:
    import pandas as pd
    head, rows = [], []
    for c in df.columns:
        num = pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
        head.append(f'<th{" class=num" if num else ""}>{html.escape(str(c))}</th>')
    for row in df.itertuples(index=False, name=None):
        tds = []
        for c, v in zip(df.columns, row):
            v = scalar(v)
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            text = fmt_value(v, fmts.get(c, "")) if num or fmts.get(c) else ("" if v is None else str(v))
            raw = "" if v is None else html.escape(str(v), quote=True)
            tds.append(f'<td{" class=num" if num else ""} data-v="{raw}">{html.escape(text)}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="tablewrap"><table class="data"><thead><tr>{"".join(head)}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


# ------------------------------------------------------------------ the report

def kpis_html(kpis, filler: Filler, where: str, warns: list, text: list, values: list) -> str:
    """values: figures already shown in the answer; a section repeating one gets a check: line."""
    tiles = []
    for i, k in enumerate(kpis or []):
        if not isinstance(k, (list, tuple)) or len(k) not in (2, 3):
            raise Stop(f"{where}: kpi {i + 1} must be (\"Label\", \"{{metric}}\") or (label, value, note)")
        label = filler.fill(k[0], f"{where} kpi {i + 1}", warns, check=False)
        value = filler.fill(k[1], f"{where} kpi {i + 1}", warns)
        note = filler.fill(k[2], f"{where} kpi {i + 1}", warns) if len(k) == 3 and k[2] else ""
        if where != "ANSWER" and value in values:
            warns.append(f"{where} kpi {i + 1}: {value} repeats a figure in the answer")
        values.append(value)
        text.append(f"  [figure] {label}: {value}" + (f" ({note})" if note else ""))
        tiles.append(f'<div class="kpi"><div class="kpi-value">{html.escape(value)}</div>'
                     f'<div class="kpi-label">{html.escape(label)}</div>'
                     + (f'<div class="kpi-note">{rich(note)}</div>' if note else "") + "</div>")
    return f'<div class="kpis n{len(tiles)}">{"".join(tiles)}</div>' if tiles else ""


def bullets_html(bullets, filler: Filler, where: str, warns: list, text: list, cls: str = "") -> str:
    if isinstance(bullets, str):
        bullets = [bullets]
    lis = []
    for i, b in enumerate(bullets or []):
        t = filler.fill(b, f"{where} bullet {i + 1}", warns)
        text.append(f"  - {t.replace('**', '')}")
        lis.append(f"<li>{rich(t)}</li>")
    return f'<ul class="bullets{cls}">{"".join(lis)}</ul>' if lis else ""


def chart_summary(o: dict) -> list[str]:
    lines = []
    axes = [a for k in ("xAxis", "yAxis") for a in ([o.get(k)] if isinstance(o.get(k), dict) else (o.get(k) or []))]
    cats = next((a.get("data") for a in axes if isinstance(a, dict) and a.get("data") is not None), None)
    names = [str(a["name"]) for a in axes if isinstance(a, dict) and a.get("name")]
    if names:
        lines.append("    axes: " + ", ".join(names))
    for s in (o.get("series") or []):
        if not isinstance(s, dict):
            continue
        vals = [v.get("value") if isinstance(v, dict) else v for v in (s.get("data") or [])]
        if cats and len(cats) == len(vals) and len(cats) <= 24:
            pts = ", ".join(f"{c}: {fmt_value(v, o.get('format', ''))}" for c, v in zip(cats, vals))
            lines.append(f"    {s.get('name') or 'values'}: {pts}")
        else:
            lines.append(f"    {s.get('name') or 'values'}: {len(vals)} points")
    return lines


def build(rep, runner: Runner, write: bool = True):
    if not rep.SECTIONS:
        raise Stop("report.py: SECTIONS is empty. Agree the answer and its sections first, then list them")
    warns: list = []
    text: list = [rep.TITLE, rep.QUESTION, ""]
    filler = Filler(runner)
    options: dict = {}

    # answer
    ans = rep.ANSWER
    bad = set(ans) - {"headline", "basis", "bullets", "kpis"}
    if bad:
        raise Stop(f"report.py ANSWER: unknown keys {sorted(bad)}; allowed: headline, basis, bullets, kpis")
    if not str(ans.get("headline") or "").strip():
        raise Stop("report.py ANSWER: write the headline (one sentence) before building")
    if not str(ans.get("basis") or "").strip():
        raise Stop("report.py ANSWER: 'basis' is empty. One line: which date, compared with what, "
                   "what is excluded, data through when")
    headline = filler.fill(ans["headline"], "ANSWER headline", warns)
    basis = filler.fill(ans["basis"], "ANSWER basis", warns)
    text += ["THE ANSWER", f"  {headline}", f"  basis: {basis}"]
    shown: list = []
    a_bul = bullets_html(ans.get("bullets"), filler, "ANSWER", warns, text)
    a_kpi = kpis_html(ans.get("kpis"), filler, "ANSWER", warns, text, shown)
    answer = ('<section class="answer"><div class="label">The answer</div>'
              f'<p class="headline">{rich(headline)}</p><p class="basis">{rich(basis)}</p>'
              f'{a_bul}{a_kpi}</section>')

    # sections
    secs_html, contents, method = [], [], []
    exported = []
    for i, sec in enumerate(rep.SECTIONS, 1):
        where = f"SECTIONS[{i - 1}]"
        if not isinstance(sec, dict):
            raise Stop(f"report.py {where}: must be a dict")
        bad = set(sec) - SECTION_KEYS
        if bad:
            raise Stop(f"report.py {where}: unknown keys {sorted(bad)}; allowed: {', '.join(sorted(SECTION_KEYS))}")
        if not sec.get("analytic"):
            raise Stop(f"report.py {where}: needs 'analytic' (the function it shows)")
        res = runner.run(sec["analytic"])
        where = f"section {i} ({res['name']})"
        filler.own, filler.own_name = res["metrics"], f"analytic '{res['name']}'"
        title = filler.fill(sec.get("title") or "", f"{where} title", warns)
        if not title:
            raise Stop(f"{where}: needs a 'title' (the finding, as a sentence)")
        text += ["", f"SECTION {i}: {title}", f"  question: {res['question']}"]
        kpi = kpis_html(sec.get("kpis"), filler, where, warns, text, shown)
        layout = sec.get("layout", "side")
        if layout not in ("side", "wide"):
            raise Stop(f"{where}: layout must be 'side' (chart beside bullets) or 'wide' (chart above)")
        has_chart = sec.get("chart") is not None
        bul = bullets_html(sec.get("bullets"), filler, where, warns, text,
                           " cols" if layout == "wide" and has_chart else "")
        fig = ""
        if has_chart:
            ch = sec["chart"]
            if callable(ch):
                try:
                    opt = ch(res["tables"])
                except Exception:
                    traceback.print_exc()
                    raise Stop(f"{where}: the chart function failed (traceback above)")
                if not isinstance(opt, dict):
                    raise Stop(f"{where}: a chart function must return an ECharts option dict")
                opt = dict(opt)
                cap, h = str(opt.pop("caption", "") or ""), int(opt.pop("height", 0) or 0)
            elif isinstance(ch, dict):
                if isinstance(ch.get("highlight"), str) and "{" in ch["highlight"]:
                    ch = {**ch, "highlight": filler.fill(ch["highlight"], f"{where} highlight", warns, check=False)}
                opt = chart_option(ch, res, where)
                cap, h = ch.get("title", ""), int(ch.get("height", 0) or 0)
            else:
                raise Stop(f"{where}: 'chart' must be a dict (shorthand) or a function of the tables")
            cid = f"c{i}"
            options[cid] = jsonable(opt)
            if not h and isinstance(ch, dict) and ch.get("type") == "hbar":
                n = len((opt.get("yAxis") or {}).get("data") or [])
                h = max(170, min(460, 70 + 44 * n))  # height follows the number of bars
            h = h or (340 if layout == "wide" else 300)
            cap = filler.fill(cap, f"{where} chart title", warns, check=False) if cap else ""
            text.append(f"  [chart] {cap or 'untitled'}")
            text += chart_summary(options[cid])
            note = filler.fill(sec["note"], f"{where} note", warns) if sec.get("note") else ""
            if note:
                text.append(f"    note: {note}")
            fig = ('<figure class="chart-card">' + (f"<figcaption>{html.escape(cap)}</figcaption>" if cap else "")
                   + f'<div class="chart" data-chart="{cid}" style="height:{h}px"></div>'
                   + (f'<p class="note">{rich(note)}</p>' if note else "") + "</figure>")
        tbl = ""
        if sec.get("table") is not None:
            tspec = sec["table"]
            df, fmts = table_spec(tspec, res, where)
            cap = tspec.get("title", "") if isinstance(tspec, dict) else ""
            cap = filler.fill(cap, f"{where} table title", warns, check=False) if cap else ""
            tbl = ('<figure class="table-card">' + (f"<figcaption>{html.escape(cap)}</figcaption>" if cap else "")
                   + render_table(df, fmts) + "</figure>")
            text.append(f"  [table] {cap or 'untitled'}")
            text.append("    " + " | ".join(map(str, df.columns)))
            for row in df.head(15).itertuples(index=False, name=None):
                text.append("    " + " | ".join(fmt_value(v, fmts.get(c, "")) for c, v in zip(df.columns, row)))
            if not has_chart and sec.get("note"):
                note = filler.fill(sec["note"], f"{where} note", warns)
                tbl += f'<p class="note">{rich(note)}</p>'
        links = []
        for t in sec.get("export") or []:
            if t not in res["tables"]:
                raise Stop(f"{where}: export names '{t}', which {res['name']}() did not return")
            fn = f"{ROOT.name}_{t}.csv"
            if write:
                res["tables"][t].to_csv(ROOT / fn, index=False)
            exported.append(fn)
            links.append(f'<a href="{html.escape(fn)}">{html.escape(fn)}</a> '
                         f'({len(res["tables"][t]):,} rows)')
            text.append(f"  [file] {fn}")
        exp = f'<p class="export">Full list, saved beside this report: {"; ".join(links)}</p>' if links else ""
        if not (bul or fig or tbl or kpi):
            raise Stop(f"{where}: add bullets, a chart or a table")
        body_cls = "side" if (layout == "side" and fig and bul) else "stack"
        first, second = (bul, fig) if body_cls == "side" else (fig, bul)
        secs_html.append(
            f'<section class="sec" id="s{i}"><div class="sec-head"><span class="num">{i:02d}</span>'
            f'<h2>{rich(title)}</h2></div>'
            f'{kpi}<div class="body {body_cls}">{first}{second}</div>{tbl}{exp}</section>')
        contents.append(f'<a href="#s{i}"><span class="num">{i:02d}</span>{html.escape(title)}</a>')
        m = f"<li><b>{i:02d}</b> <code>{html.escape(res['name'])}</code> in {html.escape(res['where'])}: "
        m += html.escape(res["question"]) + (f" <i>{html.escape(res['notes'])}</i>" if res["notes"] else "")
        method.append(m + "</li>")
    filler.own, filler.own_name = {}, ""

    # footer
    srcs = "".join(f"<li><b>{html.escape(n)}</b>: {html.escape(u['from'])}, {u['rows']:,} rows"
                   + (f", {html.escape(u['note'])}" if u["note"] else "") + "</li>"
                   for n, u in runner.src.used.items()) or "<li>none read</li>"
    params = "; ".join(f"{k} = {v}" for k, v in runner.all_params().items()) or "none"
    footer = ('<h3>How this was made</h3><div class="foot-grid">'
              f'<div><h4>Sources</h4><ul>{srcs}</ul><h4>Parameters</h4><p>{html.escape(params)}</p></div>'
              f'<div><h4>Analytics behind each section</h4><ul>{"".join(method)}</ul></div></div>'
              f'<p class="foot-line">Every figure in the text is pulled from these analytics when the report '
              f'is built ({now()}). Rerun: <code>python run.py report</code> in this folder.</p>')

    if not write:
        return "\n".join(text), warns
    page_file = ROOT / "page.html"
    if not page_file.exists():
        raise Stop("page.html is missing. Copy it from the analysis skill's template/")
    page = page_file.read_text(encoding="utf-8")
    lost = [t for t in ("__ANSWER__", "__SECTIONS__", "__CHARTS__", "__ECHARTS__") if t not in page]
    if lost:
        raise Stop(f"page.html has lost {', '.join(lost)}. Put them back; the build fills them in")
    lib = ROOT / "echarts.min.js"
    echarts = ("<script>" + lib.read_text(encoding="utf-8").replace("</script", "<\\/script") + "</script>"
               if lib.exists() else f'<script src="{ECHARTS_CDN}"></script>')
    toc = (f'<nav class="contents"><div class="label">In this report</div>{"".join(contents)}</nav>'
           if len(contents) >= 3 else "")
    today = dt.date.today()
    date = f"{today.day} {today:%B %Y}"
    reader = str(getattr(rep, "FOR", "") or "").strip()
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower())  # noqa: E731
    same = difflib.SequenceMatcher(None, norm(rep.TITLE), norm(rep.QUESTION)).ratio() >= 0.7
    for token, value in {
        "__TITLE__": html.escape(rep.TITLE), "__EYEBROW__": html.escape(f"For {reader} · {date}" if reader else date),
        "__SUBTITLE__": "" if same else f'<p class="question">{html.escape(rep.QUESTION)}</p>',
        "__QUESTION__": html.escape(rep.QUESTION),
        "__DATE__": date, "__ANSWER__": answer, "__CONTENTS__": toc,
        "__SECTIONS__": "\n".join(secs_html), "__FOOTER__": footer,
        "__CHARTS__": json.dumps(options).replace("</", "<\\/"), "__ECHARTS__": echarts,
    }.items():
        page = page.replace(token, value)
    out = ROOT / f"{ROOT.name}.html"
    out.write_text(page, encoding="utf-8")
    return out, warns


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ explore and main

def print_result(res: dict):
    import pandas as pd
    print(f"\n{res['name']}  ({res['where']})\n  {res['question']}")
    for m, v in res["metrics"].items():
        print(f"  {m} = {v!r}")
    for t, df in res["tables"].items():
        print(f"  table {t}: {len(df):,} rows x {len(df.columns)} columns")
        with pd.option_context("display.width", 160, "display.max_columns", 12):
            print("\n".join("    " + line for line in df.head(12).to_string(index=False).splitlines()))
    if res["notes"]:
        print(f"  notes: {res['notes']}")


def export_data(runner: Runner, args: list, as_json: bool, out: str | None) -> int:
    """data NAME [TABLE]: one table (or 'metrics') as CSV or JSON, to stdout or --out. Nothing else saved."""
    if not args or len(args) > 2:
        raise Stop("use: python run.py data NAME [TABLE] [--json] [--out FILE]")
    res = runner.run(args[0])
    name = args[1] if len(args) == 2 else None
    if name == "metrics":
        body = json.dumps(jsonable(res["metrics"]), indent=1) if as_json else \
            "metric,value\n" + "".join(f"{k},{jsonable(v)}\n" for k, v in res["metrics"].items())
    else:
        if name is None and len(res["tables"]) != 1:
            raise Stop(f"{args[0]} has tables: {', '.join(res['tables']) or 'none'} (and metrics). Name one")
        df = table_of(res, name, f"data {args[0]}")
        body = df.to_json(orient="records", date_format="iso", indent=1) if as_json else df.to_csv(index=False)
    if out:
        Path(out).write_text(body, encoding="utf-8", newline="")
        print(f"Wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(body)
    return 0


BROWSERS = [
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "~/AppData/Local/Google/Chrome/Application/chrome.exe",
    "~/AppData/Local/Microsoft/Edge/Application/msedge.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
BROWSER_NAMES = ["msedge", "microsoft-edge", "microsoft-edge-stable", "google-chrome", "google-chrome-stable",
                 "chrome", "chromium", "chromium-browser"]


def screenshot(rep, args: list) -> int:
    """shot [OUT.png]: the built report as a PNG, via headless Edge or Chrome."""
    import shutil
    import subprocess
    import tempfile
    page = ROOT / f"{ROOT.name}.html"
    if not page.exists():
        raise Stop(f"{page.name} is not built yet. Run `python run.py report` first")
    found = [p for p in (Path(b).expanduser() for b in BROWSERS) if p.is_file()]
    found += [Path(w) for w in (shutil.which(n) for n in BROWSER_NAMES) if w]
    if not found:
        raise Stop("no Edge or Chrome found (looked in the standard Windows, macOS and Linux install "
                   f"folders and on the path for {', '.join(BROWSER_NAMES)}). Open {page.name} by hand")
    out = Path(args[0]) if args else ROOT / f"{ROOT.name}_shot.png"
    out = out.resolve()
    out.unlink(missing_ok=True)
    tables = sum(1 for s in rep.SECTIONS if isinstance(s, dict) and s.get("table") is not None)
    height = 750 + 600 * len(rep.SECTIONS) + 450 * tables     # rough page height; spare space is blank
    profile = tempfile.mkdtemp(prefix="report-shot-")
    try:
        subprocess.run([str(found[0]), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--no-first-run", f"--user-data-dir={profile}", f"--window-size=1280,{height}",
                        "--virtual-time-budget=8000", f"--screenshot={out}", page.as_uri()],
                       capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(f"{found[0].name} did not finish the screenshot: {e}")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise Stop(f"{found[0].name} ran but wrote no screenshot to {out}")
    print(f"Screenshot: {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="*", help="nothing, analytic names, report, text, or data NAME [TABLE]")
    ap.add_argument("--refresh", action="store_true", help="pull sources listed in KEEP again")
    ap.add_argument("--json", action="store_true", help="with data: JSON instead of CSV")
    ap.add_argument("--out", help="with data: write to this file instead of printing")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        rep = load_report()
        runner = Runner(rep, load_analytics(rep), args.refresh)
        what = args.what
        if what[:1] == ["shot"]:
            return screenshot(rep, what[1:])
        if what[:1] == ["data"]:
            return export_data(runner, what[1:], args.json, args.out)
        if what in (["report"], ["text"]):
            out, warns = build(rep, runner, write=what == ["report"])
            if what == ["text"]:
                print(out)
            else:
                print(f"Report: {out}")
            for w in warns:
                print(f"  check: {w}")
            return 0
        names = what or list(runner.analytics)
        for n in names:
            print_result(runner.run(n))
        print("\nNothing saved. The report is `python run.py report`.")
        return 0
    except Stop as e:
        print(f"STOP: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
