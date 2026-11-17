#!/usr/bin/env python3
"""Save a hand edit as a new version (source = edited). Skips the number check.
Writes one new output file in commentary_outputs/.

Usage:
  edit.py <plan> <unit_id> --bullet "First point" --bullet "Second point" [--dim k=v ...] [--as-of X]
  edit.py <plan> <unit_id> --from-file bullets.txt      (one bullet per line)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PlanError, load_plan, now_iso, whoami  # noqa: E402
from store import open_store  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("unit_id")
    ap.add_argument("--bullet", action="append", default=[])
    ap.add_argument("--from-file")
    ap.add_argument("--dim", action="append", default=[])
    ap.add_argument("--as-of")
    ap.add_argument("--lan-id")
    args = ap.parse_args(argv)
    plan, plan_dir = load_plan(args.plan)
    units = {u["id"]: u for u in plan["units"]}
    if args.unit_id not in units:
        print(f"unknown unit {args.unit_id}")
        return 2
    bullets = list(args.bullet)
    if args.from_file:
        bullets += [ln.strip() for ln in Path(args.from_file).read_text().splitlines() if ln.strip()]
    if not bullets:
        print("no bullets given")
        return 2
    store = open_store(plan, plan_dir)
    dims = dict(kv.split("=", 1) for kv in args.dim)
    if plan.get("medium") == "dashboard":
        gen = plan["generators"][str(units[args.unit_id]["generator"])]
        need = [d for d in gen.get("dimensions") or [] if d not in dims]
        if need:
            print(f"pass every dimension of this unit with --dim: missing {', '.join(need)}")
            return 2
    as_of = args.as_of
    if as_of is None:
        mine = [r for r in store.rows() if r["unit_id"] == args.unit_id]
        if not mine:
            raise PlanError("no existing commentary for that unit; pass --as-of")
        as_of = max(str(r["as_of"]) for r in mine)
    prev = store.latest(args.unit_id, as_of, dims)
    row = {"unit_id": args.unit_id, "generator": str(units[args.unit_id]["generator"]), "as_of": as_of,
           "source": "edited", "status": "ok",
           "bullets": [{"text": b, "unverified": False, "numbers": [], "flags": ["hand edit, not number-checked"]}
                       for b in bullets],
           "basis": "Hand edit; not written from the tables and not number-checked.",
           "missing": [], "input_hash": (prev or {}).get("input_hash"), "plan_hash": (prev or {}).get("plan_hash"),
           "model": None, "created_at": now_iso(), "created_by": whoami(plan_dir, args.lan_id)}
    row.update(dims)
    saved = store.save(row)
    who = whoami(plan_dir, args.lan_id)
    written = store.commit(who, f"hand edit {args.unit_id}")
    print(f"{args.unit_id}: saved hand edit as version {saved['version']}. Saved: {written[0].name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
