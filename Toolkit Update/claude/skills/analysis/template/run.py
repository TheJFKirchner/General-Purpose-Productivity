#!/usr/bin/env python3
"""Run and build this report. Do not edit. Do not read unless a command ended in a Python
traceback (not a STOP: line) whose last lines are in this file.

  python run.py list             the registry: sections in order (file, visual, title, description),
                                 then sources with their columns
  python run.py                  run every section's analytic; print question, metrics, table columns
  python run.py NAME [NAME ...]  run only those (a section name or file id) [--rows N]
  python run.py report           build <folder>.html
  python run.py show ID          a library item's parts, the columns that fit them, an add-section to copy
  python run.py add-section NAME --use ID --source SRC --slot SLOT=COL[,COL] ...
        [--agg sum|mean|count] [--by COL] [--where COL=VALUE] [--desc "..."] [--bullets N] [--after N]
                                 copy a design-library chart, table or hero card into sections/sN_NAME.py
  python run.py add-section NAME --own chart|html --source SRC
                                 a blank section to draw your own visual in
  python run.py theme TH-02      put a design-library theme on page.html
  python run.py shot [OUT.png]   screenshot the built report with Edge or Chrome
  python run.py data NAME [TABLE] [--json] [--out FILE]
                                 one table of an analytic (or TABLE=metrics) as CSV or JSON;
                                 --out FILE.xlsx: a workbook, one sheet per table when TABLE is left out
  --refresh                      pull sources listed in KEEP again

Sources and tables are held in memory for one run. Nothing is written except the report,
CSV files a section exports, sources listed in KEEP (saved in data/), and a --out file.
Adding from the library and changing the theme need Node.js; building does not.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import difflib
import html
import importlib.util
import json
import math
import os
import re
import shutil
import string
import subprocess
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True   # no __pycache__ folders in the report
ROOT = Path(__file__).resolve().parent
KEEP_DIR = ROOT / "data"
ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
NUM_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?[%KMB]?(?![\w])")
LAYOUTS = ("side", "flip", "above", "below")
SAMPLE_WORDS = ("Sample values", "What is measured, the period and the basis", "What is counted, the period and the basis",
                "Heading: what", "Caption: the")


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
    r.SECTION_IDS = [str(s) for s in (getattr(r, "SECTIONS", None) or [])]
    if not isinstance(r.SOURCES, dict):
        raise Stop("report.py: SOURCES must be a dict of name -> file or function")
    for name in list(r.SOURCES) + r.KEEP:
        if not NAME_RE.match(str(name)):
            raise Stop(f"report.py: source name '{name}' must be lower_snake_case")
    for name in r.KEEP:
        if name not in r.SOURCES:
            raise Stop(f"report.py: KEEP names '{name}', which is not in SOURCES")
    return r


SECTIONS_DIR = ROOT / "sections"
SECTION_FILE_RE = re.compile(r"^s(\d+)_([a-z][a-z0-9_]*)$")
SECTION_ATTRS = {"TITLE": "title", "BULLETS": "bullets", "CHART": "chart", "HTML": "html", "KEY": "key",
                 "BASIS": "basis", "KPIS": "kpis", "LAYOUT": "layout", "EXPORT": "export", "HEIGHT": "height",
                 "DESCRIPTION": "description", "USE": "use", "DATA": "data", "SLOTS": "slots", "NAMES": "names",
                 "FORMAT": "format", "CSS": "css", "SCRIPT": "script",
                 "MOTION": "motion"}


def load_sections(rep) -> dict:
    """Each sections/sN_<name>.py is one block: DESCRIPTION, <name>(src, params), TITLE, BULLETS, CHART ...
    sections/_shared.py holds DEFAULTS and helpers. Returns name -> (function, file, DEFAULTS) and sets
    rep.SECTIONS (dicts, in report order) and rep.UNUSED (section files not in the order)."""
    if str(SECTIONS_DIR) not in sys.path:
        sys.path.insert(0, str(SECTIONS_DIR))  # so a section can `from _shared import ...`
    shared = SECTIONS_DIR / "_shared.py"
    defaults = (getattr(_load(shared, "_shared"), "DEFAULTS", None) or {}) if shared.exists() else {}
    if not isinstance(defaults, dict):
        raise Stop("sections/_shared.py: DEFAULTS must be a dict")
    found, secs = {}, {}
    for p in sorted(SECTIONS_DIR.glob("s*.py"), key=lambda p: (len(p.stem), p.stem)):
        m = SECTION_FILE_RE.match(p.stem)
        if not m:
            continue
        name = m.group(2)
        try:
            mod = _load(p, p.stem)
        except NameError as e:
            if re.search(r"'(true|false|null)'", str(e)):
                raise Stop(f"sections/{p.name}: write True, False and None (Python), not true, false, null")
            raise
        except SyntaxError as e:
            raise Stop(f"sections/{p.name} line {e.lineno}: {e.msg} (a bracket, comma or quote is off)")
        fn = getattr(mod, name, None)
        if not callable(fn):
            raise Stop(f"sections/{p.name} must define its analytic: def {name}(src, params)")
        if name in found:
            raise Stop(f"two section files are named '{name}' ({found[name][1]} and sections/{p.name})")
        found[name] = (fn, f"sections/{p.name}", defaults)
        sec = {"analytic": name, "file": p.name}
        sec.update({k: getattr(mod, a) for a, k in SECTION_ATTRS.items() if hasattr(mod, a)})
        secs[p.stem] = sec
    missing = [s for s in rep.SECTION_IDS if s not in secs]
    if missing:
        raise Stop(f"report.py SECTIONS names {', '.join(missing)}, but sections/ has: {', '.join(secs) or 'nothing'}")
    rep.SECTIONS = [secs[s] for s in rep.SECTION_IDS]
    rep.UNUSED = [s for s in secs if s not in rep.SECTION_IDS]
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
            path = Path(os.path.normpath(path if path.is_absolute() else ROOT / path))
            if not path.exists():
                raise Stop(f"source '{name}': file not found: {spec} (looked for {path}). Repoint it in report.py "
                           "SOURCES, relative to this report folder")
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
        m = SECTION_FILE_RE.match(name.removesuffix(".py"))
        name = m.group(2) if m and m.group(2) in self.analytics else name   # s2_paid_by_month -> paid_by_month
        if name in self.results:
            return self.results[name]
        if name not in self.analytics:
            raise Stop(f"no section or analytic named '{name}'. Sections: {', '.join(self.analytics) or 'none'}")
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
    """Python format specs, plus a leading + (always a sign), $, 'short' (4.1M, 820K) and 'abs' (drop the sign)."""
    v = scalar(v)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return format(str(v), spec) if spec and not spec.startswith(("$", "+")) else str(v)
    plus = spec.startswith("+")
    spec = spec[1:] if plus else spec
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
    sign = "-" if neg and s.strip("0.,%$KMB") else ("+" if plus and v > 0 and s.strip("0.,%$KMB") else "")
    return sign + ("$" if cur else "") + s


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
            bad = [t for t in NUM_RE.findall(re.sub(r"\{[^{}]*\}|&#?\w+;", " ", text)) if not self._allowed(t)]
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


def table_of(res: dict, name, where: str):
    tables = res["tables"]
    if name is None:
        if len(tables) != 1:
            raise Stop(f"{where}: say which table ('table': one of {', '.join(tables) or 'none'})")
        name = next(iter(tables))
    if name not in tables:
        raise Stop(f"{where}: analytic '{res['name']}' has no table '{name}'. It has: {', '.join(tables) or 'none'}")
    return tables[name]


# ------------------------------------------------------------------ design-library items: filling slots
# A Python copy of the design library's fill (item.js, AUTHORING.md "Adding an item to a project"), so a
# rebuild refills each copied item from its table with no Node. Charts: objects marked "slot" get their
# data from columns. HTML: data-rows repeats a row per table row; data-slot sets text, a class or a style.

VOID_RE = re.compile(r"^(area|base|br|col|embed|hr|img|input|link|meta|source|track|wbr)$", re.I)
TAG_RE = re.compile(r"<!--[\s\S]*?-->|<(/?)([a-zA-Z][\w-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>")
ATTR_RE = re.compile(r"([^\s=]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"']+))?")
STATES_RE = re.compile(r"^(good|bad|neutral|over|under|up|down|dn)$")


def h_parse(s: str) -> dict:
    root = {"tag": "#root", "attrs": [], "children": []}
    stack, last, pos = [root], 0, 0
    while True:
        m = TAG_RE.search(s, pos)
        if not m:
            break
        if m.start() > last:
            stack[-1]["children"].append(s[last:m.start()])
        last = pos = m.end()
        if m.group(0).startswith("<!--"):
            stack[-1]["children"].append({"comment": m.group(0)})
            continue
        tag = m.group(2).lower()
        if m.group(1):
            tags = [n["tag"] for n in stack]
            if tag in tags[1:]:
                del stack[len(tags) - 1 - tags[::-1].index(tag):]
            continue
        raw = m.group(3)
        node = {"tag": tag, "attrs": _attrs(re.sub(r"/\s*$", "", raw)), "children": []}
        stack[-1]["children"].append(node)
        if tag in ("script", "style"):
            end = s.lower().find(f"</{tag}", last)
            node["raw"] = s[last:end if end != -1 else len(s)]
            last = pos = len(s) if end == -1 else s.find(">", end) + 1
        elif not VOID_RE.match(tag) and not re.search(r"/\s*$", raw):
            stack.append(node)
    if last < len(s):
        stack[-1]["children"].append(s[last:])
    return root


def _attrs(s: str) -> list:
    out = []
    for m in ATTR_RE.finditer(s):
        v = m.group(2)
        out.append([m.group(1), None if v is None else re.sub(r"^[\"']|[\"']$", "", v)])
    return out


def is_el(n) -> bool:
    return isinstance(n, dict) and "tag" in n


def h_attr(n, k):
    for a, v in n.get("attrs") or []:
        if a == k:
            return "" if v is None else v
    return None


def h_set(n, k, v):
    if v is None:
        n["attrs"] = [a for a in n["attrs"] if a[0] != k]
        return
    for a in n["attrs"]:
        if a[0] == k:
            a[1] = v
            return
    n["attrs"].append([k, v])


def h_text(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def h_serialize(n) -> str:
    if isinstance(n, str):
        return n
    if "comment" in n:
        return n["comment"]
    inner = n["raw"] if "raw" in n else "".join(h_serialize(c) for c in n["children"])
    if n["tag"] == "#root":
        return inner
    attrs = "".join(f" {k}" if v is None else f' {k}="{v}"' for k, v in n["attrs"])
    return f"<{n['tag']}{attrs}>" if VOID_RE.match(n["tag"]) else f"<{n['tag']}{attrs}>{inner}</{n['tag']}>"


def h_walk(n, fn, parent=None):
    if not is_el(n):
        return
    if fn(n, parent) is False:
        return
    for c in list(n.get("children") or []):
        h_walk(c, fn, n)


def h_elements(n) -> list:
    return [c for c in n.get("children") or [] if is_el(c)]


def h_has_class(n, c) -> bool:
    return f" {c} " in f" {h_attr(n, 'class') or ''} "


class Fill:
    """One table's rows and a section's wiring: SLOTS (slot -> columns), NAMES and FORMAT (by column)."""

    def __init__(self, rows: list, smap: dict, known: set, names: dict | None = None, fmts: dict | None = None,
                 where: str = "", metrics: dict | None = None):
        self.rows, self.smap, self.known, self.metrics = rows, smap, known, metrics or {}
        self.names, self.fmts, self.where = names or {}, fmts or {}, where

    def label(self, c) -> str:
        return str(self.names.get(c) or pretty(c))

    def fmt(self, c) -> str:
        return str(self.fmts.get(c) or self.fmts.get("*") or "")

    def show(self, v, c) -> str:
        if v is None:
            return ""
        return fmt_value(v, self.fmt(c)) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)

    def need(self, c):
        if c not in self.known:
            raise Stop(f"{self.where}: SLOTS names '{c}', which is not a column of the table. "
                       f"It has: {', '.join(map(str, self.known)) or 'nothing'}")

    def column(self, c) -> list:
        self.need(c)
        v = [r.get(c) for r in self.rows]
        while v and v[-1] is None:
            v.pop()
        return v

    def figure(self, c):
        """A figure: the first value of a column, else the section's metric of that name, else the value as given."""
        if isinstance(c, str) and c in self.known:
            return next((v for v in self.column(c) if v is not None), None)
        if isinstance(c, str) and c in self.metrics:
            return self.metrics[c]
        return c


def slot_names(spec: str) -> list:
    return [s.strip().lstrip("=") for s in str(spec).split(":")[0].split(",")]   # "=value" follows value


def chart_marks(o) -> list:
    """[(object, parent, key)] for every object marked "slot", in order."""
    out = []

    def go(x, parent, key):
        if isinstance(x, list):
            for i, v in enumerate(x):
                go(v, x, i)
        elif isinstance(x, dict):
            if isinstance(x.get("slot"), str):
                out.append((x, parent, key))
            for k in list(x):
                go(x[k], x, k)
    go(o, None, None)
    return out


def _restyle(old, v):
    """Keep a sample entry's own style by position; drop its label text."""
    if not isinstance(old, dict) or "value" not in old:
        return v
    o = copy.deepcopy(old)
    o["value"] = v
    if isinstance(o.get("label"), dict):
        o["label"].pop("formatter", None)
        if not o["label"]:
            del o["label"]
    return o


def _drop_colour(o):
    for k in ("itemStyle", "lineStyle", "areaStyle", "endLabel", "label"):
        if isinstance(o.get(k), dict):
            o[k].pop("color", None)
            o[k].pop("borderColor", None)


AXIS_TYPES = ("category", "value", "time", "log")


def fill_chart(o: dict, f: Fill, first: bool = False, column_names: bool = False) -> dict:
    """Puts the columns into the chart's slots (as the library's item.js fill does). Returns {id(series): column}
    for formatting. first: as on adding (series names left to NAMES, the sample's fixed axis ranges dropped).
    A follower ("slot": "=value", a lollipop's dot) takes the value slot's first column and is not one of its series."""
    filled, done = {}, set()
    names = list(dict.fromkeys(n for m in chart_marks(o) for n in slot_names(m[0]["slot"])))

    def is_axis(m):
        return str(m[0].get("type") or "") in AXIS_TYPES

    def removable(m):
        return isinstance(m[1], list) and not is_axis(m)

    def remove(m):
        if removable(m) and any(x is m[0] for x in m[1]):
            m[1].remove(m[0])

    for name in names:
        ms = [m for m in chart_marks(o) if name in slot_names(m[0]["slot"])]
        cols = f.smap.get(name) or []
        if any(":" in m[0]["slot"] for m in ms):           # "target:yAxis": one property takes a figure
            for m in ms:
                prop = m[0]["slot"].split(":", 1)[1]
                if cols:
                    m[0][prop] = f.figure(cols[0])
                else:
                    remove(m)
            continue
        tup = [m for m in ms if len(slot_names(m[0]["slot"])) > 1]
        for m in tup:                                       # "x,y": rows of [x, y]; a row with an empty cell left out
            if id(m[0]) in done:
                continue
            done.add(id(m[0]))
            parts = slot_names(m[0]["slot"])
            if any(not f.smap.get(p) for p in parts):
                remove(m)
                continue
            for p in parts:
                f.need(f.smap[p][0])
            old = m[0].get("data") or []
            data = [[r.get(f.smap[p][0]) for p in parts] for r in f.rows]
            m[0]["data"] = [_restyle(old[i] if i < len(old) else None, t)
                            for i, t in enumerate(t for t in data if all(v is not None for v in t))]
            if first and not column_names:
                m[0].pop("name", None)
        if tup and len(tup) == len(ms):
            continue
        single = [m for m in ms if len(slot_names(m[0]["slot"])) == 1]
        for m in single:                                    # an axis (panels share one) takes the first column
            if is_axis(m) and cols:
                col = f.column(cols[0])
                m[0]["data"] = list(dict.fromkeys(str(v) for v in col if v is not None)) \
                    if m[0].get("type") == "category" else col
        for m in single:                                    # a follower takes the first column too
            if not str(m[0]["slot"]).startswith("="):
                continue
            if not cols:
                remove(m)
                continue
            old = m[0].get("data") or []
            m[0]["data"] = [_restyle(old[k] if k < len(old) else None, v) for k, v in enumerate(f.column(cols[0]))]
            filled[id(m[0])] = cols[0]
        plain = [m for m in single if not is_axis(m) and not str(m[0]["slot"]).startswith("=")]
        if not plain:
            continue
        if not cols:
            for m in reversed(plain):
                remove(m)
            continue
        for i, c in enumerate(cols):
            if i < len(plain):
                obj = plain[i][0]
            else:                                           # more columns than marks: repeat the last mark
                last = plain[-1]
                obj = copy.deepcopy(last[0])
                _drop_colour(obj)
                obj.pop("name", None)
                if isinstance(last[1], list):
                    at = next(k for k, x in enumerate(last[1]) if x is last[0]) + (i - len(plain)) + 1
                    last[1].insert(at, obj)
            if obj.get("type") == "category":
                obj["data"] = list(dict.fromkeys(str(v) for v in f.column(c) if v is not None))
                continue
            old = obj.get("data") or []
            obj["data"] = [_restyle(old[k] if k < len(old) else None, v) for k, v in enumerate(f.column(c))]
            if obj.get("type") and obj.get("type") != "value":
                if column_names:                            # records an item's script reads: the name is the column
                    obj["name"] = c
                elif first:
                    obj.pop("name", None)
                elif not obj.get("name"):
                    obj["name"] = f.label(c)
                filled[id(obj)] = c
        for m in reversed(plain[len(cols):]):               # two series on one column: name it twice (value=v,v)
            remove(m)
    if names and first:   # a shown value axis drops the sample's fixed range so it fits the real values
        for a in _axes(o, "xAxis") + _axes(o, "yAxis"):
            if a.get("type") == "value" and a.get("show") is not False:
                for k in ("min", "max", "interval"):
                    a.pop(k, None)
    return filled


def _axes(o, key) -> list:
    a = o.get(key)
    return [x for x in (a if isinstance(a, list) else [a]) if isinstance(x, dict)]


PLAIN_AXIS_FMT = re.compile(r"^\$?\{value(:(short|comma))?\}[%KMB]?$")   # FORMAT may replace these


def format_chart(o: dict, filled: dict, f: Fill) -> dict:
    """FORMAT on the page: each filled point gets its label text; returns the value-axis formats to apply.
    A series may name columns for its points: "color_column" (a colour per point, e.g. "var(--muted)" for a
    total) and "label_column" (the label text per point, e.g. "+$16K")."""
    series = o.get("series") if isinstance(o.get("series"), list) else [o.get("series")]
    for s in series:
        if not isinstance(s, dict):
            continue
        by_col = {k: s.pop(k) for k in ("color_column", "label_column") if k in s}
        spec = f.fmt(filled[id(s)]) if id(s) in filled else ""
        if not spec and isinstance(s.get("slot"), str) and "," in s["slot"]:
            first = (f.smap.get(slot_names(s["slot"])[0]) or [None])[0]
            spec = f.fmt(first) if first else ""
        if spec:
            _format_templates(s, spec)
        lab = s.get("label") if isinstance(s.get("label"), dict) else {}
        if not by_col and (not spec or lab.get("formatter")):
            continue
        cols = {k: f.column(c) for k, c in by_col.items()}
        out = []
        for i, d in enumerate(s.get("data") or []):
            v = d.get("value") if isinstance(d, dict) else d
            e = dict(d) if isinstance(d, dict) else {"value": v}
            colour = (cols.get("color_column") or [])[i] if i < len(cols.get("color_column") or []) else None
            text = (cols.get("label_column") or [])[i] if i < len(cols.get("label_column") or []) else None
            if colour not in (None, ""):
                e["itemStyle"] = {**(e.get("itemStyle") or {}), "color": str(colour)}
            if text not in (None, ""):
                e["label"] = {**(e.get("label") or {}), "formatter": str(text)}
            elif spec and not lab.get("formatter") and isinstance(v, (int, float)) and not isinstance(v, bool):
                e["label"] = {**(e.get("label") or {}), "formatter": fmt_value(v, spec)}
            out.append(e if (e.keys() - {"value"}) else d)
        s["data"] = out
    axis_fmt = {}
    for key in ("xAxis", "yAxis"):
        specs, any_ = [], False
        for j, a in enumerate(_axes(o, key)):
            spec = None
            kind = a.get("type") or ("value" if key == "yAxis" else "category")
            own = (a.get("axisLabel") or {}).get("formatter")
            if kind == "value" and (not own or (isinstance(own, str) and PLAIN_AXIS_FMT.match(own))):
                for s in series:
                    if isinstance(s, dict) and id(s) in filled and int(s.get(key + "Index") or 0) == j:
                        spec = f.fmt(filled[id(s)]) or None
                        if spec:
                            break
                if spec and own:                      # FORMAT beats a plain "${value}" template
                    a["axisLabel"].pop("formatter")
            specs.append(spec)
            any_ = any_ or bool(spec)
        if any_:
            axis_fmt[key] = specs
    return axis_fmt


def _format_templates(s: dict, spec: str):
    """FORMAT in the label texts the item wrote itself ("{c}", "{a}  {c}"): the runtime's code when there is one
    ("${c:short}"), else the formatted value put in (each point's label; the end label takes the last value)."""
    data = s.get("data") or []
    pair = lambda d: (d.get("value") if isinstance(d, dict) else d)  # noqa: E731
    if any(isinstance(pair(d), list) for d in data):   # [value, "name"] points: each label shows its value, formatted
        lb = s.get("label")
        if isinstance(lb, dict) and isinstance(lb.get("formatter"), str) and "{@[0]}" in lb["formatter"]:
            t, out = lb["formatter"], []
            for d in data:
                v = pair(d)
                if not (isinstance(v, list) and v and isinstance(v[0], (int, float))):
                    out.append(d)
                    continue
                e = dict(d) if isinstance(d, dict) else {"value": d}
                e["label"] = {**(e.get("label") or {}),
                              "formatter": re.sub(r"\$?\{@\[0\]\}[KMB%]?", lambda _: fmt_value(v[0], spec), t)}
                out.append(e)
            s["data"] = out
            lb.pop("formatter")                     # each point now carries its own text
        return
    code = runtime_code(spec, "c")
    for key in ("label", "endLabel"):
        lb = s.get(key)
        if not (isinstance(lb, dict) and isinstance(lb.get("formatter"), str) and "{c" in lb["formatter"]):
            continue
        t = lb["formatter"]
        if key == "endLabel":
            vals = [d.get("value") if isinstance(d, dict) else d for d in data]
            last = next((v for v in reversed(vals) if v is not None), None)
            lb["formatter"] = re.sub(r"\$?\{c(:\w+)?\}[KMB%]?", lambda _: fmt_value(last, spec), t)
        elif not re.search(r"\{c(:\w+)?\}", t):
            continue
        elif code:
            lb["formatter"] = re.sub(r"\$?\{c(:\w+)?\}[KMB%]?", lambda _: code, t)
        else:
            out = []
            for d in data:
                v = d.get("value") if isinstance(d, dict) else d
                if v is None:
                    out.append(d)
                    continue
                e = dict(d) if isinstance(d, dict) else {"value": v}
                e["label"] = {**(e.get("label") or {}), "formatter": re.sub(r"\$?\{c(:\w+)?\}[KMB%]?",
                                                                           lambda _: fmt_value(v, spec), t)}
                out.append(e)
            s["data"] = out


def unit_check(o: dict, where: str, warns: list):
    """A % format on values over 1,000, or a $ on values all under 1: almost certainly the wrong format."""
    series = o.get("series") if isinstance(o.get("series"), list) else []
    for s in series:
        if not isinstance(s, dict):
            continue
        vals = []
        for d in s.get("data") or []:
            v = d.get("value") if isinstance(d, dict) else d
            v = v[0] if isinstance(v, list) and v else v
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(abs(v))
        texts = [x.get("formatter") for x in (s.get("label"), s.get("endLabel")) if isinstance(x, dict)]
        texts += [d["label"]["formatter"] for d in (s.get("data") or [])
                  if isinstance(d, dict) and isinstance(d.get("label"), dict) and isinstance(d["label"].get("formatter"), str)][:1]
        texts = [t for t in texts if isinstance(t, str)]
        if vals and max(vals) > 1000 and any(re.search(r"\{[^}]*\}\s*%", t) for t in texts):
            warns.append(f"{where}: the '{s.get('slot')}' labels show % but the values reach {fmt_value(max(vals), ',')}: "
                         "set FORMAT for its column (e.g. \"$short\") or edit the label's formatter")
        elif vals and max(vals) < 1 and any(re.search(r"\$\{", t) for t in texts):
            warns.append(f"{where}: the '{s.get('slot')}' labels show $ but every value is under 1 (a share?): "
                         "set FORMAT for its column (e.g. \".0%\")")


def tidy_chart(o: dict):
    """Room for a value-axis name above the plot (the library runtime spaces end labels itself)."""
    named = any(a.get("name") and a.get("show") is not False and (a.get("nameLocation") or "end") == "end"
                for a in _axes(o, "yAxis"))
    for g in ([o["grid"]] if isinstance(o.get("grid"), dict) else []):
        if named and isinstance(g.get("top"), (int, float)) and g["top"] < 36:
            g["top"] = 36


def _expand_columns(parent, f: Fill, keep: bool):
    """A cell whose slot has several columns repeats once per column; a text slot given none leaves rows."""
    done, out = set(), []
    for c in parent["children"]:
        spec = h_attr(c, "data-slot") if is_el(c) else None
        if not spec:
            out.append(c)
            continue
        t = next((x for x in spec.split() if "@" not in x), "").split("=")[0]
        if not t:
            out.append(c)
            continue
        if t in done:
            continue
        done.add(t)
        cols = f.smap.get(t) or []
        if not cols:
            if keep:
                out.append(c)
            continue
        if len(cols) == 1:
            out.append(c)
            continue
        for i in range(len(cols)):
            k = copy.deepcopy(c)
            h_set(k, "data-slot", re.sub(rf"(^|\s){re.escape(t)}(@|\s|$)", rf"\g<1>{t}={i}\g<2>", spec))
            out.append(k)
    parent["children"] = out
    for c in out:
        if is_el(c) and c["tag"] not in ("script", "style"):
            _expand_columns(c, f, keep and h_attr(c, "data-rows") is None and c["tag"] != "thead")


def _apply_slot(n, row, m: dict, in_head: bool, f: Fill):
    for t in (h_attr(n, "data-slot") or "").split():
        name, _, prop = t.partition("@")
        cols = m.get(name) or []
        c = cols[0] if cols else None
        if c is None:
            if not prop and row is None and not in_head:
                n["children"] = []                     # a figure given nothing is emptied
            continue
        if in_head:
            v = f.label(c)
        elif row is not None:
            f.need(c)
            v = row.get(c)
        else:
            v = f.figure(c)
        if not prop:
            n["children"] = [h_text(f.show(v, c))]
        elif prop == "class":
            cls = [x for x in (h_attr(n, "class") or "").split() if not STATES_RE.match(x)]
            if v not in (None, ""):
                cls.append(str(v))
            h_set(n, "class", " ".join(cls))
        elif re.match(r"^(aria-|title$)", prop):
            h_set(n, prop, html.escape(f.show(v, c), quote=True))
        elif re.match(r"^data-(?!slot|rows|template)", prop):          # data-tick-up, data-v ...: the raw value
            h_set(n, prop, html.escape("" if v is None else str(v), quote=True))
        else:
            unitless = re.match(r"^(flex-grow|flex-shrink|opacity|order|z-index)$", prop)
            st = [x.strip() for x in (h_attr(n, "style") or "").split(";")
                  if x.strip() and not x.strip().startswith(prop + ":")]
            if v not in (None, ""):
                st.append(f"{prop}: {v}%" if re.fullmatch(r"-?\d+(\.\d+)?", str(v)) and not unitless
                          else f"{prop}: {html.escape(str(v), quote=True)}")
            h_set(n, "style", "; ".join(st) + ";" if st else None)


def fill_html(markup: str, f: Fill, text=None, collapse: bool = False) -> str:
    """The block with its rows and slots filled. text(s): fills free text (not in slots or scripts).
    collapse: keep one row (the template) for writing into a section file."""
    def records(m):   # an item that builds itself from records keeps them in JSON marked like a chart
        o = json.loads(m.group(2))
        fill_chart(o, f, first=True, column_names=True)
        js = json.dumps(jsonable(o), ensure_ascii=False, separators=(",", ":"))
        return m.group(1) + js.replace("</", "<\\/") + m.group(3)
    markup = re.sub(r'(<script type="application/json"[^>]*>)([\s\S]*?)(</script>)', records, markup)
    tree = h_parse(markup)

    def template(n, _):
        if h_attr(n, "data-rows") is not None:
            kids = h_elements(n)
            tpl = next((k for k in kids if h_attr(k, "data-template") is not None), kids[0] if kids else None)
            if tpl is not None:
                n["children"] = ["\n", tpl, "\n"]
    h_walk(tree, template)
    _expand_columns(tree, f, True)
    heads = set()

    def mark_head(n, _):
        if n["tag"] == "thead":
            h_walk(n, lambda x, __: heads.add(id(x)))
            return False
    h_walk(tree, mark_head)

    def at(n, in_head, row):
        spec, m = h_attr(n, "data-slot"), {}
        for t in spec.split():
            nm = t.split("@")[0]
            s, eq, k = nm.partition("=")
            cols = f.smap.get(s) or []
            m[s] = ([cols[int(k)]] if int(k) < len(cols) else []) if eq else cols
        h_set(n, "data-slot", re.sub(r"=[^@\s]+", "", spec))
        _apply_slot(n, row, m, in_head, f)

    def visit(n, parent):
        if h_attr(n, "data-rows") is not None:
            kids = h_elements(n)
            if not kids:
                return False
            tpl, made = kids[0], []
            if collapse and not f.rows:
                return False
            for i, r in enumerate(f.rows[:1] if collapse else f.rows):
                k = copy.deepcopy(tpl)
                if i:
                    h_set(k, "data-template", None)
                cls = [x for x in (h_attr(k, "class") or "").split() if x != "on"]
                h_set(k, "class", " ".join(cls) or None)
                h_walk(k, lambda x, _: at(x, False, r) if h_attr(x, "data-slot") else None)
                made.append(k)
            n["children"] = ["\n"] + [y for k in made for y in (k, "\n")]
            return False
        if h_attr(n, "data-slot"):
            at(n, id(n) in heads, None)
    h_walk(tree, visit)
    if text:
        free_text(tree, text)
    return h_serialize(tree)


def free_text(tree, text):
    """text(s) on every piece of visible text outside slots, rows and scripts."""
    def go(n):
        if not is_el(n) or n["tag"] in ("script", "style") or (n["tag"] != "#root" and (
                h_attr(n, "data-slot") is not None or h_attr(n, "data-rows") is not None)):
            return
        n["children"] = [text(c) if isinstance(c, str) and c.strip() else c for c in n["children"]]
        for c in n["children"]:
            go(c)
    go(tree)


NUM_TEXT_RE = re.compile(r"^(\D*?)(-?\d[\d,]*(?:\.(\d+))?)(\D*)$")


def count_ups(tree, add: bool = False):
    """A count-up ends on the text it shows: $4.2M gives data-tick-up 4.2, prefix $, suffix M, 1 decimal.
    add: every big figure (.lib-big, .kpi-value) holding plain text counts up too (MOTION = "count-up")."""
    def go(n, _):
        plain = all(isinstance(c, str) for c in n["children"])
        if add and plain and (h_has_class(n, "lib-big") or h_has_class(n, "kpi-value")) \
                and h_attr(n, "data-tick-up") is None:
            h_set(n, "data-tick-up", "0")
        if h_attr(n, "data-tick-up") is None:
            return
        text = html.unescape(re.sub(r"<[^>]+>", "", "".join(h_serialize(c) for c in n["children"]))).strip()
        m = NUM_TEXT_RE.match(text)
        if not m:
            h_set(n, "data-tick-up", None)
            return
        h_set(n, "data-tick-up", m.group(2).replace(",", ""))
        h_set(n, "data-prefix", html.escape(m.group(1), quote=True) or None)
        h_set(n, "data-suffix", html.escape(m.group(4), quote=True) or None)
        h_set(n, "data-decimals", str(len(m.group(3) or "")))
    h_walk(tree, go)


def put_chart(markup: str, box: str) -> str:
    """Puts the filled chart into the empty chart element of a block's HTML."""
    tree, done = h_parse(markup), []

    def find(n, parent):
        if not done and h_has_class(n, "chart") and h_attr(n, "data-echart") is not None and parent is not None:
            parent["children"][next(i for i, x in enumerate(parent["children"]) if x is n)] = box
            done.append(1)
            return False
    h_walk(tree, find)
    return h_serialize(tree) if done else box + markup


def check_note(note: list, smap: dict) -> list:
    """What a SLOTS mapping is missing against an item's data note."""
    out = []
    for s in note:
        n = len(smap.get(s["name"]) or [])
        if s["count"] == "one" and n != 1:
            out.append(f"{s['name']} needs one column")
        if s["count"] == "one or more" and n < 1:
            out.append(f"{s['name']} needs one or more columns")
        if s["count"] == "optional" and n > 1:
            out.append(f"{s['name']} takes at most one column")
    names = [s["name"] for s in note]
    out += [f"{k} is not a slot of this item (its slots: {', '.join(names)})" for k in smap if k not in names]
    return out


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


def as_cols(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else [v]


def section_fill(sec: dict, res: dict, where: str) -> Fill | None:
    """The section's table and wiring, ready to fill its visual. None when it has no SLOTS."""
    slots = sec.get("slots")
    if not slots:
        return None
    if not isinstance(slots, dict):
        raise Stop(f"{where}: SLOTS must be a dict: {{\"slot\": \"column\"}} or {{\"slot\": [\"col\", \"col\"]}}")
    df = table_of(res, sec.get("data"), where)
    cols = [str(c) for c in df.columns]
    used = {c for v in slots.values() for c in as_cols(v) if isinstance(c, str) and c != "*"}
    smap = {}
    for k, v in slots.items():
        out = []
        for c in as_cols(v):
            out += [x for x in cols if x not in used] if c == "*" else [c]
        smap[str(k)] = out
    rows = [{c: jsonable(v) for c, v in zip(cols, r)} for r in df.itertuples(index=False, name=None)]
    for d, label in ((sec.get("names"), "NAMES"), (sec.get("format"), "FORMAT")):
        if d is not None and not isinstance(d, dict):
            raise Stop(f"{where}: {label} must be a dict of column -> text")
    for c, spec in (sec.get("format") or {}).items():
        if str(spec).startswith("$") and "%" in str(spec):
            raise Stop(f"{where}: FORMAT {c} '{spec}' mixes $ and %. Use one: '$short' or '.0%'")
    return Fill(rows, smap, set(cols), sec.get("names"), sec.get("format"), where, res.get("metrics"))


def visual_html(sec: dict, res: dict, filler, where: str, warns: list) -> str:
    """The section's copied item, filled from its table: <div data-item>...</div>, or ''."""
    chart, markup = sec.get("chart"), sec.get("html")
    if chart is None and markup is None:
        return ""
    f = section_fill(sec, res, where)
    item = str(sec.get("use") or "").split(" ")[0] or "own-" + res["name"]

    def text(s):   # free text in the item's HTML: placeholders filled, typed numbers flagged
        out = filler.fill(s, f"{where} HTML", warns)
        return out.replace("<", "&lt;").replace(">", "&gt;")
    if chart is not None:
        if callable(chart):
            try:
                opt = chart(res["tables"])
            except Exception:
                traceback.print_exc()
                raise Stop(f"{where}: the CHART function failed (traceback above)")
        else:
            opt = copy.deepcopy(chart)
        if not isinstance(opt, dict):
            raise Stop(f"{where}: CHART must be ECharts options (a dict) or a function of the tables returning one")
        axis_fmt = format_chart(opt, fill_chart(opt, f), f) if f else {}
        unit_check(opt, where, warns)
        for x in (opt.get("series") if isinstance(opt.get("series"), list) else []):
            vals = [d.get("value") if isinstance(d, dict) else d for d in (x.get("data") or [])] if isinstance(x, dict) else []
            if isinstance(x, dict) and x.get("slot") and not any(v is not None and v != [] for v in vals):
                warns.append(f"{where}: the {x.get('type')} series for slot '{x.get('slot')}' has no data (fine if expected, e.g. no rises); "
                             "check its column in SLOTS")
        tidy_chart(opt)
        js = json.dumps(jsonable(opt), ensure_ascii=False).replace("</", "<\\/")
        fmt_attr = f' data-axis-format="{html.escape(json.dumps(axis_fmt), quote=True)}"' if axis_fmt else ""
        box = f'<div class="chart" data-echart{fmt_attr}><script type="application/json">{js}</script></div>'
        if markup:   # the HTML round the chart (a wrapper, an animation's stage): its slots and words first
            filled = fill_html(str(markup), f, text) if f else str(markup)
            if not f:
                t = h_parse(filled)
                free_text(t, text)
                filled = h_serialize(t)
            body = put_chart(filled, box)
        else:
            body = box + str(sec.get("key") or "")
    else:
        if f:
            body = fill_html(str(markup), f, text)
        else:
            t = h_parse(str(markup))
            free_text(t, text)
            body = h_serialize(t)
    motion = str(sec.get("motion") or "")
    if motion and motion != "count-up":
        raise Stop(f"{where}: MOTION is \"count-up\" (the section's big figures count up when they come into view)")
    if "data-tick-up" in body or motion:
        t = h_parse(body)
        count_ups(t, add=bool(motion))
        body = h_serialize(t)
    basis = filler.fill(sec["basis"], f"{where} BASIS", warns) if sec.get("basis") else ""
    seen = " ".join([basis, re.sub(r"<[^>]+>", " ", body if chart is None else str(markup or ""))])
    left = [w for w in SAMPLE_WORDS if w in seen]
    if left:
        said = "; ".join(left)
        warns.append(f"{where}: still has the library sample's words ({said} ...). Write the real ones")
    h = sec.get("height")
    style = f' style="--chart-height: {int(h)}px"' if h else ""
    out = (f'<div data-item="{html.escape(item)}"{style}>\n{body}\n'
           + (f'<p class="basis">{rich(basis)}</p>\n' if basis else "") + "</div>")
    return f'<div data-item="AN-count-up">\n{out}\n</div>' if motion else out


def build(rep, runner: Runner):
    warns: list = []
    filler = Filler(runner)

    # answer (a report with no sections yet builds as a shell, so it can be looked at)
    ans = dict(rep.ANSWER)
    bad = set(ans) - {"headline", "basis", "bullets", "kpis"}
    if bad:
        raise Stop(f"report.py ANSWER: unknown keys {sorted(bad)}; allowed: headline, basis, bullets, kpis")
    if not rep.SECTIONS:
        warns.append("no sections yet: python run.py add-section NAME --use <id> ...")
    for k, say in (("headline", "the answer in one sentence"),
                   ("basis", "which date, compared with what, what is excluded, data through when")):
        if not str(ans.get(k) or "").strip():
            ans[k] = f"({k} to write in report.py ANSWER)"
            if rep.SECTIONS:
                warns.append(f"report.py ANSWER: '{k}' is empty; write {say}")
    headline = filler.fill(ans["headline"], "ANSWER headline", warns)
    basis = filler.fill(ans["basis"], "ANSWER basis", warns)
    shown, scratch = [], []
    a_bul = bullets_html(ans.get("bullets"), filler, "ANSWER", warns, scratch)
    a_kpi = kpis_html(ans.get("kpis"), filler, "ANSWER", warns, scratch, shown)
    answer = ('<section class="answer"><div class="label">The answer</div>'
              f'<p class="headline">{rich(headline)}</p><p class="basis">{rich(basis)}</p>'
              f'{a_bul}{a_kpi}</section>')

    # sections
    secs_html, contents, method, exported = [], [], [], []
    item_css, item_js = [], []
    for i, sec in enumerate(rep.SECTIONS, 1):
        res = runner.run(sec["analytic"])
        where = f"sections/{sec['file']}"
        if not str(sec.get("description") or "").strip():
            warns.append(f"{where}: no DESCRIPTION (8 to 10 words, shown by `python run.py list`)")
        for k, ln in enumerate((SECTIONS_DIR / sec["file"]).read_text(encoding="utf-8").splitlines(), 1):
            if "MANUAL" in ln or "TODO" in ln or '"(to fill)"' in ln:
                what = ln.split("#", 1)[1].strip() if "#" in ln else "a slot still to fill"
                warns.append(f"{where}:{k}: placeholder data, not filled yet: {what}")
        filler.own, filler.own_name = res["metrics"], f"analytic '{res['name']}'"
        title = filler.fill(sec.get("title") or "", f"{where} TITLE", warns)
        if not title:
            raise Stop(f"{where}: needs a TITLE (the finding, as a sentence)")
        kpi = kpis_html(sec.get("kpis"), filler, where, warns, scratch, shown)
        layout = {"wide": "above"}.get(sec.get("layout"), sec.get("layout") or "side")
        if layout not in LAYOUTS:
            raise Stop(f"{where}: LAYOUT is side (text, then the visual beside it), flip (visual left), "
                       "above (visual above the text) or below")
        vis = visual_html(sec, res, filler, where, warns)
        bul = bullets_html(sec.get("bullets"), filler, where, warns, scratch, " cols" if layout == "above" else "")
        for part, store in ((sec.get("css"), item_css), (sec.get("script"), item_js)):
            if part and str(part).strip() not in store:
                store.append(str(part).strip())
        links = []
        for t in sec.get("export") or []:
            if t not in res["tables"]:
                raise Stop(f"{where}: EXPORT names '{t}', which {res['name']}() did not return")
            fn = f"{ROOT.name}_{t}.csv"
            res["tables"][t].to_csv(ROOT / fn, index=False)
            exported.append(fn)
            links.append(f'<a href="{html.escape(fn)}">{html.escape(fn)}</a> ({len(res["tables"][t]):,} rows)')
        exp = f'<p class="export">Full list, saved beside this report: {"; ".join(links)}</p>' if links else ""
        if not (bul or vis or kpi):
            raise Stop(f"{where}: add bullets or a visual")
        parts = (f'<div class="text">{bul}</div>' if bul else "") + (f'<div class="visual">{vis}</div>' if vis else "")
        lay = layout if (bul and vis) else "one"
        secs_html.append(
            f'<section class="sec" id="s{i}"><div class="sec-head"><span class="num">{i:02d}</span>'
            f'<h2>{rich(title)}</h2></div>{kpi}<div class="body lay-{lay}">{parts}</div>{exp}</section>')
        contents.append(f'<a href="#s{i}"><span class="num">{i:02d}</span>{html.escape(title)}</a>')
        m = f"<li><b>{i:02d}</b> " + html.escape(res["question"]) + (
            f" <i>{html.escape(res['notes'])}</i>" if res["notes"] else "")
        method.append(m + "</li>")
    filler.own, filler.own_name = {}, ""

    # footer
    srcs = "".join(f"<li><b>{html.escape(pretty(n))}</b>: "
                   + (f"{html.escape(u['from'])}, " if not u['from'].endswith("()") else "") + f"{u['rows']:,} rows"
                   + (f", {html.escape(u['note'])}" if u["note"] else "") + "</li>"
                   for n, u in runner.src.used.items()) or "<li>none read</li>"
    footer = ('<h3>How this was made</h3><div class="foot-grid">'
              f'<div><h4>Data</h4><ul>{srcs}</ul></div>'
              f'<div><h4>What each section answers</h4><ul>{"".join(method)}</ul></div></div>'
              f'<p class="foot-line">Every figure and chart is filled from the data when the report is built '
              f'({now()}).</p>')

    page_file = ROOT / "page.html"
    if not page_file.exists():
        raise Stop("page.html is missing. Copy it from the analysis skill's template/")
    page = page_file.read_text(encoding="utf-8")
    inert = '<script id="host-motion" type="text/x-host-motion">'
    if any(str(x.get("use") or "").startswith("AN-") or x.get("motion") for x in rep.SECTIONS):
        if inert not in page:
            raise Stop("page.html has no host-motion block (it predates animations): copy page.html from the "
                       "analysis skill's template/, then python run.py theme <id> if the report had a theme")
        page = page.replace(inert, '<script id="host-motion">', 1)   # played only where a section animates
    else:
        page = re.sub(r'<script id="host-motion" type="text/x-host-motion">[\s\S]*?</script>\n?', "", page, count=1)
    lost = [t for t in ("__ANSWER__", "__SECTIONS__", "__ECHARTS__", "__ITEM_CSS__", "__ITEM_JS__") if t not in page]
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
    js = "".join("<script>\n" + j.replace("</script", "<\\/script") + "\n</script>\n" for j in item_js)
    for token, value in {
        "__TITLE__": html.escape(rep.TITLE), "__EYEBROW__": html.escape(f"For {reader} · {date}" if reader else date),
        "__SUBTITLE__": "" if same else f'<p class="question">{html.escape(rep.QUESTION)}</p>',
        "__QUESTION__": html.escape(rep.QUESTION),
        "__DATE__": date, "__ANSWER__": answer, "__CONTENTS__": toc,
        "__SECTIONS__": "\n".join(secs_html), "__FOOTER__": footer, "__ECHARTS__": echarts,
        "__ITEM_CSS__": "\n".join(item_css).replace("</", "<\\/"), "__ITEM_JS__": js,
    }.items():
        page = page.replace(token, value)
    out = ROOT / f"{ROOT.name}.html"
    out.write_text(page, encoding="utf-8")
    return out, warns


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ explore and main

def print_result(res: dict, rows: int = 3):
    import pandas as pd
    print(f"\n{res['name']}  ({res['where']})\n  {res['question']}")
    print("  metrics: " + (", ".join(f"{m}={(f'{v:,.0f}' if abs(v) >= 1000 else f'{v:.4g}') if isinstance(v, float) else v}"
                                     for m, v in res["metrics"].items()) or "none"))
    for t, df in res["tables"].items():
        print(f"  table {t} ({len(df):,} rows): {', '.join(map(str, df.columns))}")
        if rows:
            with pd.option_context("display.width", 160, "display.max_columns", 12):
                print("\n".join("    " + line for line in df.head(rows).to_string(index=False).splitlines()))
    if res["notes"]:
        print(f"  notes: {res['notes']}")


def export_data(runner: Runner, args: list, as_json: bool, out: str | None) -> int:
    """data NAME [TABLE]: one table (or 'metrics') as CSV or JSON, to stdout or --out. Nothing else saved."""
    m = SECTION_FILE_RE.match(args[0].removesuffix(".py")) if args else None
    known = args and (args[0] in runner.analytics or (m and m.group(2) in runner.analytics))
    if not known or len(args) > 2:
        print("Analytics and their tables (python run.py data NAME TABLE [--json] [--out FILE]):")
        print("\n".join(_analytic_line(runner, n, _live(runner.rep)) for n in runner.analytics))
        raise Stop(f"no analytic named '{args[0]}'" if args and not known else
                   "use: python run.py data NAME [TABLE] [--json] [--out FILE]")
    res = runner.run(args[0])
    name = args[1] if len(args) == 2 else None
    if out and out.lower().endswith(".xlsx"):   # a real workbook: the named table, or one sheet per table
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            raise Stop("an .xlsx file needs openpyxl: python -m pip install openpyxl (or use --out FILE.csv)")
        import pandas as pd
        sheets = {"metrics": pd.DataFrame([{"metric": k, "value": jsonable(v)} for k, v in res["metrics"].items()])} \
            if name == "metrics" else {t: table_of(res, t, f"data {args[0]}") for t in ([name] if name else res["tables"])}
        if not sheets:
            raise Stop(f"{args[0]} returned no tables")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(out, engine="openpyxl") as xl:
            for t, df in sheets.items():
                df.to_excel(xl, sheet_name=re.sub(r"[\[\]:*?/\\]", "_", t)[:31], index=False)
        print(f"Wrote {out} (sheets: {', '.join(sheets)})", file=sys.stderr)
        return 0
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


# ------------------------------------------------------------------ the design library

def find_library(rep, given: str | None = None) -> Path:
    """The design library: --library, report.py LIBRARY, a map's `Design library:` line, design-library
    beside a .claude folder, Toolkit Update/design-library (searched up from this folder), ~/design-library."""
    cands, ups = [], [ROOT, *ROOT.parents]
    for g, base in ((given, Path.cwd()), (str(getattr(rep, "LIBRARY", "") or ""), ROOT)):
        if g:
            p = Path(g).expanduser()
            cands.append(p if p.is_absolute() else base / p)
    for d in ups:
        md = d / "CLAUDE.md"
        if md.is_file():
            m = re.search(r"Design library:\**\s*`?([^`\n|]+?)`?\s*(?:\||$)", md.read_text(encoding="utf-8"), re.M)
            if m:
                p = Path(m.group(1).strip()).expanduser()
                cands.append(p if p.is_absolute() else d / p)
    cands += [d / "design-library" for d in ups] + [d / "Toolkit Update" / "design-library" for d in ups]
    cands.append(Path.home() / "design-library")
    for c in cands:
        c = Path(os.path.normpath(os.path.abspath(c)))      # no "../.." left: Windows limits path length
        if (c / "item.js").is_file():
            if given:
                remember_library(c)
            return c
    raise Stop("design library not found. Give it once: --library <folder with item.js> "
               "(or LIBRARY = \"<path>\" in report.py)")


def remember_library(lib: Path):
    """--library: written into report.py LIBRARY (relative to this folder) so it is not needed again."""
    try:
        rel = Path(os.path.relpath(lib, ROOT)).as_posix()
    except ValueError:                                   # another drive
        rel = lib.as_posix()
    f = ROOT / "report.py"
    text = f.read_text(encoding="utf-8")
    new, n = re.subn(r'(?m)^LIBRARY\s*=.*$', lambda _: "LIBRARY = " + json.dumps(rel), text, count=1)
    if not n:
        new = text.rstrip("\n") + "\n\n# The design library, for add-section --use and theme.\nLIBRARY = " + json.dumps(rel) + "\n"
    if new != text:
        f.write_text(new, encoding="utf-8")


def node_item(lib: Path, *args) -> str:
    node = shutil.which("node")
    if not node:
        raise Stop("this needs Node.js (node on the path) to read the design library. Building does not")
    r = subprocess.run([node, str(lib / "item.js"), *args], capture_output=True, text=True, encoding="utf-8", cwd=lib)
    if r.returncode:
        raise Stop("design library: " + (r.stderr.strip() or r.stdout.strip()).replace("STOP: ", ""))
    return r.stdout


def set_theme(rep, tid: str, given: str | None) -> int:
    """theme TH-nn: the theme's tokens (and embedded font) into page.html."""
    if not re.fullmatch(r"TH-\d{2,}", tid or ""):
        raise Stop("use: python run.py theme TH-02 (themes: the library's index/themes.md)")
    lib = find_library(rep, given)
    info = json.loads(node_item(lib, "theme", tid, "--json"))
    block = node_item(lib, "theme", tid, *(["--fonts"] if info.get("hasFonts") else []))
    page_file = ROOT / "page.html"
    page = page_file.read_text(encoding="utf-8")
    tok = re.search(r'<style id="tokens"[^>]*>[\s\S]*?</style>', block)
    if not tok or not re.search(r'<style id="tokens"[^>]*>', page):
        raise Stop('page.html has no <style id="tokens"> block to replace (an older report: edit its :root by hand)')
    new = tok.group(0).replace('<style id="tokens">', f'<style id="tokens" data-theme="{tid}">', 1)
    fonts = re.search(r'<style id="theme-fonts">[\s\S]*?</style>', block)
    page = re.sub(r'\n?<style id="theme-fonts">[\s\S]*?</style>', "", page)
    page = re.sub(r'<style id="tokens"[^>]*>[\s\S]*?</style>',
                  lambda _: new + ("\n" + fonts.group(0) if fonts else ""), page, count=1)
    page_file.write_text(page, encoding="utf-8")
    keep = Path(info["licence"]).name if info.get("hasFonts") and info.get("licence") else ""
    for lic in (lib / "themes").glob("*.txt"):          # a font licence left by an earlier theme goes
        if lic.name != keep and (ROOT / lic.name).is_file():
            (ROOT / lic.name).unlink()
            print(f"Removed {lic.name}: this theme does not embed that font.")
    if keep:
        shutil.copy2(lib / info["licence"], ROOT / keep)
        print(f"Its font travels with its licence: copied {keep} beside the report.")
    print(f"Theme {tid} ({info.get('name')}) is on page.html. Next: python run.py report")
    return 0


# ------------------------------------------------------------------ list and add-section

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})")
MONEY_RE = re.compile(r"paid|amount|cost|price|spend|revenue|charge|premium|dollar", re.I)
WHERE_RE = re.compile(r"^\s*([^<>=]+?)\s*(>=|<=|=)\s*(.+?)\s*$")
WHERE_WORDS = {"=": "is", ">=": "is at least", "<=": "is at most"}


def where_text(wheres) -> str:
    return " and ".join(f"{pretty(c).lower()} {WHERE_WORDS[op]} {v}" for c, op, v, _ in wheres)


def py_lit(v) -> str:
    """A value as a Python literal, on one line."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{json.dumps(str(k), ensure_ascii=False)}: {py_lit(x)}" for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(py_lit(x) for x in v) + "]"
    if v is True or v is False or v is None:
        return repr(v)
    return json.dumps(v, ensure_ascii=False)


def chart_text(o: dict) -> list:
    """CHART = {...}: one key a line, one series a line (a series with styled points: one point a line)."""
    out = ["CHART = {"]
    for k, v in o.items():
        key = json.dumps(k, ensure_ascii=False)
        if k == "series" and isinstance(v, list):
            out.append(f"    {key}: [")
            for s in v:
                d = s.get("data") if isinstance(s, dict) else None
                if isinstance(d, list) and any(isinstance(x, dict) for x in d):
                    head = py_lit({a: b for a, b in s.items() if a != "data"})[:-1]
                    out.append(f"        {head}{', ' if len(head) > 1 else ''}\"data\": [")
                    out += [f"            {py_lit(x)}," for x in d] + ["        ]},"]
                else:
                    out.append(f"        {py_lit(s)},")
            out.append("    ],")
        elif len(f"    {key}: {py_lit(v)},") > 110 and isinstance(v, (dict, list)) and v:
            items = v.items() if isinstance(v, dict) else enumerate(v)
            out.append(f"    {key}: " + ("{" if isinstance(v, dict) else "["))
            out += [f"        {json.dumps(a, ensure_ascii=False) + ': ' if isinstance(v, dict) else ''}{py_lit(b)},"
                    for a, b in items]
            out.append("    " + ("}," if isinstance(v, dict) else "],"))
        else:
            out.append(f"    {key}: {py_lit(v)},")
    return out + ["}"]


def py_block(s: str, raw: bool = False) -> str:
    s = s.strip("\n")
    if raw and '"""' not in s and not s.endswith("\\"):
        return 'r"""\n' + s + '\n"""'
    return '"""\n' + s.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') + '\n"""'


def time_kind(s) -> str:
    """'date', 'month' or '' for a column."""
    import pandas as pd
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"
    if not (s.dtype == object or pd.api.types.is_string_dtype(s)):
        return ""
    v = s.dropna().astype(str).head(200)
    if not len(v):
        return ""
    return "month" if v.str.match(MONTH_RE).all() else ("date" if v.str.match(DATE_RE).all() else "")


def describe_column(name, s) -> str:
    import pandas as pd
    kind, v = time_kind(s), s.dropna()
    if kind:
        d = pd.to_datetime(v, errors="coerce").dropna()
        f = "%Y-%m-%d" if kind == "date" else "%Y-%m"
        info = f"{d.min():{f}} to {d.max():{f}}" if len(d) else "no dates"
    elif pd.api.types.is_bool_dtype(s):
        kind, info = "yes/no", f"{int(v.sum()):,} yes"
    elif pd.api.types.is_numeric_dtype(s):
        kind = "number"
        info = f"{fmt_value(v.min(), 'short')} to {fmt_value(v.max(), 'short')}" if len(v) else "empty"
    else:
        kind, n = "text", v.nunique()
        eg = [str(x) for x in v.drop_duplicates().head(3)]
        info = f"all different, e.g. {eg[0]}" if n == len(v) and n > 20 else \
            f"{n:,} values: {', '.join(eg)}" + (" ..." if n > 3 else "")
    return f"    {str(name):<18} {kind:<7} {info}"


def _analytic_code(name, src, keys, nums, agg, by, timed, wheres, stubs, sig, period="month",
                   top=None, kinds=None, derived=None) -> tuple[str, str, list, str]:
    """-> (code, table name, metric names, value format)."""
    per, out = {"month": ("M", "%b %Y"), "quarter": ("Q", "%Y Q%q"), "year": ("Y", "%Y")}[period]
    first = nums[0] if nums else None
    tname = ("by_" + re.sub(r"[^a-z0-9_]", "_", keys[0].lower())) if keys else "totals"
    what = {"sum": f"total {pretty(first or '').lower()}", "count": f"the number of {pretty(src).lower()}",
            "mean": f"the average {pretty(first or '').lower()}"}[agg]
    q = (f"What does each {pretty(keys[0]).lower()} show" if keys and not first else
         f"How does {what} vary by {pretty(keys[0]).lower()}" if keys else f"What is {what}") \
        + (f", split by {pretty(by).lower()}" if by else "") + (f", where {where_text(wheres)}?" if wheres else "?")
    L = [f"def {name}(src, params):", f'    """Added by add-section: {sig}. Edit freely."""',
         "    import pandas as pd", f'    df = src("{src}")']
    for c, op, v, numeric in wheres:
        op = "==" if op == "=" else op
        L.append(f'    df = df[df["{c}"] {op} {v!r}]' if numeric else
                 f'    df = df[df["{c}"].astype(str) {op} {json.dumps(str(v))}]')
    for c in keys:
        if timed.get(c):
            L += [f'    df["{c}"] = pd.to_datetime(df["{c}"], errors="coerce").dt.to_period("{per}")   # by {period}',
                  f'    df = df.dropna(subset=["{c}"])']
    how = "count" if agg == "count" else agg
    if keys and by:
        L += [f'    t = df.groupby({keys + [by]!r})["{first}"].{how}().unstack(fill_value=0)',
              "    t = t[t.sum().sort_values(ascending=False).index]",
              "    if t.shape[1] > 6:   # the five largest groups, the rest summed",
              '        t = pd.concat([t.iloc[:, :5], t.iloc[:, 5:].sum(axis=1).rename("All other")], axis=1)',
              "    t.columns = [str(c) for c in t.columns]", "    t = t.reset_index()"]
    elif keys:
        L.append(f"    t = df.groupby({keys!r}, as_index=False)[{nums!r}].{how}()" if nums else
                 f"    t = df[{keys!r}].drop_duplicates()")
        if first and not any(timed.get(c) for c in keys):
            L.append(f'    t = t.sort_values("{first}", ascending=False)')
            if top:
                L += [f'    whole = t["{first}"].sum()', f"    t = t.head({top})   # the {top} largest"]
    elif nums:
        L.append(f"    t = df[{nums!r}].{how}().to_frame().T")
    else:
        L.append("    t = pd.DataFrame(index=range(3))   # MANUAL: placeholder rows until the slots name real columns")
    for c in keys:
        if timed.get(c):
            L += [f'    t = t.sort_values("{c}")', f'    t["{c}"] = t["{c}"].dt.strftime("{out}")']
    for c in stubs:
        if (kinds or {}).get(c) == "text":
            L.append(f'    t["{c}"] = [f"Placeholder {{i + 1}}" for i in range(len(t))]   # MANUAL: placeholder - make this column')
        else:
            L.append(f'    t["{c}"] = 1   # MANUAL: placeholder - make this column')
    L += list(derived or [])
    L.append("    t = t.reset_index(drop=True)")
    names = ["rows"]
    if first:
        L.append((f'    vals = t.drop(columns={keys!r}).{"mean" if agg == "mean" else "sum"}(axis=1)') if by
                 else f'    vals = t["{first}"]')
        names = ["overall" if agg == "mean" else "total"]
        if keys:
            L.append(f'    labels = t["{keys[0]}"].astype(str)')
            names += ["largest", "largest_label", "smallest", "smallest_label", "groups"] \
                + (["latest", "latest_label"] if timed.get(keys[0]) else []) + (["top_group", "top_group_total"] if by else [])
    topped = bool(top and first and keys and not by and not any(timed.get(c) for c in keys))
    if topped:
        names += ["share_of_all", "top_n"]
    L.append(f"    m = dict.fromkeys({names!r})   # empty input: every metric stays None")
    if topped:
        L.append(f'    m["top_n"] = {top}')
    if wheres:
        names.append("where")
        L.append(f'    m["where"] = {json.dumps(where_text(wheres))}   # the filter, in words')
    L.append("    if len(t):")
    if not first:
        L.append("        m['rows'] = len(t)")
    else:
        L.append(f'        m["overall"] = df["{first}"].mean()' if agg == "mean" else '        m["total"] = vals.sum()')
        if keys:
            L.append("        m.update(largest=vals.max(), largest_label=labels[vals.idxmax()], smallest=vals.min(),")
            L.append("                 smallest_label=labels[vals.idxmin()], groups=len(t))")
            if timed.get(keys[0]):
                L.append("        m.update(latest=vals.iloc[-1], latest_label=labels.iloc[-1])")
            if topped:
                L.append("        m[\"share_of_all\"] = vals.sum() / whole if whole else None   # the top rows' share")
            if by:
                L.append(f"        g = t.drop(columns={keys!r}).iloc[-1]   # averages: the latest row, never summed"
                         if agg == "mean" else f"        g = t.drop(columns={keys!r}).sum()")
                L.append("        m.update(top_group=g.idxmax(), top_group_total=g.max())")
    L.append('    # another figure: add a key to m, e.g. m["share"] = ..., then use it in the text as {share}')
    notes = " ".join(([f"{period.title()}s come from {pretty(c).lower()}." for c in keys if timed.get(c) == "date"])
                     + ([f"Only {pretty(src).lower()} where {where_text(wheres)}."] if wheres else []))
    L += ["    return {", f'        "question": {json.dumps(q)},', f'        "tables": {{"{tname}": t}},',
          '        "metrics": m,', f'        "notes": {json.dumps(notes)},', "    }"]
    money = bool(first and MONEY_RE.search(first)) and agg != "count"
    f = "$short" if money else ("," if agg == "count" else (",.1f" if agg == "mean" else ",.0f"))
    return "\n".join(L) + "\n", tname, names, f


def _insert_section(src: str, item: str, pos: int) -> str:
    """Put one string item into the SECTIONS list of report.py at position pos."""
    import ast
    node = next((n for n in ast.parse(src).body if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == "SECTIONS" for t in n.targets)), None)
    if node is None or not isinstance(node.value, ast.List):
        raise Stop("report.py: SECTIONS is not a plain list; add the section id to it by hand")
    b = src.encode("utf-8")
    starts = [0]
    for line in b.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    off = lambda ln, col: starts[ln - 1] + col  # noqa: E731
    elts, it = node.value.elts, item.encode("utf-8")
    if not elts:
        lst = node.value
        new = b"[\n    " + it + b",\n]"
        return (b[:off(lst.lineno, lst.col_offset)] + new + b[off(lst.end_lineno, lst.end_col_offset):]).decode("utf-8")
    if pos < len(elts):
        at = off(elts[pos].lineno, elts[pos].col_offset)
        return (b[:at] + it + b",\n" + b" " * elts[pos].col_offset + b[at:]).decode("utf-8")
    at = off(elts[-1].end_lineno, elts[-1].end_col_offset)
    return (b[:at] + b",\n" + b" " * elts[0].col_offset + it + b[at:]).decode("utf-8")


def _parse_wheres(df, given, src) -> list:
    import pandas as pd
    wheres, rows = [], df
    for w in given or []:
        mt = WHERE_RE.match(w)
        if not mt or mt.group(1) not in df.columns:
            raise Stop(f"--where {w}: use col=value, col>=value or col<=value with a column of '{src}': "
                       f"{', '.join(map(str, df.columns))}")
        c, op, v = mt.groups()
        num = pd.api.types.is_numeric_dtype(df[c])
        if num:
            try:
                v = int(v) if re.fullmatch(r"-?\d+", v) else float(v)
            except ValueError:
                raise Stop(f"--where {w}: '{c}' holds numbers, so the value must be a number")
        col = rows[c] if num else rows[c].astype(str)
        keep = {"=": col == v, ">=": col >= v, "<=": col <= v}[op]
        if not keep.any():
            vals = sorted(map(str, rows[c].dropna().unique()))
            raise Stop(f"--where {w} matches no rows. '{c}' has: {', '.join(vals[:15])}"
                       + (f" ... ({len(vals)} values)" if len(vals) > 15 else ""))
        rows = rows[keep]
        wheres.append((c, op, v, num))
    return wheres


def split_chart_block(block: str) -> dict:
    """A chart item's block -> CHART (options), KEY, BASIS, and HTML only when it wraps the chart."""
    wrap = h_elements(h_parse(block))[0]
    kids, charts = h_elements(wrap), []
    h_walk(wrap, lambda n, _: charts.append(n) if h_has_class(n, "chart") and h_attr(n, "data-echart") is not None else None)
    if len(charts) != 1:
        raise Stop("this item holds several charts; add it with --own and copy its parts by hand")
    script = next((c for c in h_elements(charts[0]) if c["tag"] == "script"), None)
    out = {"chart": json.loads(script["raw"]), "key": "", "html": "", "basis": ""}
    basis = next((k for k in kids if k["tag"] == "p" and h_has_class(k, "basis")), None)
    if basis:
        out["basis"] = html.unescape(re.sub(r"<[^>]+>", "", "".join(h_serialize(c) for c in basis["children"]))).strip()
    others = [k for k in kids if k is not basis and k is not charts[0]]
    if all(h_has_class(k, "key") for k in others):
        out["key"] = "\n".join(h_serialize(k) for k in others)
    else:
        charts[0]["children"] = []
        out["html"] = "\n".join(h_serialize(k) for k in kids if k is not basis)
    return out


def _default_text_col(df) -> str:
    import pandas as pd
    text = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and not time_kind(df[c])]
    text.sort(key=lambda c: (df[c].nunique() < 2, df[c].nunique()))     # few groups first
    return str((text or list(df.columns))[0])


def _own_section(name, src, kind, df, sid, bullets) -> str:
    col = _default_text_col(df)
    tname = "by_" + re.sub(r"[^a-z0-9_]", "_", col.lower())
    L = [f'"""Section {sid}: one block of the report. Everything for it is in this file."""', "",
         f'DESCRIPTION = "Your own {kind}: rows by {pretty(col).lower()} (reword)"', "",
         "# Wiring: the visual's slots, filled from table DATA at every build (data changes need no edits).",
         f'DATA = "{tname}"', f'SLOTS = {{"label": "{col}", "value": ["rows"]}}',
         f'NAMES = {{"{col}": "{pretty(col)}", "rows": "Rows"}}   # words the reader sees for a column',
         'FORMAT = {"rows": ","}   # number format per column: "$short", ".0%", ",", "$,.0f"', "", "",
         f"def {name}(src, params):", '    """Your own section: make the table your visual needs."""',
         "    import pandas as pd", f'    df = src("{src}")',
         f'    t = df.groupby("{col}", as_index=False).size().rename(columns={{"size": "rows"}})',
         '    t = t.sort_values("rows", ascending=False).reset_index(drop=True)',
         '    m = {"total": int(t["rows"].sum()) if len(t) else None}',
         f'    return {{"question": "How many rows fall in each {pretty(col).lower()}?", "tables": {{"{tname}": t}},',
         '            "metrics": m, "notes": ""}', "", "",
         f'TITLE = "{pretty(col)}: {{total:,}} rows in all"   # reword: the finding, as a sentence',
         *(['BULLETS = [   # reword each; keep the {placeholders}', '    "**Total:** {total:,} rows.",', "]"]
           if bullets else []),
         'LAYOUT = "side"   # side, flip (visual left), above or below the text', ""]
    if kind == "chart":
        L += ["# Your own chart: ECharts options (echarts.apache.org/en/option.html). \"slot\" marks where a",
              "# SLOTS column goes; colours as \"var(--blue)\"; the data lists refill at every build.",
              'CHART = {', '    "grid": {"left": 8, "right": 56, "top": 30, "bottom": 8, "containLabel": True},',
              '    "xAxis": {"type": "category", "slot": "label", "data": []},',
              '    "yAxis": {"type": "value"},', '    "series": [',
              '        {"type": "bar", "slot": "value", "label": {"show": True, "position": "top"}, "data": []},',
              "    ],", "}", 'BASIS = "What is counted, the period and the basis"   # the line under the chart']
    else:
        L += ["# Your own HTML: data-rows repeats its first child once per table row; data-slot=\"name\"",
              "# puts a SLOTS column's value in (\"name@class\" a class, \"name@width\" a width in %).",
              "# Classes: the library's kit (lib-panel, lib-cards, lib-card, lib-big, lib-table ...).",
              "HTML = " + py_block('<div class="lib-panel">\n<h2>Heading: what this shows</h2>\n<div class="lib-cards" data-rows>\n'
                                   '<div class="lib-card"><div class="lib-lab" data-slot="label">Label</div>'
                                   '<div class="lib-big" data-slot="value">0</div></div>\n</div>\n</div>'),
              "CSS = " + py_block(f'[data-item="own-{name}"] .lib-big {{ font-size: 36px; }}', raw=True)]
    return "\n".join(L) + "\n"


def add_section(rep, runner, rest, a) -> int:
    """add-section NAME --use ID ...: copy a library item into a new sections/sN_NAME.py, or --own."""
    use = "use: python run.py add-section NAME --use CT-34 --source SRC --slot label=COL --slot value=COL"
    if len(rest) != 1 or not NAME_RE.match(rest[0]):
        raise Stop(f"{use} (NAME in lower_snake_case)")
    name = rest[0]
    if name in runner.analytics:
        raise Stop(f"a section named '{name}' already exists ({runner.analytics[name][1]}). Pick another NAME")
    if bool(a.use) == bool(a.own):
        raise Stop(f"give --use <library id> or --own chart|html. {use}")
    if a.own and a.own not in ("chart", "html"):
        raise Stop("--own is chart or html")
    if a.agg not in (None, "sum", "count", "mean"):
        raise Stop("--agg is sum, count or mean. Anything else: edit the new file's calculation")
    if not a.source and rep.SOURCES and (a.own or len(rep.SOURCES) == 1):
        a.source = next(iter(rep.SOURCES))               # the only source, or a blank section's first one
    if not a.source:
        raise Stop(f"--source is needed. Sources: {', '.join(rep.SOURCES) or 'none (add one to SOURCES in report.py)'}")
    if not 0 <= a.bullets <= 3:
        raise Stop("--bullets is 0 to 3")
    pos = len(rep.SECTIONS) if a.after is None else a.after
    if not 0 <= pos <= len(rep.SECTIONS):
        raise Stop(f"--after is 0 to {len(rep.SECTIONS)}")
    df = runner.src(a.source)
    used = [int(m.group(1)) for p in SECTIONS_DIR.glob("s*.py") if (m := SECTION_FILE_RE.match(p.stem))]
    sid = f"s{max(used, default=0) + 1}_{name}"
    if a.own:
        text = _own_section(name, a.source, a.own, df, sid, a.bullets)
        edit = ["DESCRIPTION", "def ", "t = ", "TITLE", "CHART", "HTML"]
        head = f"a blank {a.own} section to make your own"
    else:
        text, edit, head = _library_section(rep, runner, name, sid, df, a)
    sfile, rfile = SECTIONS_DIR / f"{sid}.py", ROOT / "report.py"
    old_r = rfile.read_text(encoding="utf-8")
    new_r = _insert_section(old_r, json.dumps(sid), pos)
    SECTIONS_DIR.mkdir(exist_ok=True)
    sfile.write_text(text, encoding="utf-8")
    rfile.write_text(new_r, encoding="utf-8")
    chk = subprocess.run([sys.executable, str(ROOT / "run.py"), "_check", name], capture_output=True,
                         text=True, encoding="utf-8", cwd=ROOT)
    if chk.returncode != 0 or "STOP" in chk.stdout:
        sfile.unlink()
        rfile.write_text(old_r, encoding="utf-8")
        print(chk.stdout + chk.stderr[-2000:])
        raise Stop("the new section did not build (above), so nothing was changed")
    print(f"Added sections/{sid}.py, {head}, as section {pos + 1} of {len(rep.SECTIONS) + 1}. Lines to edit:")
    in_bullets = False
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        show = any(s.startswith(e) for e in edit) or "TODO" in s or             any(h in s for h in ("<h2", 'class="cap"', 'class="lib-source"')) or             (s.startswith(('"name":', '"text":')) and not in_bullets)
        if s.startswith("BULLETS"):
            in_bullets, show = True, False
        elif in_bullets:
            in_bullets = s != "]"
            show = in_bullets
        if show:
            print(f"  {i:>3}  {s[:110]}" + (" ..." if len(s) > 110 else ""))
    print("Then: python run.py report, and python run.py shot to look at it.")
    return 0


PERIODS = {"month": ("M", "%b %Y"), "quarter": ("Q", "%Y Q%q"), "year": ("Y", "%Y")}


def parse_compare(df, given: str | None):
    """--compare COL=A,B -> (column, a, b, side expression, a label, b label), or None.
    A date column compares months (2026-04), quarters (2026-Q2) or years (2026); any other column, values."""
    import pandas as pd
    if not given:
        return None
    col, eq, vals = given.partition("=")
    parts = [v.strip() for v in vals.split(",") if v.strip()]
    if not eq or col not in df.columns or len(parts) != 2:
        raise Stop(f"--compare {given}: use --compare COL=A,B with a column of the source: {', '.join(map(str, df.columns))}")
    a, b = parts
    if time_kind(df[col]):
        if re.fullmatch(r"\d{4}-\d{2}", a) and re.fullmatch(r"\d{4}-\d{2}", b):
            per, lab = "M", lambda v: pd.Period(v, "M").strftime("%b %Y")
        elif re.fullmatch(r"\d{4}-?Q[1-4]", a, re.I) and re.fullmatch(r"\d{4}-?Q[1-4]", b, re.I):
            a, b = (re.sub(r"-?q", "Q", v, flags=re.I) for v in (a, b))
            per, lab = "Q", lambda v: v.replace("Q", " Q")
        elif re.fullmatch(r"\d{4}", a) and re.fullmatch(r"\d{4}", b):
            per, lab = "Y", str
        else:
            raise Stop(f"--compare {given}: {col} is a date; compare months (2026-04), quarters (2026-Q2) or years (2026)")
        expr = f'pd.to_datetime(df["{col}"], errors="coerce").dt.to_period("{per}").astype(str)'
        return col, a, b, expr, lab(a), lab(b)
    have = set(df[col].astype(str))
    for v in (a, b):
        if v not in have:
            raise Stop(f"--compare {given}: no rows where {col} is {v}. It has: {', '.join(sorted(have)[:12])}")
    return col, a, b, f'df["{col}"].astype(str)', a, b


def _head(name, src, sig, wheres, cmp=None) -> list:
    L = [f"def {name}(src, params):", f'    """Added by add-section: {sig}. Edit freely."""',
         "    import pandas as pd", f'    df = src("{src}")']
    for c, op, v, numeric in wheres:
        op = "==" if op == "=" else op
        L.append(f'    df = df[df["{c}"] {op} {v!r}]' if numeric else
                 f'    df = df[df["{c}"].astype(str) {op} {json.dumps(str(v))}]')
    if cmp:
        L += [f"    a, b = {cmp[1]!r}, {cmp[2]!r}   # the two compared ({pretty(cmp[0]).lower()})",
              f"    df[\"_side\"] = {cmp[3]}", '    df = df[df["_side"].isin([a, b])]']
    return L


def _tail(L, tname, q, notes) -> str:
    L += ['    # another figure: add a key to m, e.g. m["share"] = ..., then use it in the text as {share}',
          "    return {", f'        "question": {json.dumps(q)},', f'        "tables": {{"{tname}": t}},',
          '        "metrics": m,', f'        "notes": {json.dumps(notes)},', "    }"]
    return "\n".join(L) + "\n"


def _value_format(col, agg) -> str:
    money = bool(col and MONEY_RE.search(col)) and agg != "count"
    return "$short" if money else ("," if agg == "count" else (",.1f" if agg == "mean" else ",.0f"))


def _bridge_code(name, src, step, meas, cmp, wheres, top, sig):
    """CT-06 shape: one row per bar; totals at both ends, each step's size in rise, fall or key (the biggest rise)."""
    L = _head(name, src, sig, wheres, cmp)
    L += [f'    g = df.pivot_table(index="{step}", columns="_side", values="{meas}", aggfunc="sum", fill_value=0)',
          "    g = g.reindex(columns=[a, b], fill_value=0)",
          "    start, end = g[a].sum(), g[b].sum()",
          "    d = g[b] - g[a]",
          "    d = d[d != 0]",
          "    d = d.reindex(d.abs().sort_values(ascending=False).index)"]
    if top:
        L += [f"    if len(d) > {top}:   # the {top} biggest movers, the rest together",
              f'        d = pd.concat([d.iloc[:{top}], pd.Series({{"All other": d.iloc[{top}:].sum()}})])']
    L += ["    key = d.idxmax() if len(d) and d.max() > 0 and d.abs().idxmax() == d.idxmax() else None   # stands out",
          f'    rows, run = [{{"step": {json.dumps(cmp[4])}, "base": 0, "total": start}}], start',
          "    for step, x in d.items():   # base: the running total before a rise, after a fall",
          '        rows.append({"step": str(step), "base": run if x >= 0 else run + x,',
          '                     ("key" if step == key else "rise" if x >= 0 else "fall"): abs(x)})',
          "        run += x",
          f'    rows.append({{"step": {json.dumps(cmp[5])}, "base": 0, "total": end}})',
          '    t = pd.DataFrame(rows, columns=["step", "base", "total", "rise", "fall", "key"])',
          "    tops = t[[\"base\", \"total\", \"rise\", \"fall\", \"key\"]].fillna(0).sum(axis=1)",
          "    low = min([start, end] + t[\"base\"].iloc[1:-1].tolist()) if len(t) > 2 else 0",
          "    p = 10 ** max(len(str(int(abs(low)))) - 2, 0)",
          "    t[\"floor\"] = 0 if low < 0.6 * tops.max() else low * 0.95 // p * p   # where the value axis starts",
          '    m = dict.fromkeys(["start", "end", "change", "change_pct", "top_step", "top_change", "a_label", "b_label"])',
          f'    m.update(a_label={json.dumps(cmp[4])}, b_label={json.dumps(cmp[5])})',
          "    if len(d):",
          "        m.update(start=start, end=end, change=end - start, change_pct=(end / start - 1) if start else None,",
          "                 top_step=d.abs().idxmax(), top_change=d[d.abs().idxmax()])"]
    q = f"Which {pretty(step).lower()} moved {pretty(meas).lower()} between {cmp[4]} and {cmp[5]}?"
    return _tail(L, "bridge", q, ""), "bridge"


def _figures_code(name, src, meas, agg, cmp, wheres, with_note, sig):
    """Hero cards: the two compared figures and the change."""
    L = _head(name, src, sig, wheres, cmp)
    L += [f'    s = df.groupby("_side")["{meas}"].{agg}().reindex([a, b], fill_value=0)',
          "    chg = s[b] - s[a]",
          f'    t = pd.DataFrame({{"label": [{json.dumps(cmp[4])}, {json.dumps(cmp[5])}, "Change"], "{meas}": [s[a], s[b], chg]}})']
    if with_note:
        L.append(f'    t["note"] = ["", "", f"{{chg / s[a]:+.0%}} on {cmp[4]}" if s[a] else ""]')
    L += ['    m = {"a_value": s[a], "b_value": s[b], "change": chg, "change_pct": (chg / s[a]) if s[a] else None,',
          f'         "a_label": {json.dumps(cmp[4])}, "b_label": {json.dumps(cmp[5])}}}']
    q = f"How did {pretty(meas).lower()} change from {cmp[4]} to {cmp[5]}?"
    return _tail(L, "figures", q, ""), "figures"


def _pivot_code(name, src, keys, meas, agg, cmp, wheres, timed, period, top, sig):
    """One column per compared value (A, B), one row per group."""
    L = _head(name, src, sig, wheres, cmp)
    per, out = PERIODS[period]
    for c in keys:
        if timed.get(c):
            L.append(f'    df["{c}"] = pd.to_datetime(df["{c}"], errors="coerce").dt.to_period("{per}")')
    L += [f'    t = df.pivot_table(index={keys!r}, columns="_side", values="{meas}", aggfunc="{agg}", fill_value=0)',
          "    t = t.reindex(columns=[a, b], fill_value=0)",
          f"    t.columns = [{json.dumps(cmp[4])}, {json.dumps(cmp[5])}]",
          "    t = t.reset_index()"]
    if any(timed.get(c) for c in keys):
        L += [f'    t = t.sort_values("{keys[0]}")', f'    t["{keys[0]}"] = t["{keys[0]}"].dt.strftime("{out}")']
    else:
        L.append(f'    t = t.sort_values({json.dumps(cmp[5])}, ascending=False)')
        if top:
            L.append(f"    t = t.head({top})   # the {top} largest")
    L += ["    t = t.reset_index(drop=True)",
          f'    chg = t[{json.dumps(cmp[5])}] - t[{json.dumps(cmp[4])}]',
          '    m = dict.fromkeys(["total_a", "total_b", "change", "change_pct", "top_label", "top_change"])',
          "    if len(t):",
          f'        ta, tb = t[{json.dumps(cmp[4])}].sum(), t[{json.dumps(cmp[5])}].sum()',
          "        m.update(total_a=ta, total_b=tb, change=tb - ta, change_pct=(tb / ta - 1) if ta else None,",
          f'                 top_label=t["{keys[0]}"][chg.abs().idxmax()], top_change=chg[chg.abs().idxmax()])']
    q = f"How did {pretty(meas).lower()} by {pretty(keys[0]).lower()} change from {cmp[4]} to {cmp[5]}?"
    return _tail(L, "by_" + re.sub(r"[^a-z0-9_]", "_", keys[0].lower()), q, ""), \
        "by_" + re.sub(r"[^a-z0-9_]", "_", keys[0].lower())


def runtime_code(spec: str, var: str) -> str | None:
    """A FORMAT spec as the library runtime's own code: "$short" -> "${value:short}"; None when it has none."""
    core = spec.lstrip("+$")
    if core == "short":
        code = f"{{{var}:short}}"
    elif core in (",", ",.0f", ",d"):
        code = f"{{{var}:comma}}"
    else:
        return None
    return ("$" if "$" in spec else "") + code


def _library_section(rep, runner, name, sid, df, a):
    import pandas as pd
    item_id = a.use.upper()
    lib = find_library(rep, a.library)
    c = json.loads(node_item(lib, item_id, "--json"))[0]
    if c["type"] not in ("chart", "table", "hero card", "animation"):
        raise Stop(f"{item_id} is a {c['type']}; add-section takes a chart (CT), table (TB), hero card (HC) "
                   "or animation (AN)")
    fits = str(c.get("fits") or "")
    if c["type"] == "animation" and (fits.startswith("none") or "report" not in [x.strip() for x in fits.split(",")]):
        raise Stop(f"{item_id} does not fit a report ({c.get('fits')}). Use a chart instead")
    note = c.get("data") or []
    slot_names_ = {s["name"] for s in note}
    req, manual = {}, []                 # manual: (slot, column, kind, what to do) left on placeholder data
    for s in a.slot or []:
        k, eq, v = s.partition("=")
        if not eq or not k:
            print(f"note: --slot {s} ignored (use --slot NAME=COLUMN)")
            continue
        if k.strip() not in slot_names_:
            print(f"note: {item_id} has no slot '{k.strip()}'; ignored (its slots: {', '.join(sorted(slot_names_)) or 'none'})")
            continue
        req[k.strip()] = [x.strip() for x in v.split(",") if x.strip()]
    period = (a.period or "month").lower()
    if period not in PERIODS:
        print(f"note: --period {a.period} ignored (month, quarter or year); grouping by month")
        period = "month"
    top = a.top
    agg = a.agg or "sum"
    wheres = _parse_wheres(df, a.where, a.source)
    try:
        cmp = parse_compare(df, a.compare)
    except Stop as e:
        print(f"note: --compare ignored: {e}")
        cmp = None
    for s in note:                       # a number slot given a text column cannot be summed: placeholder instead
        if s["kind"] != "text" and agg != "count":
            for col in list(req.get(s["name"]) or []):
                if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                    req[s["name"]] = [x if x != col else f"{col}_number" for x in req[s["name"]]]
                    manual.append((s["name"], f"{col}_number", "number",
                                   f"'{col}' is text, not numbers: make a number column here, or use --agg count"))
    nums_in = [col for s in note if s["kind"] != "text" for col in req.get(s["name"]) or [] if col in df.columns]
    texts_in = [col for s in note if s["kind"] == "text" for col in req.get(s["name"]) or [] if col in df.columns]
    shape = "plain"
    if cmp:
        if {"step", "base", "total", "rise", "fall"} <= slot_names_ and not any(s["kind"] == "figure" for s in note):
            shape = "bridge"
        elif c["type"] == "hero card" and slot_names_ <= {"label", "value", "note", "status"}:
            shape = "figures"
        elif any(s["count"] in ("one or more", "any") and s["kind"] == "number" for s in note) and texts_in:
            shape = "pivot"
        else:
            print(f"note: --compare ignored: it does not fit {item_id} ({c['dataLine']})")
            cmp = None
        if cmp and not nums_in:
            print(f"note: --compare ignored: no slot names the number to compare "
                  f"(e.g. --slot {'total' if shape == 'bridge' else 'value'}=AMOUNT)")
            cmp, shape = None, "plain"
        if shape == "bridge" and not texts_in:
            print("note: --compare ignored: a waterfall needs its steps (--slot step=COLUMN)")
            cmp, shape = None, "plain"
        if not cmp:
            shape = "plain"
    sig = f"{a.source} | {item_id} | " + " | ".join(f"{k}={','.join(v)}" for k, v in req.items()) \
        + (f" | {agg}" if nums_in else "") + (f" | by {a.by}" if a.by else "") + (f" | {period}s" if a.period else "") \
        + (f" | top {top}" if top else "") + (f" | compare {a.compare}" if cmp else "") \
        + (f" | where {where_text(wheres)}" if wheres else "")
    stubs, literal, many, timed, keys = [], {}, [], {}, []
    meas = nums_in[0] if nums_in else None
    f = _value_format(meas, agg)
    if shape == "bridge":
        step = texts_in[0]
        code, tname = _bridge_code(name, a.source, step, meas, cmp, wheres, top, sig)
        slots = {k: k for k in ("step", "base", "total", "rise", "fall", "key") if k in slot_names_}
        slots["floor"] = "floor"
        labels = {"step": pretty(step), "total": pretty(meas)}
        fmts = {k: f for k in ("base", "total", "rise", "fall", "key")}
        keys = ["step"]
        title = f"{pretty(meas)} went from {{start:{f}}} in {{a_label}} to {{end:{f}}} in {{b_label}}; {{top_step}} moved most"
        pool = [f"**Biggest mover:** {{top_step}}, {{top_change:+{f}}}.",
                f"**Overall:** {{change:+{f}}}, or {{change_pct:+.0%}}."]
    elif shape == "figures":
        code, tname = _figures_code(name, a.source, meas, agg, cmp, wheres, "note" in slot_names_, sig)
        slots = {"label": "label", "value": meas}
        if "note" in slot_names_:
            slots["note"] = "note"
        labels, fmts = {meas: pretty(meas)}, {meas: f}
        title = f"{pretty(meas)} {{change:+{f}}} from {{a_label}} to {{b_label}}"
        pool = [f"**{{b_label}}:** {{b_value:{f}}}, against {{a_value:{f}}} in {{a_label}} ({{change_pct:+.0%}})."]
    elif shape == "pivot":
        keys = list(dict.fromkeys(texts_in))
        timed = {k: time_kind(df[k]) for k in keys}
        code, tname = _pivot_code(name, a.source, keys, meas, agg, cmp, wheres, timed, period, top, sig)
        many = [s["name"] for s in note if s["count"] in ("one or more", "any") and s["kind"] == "number"][0]
        slots = {s["name"]: req[s["name"]][0] for s in note if s["kind"] == "text" and req.get(s["name"])}
        slots[many] = [cmp[4], cmp[5]]
        labels = {k: pretty(k) for k in keys}
        fmts = {cmp[4]: f, cmp[5]: f}
        title = f"{pretty(meas)} by {pretty(keys[0]).lower()}: {{top_label}} moved most, {{top_change:+{f}}}"
        pool = [f"**{{top_label}}:** {{top_change:+{f}}} from {{a_label}} to {{b_label}}.".replace(
                    "{a_label}", cmp[4]).replace("{b_label}", cmp[5]),
                f"**All groups:** {{total_a:{f}}} to {{total_b:{f}}} ({{change_pct:+.0%}})."]
    else:
        if a.by:
            many = [s["name"] for s in note if s["count"] in ("one or more", "any") and s["kind"] == "number"]
            if a.by not in df.columns:
                print(f"note: --by {a.by} ignored: '{a.source}' has no such column")
                a.by = None
            elif not many or len(req.get(many[0]) or []) != 1:
                print("note: --by ignored: it needs a slot taking one or more number columns, given one column")
                a.by = None
        recipe = c.get("recipe") or ""
        rules = recipe_rules(recipe, note)
        auto_slots = {}
        for slot, r in rules.items():   # worked out from the columns given, in the recipe's order
            if r["auto"] and all((req.get(d) and req[d][0] in df.columns) or d in auto_slots for d in r["auto"][1]):
                if req.get(slot):
                    print(f"note: {slot} is worked out for you ({r['text']}); --slot {slot}={','.join(req[slot])} ignored")
                auto_slots[slot] = r
                req.pop(slot, None)
            elif r["derived"] and req.get(slot):
                print(f"note: {slot} should be {r['text']}: make sure '{req[slot][0]}' is that")
        for s in note:
            if s["name"] in auto_slots:
                continue
            if s["count"] in ("one", "one or more") and not req.get(s["name"]):
                r = rules.get(s["name"]) or {}
                if r.get("derived") and s["kind"] != "figure":
                    req[s["name"]] = [s["name"]]
                    manual.append((s["name"], s["name"], s["kind"], f"work it out: {r['text']}"))
                    continue
                if s["kind"] == "figure":
                    literal[s["name"]] = "(to fill)"
                    manual.append((s["name"], None, "figure", "give a number, a column or a metric name in SLOTS"))
                else:
                    req[s["name"]] = [s["name"]]
                    manual.append((s["name"], s["name"], s["kind"], "make this column in the calculation"
                                   + (" (see the recipe line near the top)" if recipe else "")))
            elif s["count"] in ("optional", "any") and not req.get(s["name"]):
                print(f"info: optional slot '{s['name']}' left out")
        nums, kinds_ = [], {}
        for s in note:
            for col in req.get(s["name"]) or []:
                if col in df.columns:
                    (keys if s["kind"] == "text" else nums).append(col)
                elif s["kind"] == "figure":
                    literal[s["name"]] = float(col) if re.fullmatch(r"-?\d+(\.\d+)?", col) else col
                else:
                    stubs.append(col)
                    kinds_[col] = s["kind"]
                    if not any(m[1] == col for m in manual):
                        manual.append((s["name"], col, s["kind"], f"'{col}' is not in '{a.source}': make it in the "
                                       "calculation" + (" (see the recipe line near the top)" if recipe else "")))
        keys, nums, stubs = list(dict.fromkeys(keys)), list(dict.fromkeys(nums)), list(dict.fromkeys(stubs))
        numeric_stubs = {x for x in stubs if kinds_.get(x) == "number"}
        col_of = {sl: cols[0] for sl, cols in req.items() if cols}
        derived_lines = []
        for slot, r in auto_slots.items():
            target = slot.replace("-", "_") if slot.replace("-", "_") not in df.columns else slot.replace("-", "_") + "_calc"
            line = derive_code(slot, r["auto"], col_of, target)
            if line:
                derived_lines.append(f"{line}   # worked out (recipe): {r['text']}")
            else:                          # the recipe could not be turned into code: placeholder data instead
                stubs.append(target)
                kinds_[target] = "number"
                manual.append((slot, target, "number", f"work it out: {r['text']}"))
            col_of[slot] = target
            req[slot] = [target]
            numeric_stubs.add(target)
        if not note:   # an item whose data lives in its own script (AN-03): nothing to fill
            shape = "static"
        timed = {k: time_kind(df[k]) for k in keys}
    if shape == "static":
        code = (f'def {name}(src, params):\n    """Added by add-section: {sig}. {item_id} keeps its data in its own '
                f'script (SCRIPT below): change it there."""\n    df = src("{a.source}")\n'
                f'    return {{"question": "What does this show?", "tables": {{}}, "metrics": {{"rows": len(df)}}, "notes": ""}}\n')
        tname, slots, labels, fmts, title, pool = None, {}, {}, {}, f"{c['name']} (reword)", ["**Point:** reword."]
    elif shape == "plain":
        code, tname, _, f = _analytic_code(name, a.source, keys, nums, agg, a.by, timed, wheres, stubs, sig, period, top,
                                           kinds_, derived_lines)
        slots = {k: (v[0] if len(v) == 1 else v) for k, v in req.items() if k not in literal}
        slots.update(literal)
        if a.by:
            slots[many[0]] = "*"
        fmts = {"*": f} if a.by else {col: f for col in nums + [x for x in stubs if x in numeric_stubs]}
        fmts.update({req[sl][0]: f for sl in auto_slots if req.get(sl)})   # worked-out columns share the measure's format
        fmts.update({v: f for v in literal.values() if isinstance(v, str)})   # a figure named by a metric
        per_word = {"month": "Month", "quarter": "Quarter", "year": "Year"}[period]
        labels = {col: (f"{per_word} of {pretty(col).lower()}" if timed.get(col) == "date" else pretty(col))
                  for col in keys + ([] if a.by else nums) + stubs}
        first = nums[0] if nums else None
        ylab = pretty(first) if first and agg != "mean" else (f"Average {pretty(first).lower()}" if first else "Rows")
        xlab = labels.get(keys[0], "").lower() if keys else ""
        if keys and first:
            title = f"{ylab} by {xlab}: highest {{largest:{f}}}, in {{largest_label}}"
            pool = [f"**Highest:** {{largest_label}}, {{largest:{f}}}.",
                    ((f"**Highest {pretty(a.by).lower()}, latest {per_word.lower() if timed.get(keys[0]) else 'row'}:** "
                      f"{{top_group}}, {{top_group_total:{f}}}." if agg == "mean" else
                      f"**Largest {pretty(a.by).lower()}:** {{top_group}}, {{top_group_total:{f}}} in total.") if a.by else
                     f"**Latest:** {{latest_label}}, {{latest:{f}}}." if timed.get(keys[0]) else
                     "**Top {top_n}:** {share_of_all:.0%} of the total." if top else
                     f"**Lowest:** {{smallest_label}}, {{smallest:{f}}}."),
                    f"**{'Average' if agg == 'mean' else 'Total'}:** {{{'overall' if agg == 'mean' else 'total'}:{f}}}"
                    f" over {{groups}} {per_word.lower() + 's' if timed.get(keys[0]) else 'groups'}."]
        elif first:
            title, pool = f"{ylab}: {{total:{f}}}", [f"**Total:** {{total:{f}}}."]
        elif keys:
            title, pool = f"{pretty(keys[0])}: {{rows}} rows", ["**Rows:** {rows}."]
        else:
            title, pool = "Placeholder: fill the slots, then reword this title", ["**Point:** reword."]
    ns: dict = {}
    exec(code, ns)
    try:
        out = ns[name](runner.src, runner.all_params())
    except Exception as e:
        raise Stop(f"the calculation for the new section failed: {e}")
    import pandas as pd
    t = out["tables"][tname] if tname else pd.DataFrame()
    known = {str(x) for x in t.columns}
    smap = {k: ([x for x in map(str, t.columns) if x not in keys] if v == "*" else as_cols(v)) for k, v in slots.items()}
    if c["html"].count("data-echart") == 1:   # series of different types sharing a slot (a stem and a dot) read the same column
        sample = split_chart_block(c["html"])["chart"]
        for k, cols in list(smap.items()):
            ms = [m[0] for m in chart_marks(sample) if slot_names(m[0]["slot"]) == [k] and ":" not in m[0]["slot"]
                  and str(m[0].get("type") or "") not in AXIS_TYPES and not m[0]["slot"].startswith("=")]
            types = [m.get("type") for m in ms]
            if slots.get(k) != "*" and cols and len(set(types)) > 1 and len(cols) < len(ms):
                seen, wired = {}, []
                for typ in types:
                    seen[typ] = seen.get(typ, -1) + 1
                    wired.append(cols[min(seen[typ], len(cols) - 1)])
                smap[k] = slots[k] = wired
    rows = [{str(k): jsonable(v) for k, v in r.items()} for r in t.to_dict("records")]
    fill = Fill(rows, smap, known, labels, fmts, f"sections/{sid}.py", out.get("metrics"))
    q = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    what = {"bridge": f"{pretty(meas)} from {cmp[4]} to {cmp[5]}" if cmp else "",
            "figures": f"{pretty(meas or '')}, {cmp[4]} against {cmp[5]}" if cmp else "",
            "pivot": f"{pretty(meas or '')} by {pretty(keys[0]).lower() if keys else ''}, {cmp[4]} against {cmp[5]}" if cmp else ""}
    desc = a.desc or (what.get(shape) or title.split(":")[0]) + f", {item_id} {c['name']}"
    kind = c["type"]
    layout = "below" if kind == "table" else "above" if kind in ("hero card", "animation") or any(timed.values()) else "side"
    L = [f'"""Section {sid}: one block of the report. Everything for it is in this file."""', "",
         f"DESCRIPTION = {q(desc)}", f"USE = {q(item_id + ' ' + c['name'])}   # the library item this was copied from", "",
         "# Wiring: the visual's slots, filled from table DATA at every build (data changes need no edits).",
         f"# {item_id} takes: {c['dataLine']}"]
    if c.get("recipe") and shape == "plain":
        L.append(f"# recipe: {c['recipe']}")
    L += ([f"DATA = {q(tname)}"] if tname else []) + [f"SLOTS = {py_lit(slots)}",
          f"NAMES = {py_lit(labels)}   # words the reader sees for a column: legend, table headings",
          f"FORMAT = {py_lit(fmts)}   # number format per column: \"$short\", \".0%\", \",\", \"$,.0f\"",
          "", "", code.rstrip("\n"), "", "",
          f"TITLE = {q(title)}   # reword: the finding, as a sentence"]
    if a.bullets:
        L += ["BULLETS = [   # reword each: what the figure means; keep the {placeholders}"]
        L += [f"    {q(b)}," for b in pool[:a.bullets]] + ["]"]
    L += [f'LAYOUT = "{layout}"   # side, flip (visual left), above or below the text', "",
          f"# {item_id} {c['name']}, copied from the design library. Edit freely; data lists refill at every build."]
    edit = ["TITLE", "BASIS", "NAMES"]
    if kind == "chart" or (kind == "animation" and c["html"].count("data-echart") == 1):
        parts = split_chart_block(c["html"])
        opt = parts["chart"]
        before = [(x.get("type"), x.get("slot")) for x in (opt.get("series") or []) if isinstance(x, dict)]
        filled = fill_chart(opt, fill, first=True)
        after = [(x.get("type"), x.get("slot")) for x in (opt.get("series") or []) if isinstance(x, dict)]
        for typ, slot in before:
            if (typ, slot) in after:
                after.remove((typ, slot))
            elif slot in req:
                print(f"  check: the item's {typ} series for slot '{slot}' was left out: give that slot a column")
        for obj, _, _ in chart_marks(opt):   # data lists refill at build: keep only each styled point's style
            d = obj.get("data")
            if ":" not in obj["slot"] and isinstance(d, list):
                d = [dict(x, value=None) if isinstance(x, dict) and "value" in x else None for x in d]
                while d and d[-1] is None:
                    d.pop()
                obj["data"] = d
        _adapt_chart(opt, filled, fill, shape)
        L += chart_text(opt)
        if parts["key"]:
            L.append("KEY = " + py_block(parts["key"]) + "   # the legend, written by hand")
        if parts["html"]:
            L.append("HTML = " + py_block(parts["html"]) + "   # holds the chart; the build puts CHART in it")
        L.append(f"BASIS = {q(parts['basis'])}   # the line under the chart")
    else:
        block = c["html"].strip()
        inner = block[block.index(">") + 1:block.rindex("</div>")].strip("\n")
        L.append("HTML = " + py_block(fill_html(inner, fill, collapse=True)))
    if c.get("css"):
        L.append("CSS = " + py_block(c["css"], raw=True))
    if c.get("js"):
        L.append("SCRIPT = " + py_block(c["js"], raw=True))
    lines = ("\n".join(L) + "\n").splitlines()
    for slot, col, kind, todo in manual:   # the placeholder's own line says what to write there
        lines = [re.sub(r"# MANUAL: placeholder - make this column.*$", f"# MANUAL: {slot} - {todo}", ln)
                 if col and ln.lstrip().startswith(f't["{col}"]') else ln for ln in lines]
    text = "\n".join(lines) + "\n"
    for slot, col, kind, todo in manual:   # each placeholder, with the line to edit
        at = next((i for i, ln in enumerate(lines, 1) if (col and ln.lstrip().startswith(f't["{col}"]'))
                   or (not col and ln.startswith("SLOTS"))), 0)
        print(f"MANUAL: {slot} not filled - edit sections/{sid}.py:{at}: {todo}")
    return text, edit, f"{item_id} {c['name']}"


def _adapt_chart(o: dict, filled: dict, f: Fill, shape: str):
    """On adding: the sample's axis name follows the real column (number formats follow FORMAT at each build)."""
    series = o.get("series") if isinstance(o.get("series"), list) else []
    col_of = {id(s): c for s in series for c in [filled.get(id(s))] if c}
    if shape == "bridge":
        for s in series:
            if isinstance(s, dict) and s.get("slot") in ("total", "rise", "fall", "key"):
                col_of[id(s)] = s["slot"]
    for key in ("xAxis", "yAxis"):
        for j, ax in enumerate(_axes(o, key)):
            if ax.get("type", "value" if key == "yAxis" else "category") != "value":
                continue
            on_axis = [col_of[id(s)] for s in series if isinstance(s, dict) and id(s) in col_of
                       and int(s.get(key + "Index") or 0) == j]
            src = next((x for x in on_axis if x in f.names),          # a measure, not a worked-out column
                       next((x for x in f.names if x in f.fmts), on_axis[0] if on_axis else None))
            if src is None:
                continue
            if ax.get("name"):
                ax["name"] = f.label(src if shape != "bridge" else "total")
            if shape == "bridge" and key == "yAxis" and j == 0:
                ax["slot"] = "floor:min"


# ------------------------------------------------------------------ recipes: columns an item needs worked out first
# An item's recipe line names, slot by slot, how a column is made ("low: the smaller of start and end; gap: the
# difference between them"). The phrasings below are worked out by add-section itself; any other slot the recipe
# describes as a calculation is marked "work this out first" and gets placeholder data and a MANUAL line.

DERIVED_WORDS = re.compile(r"%|\bminus\b|difference|\bsum\b|running|cumulative|smaller|larger|position|as text|"
                           r"combined|indexed|in words|width|\bshare\b|=", re.I)


def recipe_rules(recipe: str, note: list) -> dict:
    """slot -> {"text": the recipe's words, "auto": (how, [slots]) or None, "derived": bool}."""
    names = {s["name"]: s for s in note}
    norm = lambda w: re.sub(r"\s+", "-", w.strip().lower())  # noqa: E731
    out, prev = {}, None
    for clause in re.split(r";\s*", recipe or ""):
        m = re.match(r"^\s*([A-Za-z][A-Za-z0-9 -]*?)\s*(:|=)\s*(.+)$", clause)
        if not m or norm(m.group(1)) not in names:
            continue
        slot, op, body = norm(m.group(1)), m.group(2), m.group(3).strip().rstrip(".")
        auto = None
        mm = re.match(r"^the (smaller|larger) of ([A-Za-z -]+?) and ([A-Za-z -]+?)$", body, re.I)
        if mm and norm(mm.group(2)) in names and norm(mm.group(3)) in names:
            auto = ("min" if mm.group(1).lower() == "smaller" else "max", [norm(mm.group(2)), norm(mm.group(3))])
        elif re.match(r"^the difference between them", body, re.I) and prev and prev[1] and len(prev[1]) == 2:
            auto = ("absdiff", list(prev[1]))
        elif re.match(r"^its (cumulative sum|running total)", body, re.I) and prev:
            auto = ("cumsum", [prev[0]])
        elif re.match(r"^the running total as a % of the grand total", body, re.I):
            main = next((n for n, s in names.items() if s["kind"] == "number" and n != slot), None)
            auto = ("cumshare", [main]) if main else None
        elif op == "=" and names[slot]["kind"] == "number":
            words = sorted(names, key=len, reverse=True)
            expr, deps = body, []
            for w in words:
                pat = r"(?<![\w-])" + re.escape(w).replace(r"\-", r"[\s-]") + r"(?![\w-])"
                if re.search(pat, expr, re.I):
                    deps.append(w)
                    expr = re.sub(pat, "{" + w + "}", expr, flags=re.I)
            expr = expr.replace("×", "*").replace("÷", "/").replace("−", "-")
            # only slot names, numbers and arithmetic: any other word (a name that is not a slot) means no code
            if deps and re.fullmatch(r"[\s0-9.()+*/-]*", re.sub(r"\{[a-z0-9-]+\}", "", expr)) \
                    and all(names[d]["kind"] == "number" for d in deps):
                auto = ("expr", deps, expr)
        derived = bool(auto or op == "=" or DERIVED_WORDS.search(body)) and names[slot]["kind"] != "figure"
        out[slot] = {"text": body, "auto": auto, "derived": derived}
        prev = (slot, auto[1] if auto else None)
    return out


def derive_code(slot: str, auto: tuple, col_of: dict, target: str) -> str | None:
    """The calculation line that works out a slot's column, or None when a column it needs is missing."""
    how, deps = auto[0], auto[1]
    cols = [col_of.get(d) for d in deps]
    if not all(cols):
        return None
    c = [json.dumps(x) for x in cols]
    expr = {"min": f"t[[{c[0]}, {c[1]}]].min(axis=1)" if len(c) == 2 else None,
            "max": f"t[[{c[0]}, {c[1]}]].max(axis=1)" if len(c) == 2 else None,
            "absdiff": f"(t[{c[0]}] - t[{c[1]}]).abs()" if len(c) == 2 else None,
            "cumsum": f"t[{c[0]}].cumsum()",
            "cumshare": f"t[{c[0]}].cumsum() / t[{c[0]}].sum() * 100"}.get(how)
    if how == "expr":
        expr = auto[2]
        for d, col in zip(deps, cols):
            expr = expr.replace("{" + d + "}", f"t[{json.dumps(col)}]")
    if not expr:
        return None
    line = f"    t[{json.dumps(target)}] = {expr}"
    try:                                   # never write a line that will not run
        compile(line.strip(), "<recipe>", "exec")
    except SyntaxError:
        return None
    return line


def show_item(rep, runner, rest, a) -> int:
    """show ID: an item's parts (never its code), the source columns that fit each, and an add-section to copy."""
    import contextlib
    import io
    import pandas as pd
    if len(rest) != 1:
        raise Stop("use: python run.py show CT-34 (ids: the design library's index/charts.md, tables.md, ...)")
    item_id = rest[0].upper()
    c = json.loads(node_item(find_library(rep, a.library), item_id, "--json"))[0]
    purpose = " ".join(str(c.get("purpose") or "").split())
    out = [f"{item_id} {c['name']} ({c['type']})", f"  {purpose[:150] + ' ...' if len(purpose) > 150 else purpose}"]
    if c["type"] == "animation":
        out.append(f"  moves: {c.get('attaches') or '-'}; fits: {c.get('fits') or '-'}")
        if str(c.get("fits") or "").startswith("none") or "report" not in str(c.get("fits") or ""):
            out.append("  not for a report: add a chart instead")
    note = c.get("data") or []
    need = {"one": "required, one column", "one or more": "required, one or more columns",
            "optional": "optional, one column", "any": "optional, any number of columns"}
    kind_word = {"text": "labels", "number": "numbers", "figure": "one value"}
    out.append("Parts:" if note else "Parts: none (its data is in its own script)")
    rules = recipe_rules(c.get("recipe") or "", note)
    for sl in note:
        r = rules.get(sl["name"]) or {}
        mark = "  worked out for you" if r.get("auto") else ("  work this out first" if r.get("derived") else "")
        out.append(f"  {sl['name']:<14} {kind_word.get(sl['kind'], sl['kind']):<9} {need.get(sl['count'], sl['count'])}{mark}")
    if c.get("recipe"):
        r = " ".join(c["recipe"].split())
        out.append(f"Recipe: {r[:300] + ' ...' if len(r) > 300 else r}")
    src = next((n for n in rep.SOURCES if n not in _live(rep)), None)
    if not note or src is None:
        out.append("No source to read here." if src is None and note else "")
        print("\n".join(x for x in out if x))
        return 0
    with contextlib.redirect_stderr(io.StringIO()):
        df = runner.src(src)
    text = [x for x in df.columns if not pd.api.types.is_numeric_dtype(df[x])]
    dates = [x for x in text if time_kind(df[x])]
    groups = sorted([x for x in text if x not in dates and 1 < df[x].nunique() <= 50], key=lambda x: df[x].nunique())
    numbers = [x for x in df.columns if pd.api.types.is_numeric_dtype(df[x]) and not pd.api.types.is_bool_dtype(df[x])]
    money = sorted(numbers, key=lambda x: not MONEY_RE.search(str(x)))
    out.append(f"Columns of '{src}' that fit:")
    picks, used = {}, set()
    for sl in note:
        r = rules.get(sl["name"]) or {}
        if r.get("auto"):
            out.append(f"  {sl['name']:<14} worked out from {' and '.join(r['auto'][1])}: {r['text']}")
            continue
        if r.get("derived"):
            out.append(f"  {sl['name']:<14} work this out first - {r['text']} (a MANUAL line will say where)")
            continue
        if sl["kind"] == "text":
            fit = (dates + groups) if re.search(r"month|period|quarter|year|date|age", sl["name"]) else (groups + dates)
        elif sl["kind"] == "number":
            fit = money
        else:
            fit = ["a number", "a metric name", *money[:2]]
        out.append(f"  {sl['name']:<14} {', '.join(map(str, fit[:6])) or '(none: it gets placeholder data)'}")
        if sl["count"] in ("one", "one or more") and sl["kind"] != "figure":
            pick = next((x for x in fit if x not in used), fit[0] if fit else None)
            if pick:
                picks[sl["name"]] = pick
                used.add(pick)
    bridge = {"step", "base", "total", "rise", "fall"} <= {sl["name"] for sl in note}
    cmd = f"python run.py add-section NAME --use {item_id} --source {src}"
    extra = ""
    if bridge and dates:
        months = sorted(pd.to_datetime(df[dates[0]], errors="coerce").dropna().dt.to_period("M").astype(str).unique())
        picks = {k: v for k, v in picks.items() if k in ("step", "total")}
        if len(months) >= 2:
            extra = f" --compare {dates[0]}={months[-2]},{months[-1]}"
    cmd += "".join(f" --slot {k}={v}" for k, v in picks.items()) + extra
    shaped = [x for x in picks.values() if x in dates]
    out.append("Add it (NAME: a short lower_snake_case name):")
    out.append(f"  {cmd}")
    tips = []
    if shaped:
        tips.append(f"{shaped[0]} is a date: grouped by month (--period quarter|year)")
    if any(x in groups and df[x].nunique() > 12 for x in picks.values()):
        tips.append("many groups: --top 10 keeps the largest")
    if bridge and not extra:
        tips.append("--compare COL=A,B builds the waterfall's columns")
    if c.get("recipe") and not bridge and any(r["derived"] and not r["auto"] for r in rules.values()):
        tips.append("slots marked 'work this out first' get placeholder data and a MANUAL line saying where to work them out")
    out += [f"  ({t})" for t in tips]
    print("\n".join(out))
    return 0


def check_section(rep, runner, name) -> int:
    """_check NAME: fill the texts and the visual of the sections that show NAME."""
    warns, filler = [], Filler(runner)
    for i, sec in enumerate(rep.SECTIONS, 1):
        if not isinstance(sec, dict) or sec.get("analytic") != name:
            continue
        res, where = runner.run(name), f"sections/{sec['file']}"
        filler.own, filler.own_name = res["metrics"], f"analytic '{name}'"
        print(f"  section {i}: {filler.fill(sec.get('title') or '', where + ' title', warns)}")
        for j, b in enumerate(sec.get("bullets") or []):
            print(f"    - {filler.fill(b, f'{where} bullet {j + 1}', warns).replace('**', '')}")
        visual_html(sec, res, filler, where, warns)
    for w in warns:
        print(f"  check: {w}")
    return 0


def _short(items, n=8) -> str:
    items = list(items)
    return ", ".join(map(str, items[:n])) + (f" (+{len(items) - n} more)" if len(items) > n else "") or "none"


def _live(rep) -> list:
    """Sources that need a live query (no file, no kept copy)."""
    return [n for n, s in rep.SOURCES.items() if (callable(s) or str(s).lower().endswith(".sql"))
            and not (n in rep.KEEP and (KEEP_DIR / f"{n}.parquet").exists())]


def _analytic_line(runner, name, live) -> str:
    """One line: the analytic's tables with their columns, and its metric names."""
    import contextlib
    import io
    if live:
        return f"     {name}(): not run here (a source is a live query); `python run.py {name}` shows it"
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            r = runner.run(name)
    except Stop as e:
        return f"     {name}(): fails: {e}"
    tabs = "; ".join(f"table {t} [{_short(df.columns, 10)}]" for t, df in r["tables"].items()) or "no tables"
    return f"     {name}(): {tabs}; metrics {_short(r['metrics'], 10)}"


def inventory(rep, runner) -> int:
    """list: the registry. One line per section in order, then sources with their columns."""
    import contextlib
    import io
    page = ROOT / f"{ROOT.name}.html"
    built = dt.datetime.fromtimestamp(page.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if page.exists() else "not built"
    basis = str(rep.ANSWER.get("basis") or "(not written)")
    out = [f"{rep.TITLE}  ({page.name}: {built})",
           "basis: " + (basis[:140] + " ..." if len(basis) > 140 else basis),
           f"DEFAULTS (sections/_shared.py): {_short(f'{k}={v}' for k, v in runner.all_params().items() if k not in rep.PARAMS)}"
           f" | PARAMS: {_short(f'{k}={v}' for k, v in rep.PARAMS.items())}",
           ""]
    live = _live(rep)
    out.append(f"Sections ({len(rep.SECTIONS)}), in order"
               + ("" if live else "; tables and metrics come from running each analytic once") + ":")
    for i, s in enumerate(rep.SECTIONS, 1):
        title = str(s.get("title") or "(no title)")
        kind = str(s.get("use") or "").split(" ")[0] or (
            "own" if s.get("chart") is not None or s.get("html") is not None else "text")
        desc = str(s.get("description") or "(no description)")
        out.append(f"  {i}. {s['file']:<28} {kind:<6} {title[:50] + '...' if len(title) > 50 else title}  | {desc}")
        out.append(_analytic_line(runner, s["analytic"], live))
    for sid in rep.UNUSED:
        out.append(f"  -  {sid}.py (not in the report)")
        out.append(_analytic_line(runner, SECTION_FILE_RE.match(sid).group(2), live))
    out.append("Sources:")
    for n in rep.SOURCES:
        if n in live:
            out.append(f"  {n}: live query, not read here")
            continue
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                df = runner.src(n)
        except Stop as e:
            out.append(f"  {n}: {e}")
            continue
        out.append(f"  {n}: {runner.src.used[n]['from']}, {len(df):,} rows")
        out += [describe_column(c, df[c]) for c in df.columns[:15]]
        if len(df.columns) > 15:
            out.append(f"    ... {len(df.columns) - 15} more columns")
    out.append("\nSee an item's parts and a ready command: python run.py show CT-34")
    print("\n".join(out))
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
    given = args[0] if args else ""
    if sys.platform == "win32":
        given = re.sub(r"^/([a-zA-Z])/", r"\1:/", given)          # /c/... from Git Bash
    out = Path(given) if given else ROOT / f"{ROOT.name}_shot.png"
    out = out.resolve()
    out.unlink(missing_ok=True)
    profile = tempfile.mkdtemp(prefix="report-shot-")
    base = [str(found[0]), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={profile}", "--virtual-time-budget=8000"]
    try:   # first the page's own height (page.html writes it on <html>), then the picture at that height
        url = page.as_uri() + "#shot"                     # every animation in its end state
        dom = subprocess.run(base + ["--window-size=1280,900", "--dump-dom", url],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120).stdout
        m = re.search(r'data-height="(\d+)"', dom or "")
        height = int(m.group(1)) + 4 if m else 750 + 600 * len(rep.SECTIONS)
        errors = re.search(r'data-errors="([^"]*)"', dom or "")
        subprocess.run(base + [f"--window-size=1280,{min(height, 16000)}", f"--screenshot={out}", url],
                       capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(f"{found[0].name} did not finish the screenshot: {e}")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not out.exists():
        raise Stop(f"{found[0].name} ran but wrote no screenshot to {out}")
    print(f"Screenshot: {out}")
    if errors:
        print(f"  check: the page had script errors: {html.unescape(errors.group(1)).strip(' |')}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="*", help="nothing, analytic names, report, list, add-section, theme, shot or data")
    ap.add_argument("--refresh", action="store_true", help="pull sources listed in KEEP again")
    ap.add_argument("--json", action="store_true", help="with data: JSON instead of CSV")
    ap.add_argument("--out", help="with data: write to this file instead of printing")
    ap.add_argument("--rows", type=int, default=3, help="with NAME: table rows to print")
    for opt in ("--use", "--own", "--source", "--agg", "--by", "--desc", "--library"):
        ap.add_argument(opt, help="with add-section (--library also with theme)")
    ap.add_argument("--slot", action="append", help="with add-section: SLOT=COLUMN or SLOT=COL1,COL2")
    ap.add_argument("--where", action="append", help="with add-section: col=value, col>=value or col<=value")
    ap.add_argument("--bullets", type=int, default=2, help="with add-section: 0 to 3")
    ap.add_argument("--period", help="with add-section: month (default), quarter or year for a date column")
    ap.add_argument("--top", type=int, help="with add-section: keep the N largest groups")
    ap.add_argument("--compare", help="with add-section: COL=A,B, two periods or groups side by side")
    ap.add_argument("--after", type=int, help="with add-section: put it after section N (default last)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        rep = load_report()
        what = args.what
        if what[:1] == ["theme"]:
            return set_theme(rep, what[1] if len(what) > 1 else "", args.library)
        runner = Runner(rep, load_sections(rep), args.refresh)
        if what == ["list"]:
            return inventory(rep, runner)
        if what[:1] == ["_check"] and len(what) == 2:
            return check_section(rep, runner, what[1])
        if what[:1] == ["add-section"]:
            return add_section(rep, runner, what[1:], args)
        if what[:1] == ["show"]:
            return show_item(rep, runner, what[1:], args)
        if what[:1] == ["shot"]:
            return screenshot(rep, what[1:])
        if what[:1] == ["data"]:
            return export_data(runner, what[1:], args.json, args.out)
        if what == ["report"]:
            out, warns = build(rep, runner)
            print(f"Report: {out}")
            for w in warns:
                print(f"  check: {w}")
            return 0
        names = what or list(runner.analytics)
        for n in names:
            print_result(runner.run(n), args.rows)
        print("\nNothing saved. The report is `python run.py report`.")
        return 0
    except Stop as e:
        print(f"STOP: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
