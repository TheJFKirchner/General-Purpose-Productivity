#!/usr/bin/env python3
"""Validate a commentary shell.

Usage: validate_shell.py <commentary_shell.json> [--json]

Exit 0 when the plan is clean, 1 when anything failed. Shell-level errors stop
everything. Unit-level errors fail only that unit: in session the skill asks
the user, in batch the unit is saved as failed and the run continues.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    MEDIUMS, PLACEHOLDER_RE, PlanError, data_dir, generators, inside, is_summary,
    load_plan, read_table, resolve_table, table_name, time_dimension,
)

MAX_TABLES_PER_GENERATOR = 12
MAX_SAMPLES = 3
MAX_SAMPLE_WORDS = 200  # "about 150"; hard stop a little above
STYLE_FORMATS = ("bullets", "paragraph")
TEMPLATE_RE = __import__("re").compile(r"\{[^{}]*\}|%[sd]|<[A-Za-z_]+>|\[[A-Z_]{3,}\]")


def validate(plan: dict, plan_dir: Path) -> dict:
    plan_errors: list[str] = []
    unit_errors: dict[str, list[str]] = {}
    warnings: list[str] = []

    def uerr(uid, msg):
        unit_errors.setdefault(uid, []).append(msg)

    # ---- top level
    if not plan.get("deliverable"):
        plan_errors.append("`deliverable` is missing")
    medium = plan.get("medium")
    if medium not in MEDIUMS:
        plan_errors.append(f"`medium` must be one of {', '.join(MEDIUMS)} (got {medium!r})")
    gens = generators(plan)
    if not gens:
        plan_errors.append("`generators` is missing or empty")
    units = plan.get("units") or []
    if not units:
        plan_errors.append("`units` is missing or empty")
    dd = data_dir(plan, plan_dir)
    if not dd.exists():
        plan_errors.append(f"data folder not found: {dd}")

    # ---- as_of
    a = plan.get("as_of")
    if medium == "dashboard" and not a:
        plan_errors.append("dashboards require `as_of` (table and field the refresh date is read from)")
    if a:
        if not a.get("table") or not a.get("field"):
            plan_errors.append("`as_of` needs `table` and `field`")
        else:
            p = resolve_table(plan, plan_dir, a["table"])
            if not p.exists():
                plan_errors.append(f"as_of table not found: {a['table']}")
            elif not inside(p, dd):
                plan_errors.append(f"as_of table is outside the data folder: {p}")
            else:
                try:
                    df = read_table(p)
                    if a["field"] not in df.columns:
                        plan_errors.append(f"as_of field `{a['field']}` is not a column of {p.name}")
                except Exception as e:  # noqa: BLE001
                    plan_errors.append(f"cannot read as_of table {p.name}: {e}")

    # ---- generators
    td = time_dimension(plan)
    gen_tables: dict[str, set[str]] = {g: set() for g in gens}
    for gid, g in gens.items():
        samples = g.get("samples") or []
        if len(samples) > MAX_SAMPLES:
            plan_errors.append(f"generator {gid}: at most {MAX_SAMPLES} samples (got {len(samples)})")
        for s in samples:
            sp = _sample_path(s, plan_dir)
            if not sp:
                plan_errors.append(f"generator {gid}: sample not found: {s}")
            else:
                n = len(sp.read_text().split())
                if n > MAX_SAMPLE_WORDS:
                    plan_errors.append(f"generator {gid}: sample {s} is {n} words (limit about 150)")
        if not g.get("audience"):
            plan_errors.append(f"generator {gid}: `audience` is missing")
        if medium == "dashboard" and "dimensions" not in g:
            plan_errors.append(f"generator {gid}: `dimensions` must be assigned explicitly (use [] for none)")
        if medium != "dashboard" and g.get("dimensions"):
            warnings.append(f"generator {gid}: dimensions are ignored for {medium}s")
        dims = g.get("dimensions") or []
        if medium == "dashboard":
            for d in dims:
                if td is None and _looks_time(d):
                    warnings.append(
                        f"generator {gid}: dimension `{d}` looks like a period but is not tied to as_of "
                        f"(set as_of.dimension = \"{d}\"); every refresh would regenerate every past period")

    # ---- units
    seen: set[str] = set()
    for i, u in enumerate(units):
        uid = u.get("id") or f"<unit #{i + 1}>"
        if not u.get("id"):
            uerr(uid, "`id` is missing")
        elif uid in seen:
            plan_errors.append(f"unit id `{uid}` is not unique")
        seen.add(uid)
        gid = str(u.get("generator"))
        g = gens.get(gid)
        if g is None:
            uerr(uid, f"generator `{u.get('generator')}` does not exist")
        covers = (u.get("covers") or "").strip()
        if not covers:
            uerr(uid, "`covers` is missing: say what this commentary must address")
        elif TEMPLATE_RE.search(covers):
            uerr(uid, "`covers` looks like a fill-in template; sentences with slots "
                      "(\"the trend is {trend}\") belong in code, not this skill")
        if not u.get("placement"):
            uerr(uid, "`placement` is missing")
        st = u.get("style")
        if not isinstance(st, dict):
            uerr(uid, "`style` is missing (format, bullets, max_words)")
        else:
            if st.get("format") not in STYLE_FORMATS:
                uerr(uid, f"style.format must be one of {STYLE_FORMATS}")
            if not isinstance(st.get("bullets"), int) or st["bullets"] < 1:
                uerr(uid, "style.bullets must be a positive integer")
            if not isinstance(st.get("max_words"), int) or st["max_words"] < 3:
                uerr(uid, "style.max_words must be an integer of at least 3")
        tables = u.get("tables") or []
        summary = bool(g) and is_summary(g)
        if not tables and not summary:
            uerr(uid, "needs at least one table")
        if summary and tables:
            warnings.append(f"unit {uid}: summary generators read commentary, not tables; tables ignored")
            continue
        names: dict[str, str] = {}
        for t in tables:
            p = resolve_table(plan, plan_dir, t)
            if p.suffix.lower() not in (".csv", ".parquet"):
                uerr(uid, f"table {t}: only Parquet or CSV")
                continue
            if not p.exists():
                uerr(uid, f"table not found: {t}")
                continue
            if not inside(p, dd):
                uerr(uid, f"table is outside the data folder: {t}")
                continue
            n = table_name(t)
            if n in names and names[n] != str(p):
                uerr(uid, f"two tables share the name `{n}`")
            names[n] = str(p)
            if g is not None:
                gen_tables[gid].add(str(p))
                if medium == "dashboard":
                    try:
                        cols = set(read_table(p).columns)
                    except Exception as e:  # noqa: BLE001
                        uerr(uid, f"cannot read {t}: {e}")
                        continue
                    for d in g.get("dimensions") or []:
                        if d not in cols:
                            uerr(uid, f"dimension `{d}` is not a column of {t}")

    for gid, ts in gen_tables.items():
        if len(ts) > MAX_TABLES_PER_GENERATOR:
            plan_errors.append(
                f"generator {gid}: {len(ts)} tables across its units (limit {MAX_TABLES_PER_GENERATOR}); "
                "split into another generator")
        if gid in gens and not any(True for u in units if str(u.get("generator")) == gid):
            warnings.append(f"generator {gid} has no units")

    # ---- placeholders, both directions
    files = plan.get("deliverable_files") or []
    if not files:
        if medium != "dashboard":
            warnings.append("no `deliverable_files` listed: placeholder check skipped")
    else:
        found: set[str] = set()
        for f in files:
            fp = (plan_dir / f).resolve()
            if not fp.exists():
                plan_errors.append(f"deliverable file not found: {f}")
                continue
            found |= set(placeholders_in(fp))
        ids = {u.get("id") for u in units if u.get("id")}
        for pid in sorted(found - ids):
            plan_errors.append(f"placeholder {{{{commentary:{pid}}}}} has no unit in the plan")
        for uid in sorted(ids - found):
            uerr(uid, f"no placeholder {{{{commentary:{uid}}}}} in the deliverable files")

    return {"ok": not plan_errors and not unit_errors,
            "plan_errors": plan_errors, "unit_errors": unit_errors, "warnings": warnings}


def _looks_time(name: str) -> bool:
    import re
    return bool(re.search(r"(month|period|date|quarter|year|week)", name, re.I))


def _sample_path(s: str, plan_dir: Path) -> Path | None:
    from common import SKILL_DIR
    for base in (plan_dir, SKILL_DIR):
        p = (base / s)
        if p.exists():
            return p
    return None


def placeholders_in(path: Path) -> list[str]:
    if path.suffix.lower() == ".pptx":
        from pptx import Presentation
        out = []
        for slide in Presentation(str(path)).slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    out += PLACEHOLDER_RE.findall(shape.text_frame.text)
        return out
    return PLACEHOLDER_RE.findall(path.read_text(errors="ignore"))


def format_report(res: dict) -> str:
    lines = ["Shell is valid." if res["ok"] else "Shell has problems."]
    for e in res["plan_errors"]:
        lines.append(f"  SHELL {e}")
    for uid, errs in res["unit_errors"].items():
        for e in errs:
            lines.append(f"  UNIT  {uid}: {e}")
    for w in res["warnings"]:
        lines.append(f"  WARN  {w}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        plan, plan_dir = load_plan(args.plan)
    except PlanError as e:
        print(f"SHELL {e}")
        return 1
    res = validate(plan, plan_dir)
    print(json.dumps(res, indent=2) if args.json else format_report(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
