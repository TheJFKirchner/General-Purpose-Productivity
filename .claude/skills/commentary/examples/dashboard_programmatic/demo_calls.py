#!/usr/bin/env python3
"""Dashboard commentary without a dashboard: every programmatic call, on mock data.

Shows the life of a dashboard's commentary end to end:

  1. read the shell (status.py)                         what commentary is planned
  2. setup (generate.py --setup)                        stamps run_commentary.py
  3. refresh for September, then October (run_commentary.py, no arguments)
                                                        one output file per snapshot
  4. rerun with the same data                           nothing regenerated, no new file
  5. override one unit                                  a newer October file, old one kept
  6. hand edit one unit (edit.py)                       another newer October file
  7. the output files, and what the newest one holds
  8. run-time lookups, as the hosted dashboard would call them
  9. status.py again

Usage: python3 demo_calls.py            (live writer calls, about $0.25)
Output is printed and saved to demo_output.txt. Commentary is saved in
commentary_outputs/: one file per run, per snapshot.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "scripts"
SHELL = HERE / "commentary_shell.json"
ENV = dict(os.environ)
OUT = HERE / "commentary_outputs"
LAN = ["--lan-id", "demo_user"]

out = io.StringIO()


def say(*a):
    print(*a)
    print(*a, file=out)


def step(title):
    say("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def run(*cmd):
    shown = " ".join("python3" if str(c) == sys.executable else
                     (f'"{c}"' if " " in str(c) else str(c)).replace(str(HERE) + "/", "").replace(str(SCRIPTS), "<skill>/scripts")
                     for c in cmd)
    say(f"$ {shown}")
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=ENV, cwd=HERE)
    text = (p.stdout + p.stderr).strip().replace(str(HERE) + "/", "")
    say(text)
    return p.returncode


def load_snapshot(month):
    for f in (HERE / "snapshots" / month).iterdir():
        shutil.copy(f, HERE / "data" / f.name)
    say(f"(data/ now holds the {month} refresh)")


def reset():
    for p in ["commentary_run.md", "run_commentary.py"]:
        (HERE / p).unlink(missing_ok=True)
    shutil.rmtree(OUT, ignore_errors=True)


def main():
    reset()
    py = sys.executable

    step("1. Read the shell first: what commentary does this dashboard have?")
    run(py, SCRIPTS / "status.py", SHELL)

    step("2. One-time setup: the stamped no-argument batch script")
    run(py, SCRIPTS / "generate.py", SHELL, "--setup", *LAN)

    step("3a. Data refresh: September")
    load_snapshot("2026-09")
    run(py, HERE / "run_commentary.py", *LAN)

    step("3b. Data refresh: October (use_prior passes September's commentary to the writer)")
    load_snapshot("2026-10")
    run(py, HERE / "run_commentary.py", *LAN)

    step("4. Rerun with the same data: everything is frozen, no writer calls")
    run(py, HERE / "run_commentary.py", *LAN)

    step("5. Override one unit: a deliberate new version for every line of business")
    run(py, HERE / "run_commentary.py", "--override", "lob_trend", *LAN)

    step("6. Hand edit: the analyst rewrites the October overview (hand edits skip the number check)")
    import pandas as pd
    lob = pd.read_csv(HERE / "data" / "claims_by_lob.csv")
    tot = lob.groupby("paid_month").allowed_cost.sum()
    chg = lob.pivot(index="paid_month", columns="line_of_business", values="allowed_cost").diff().loc["2026-10"]
    lead = chg.idxmax()
    run(py, SCRIPTS / "edit.py", SHELL, "overview", "--dim", "paid_month=2026-10", *LAN,
        "--bullet", f"October allowed cost rose {(tot['2026-10'] / tot['2026-09'] - 1) * 100:.1f}% "
                    f"to ${tot['2026-10'] / 1e6:.1f}M, the largest monthly rise this year.",
        "--bullet", f"{lead} drove {chg[lead] / chg.sum() * 100:.0f}% of the increase; watch whether it repeats in November.")

    step("7. The output files (one per run, per snapshot; the newest per snapshot is shown)")
    files = sorted(OUT.glob("commentary_*.json"))
    for f in files:
        d = json.loads(f.read_text())
        say(f"{f.name}  snapshot={d['snapshot']}  reason={d['reason']}")
    newest = json.loads(files[-1].read_text())
    say(f"\nNewest file ({files[-1].name}) holds, for each unit, one entry per filter combination:")
    for u in newest["units"]:
        for e in u["commentary"]:
            first = (e["bullets"] or [{"text": ""}])[0]["text"][:60]
            say(f"  {u['id']:<15} {json.dumps(e['filters']):<55} v{e['version']} {e['source']:<9} {first}")

    step("8. Run time: what the hosted dashboard does (load once, look up on every filter change)")
    sys.path.insert(0, str(SCRIPTS))
    from runtime import CommentaryRuntime
    rt = CommentaryRuntime.from_outputs(SHELL)
    say("rt = CommentaryRuntime.from_outputs('commentary_shell.json')   # once, at startup\n")
    cases = [
        {"paid_month": "2026-10", "line_of_business": "Medicare"},
        {"paid_month": "2026-10", "line_of_business": "Medicare", "region": "West", "product": "HMO"},
        {"paid_month": "2026-09", "line_of_business": "Commercial"},
        {"paid_month": "2026-08", "line_of_business": "Medicaid"},
    ]
    notes = ["", "  # region and product are not commentary dimensions: ignored",
             "  # an older period shows its own saved commentary", "  # nothing saved for August: renders blank"]
    for f, note in zip(cases, notes):
        say(f"filters = {json.dumps(f)}{note}")
        for unit in ["overview", "lob_trend", "lob_categories"]:
            bs = rt.lookup(unit, f)
            say(f"  rt.lookup({unit!r}, filters) -> " + (json.dumps(bs[:1])[:-1] + (", ...]" if len(bs) > 1 else "]") if bs else "[]"))
        say("")

    step("9. Read the shell again: what exists now")
    run(py, SCRIPTS / "status.py", SHELL)

    (HERE / "demo_output.txt").write_text(out.getvalue())
    print("\nSaved: demo_output.txt")


if __name__ == "__main__":
    main()
