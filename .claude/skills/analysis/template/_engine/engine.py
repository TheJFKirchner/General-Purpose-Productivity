#!/usr/bin/env python3
"""DO NOT READ THIS FILE to run or build an analysis. `python run.py --help` lists the commands.
Read it only if a run.py command ended in a Python traceback (not a STOP: message) whose last
lines are in this file, and then only the function the traceback names.

Analysis engine: pulls sources, runs sections and, only when asked, builds the HTML report.

Copied into every analysis folder as _engine/. Do not edit it per analysis.
The look of the report is page.html in the analysis folder; that file may be edited.
Everything specific to an analysis lives in config.py, sections/, sql/ and inputs/.

Analysis (no report is built):
  python run.py                 pull sources if needed, run every section, print each summary table
  python run.py s2 [s3 ...]     run only those sections
  python run.py --refresh       pull every SQL source again first (also works with report)
  python run.py status          what exists and what is out of date

Report (only the sections listed in config.py REPORT, in that order):
  python run.py report          run the report's sections, build the HTML
  python run.py build           rebuild the HTML from saved tables
  python run.py commentary      write commentary for sections that need it, then build
  python run.py text            print the report as plain text (for the cold read)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent
SECTIONS = ROOT / "sections"
SRC_DIR = ROOT / "data" / "sources"
SEC_DIR = ROOT / "data" / "sections"
RUN_INFO = ROOT / "data" / "run_info.json"
COMM = ROOT / "commentary"
SHELL = COMM / "commentary_shell.json"
WRITTEN_FOR = COMM / "written_for.json"
OUT = ROOT / "output"

SUMMARY_MAX_ROWS, SUMMARY_MAX_COLS = 50, 15
REPORT_TABLE_MAX_ROWS = 500
ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"
SEC_FILE_RE = re.compile(r"^s(\d+)_[a-z0-9_]+\.py$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BODY_STYLE = {"format": "bullets", "bullets": 3, "max_words": 30}
HEADLINE_STYLE = {"format": "paragraph", "bullets": 1, "max_words": 18}
ANSWER_STYLE = {"format": "bullets", "bullets": 3, "max_words": 30}


class Stop(Exception):
    """A problem the person running the analysis must fix. Printed without a traceback."""


# ---------------------------------------------------------------- loading

def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_config():
    p = ROOT / "config.py"
    if not p.exists():
        raise Stop("config.py is missing")
    cfg = _load(p, "analysis_config")
    for f in ("TITLE", "QUESTION", "AUDIENCE", "SOURCES"):
        if not getattr(cfg, f, None):
            raise Stop(f"config.py: {f} is missing or empty")
        if "TODO" in str(getattr(cfg, f)):
            raise Stop(f"config.py: {f} still says TODO")
    if not isinstance(cfg.SOURCES, dict):
        raise Stop("config.py: SOURCES must be a dict of name -> file path")
    for name in cfg.SOURCES:
        if not NAME_RE.match(name):
            raise Stop(f"config.py: source name '{name}' must be lower_snake_case")
    if not hasattr(cfg, "PARAMS"):
        cfg.PARAMS = {}
    return cfg


class Section:
    def __init__(self, n: int, path: Path):
        self.n, self.id, self.path = n, f"s{n}", path
        self.mod = _load(path, f"section_{n}")
        for f in ("TITLE", "QUESTION", "compute"):
            if not hasattr(self.mod, f):
                raise Stop(f"sections/{path.name}: {f} is missing")
        self.title = str(self.mod.TITLE).strip()
        self.question = str(self.mod.QUESTION).strip()
        self.notes = str(getattr(self.mod, "NOTES", "") or "").strip()
        self.export = list(getattr(self.mod, "EXPORT", []) or [])
        if "TODO" in self.title or "TODO" in self.question:
            raise Stop(f"sections/{path.name}: TITLE or QUESTION still says TODO")

    def tables_on_disk(self) -> dict[str, Path]:
        pre = f"{self.id}_"
        return {p.stem[len(pre):]: p for p in sorted(SEC_DIR.glob(f"{pre}*.parquet"))}

    def summary_tables(self) -> list[str]:
        return [f"{self.id}_{n}" for n in self.tables_on_disk() if n.startswith("summary")]


def report_ids(cfg) -> list[str]:
    ids = [str(x).lower() for x in (getattr(cfg, "REPORT", None) or [])]
    if len(set(ids)) != len(ids):
        raise Stop("config.py: REPORT lists a section twice")
    return ids


def find_sections(only: list[str] | None = None) -> list[Section]:
    """Every section file, or only the ids given (in that order). Others are not loaded."""
    found = {}
    if str(SECTIONS) not in sys.path:
        sys.path.insert(0, str(SECTIONS))  # so sections can `import shared`
    for p in sorted(SECTIONS.glob("*.py")):
        if p.name == "shared.py":
            continue
        m = SEC_FILE_RE.match(p.name)
        if not m:
            raise Stop(f"sections/{p.name}: name must look like s1_short_name.py "
                       "(the only other file allowed is shared.py)")
        n = int(m.group(1))
        if n in found:
            raise Stop(f"two section files are numbered s{n}")
        found[n] = p
    if not found:
        raise Stop("no section files in sections/")
    if only is None:
        return [Section(n, found[n]) for n in sorted(found)]
    have = {f"s{n}": n for n in found}
    bad = [i for i in only if i not in have]
    if bad:
        raise Stop(f"config.py: REPORT names {', '.join(bad)}, but sections/ only has: {', '.join(have)}")
    return [Section(have[i], found[have[i]]) for i in only]


# ---------------------------------------------------------------- sources

class Sources:
    """Sections call src("name"). SQL results are saved in data/sources and reused."""

    def __init__(self, cfg, refresh: bool):
        self.cfg, self.refresh = cfg, refresh
        self.cache: dict[str, object] = {}
        self.used: dict[str, dict] = {}

    def __call__(self, name: str):
        import pandas as pd
        if name in self.cache:
            return self.cache[name].copy()
        if name not in self.cfg.SOURCES:
            raise Stop(f"a section asked for source '{name}', but config.py SOURCES only has: "
                       f"{', '.join(self.cfg.SOURCES) or 'nothing'}")
        spec = str(self.cfg.SOURCES[name])
        path = Path(spec) if Path(spec).is_absolute() else ROOT / spec
        if not path.exists():
            raise Stop(f"source '{name}': file not found: {spec}")
        ext = path.suffix.lower()
        pulled = None
        if ext == ".sql":
            saved = SRC_DIR / f"{name}.parquet"
            if saved.exists() and not self.refresh:
                df = pd.read_parquet(saved)
            else:
                run_query = getattr(self.cfg, "run_query", None)
                if run_query is None:
                    raise Stop(f"source '{name}' is a SQL file, but config.py has no run_query(sql) function")
                sql = path.read_text(encoding="utf-8")
                for k, v in self.cfg.PARAMS.items():
                    sql = sql.replace("{" + str(k) + "}", str(v))
                print(f"  pulling {name} ({spec}) ...", flush=True)
                df = run_query(sql)
                if not isinstance(df, pd.DataFrame):
                    raise Stop("config.py run_query(sql) must return a pandas DataFrame")
                SRC_DIR.mkdir(parents=True, exist_ok=True)
                df.to_parquet(saved, index=False)
            pulled = dt.datetime.fromtimestamp(saved.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        elif ext == ".csv":
            df = pd.read_csv(path)
        elif ext in (".tsv", ".txt"):
            df = pd.read_csv(path, sep="\t")
        elif ext == ".parquet":
            df = pd.read_parquet(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            raise Stop(f"source '{name}': unsupported file type {ext} (use .sql, .csv, .tsv, .parquet or .xlsx)")
        self.cache[name] = df
        self.used[name] = {"from": spec, "rows": int(len(df)), "pulled_at": pulled}
        return df.copy()


# ---------------------------------------------------------------- compute

def compute_section(sec: Section, src: Sources, params: dict) -> dict[str, int]:
    import pandas as pd
    try:
        out = sec.mod.compute(src, params)
    except Stop:
        raise
    except Exception:
        traceback.print_exc()
        raise Stop(f"sections/{sec.path.name}: compute() failed (traceback above)")
    if not isinstance(out, dict) or not out:
        raise Stop(f"sections/{sec.path.name}: compute() must return a dict of table name -> DataFrame")
    if "summary" not in out:
        raise Stop(f"sections/{sec.path.name}: compute() must return a table named 'summary' "
                   "(the small table the commentary is written from)")
    for name, df in out.items():
        if not NAME_RE.match(str(name)):
            raise Stop(f"sections/{sec.path.name}: table name '{name}' must be lower_snake_case")
        if not isinstance(df, pd.DataFrame):
            raise Stop(f"sections/{sec.path.name}: table '{name}' is not a DataFrame")
        if name.startswith("summary") and (len(df) > SUMMARY_MAX_ROWS or len(df.columns) > SUMMARY_MAX_COLS):
            raise Stop(f"sections/{sec.path.name}: table '{name}' is {len(df)} rows x {len(df.columns)} columns. "
                       f"Summary tables go to the commentary writer and must be at most "
                       f"{SUMMARY_MAX_ROWS} x {SUMMARY_MAX_COLS}. Aggregate it, or rename the table "
                       "so it is chart data only.")
        if name.startswith("summary") and len(df) == 0:
            raise Stop(f"sections/{sec.path.name}: table '{name}' is empty")
    for name in sec.export:
        if name not in out:
            raise Stop(f"sections/{sec.path.name}: EXPORT names '{name}', which compute() did not return")
    SEC_DIR.mkdir(parents=True, exist_ok=True)
    for old in sec.tables_on_disk().values():
        old.unlink()
    for name, df in out.items():
        df.to_parquet(SEC_DIR / f"{sec.id}_{name}.parquet", index=False)
    return {name: int(len(df)) for name, df in out.items()}


def save_run_info(src: Sources, ran: list[str]):
    info = json.loads(RUN_INFO.read_text(encoding="utf-8")) if RUN_INFO.exists() else {}
    info.setdefault("sources", {}).update(src.used)
    info.setdefault("sections_run_at", {}).update({s: now() for s in ran})
    RUN_INFO.parent.mkdir(parents=True, exist_ok=True)
    RUN_INFO.write_text(json.dumps(info, indent=1), encoding="utf-8")


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- commentary state

def _sha(*parts) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def fingerprints(cfg, secs: list[Section]) -> dict[str, str]:
    """One value per commentary unit; it changes when the question, notes or summary data change."""
    import pandas as pd
    fp = {}
    for s in secs:
        parts = [s.question, s.notes]
        for name, p in s.tables_on_disk().items():
            if name.startswith("summary"):
                parts.append(name + pd.read_parquet(p).to_csv(index=False))
        fp[s.id] = fp[f"{s.id}_headline"] = _sha(*parts)
    fp["answer"] = _sha(cfg.QUESTION, *[fp[s.id] for s in secs])
    return fp


def _wf_file() -> dict:
    return json.loads(WRITTEN_FOR.read_text(encoding="utf-8")) if WRITTEN_FOR.exists() else {}


def unit_keys(secs: list[Section]) -> list[str]:
    return ["answer"] + [k for s in secs for k in (f"{s.id}_headline", s.id)]


def commentary_ids(keys=()) -> dict[str, str]:
    """unit -> commentary id (C1, C2 ...). An id is given once and never changes or gets reused."""
    data = _wf_file()
    ids = data.get("_ids") or {}
    new = [k for k in keys if k not in ids]
    for k in new:
        ids[k] = f"C{len(ids) + 1}"
    if new:
        data["_ids"] = ids
        COMM.mkdir(parents=True, exist_ok=True)
        WRITTEN_FOR.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return ids


def latest_commentary() -> tuple[dict[str, dict], str | None]:
    d = COMM / "commentary_outputs"
    best, best_saved = None, ""
    if d.is_dir():
        for p in d.glob("commentary_*.json"):
            try:
                data = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if (data.get("saved_at") or "") >= best_saved:
                best, best_saved = data, data.get("saved_at") or ""
    out = {}
    unit_of = {c: k for k, c in commentary_ids().items()}
    for u in (best or {}).get("units", []):
        for e in u.get("commentary", []):
            if not e.get("filters"):
                out[unit_of.get(u["id"], u["id"])] = e
    return out, (best_saved[:16].replace("T", " ") if best else None)


def written_for() -> dict[str, str]:
    return {k: v for k, v in _wf_file().items() if k != "_ids"}


def commentary_state(cfg, secs) -> dict[str, dict]:
    """unit id -> {"state": none|current|stale|failed, "bullets": [...]}"""
    entries, _ = latest_commentary()
    fp, wf = fingerprints(cfg, secs), written_for()
    out = {}
    for uid in fp:
        e = entries.get(uid)
        if not e:
            out[uid] = {"state": "none", "bullets": []}
        elif e.get("status") != "ok":
            out[uid] = {"state": "failed", "bullets": []}
        elif wf.get(uid) not in (None, fp[uid]):
            out[uid] = {"state": "stale", "bullets": []}
        else:
            out[uid] = {"state": "current", "bullets": e.get("bullets") or [], "basis": e.get("basis") or ""}
    return out


def write_shell(cfg, secs: list[Section]) -> dict:
    gens, units = {}, []
    ids = commentary_ids(unit_keys(secs))
    for s in secs:
        gid = str(s.n)  # one writer call per section: small, fast, and one failure stays local
        gens[gid] = {"audience": cfg.AUDIENCE}
        base = {"generator": int(gid), "tables": s.summary_tables()}
        if s.notes:
            base["notes"] = s.notes
        units.append({"id": ids[f"{s.id}_headline"], "placement": f"{s.id} heading", **base,
                      "covers": "The single most important finding, as one plain sentence, on: " + s.question,
                      "style": HEADLINE_STYLE})
        units.append({"id": ids[s.id], "placement": f"{s.id} body", **base,
                      "covers": s.question, "style": BODY_STYLE})
    gens["answer"] = {"audience": cfg.AUDIENCE, "inputs": "commentary"}
    units.append({"id": ids["answer"], "generator": "answer", "placement": "answer, top of report", "tables": [],
                  "covers": "The direct answer to: " + cfg.QUESTION, "style": ANSWER_STYLE})
    shell = {"deliverable": ROOT.name, "medium": "report", "data_dir": "../data/sections",
             "question": cfg.QUESTION, "derive": False, "generators": gens, "units": units}
    COMM.mkdir(parents=True, exist_ok=True)
    SHELL.write_text(json.dumps(shell, indent=1), encoding="utf-8")
    return shell


def find_commentary_skill(arg: str | None) -> Path:
    cands = [arg, os.environ.get("COMMENTARY_SKILL")]
    cands += [p / ".claude" / "skills" / "commentary" for p in [ROOT, *ROOT.parents]]
    cands.append(Path.home() / ".claude" / "skills" / "commentary")
    for c in cands:
        if c and (Path(c) / "scripts" / "generate.py").exists():
            return Path(c)
    raise Stop("cannot find the commentary skill. Pass its folder: "
               "python run.py commentary --skill <path to skills/commentary>")


def run_commentary(cfg, secs, skill_arg: str | None) -> int:
    missing = [s.id for s in secs if "summary" not in s.tables_on_disk()]
    if missing:
        raise Stop(f"no saved tables for {', '.join(missing)}. Run `python run.py report` first.")
    skill = find_commentary_skill(skill_arg)
    write_shell(cfg, secs)
    state, fp = commentary_state(cfg, secs), fingerprints(cfg, secs)
    stale = [uid for uid, st in state.items() if st["state"] == "stale"]
    todo = [uid for uid, st in state.items() if st["state"] != "current"]
    if todo and "answer" not in todo:   # the answer is written from the sections' commentary
        todo.append("answer")
        stale.append("answer")
    if not todo:
        print("Commentary is up to date for every section. Nothing to write.")
        print("To rewrite on purpose: change the section's NOTES or QUESTION, or use the commentary "
              "skill's generate.py --override.")
        return 0
    ids = commentary_ids(unit_keys(secs))
    print("Writing commentary for: " + ", ".join(f"{ids[u]} ({u})" for u in todo), flush=True)
    cmd = [sys.executable, str(skill / "scripts" / "generate.py"), str(SHELL)]
    if stale:
        cmd += ["--override", *[ids[u] for u in stale]]
    code = subprocess.run(cmd).returncode
    if code == 2:
        raise Stop("the commentary skill rejected the shell (messages above). Nothing was written.")
    entries, _ = latest_commentary()
    wf = written_for()
    for uid in fp:
        e = entries.get(uid)
        if e and e.get("status") == "ok" and (uid in todo or uid not in wf):
            wf[uid] = fp[uid]
    WRITTEN_FOR.write_text(json.dumps({**wf, "_ids": commentary_ids()}, indent=1), encoding="utf-8")
    return code


# ---------------------------------------------------------------- report pieces

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
    if isinstance(o, np.generic):
        o = o.item()
    if o is None or isinstance(o, (str, bool, int)):
        return o
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    try:
        if pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(o, "isoformat"):
        s = o.isoformat()
        return s[:10] if s.endswith("T00:00:00") else s
    return str(o)


def _fmt_cell(v, spec: str | None) -> tuple[str, bool]:
    """(text, is_number)"""
    v = jsonable(v)
    if v is None:
        return "", False
    if isinstance(v, bool):
        return ("Yes" if v else "No"), False
    if isinstance(v, (int, float)):
        if spec:
            return format(v, spec), True
        return (f"{v:,}" if isinstance(v, int) else f"{v:,.2f}"), True
    return str(v), False


def render_table(df, fmt: dict) -> str:
    cols = [str(c) for c in df.columns]
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    rows = []
    for row in df.itertuples(index=False, name=None):
        tds = []
        for c, v in zip(cols, row):
            text, num = _fmt_cell(v, fmt.get(c))
            raw = jsonable(v)
            sort = "" if raw is None else html.escape(str(raw), quote=True)
            tds.append(f'<td{" class=num" if num else ""} data-v="{sort}">{html.escape(text)}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def section_visuals(sec: Section) -> tuple[str, dict]:
    """Return (html for the section's visuals, {chart id: ECharts option})."""
    import pandas as pd
    files = sec.tables_on_disk()
    if not files:
        raise Stop(f"{sec.id}: no saved tables. Run `python run.py {sec.id}` first.")
    data = {name: pd.read_parquet(p) for name, p in files.items()}
    if not hasattr(sec.mod, "charts"):
        raise Stop(f"sections/{sec.path.name}: it is in the report, so it needs a charts(data) function")
    try:
        items = sec.mod.charts(data)
    except Exception:
        traceback.print_exc()
        raise Stop(f"sections/{sec.path.name}: charts() failed (traceback above)")
    if not isinstance(items, list):
        raise Stop(f"sections/{sec.path.name}: charts() must return a list")
    parts, options = [], {}
    for i, it in enumerate(items):
        where = f"sections/{sec.path.name}: charts() item {i + 1}"
        if not isinstance(it, dict) or not it.get("title"):
            raise Stop(f"{where}: needs a 'title'")
        if ("option" in it) == ("table" in it):
            raise Stop(f"{where}: needs exactly one of 'option' (an ECharts option) or 'table' (a DataFrame)")
        cls = "card half" if it.get("width") == "half" else "card"
        note = f'<p class="note">{html.escape(str(it["note"]))}</p>' if it.get("note") else ""
        cap = f"<figcaption>{html.escape(str(it['title']))}</figcaption>"
        if "option" in it:
            cid = f"{sec.id}-{i}"
            options[cid] = jsonable(it["option"])
            h = int(it.get("height", 360))
            body = f'<div class="chart" data-chart="{cid}" style="height:{h}px"></div>'
        else:
            df = it["table"]
            if not isinstance(df, pd.DataFrame):
                raise Stop(f"{where}: 'table' must be a DataFrame")
            if len(df) > REPORT_TABLE_MAX_ROWS:
                raise Stop(f"{where}: {len(df)} rows. A table in the report is for rows the reader will read "
                           f"(limit {REPORT_TABLE_MAX_ROWS}). Show the top rows and put the full list in EXPORT.")
            body = render_table(df, it.get("format") or {})
        parts.append(f'<figure class="{cls}">{cap}{body}{note}</figure>')
    exports = []
    for name in sec.export:
        if name not in data:
            raise Stop(f"{sec.id}: EXPORT names '{name}', which is not saved. Run `python run.py {sec.id}`.")
        fn = f"{ROOT.name}_{sec.id}_{name}.csv"
        OUT.mkdir(parents=True, exist_ok=True)
        data[name].to_csv(OUT / fn, index=False)
        exports.append(f'<a href="{html.escape(fn)}">{html.escape(fn)}</a> ({len(data[name]):,} rows)')
    if exports:
        parts.append(f'<p class="export">Full detail, saved beside this report: {"; ".join(exports)}</p>')
    return "\n".join(parts), options


def bullets_html(bullets: list[dict]) -> str:
    lis = []
    for b in bullets:
        flag = ' <span class="unverified">[unverified figure]</span>' if b.get("unverified") else ""
        lis.append(f"<li>{html.escape(b.get('text', ''))}{flag}</li>")
    return '<ul class="commentary">' + "".join(lis) + "</ul>"


def build(cfg, secs: list[Section]) -> Path:
    state = commentary_state(cfg, secs)
    _, comm_saved = latest_commentary()
    pending_msg = {"none": "Commentary has not been written yet.",
                   "stale": "The data changed after the commentary was written. Commentary is hidden until it is rewritten.",
                   "failed": "Commentary for this part failed its checks and is hidden."}
    ids = commentary_ids(unit_keys(secs))

    def source_html(uid: str) -> str:
        st = state[uid]
        if st["state"] != "current":
            return ""
        return (f'<details class="src"><summary>{ids[uid]} &middot; where these figures come from</summary>'
                f'<p>{html.escape(st.get("basis") or "No source was recorded.")}</p></details>')

    sec_html, options = [], {}
    for pos, s in enumerate(secs, 1):
        visuals, opts = section_visuals(s)
        options.update(opts)
        head, body = state[f"{s.id}_headline"], state[s.id]
        h2 = head["bullets"][0]["text"] if head["state"] == "current" and head["bullets"] else s.title
        comm = bullets_html(body["bullets"]) if body["state"] == "current" else \
            f'<p class="pending">{pending_msg[body["state"]]}</p>'
        sec_html.append(
            f'<section class="sec" id="{s.id}">'
            f'<div class="eyebrow" title="sections/{html.escape(s.path.name)}">{pos} &middot; {html.escape(s.title)}</div>'
            f'<h2 data-cid="{ids[s.id + "_headline"]}" title="{ids[s.id + "_headline"]}">{html.escape(h2)}</h2>'
            f'<p class="q">{html.escape(s.question)}</p>{comm}{source_html(s.id)}'
            f'<div class="grid">{visuals}</div></section>')
    ans = state["answer"]
    answer = bullets_html(ans["bullets"]) if ans["state"] == "current" else \
        f'<p class="pending">{pending_msg[ans["state"]]}</p>'
    answer += source_html("answer")

    info = json.loads(RUN_INFO.read_text(encoding="utf-8")) if RUN_INFO.exists() else {}
    src_rows = []
    for name, spec in cfg.SOURCES.items():
        u = (info.get("sources") or {}).get(name, {})
        rows = f"{u['rows']:,}" if "rows" in u else "not used"
        pulled = f", pulled {u['pulled_at']}" if u.get("pulled_at") else ""
        src_rows.append(f"<li><b>{html.escape(name)}</b>: {html.escape(str(spec))} ({rows} rows{pulled})</li>")
    params = "; ".join(f"{k} = {v}" for k, v in cfg.PARAMS.items()) or "none"
    n_unv = sum(1 for st in state.values() for b in st["bullets"] if b.get("unverified"))
    comm_line = f"written {comm_saved}" if comm_saved else "not written"
    if n_unv:
        comm_line += f", {n_unv} bullet(s) with a figure that could not be checked"
    files = "; ".join(f"{i} = sections/{html.escape(s.path.name)}" for i, s in enumerate(secs, 1))
    foot = (f"<p><b>Analysis:</b> {html.escape(ROOT.name)} &middot; <b>Built:</b> {now()} &middot; "
            f"<b>Parameters:</b> {html.escape(params)} &middot; <b>Commentary:</b> {comm_line}</p>"
            f"<ul>{''.join(src_rows)}</ul>"
            f"<p><b>Sections:</b> {files}</p>"
            "<p>Rerun: <code>python run.py report</code> in the analysis folder. Every figure and table reads "
            "from <code>data/sections/</code>.</p>")

    lib = ENGINE / "echarts.min.js"
    if lib.exists():
        echarts = "<script>" + lib.read_text(encoding="utf-8").replace("</script", "<\\/script") + "</script>"
    else:
        echarts = f'<script src="{ECHARTS_CDN}"></script>'
        print("  note: _engine/echarts.min.js is not present, so the report loads ECharts from the internet. "
              "Put the file there to make the report fully standalone.")
    page_file = ROOT / "page.html"
    if not page_file.exists():  # folders made before page.html moved out of _engine/
        page_file = ENGINE / "template.html"
    if not page_file.exists():
        raise Stop("page.html is missing from the analysis folder. Copy it from the analysis skill's template/.")
    page = page_file.read_text(encoding="utf-8")
    lost = [t for t in ("__ANSWER__", "__SECTIONS__", "__CHARTS__", "__ECHARTS__") if t not in page]
    if lost:
        raise Stop(f"page.html has lost {', '.join(lost)}. Put them back; the build fills them in.")
    for token, value in {
        "__TITLE__": html.escape(cfg.TITLE), "__QUESTION__": html.escape(cfg.QUESTION),
        "__SLUG__": html.escape(ROOT.name), "__DATE__": dt.date.today().isoformat(),
        "__ANSWER__": answer, "__SECTIONS__": "\n".join(sec_html), "__FOOTER__": foot,
        "__CHARTS__": json.dumps(options).replace("</", "<\\/"), "__ECHARTS__": echarts,
    }.items():
        page = page.replace(token, value)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{ROOT.name}_{dt.date.today().isoformat()}.html"
    out.write_text(page, encoding="utf-8")
    return out


def report_text(cfg, secs: list[Section]) -> str:
    """The report as a reader meets it, in plain text. Used for the cold read."""
    import pandas as pd
    state = commentary_state(cfg, secs)

    def bl(uid):
        st = state[uid]
        return [f"  - {b['text']}" for b in st["bullets"]] if st["state"] == "current" else ["  (no commentary shown)"]

    L = [cfg.TITLE, "", cfg.QUESTION, "", "THE ANSWER", *bl("answer")]
    for pos, s in enumerate(secs, 1):
        head = state[f"{s.id}_headline"]
        h = head["bullets"][0]["text"] if head["state"] == "current" and head["bullets"] else s.title
        L += ["", f"SECTION {pos} - {s.title}", h, s.question, *bl(s.id)]
        data = {n: pd.read_parquet(p) for n, p in s.tables_on_disk().items()}
        for it in s.mod.charts(data):
            kind = "table" if "table" in it else "chart"
            L.append(f"  [{kind}] {it.get('title')}" + (f" (note: {it['note']})" if it.get("note") else ""))
            if kind == "table":
                df = it["table"]
                L.append("    " + " | ".join(str(c) for c in df.columns))
                for row in df.head(15).itertuples(index=False, name=None):
                    L.append("    " + " | ".join(_fmt_cell(v, (it.get("format") or {}).get(str(c)))[0]
                                                 for c, v in zip(df.columns, row)))
                if len(df) > 15:
                    L.append(f"    ... {len(df) - 15} more rows")
            else:
                o = it["option"]
                ser = o.get("series") or []
                ser = ser if isinstance(ser, list) else [ser]
                names = [str(x.get("name")) for x in ser if isinstance(x, dict) and x.get("name")]
                axes = []
                for k in ("xAxis", "yAxis"):
                    ax = o.get(k)
                    for one in (ax if isinstance(ax, list) else [ax]):
                        if isinstance(one, dict) and one.get("name"):
                            axes.append(str(one["name"]))
                if names:
                    L.append("    series: " + ", ".join(names))
                if axes:
                    L.append("    axes: " + ", ".join(axes))
                cats = next((jsonable(a["data"]) for k in ("xAxis", "yAxis")
                             for a in ([o.get(k)] if isinstance(o.get(k), dict) else (o.get(k) or []))
                             if isinstance(a, dict) and a.get("data") is not None), None)
                if cats and len(cats) <= 24:
                    for x in ser:
                        vals = jsonable(x.get("data")) if isinstance(x, dict) else None
                        if isinstance(vals, list) and len(vals) == len(cats):
                            pts = ", ".join(f"{c}: {v.get('value') if isinstance(v, dict) else v}"
                                            for c, v in zip(cats, vals))
                            L.append(f"    {x.get('name') or 'values'}: {pts}")
        if s.export:
            L.append("  [file] full detail: " + ", ".join(s.export))
    return "\n".join(L)


# ---------------------------------------------------------------- status and main

def print_summaries(sec: Section):
    import pandas as pd
    for name, p in sec.tables_on_disk().items():
        df = pd.read_parquet(p)
        print(f"    {name}: {len(df):,} rows")
        if name.startswith("summary"):
            text = df.to_string(index=False, max_rows=20, max_cols=SUMMARY_MAX_COLS, line_width=160)
            print("\n".join("      " + line for line in text.splitlines()))


def print_status(cfg, in_report: list[str]):
    secs = find_sections()
    rep_secs = [s for i in in_report for s in secs if s.id == i]
    state = commentary_state(cfg, rep_secs) if rep_secs and all(
        "summary" in s.tables_on_disk() for s in rep_secs) else None
    ids = commentary_ids(unit_keys(rep_secs))
    for s in secs:
        tabs = s.tables_on_disk()
        t = ", ".join(tabs) if tabs else "NOT RUN"
        if s.id not in in_report:
            print(f"  {s.id}  {s.title}\n      tables: {t}\n      not in the report")
            continue
        c = state[s.id]["state"] if state else "-"
        print(f"  {s.id}  {s.title}\n      tables: {t}\n      in the report; commentary {ids[s.id]}: {c} "
              f"(heading is {ids[s.id + '_headline']})")
    if not in_report:
        print("  Report: not started (config.py REPORT is empty)")
        return
    print(f"  Report order: {', '.join(in_report)}")
    if state:
        print(f"  answer (top of report): commentary {ids['answer']}: {state['answer']['state']}")
        need = [u for u, st in state.items() if st["state"] != "current"]
        if need:
            print("  Next: python run.py commentary")
        unv = [(u, b["text"]) for u, st in state.items() for b in st["bullets"] if b.get("unverified")]
        for u, text in unv:
            print(f"  UNVERIFIED FIGURE in {ids[u]}: {text}")


REPORT_CMDS = ("report", "build", "commentary", "text")


def run_sections(cfg, todo: list[Section], refresh: bool, show: bool):
    src = Sources(cfg, refresh)
    if refresh:
        for name, spec in cfg.SOURCES.items():
            if str(spec).lower().endswith(".sql"):
                src(name)
    for s in todo:
        print(f"{s.id}  {s.title}", flush=True)
        rows = compute_section(s, src, cfg.PARAMS)
        if show:
            print_summaries(s)
        else:
            for name, n in rows.items():
                print(f"    {name}: {n:,} rows")
    save_run_info(src, [s.id for s in todo])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="*", help="nothing, section ids (s1 s2), status, report, build, commentary or text")
    ap.add_argument("--refresh", action="store_true", help="pull every SQL source again")
    ap.add_argument("--skill", help="with commentary: path to the commentary skill folder")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        cfg = load_config()
        in_report = report_ids(cfg)
        what = [w.lower() for w in args.what]
        if what == ["status"]:
            print_status(cfg, in_report)
            return 0
        if len(what) == 1 and what[0] in REPORT_CMDS:
            if not in_report:
                raise Stop("config.py: REPORT is empty, so there is no report to build. The report comes after "
                           "the answer is agreed (gate 2): then list the sections it uses, in order, "
                           'for example REPORT = ["s1", "s3"].')
            secs = find_sections(in_report)
            if what == ["text"]:
                print(report_text(cfg, secs))
                return 0
            code = 0
            if what == ["commentary"]:
                code = run_commentary(cfg, secs, args.skill)
            elif what == ["report"]:
                run_sections(cfg, secs, args.refresh, show=False)
            out = build(cfg, secs)
            print(f"Report: {out}")
            print_status(cfg, in_report)
            return code
        secs = find_sections()
        by_id = {s.id: s for s in secs}
        bad = [w for w in what if w not in by_id]
        if bad:
            raise Stop(f"unknown: {' '.join(bad)}. Use section ids ({', '.join(by_id)}), status, "
                       f"{', '.join(REPORT_CMDS)}.")
        run_sections(cfg, [by_id[w] for w in what] or secs, args.refresh, show=True)
        print("Tables saved. No report built; that is `python run.py report`, after the answer is agreed.")
        return 0
    except Stop as e:
        print(f"STOP: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
