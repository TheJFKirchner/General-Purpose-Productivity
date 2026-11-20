"""Project check for the Analysis side (used by Tools/check.mjs; no server needed).

    python Analysis/check.py                 every analytic, each run with all its fast filters at "All"
    python Analysis/check.py --cards s1_summary,s2_revenue_trend
    python Analysis/check.py --show s3_paid_by_region [--filter region=East]   one section's full result, readable
    python Analysis/check.py --tables --sections s1,s2 --by region [--out f.json]   scenario tables (npm run tables)

Prints JSON on stdout:
    {
      "cards":      {id: {"filters", "tables", "module", "metrics", "error"}},
      "modules":    {module: null | "import error"},     # a tab module that fails to import registers no analytics
      "filters":    {name: [All, ...values in the data]},
      "parameters": {name: {label, type, options, value, default}},   # same as /api/meta
      "manifest":   Data/Current/manifest.json
    }
Exit code 0 even when analytics fail (the failures are in the JSON); 2 when there is no data at all.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import itertools
import json
import re
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from Shared import engine, tables  # noqa: E402
from Shared.registry import CARDS  # noqa: E402

SKIP = {"server", "check", "precompute"}


def import_modules() -> dict:
    """Import every tab module separately, so one broken module doesn't hide the others' analytics."""
    out = {}
    for f in sorted(HERE.glob("*.py")):
        name = f.stem
        if name in SKIP or name.startswith("_"):
            continue
        try:
            importlib.import_module(name)
            out[name] = None
        except Exception as e:  # noqa: BLE001 - reported by Tools/check.mjs
            tb = traceback.extract_tb(e.__traceback__)
            where = next((f"{Path(fr.filename).name}:{fr.lineno}" for fr in reversed(tb) if Path(fr.filename).parent == HERE), "")
            if isinstance(e, SyntaxError) and e.lineno:
                where = f"{Path(e.filename or f).name}:{e.lineno}"
            out[name] = f"{type(e).__name__}: {e}" + (f" ({where})" if where else "")
    from Shared.registry import register_shapes
    register_shapes()   # sections declared in their .jsx meta
    return out


def parameters(m: dict) -> dict:
    import server  # the same parameter logic as /api/meta
    return server.parameters(m)


def uses_report(cid: str) -> bool:
    """Does this section's analytic call a report analytic (Shared.reuse.from_report)?"""
    try:
        return "from_report(" in inspect.getsource(CARDS[cid].fn)
    except (OSError, TypeError):
        return False


def slice_failures(cid: str, options: dict) -> list[str]:
    """Run a section that reuses a report analytic once per value of each of its filters; real failures only
    (a thin slice that raises NoData is fine: it shows "Not enough data for this selection")."""
    out = []
    for name in CARDS[cid].filters:
        for value in options.get(name, [])[1:]:
            r = engine.run(cid, {name: value})
            if "error" in r and not r.get("noData"):
                out.append(f"{name}={value}: {r['error']}")
    return out


def title_of(cid: str) -> str | None:
    try:
        src = (HERE.parent / "Src" / "Sections" / f"{cid}.jsx").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"title\s*:\s*([\"'])(.*?)\1", src)
    return m.group(2) if m else None


def columns_of(data) -> list | None:
    """The columns of a section's data rows (data = {"rows": [...]}), for checking its slots; None without rows."""
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    return list(dict.fromkeys(k for r in rows if isinstance(r, dict) for k in r))


def ranges_of(data) -> dict | None:
    """The largest absolute value of each number column in a section's data rows, to check its formats."""
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    out = {}
    for r in rows:
        for k, v in (r.items() if isinstance(r, dict) else []):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = max(out.get(k, 0), abs(v))
    return out


def tidy(v):
    """Round for reading: amounts to cents, small rates to 4 decimals."""
    if isinstance(v, float):
        return round(v, 2) if abs(v) >= 1 else round(v, 4)
    if isinstance(v, dict):
        return {k: tidy(x) for k, x in v.items()}
    if isinstance(v, list):
        return [tidy(x) for x in v]
    return v


def scenario_tables(section_ids: list[str], by: list[str], options: dict) -> dict:
    """For each section, each scenario: every combination of the --by filter columns that reach it (each value,
    plus All), with the section's data and metrics, and on_page: the metrics of every section on the same tab for
    that scenario (Tools/tables.mjs turns them into the notes a reader already sees). Filters are keyed by column."""
    from Shared.registry import section_tab
    specs = tables.specs("filters")
    name_of = {s.get("column", n): n for n, s in specs.items()}
    unknown = [c for c in by if c not in name_of]
    if unknown:
        raise SystemExit(f"--by: {', '.join(unknown)} is not a filter column in dashboard.config.json "
                         f"({', '.join(name_of) or 'none'})")
    out = {}
    for cid in section_ids:
        if cid not in CARDS:
            raise SystemExit(f"--sections: no analytic for {cid}")
        reach = [c for c in by if name_of[c] in CARDS[cid].filters]
        scenarios = []
        tab = section_tab(cid)
        siblings = [s for s in CARDS if section_tab(s) == tab]
        for combo in itertools.product(*[options.get(name_of[c], [tables.ALL]) for c in reach]):
            set_ = {c: v for c, v in zip(reach, combo) if v != tables.ALL}
            chosen = {name_of[c]: v for c, v in set_.items()}
            r = engine.run(cid, chosen)
            on_page = {}
            for s in siblings:
                rs = engine.run(s, {n: v for n, v in chosen.items() if n in CARDS[s].filters})
                if "error" not in rs:
                    on_page[s] = rs["metrics"]
            scenarios.append({"filters": set_, "label": ", ".join(f"{c}={v}" for c, v in set_.items()) or "all",
                              **({"note": r["error"]} if "error" in r else {"data": r["data"], "metrics": r["metrics"]}),
                              "on_page": on_page})
        out[cid] = {"title": title_of(cid), "filters_reaching": [specs[n].get("column", n) for n in CARDS[cid].filters],
                    "scenarios": scenarios}
    return tidy({"sections": out})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cards", help="comma-separated section ids (default: every registered analytic)")
    ap.add_argument("--show", metavar="CARD", help="print one section's full result (data and metrics) as indented JSON")
    ap.add_argument("--filter", action="append", default=[], metavar="NAME=VALUE", help="with --show: a filter choice")
    ap.add_argument("--tables", action="store_true", help="scenario tables for commentary (npm run tables)")
    ap.add_argument("--sections", help="with --tables: comma-separated section ids")
    ap.add_argument("--by", default="", help="with --tables: comma-separated filter columns to vary")
    ap.add_argument("--out", help="with --tables: write the JSON here (default: print it)")
    ap.add_argument("--describe", action="store_true", help="add every table's columns (type, sample, date range)")
    ap.add_argument("--describe-only", action="store_true", help="print only the tables' columns (used by new-section)")
    a = ap.parse_args()

    modules = import_modules()
    m = tables.manifest()
    if not m["tables"]:
        print(json.dumps({"error": "No data yet. Add write_source lines to Pipeline/sources.py, then npm run pipeline", "modules": modules}))
        return 2
    if a.describe_only:
        print(json.dumps({"describe": tables.describe(m)}, default=str))
        return 0
    if a.tables:
        if not a.sections:
            raise SystemExit("npm run tables -- --sections <id,id> [--by <filter column,column>] [--out <file>]")
        data = scenario_tables([c for c in a.sections.split(",") if c], [c for c in a.by.split(",") if c],
                               tables.filter_options(m))
        text = json.dumps(data, indent=1, default=str)
        if a.out:
            Path(a.out).write_text(text + "\n", encoding="utf-8", newline="\n")
            n = sum(len(s["scenarios"]) for s in data["sections"].values())
            print(f"wrote {a.out}: {len(data['sections'])} section(s), {n} scenario(s)")
        else:
            print(text)
        return 0
    if a.show:
        broken = {k: v for k, v in modules.items() if v}
        if a.show not in CARDS:
            print(json.dumps({"error": f"no analytic for {a.show}", "broken_modules": broken}, indent=2))
            return 1
        chosen = dict(f.split("=", 1) for f in a.filter if "=" in f)
        stray = [n for n in chosen if n not in CARDS[a.show].filters]
        if stray:
            print(json.dumps({"error": f"filter {', '.join(stray)} does not reach {a.show} "
                                       f"(it takes: {', '.join(CARDS[a.show].filters) or 'none'})"}, indent=2))
            return 1
        print(json.dumps({"section": a.show, "filters": engine.card_filters(a.show, chosen), **engine.run(a.show, chosen)}, indent=2, default=str))
        return 0
    options = tables.filter_options(m)
    wanted = [c for c in a.cards.split(",") if c] if a.cards else list(CARDS)
    cards = {}
    for cid in wanted:
        c = CARDS.get(cid)
        if not c:
            cards[cid] = {"filters": [], "tables": [], "module": None, "metrics": {}, "error": "no analytic registered"}
            continue
        t0 = time.perf_counter()
        result = engine.run(cid, {})    # every filter at "All"
        cards[cid] = {
            "filters": c.filters,
            "declared": c.declared is not None,
            "ignore": list(c.ignore),
            "tables": c.tables,
            "module": c.module,
            "function": c.fn.__name__,
            "metrics": result.get("metrics", {}),
            "columns": columns_of(result.get("data")),
            "ranges": ranges_of(result.get("data")),
            "error": result.get("error"),
            "slices": slice_failures(cid, options) if uses_report(cid) and "error" not in result else [],
            "bytes": len(json.dumps(result, separators=(",", ":"))) if "error" not in result else None,
            "seconds": round(time.perf_counter() - t0, 3),
        }
    print(json.dumps({
        "cards": cards,
        "modules": modules,
        "filters": options,
        "parameters": parameters(m),
        "manifest": m,
        **({"describe": tables.describe(m)} if a.describe else {}),
    }, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
