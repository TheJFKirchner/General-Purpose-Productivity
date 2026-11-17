#!/usr/bin/env python3
"""Read the shell first: what commentary is planned, and what exists so far.

Usage: status.py <commentary_shell.json>

Reads only the shell and the saved commentary rows (never data files, never
the writer). Prints the deliverable, its generators, and for every unit where
it sits, what it covers, and the version currently shown.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PlanError, generators, is_summary, load_plan, time_dimension  # noqa: E402
from store import open_store, output_files  # noqa: E402


def short(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    try:
        shell, d = load_plan(argv[0])
    except PlanError as e:
        print(f"SHELL ERROR: {e}")
        return 2
    medium = shell.get("medium")
    print(f"# {shell.get('deliverable')} ({medium})")
    if shell.get("deliverable_files"):
        print(f"Files: {', '.join(shell['deliverable_files'])}")
    if shell.get("as_of"):
        a = shell["as_of"]
        print(f"As-of: {a.get('table')}.{a.get('field')} ({a.get('rule', 'max')})"
              + (f", period dimension: {time_dimension(shell)}" if time_dimension(shell) else ""))
    print()
    print("Generators (one writer call each):")
    for gid, g in generators(shell).items():
        extra = []
        if g.get("dimensions"):
            extra.append("varies by " + ", ".join(g["dimensions"]))
        if is_summary(g):
            extra.append("summary of other units")
        if g.get("use_prior"):
            extra.append("uses prior")
        print(f"  {gid}: {g.get('audience')}" + (f" ({'; '.join(extra)})" if extra else ""))
    print()

    store = open_store(shell, d)
    rows = store.rows()

    by_unit = defaultdict(list)
    for r in rows:
        by_unit[r["unit_id"]].append(r)
    latest_as_of = max((str(r["as_of"]) for r in rows), default=None)

    print("| Unit | Gen | Placement | Covers | Shown now |")
    print("| --- | --- | --- | --- | --- |")
    for u in shell.get("units", []):
        rs = by_unit.get(u["id"], [])
        if not rs:
            shown = "none yet"
        elif medium != "dashboard":
            r = max(rs, key=lambda r: r["version"])
            shown = f"v{r['version']} {r['source']}, {r['status']}"
        else:
            cur = [r for r in rs if str(r["as_of"]) == latest_as_of]
            dims = [x for g in generators(shell).values() for x in (g.get("dimensions") or [])]
            best = {}
            for r in cur:
                k = tuple(str(r.get(x)) for x in dims)
                if k not in best or r["version"] > best[k]["version"]:
                    best[k] = r
            ok = sum(1 for r in best.values() if r["status"] == "ok")
            failed = sum(1 for r in best.values() if r["status"] != "ok")
            edited = sum(1 for r in best.values() if r["source"] == "edited")
            versions = max((r["version"] for r in cur), default=0)
            shown = (f"as of {latest_as_of}: {ok} ok, {failed} failed, {edited} edited, up to v{versions}"
                     if cur else f"nothing for {latest_as_of}")
        print(f"| {u['id']} | {u.get('generator')} | {short(u.get('placement'), 28)} | "
              f"{short(u.get('covers'), 60)} | {shown} |")
    files = output_files(store.dir)
    print(f"\nOutput files: {len(files)} in {store.dir}" + (f" (newest: {files[-1].name})" if files else ""))
    plan_md = d / "commentary_plan.md"
    print(f"Plan: {plan_md}" if plan_md.exists() else "Plan: commentary_plan.md not found beside the shell")
    run_log = d / "commentary_run.md"
    if run_log.exists():
        print(f"Last run log: {run_log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
