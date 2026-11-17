#!/usr/bin/env python3
"""The generate action: run the pipeline for one shell and write the run log.

Usage:
  generate.py <commentary_shell.json>                    generate what is missing, reuse the rest
  generate.py <plan> --override all                     new version of every unit (skips hand edits)
  generate.py <plan> --override dx_trend rx_mix         new version of named units
  generate.py <plan> --use-version dx_trend 2 [--dim k=v] [--as-of X]
  generate.py <plan> --setup                            dashboards: stamp the batch script (run_commentary.py)
  generate.py <plan> --batch                            batch mode: failed checks fail the unit, run continues

Saves one new output file per run in commentary_outputs/ (dashboards: one per
snapshot), only when something changed. Prints a short summary; details go to
commentary_run.md beside the shell (replaced each run).
Exit: 0 all good, 1 some units failed, 2 shell problem (nothing generated).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from call_writer import WriterError, call_writer  # noqa: E402
from check_numbers import check_bullet, check_shape, parse_numbers, table_values  # noqa: E402
from common import (  # noqa: E402
    PlanError, SKILL_DIR, generators, is_summary, load_config,
    load_plan, now_iso, read_table, resolve_table, time_dimension, units_for, whoami,
)
from pack import PackError, build_brief, load_tables  # noqa: E402
from store import open_store, read_output_rows  # noqa: E402
from validate_shell import format_report, validate  # noqa: E402


# ---------------------------------------------------------------- run log

class RunLog:
    def __init__(self):
        self.lock = threading.Lock()
        self.generated: list[str] = []
        self.reused: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.unverified: list[tuple[str, str]] = []
        self.restated: list[str] = []
        self.plan_changed: list[str] = []
        self.skipped_edits: list[str] = []
        self.missing: list[tuple[str, str]] = []
        self.warnings: list[str] = []
        self.retried: list[str] = []
        self.calls = 0
        self.cost = 0.0
        self.seconds = 0.0
        self.models: set[str] = set()

    def add(self, attr, item):
        with self.lock:
            getattr(self, attr).append(item)

    def warn(self, msg):
        self.add("warnings", msg)


def label(uid: str, dims: dict) -> str:
    return uid if not dims else f"{uid} [{', '.join(f'{k}={v}' for k, v in dims.items())}]"


# ---------------------------------------------------------------- as-of and combos

def read_as_of(plan: dict, plan_dir: Path):
    a = plan.get("as_of")
    if not a:
        return None
    df = read_table(resolve_table(plan, plan_dir, a["table"]))
    col = df[a["field"]].dropna()
    rule = a.get("rule", "max")
    v = col.min() if rule == "min" else col.max()
    if hasattr(v, "item"):
        v = v.item()
    if hasattr(v, "strftime"):
        v = v.strftime("%Y-%m-%d")
    return str(v)


def combinations(plan: dict, plan_dir: Path, gen_id: str, as_of) -> list[dict]:
    gen = generators(plan)[gen_id]
    dims = gen.get("dimensions") or []
    if plan.get("medium") != "dashboard" or not dims:
        return [{}]
    td = time_dimension(plan)
    explicit = gen.get("combinations")  # optional allowed list
    if explicit:
        combos = [dict(c) for c in explicit]
        for c in combos:
            if td in dims:
                c[td] = as_of
        return combos
    seen, out = set(), []
    for u in units_for(plan, gen_id):
        for t in u.get("tables", []):
            df = read_table(resolve_table(plan, plan_dir, t))
            if td in dims:
                df = df[df[td].astype(str) == str(as_of)]
            for row in df[dims].drop_duplicates().astype(str).itertuples(index=False, name=None):
                if row not in seen:
                    seen.add(row)
                    out.append(dict(zip(dims, row)))
    return out


# ---------------------------------------------------------------- prior and summary inputs

def prior_for(plan, plan_dir, store, gen, units, as_of, dims) -> dict:
    if not gen.get("use_prior"):
        return {}
    out = {}
    td = time_dimension(plan)
    if plan.get("medium") == "dashboard":
        for u in units:
            cands = []
            for r in store.rows():
                if r["unit_id"] != u["id"] or r["status"] != "ok" or str(r["as_of"]) >= str(as_of):
                    continue
                if any(str(r.get(d)) != str(v) for d, v in dims.items() if d != td):
                    continue
                cands.append(r)
            if cands:
                best_as_of = max(str(r["as_of"]) for r in cands)
                best = max((r for r in cands if str(r["as_of"]) == best_as_of), key=lambda r: r["version"])
                out[u["id"]] = [b["text"] for b in best["bullets"]]
        return out
    pf = gen.get("prior_file")  # an earlier edition's output file, or its commentary_outputs folder
    if pf and (plan_dir / pf).exists():
        rows = read_output_rows(plan_dir / pf)
        for u in units:
            rs = [r for r in rows if r["unit_id"] == u["id"] and r["status"] == "ok"]
            if rs:
                out[u["id"]] = [b["text"] for b in max(rs, key=lambda r: r["version"])["bullets"]]
    return out


def summary_inputs(plan, store, as_of, show_unverified: bool) -> tuple[dict, list[float]]:
    texts, vals = {}, []
    gens = generators(plan)
    for u in plan["units"]:
        if is_summary(gens.get(str(u["generator"]), {})):
            continue
        r = store.latest(u["id"], as_of, {})
        if not r or r["status"] != "ok":
            continue
        keep = [b for b in r["bullets"] if show_unverified or not b.get("unverified")]
        texts[u["id"]] = [b["text"] for b in keep]
        for b in keep:
            if b.get("unverified"):
                continue
            vals += b.get("verified_values", [])
            vals += [n.value * n.scale for n in parse_numbers(b["text"])]
    return texts, vals


# ---------------------------------------------------------------- one generator call

def numbers_check(output, brief, unit_ids, info, excluded, summary_vals):
    """Return {uid: {"ok": bool, "problems": [...], "bullets": [...]}} for unit_ids."""
    gp, up = check_shape(output, brief)
    res = {}
    by_id = {u.get("id"): u for u in (output.get("units") or []) if isinstance(u, dict)}
    plan_units = {u["id"]: u for u in brief["units"]}
    for uid in unit_ids:
        problems = list(gp) + up.get(uid, [])
        out_u = by_id.get(uid)
        bullets = []
        if out_u and isinstance(out_u.get("bullets"), list):
            if info["summary"]:
                tables, lookup = {}, summary_vals
            else:
                tables = {n: info["tables"][n] for n in plan_units[uid]["tables"]}
                lookup = table_values(tables)
            for b in out_u["bullets"]:
                if not isinstance(b, dict):
                    continue
                br = check_bullet(b, lookup, tables, excluded)
                if br.status == "blocked":
                    problems.append(f"bullet \"{br.text[:70]}\": " + "; ".join(br.problems))
                bullets.append({"text": br.text, "unverified": br.unverified and br.status != "blocked",
                                "numbers": b.get("numbers", []), "tables": b.get("tables", []),
                                "verified_values": br.verified_values,
                                "flags": br.problems})
        res[uid] = {"ok": not problems, "problems": problems, "bullets": bullets,
                    "missing": (out_u or {}).get("missing", []) or [],
                    "basis": str((out_u or {}).get("source") or "").strip()}
    return res


def run_generator(ctx, gen_id: str, dims: dict):
    plan, plan_dir, store, log, args, as_of = ctx["plan"], ctx["plan_dir"], ctx["store"], ctx["log"], ctx["args"], ctx["as_of"]
    gen = generators(plan)[gen_id]
    units = [u for u in units_for(plan, gen_id) if u["id"] not in ctx["invalid"]]
    if not units:
        return
    override = args.override or []
    over_all = "all" in override

    to_gen, reused = [], []
    for u in units:
        uid = u["id"]
        latest = store.latest(uid, as_of, dims)
        named = uid in override
        if latest and latest["status"] == "ok":
            if over_all and latest["source"] == "edited" and not named:
                log.add("skipped_edits", label(uid, dims))
                reused.append((u, latest))
            elif over_all or named:
                to_gen.append(u)
            else:
                reused.append((u, latest))
        else:
            to_gen.append(u)  # nothing yet, or last attempt failed

    summary = is_summary(gen)
    commentary, summary_vals = ({}, [])
    if summary:
        commentary, summary_vals = summary_inputs(plan, store, as_of, ctx["show_unverified_in_inputs"])
    prior = prior_for(plan, plan_dir, store, gen, units, as_of, dims)
    # packer limits are checked per unit, so one oversized table fails only its own unit
    if not summary:
        packable = []
        for u in units:
            try:
                load_tables(plan, plan_dir, u.get("tables", []), dims, as_of)
                packable.append(u)
            except PackError as e:
                if u in to_gen:
                    to_gen.remove(u)
                    log.add("failed", (label(u["id"], dims), f"packer: {e}"))
                    save(ctx, u, dims, status="failed", error=f"packer: {e}")
                else:
                    reused = [(ru, rl) for ru, rl in reused if ru is not u]
                    log.add("reused", label(u["id"], dims))
                    log.warn(f"{label(u['id'], dims)}: packer now fails ({e}); saved commentary left alone")
        units = packable
        if not units:
            return
    try:
        brief, info = build_brief(plan, plan_dir, gen_id, unit_ids=[u["id"] for u in units], dims=dims,
                                  as_of=as_of, prior=prior, commentary_inputs=commentary)
    except PackError as e:
        for u in to_gen:
            log.add("failed", (label(u["id"], dims), f"packer: {e}"))
            save(ctx, u, dims, status="failed", error=f"packer: {e}")
        for u, _ in reused:
            log.add("reused", label(u["id"], dims))
        return

    # stale checks on reused units
    for u, latest in reused:
        h = info["hashes"][u["id"]]
        log.add("reused", label(u["id"], dims))
        if latest["source"] == "edited":
            continue
        if latest.get("plan_hash") != h["plan_hash"]:
            log.add("plan_changed", label(u["id"], dims))
        elif latest.get("input_hash") != h["input_hash"]:
            log.add("restated", label(u["id"], dims))
    if not to_gen:
        return
    if summary and not commentary:
        for u in to_gen:
            log.add("failed", (label(u["id"], dims), "summary has no verified commentary to read yet"))
            save(ctx, u, dims, status="failed", error="no input commentary")
        return

    excluded = []
    for t in (brief.get("samples") or []) + [x for v in prior.values() for x in v]:
        excluded += [n.value * n.scale for n in parse_numbers(t)]

    model = gen.get("model") or ctx["cfg"]["default_model"]
    want = [u["id"] for u in to_gen]

    def attempt(b):
        try:
            out, meta = call_writer(json.dumps(b), model, ctx["cfg"]["writer_timeout_s"])
        except WriterError as e:
            with log.lock:
                log.calls += 1
            return None, str(e)
        with log.lock:
            log.calls += 1
            log.cost += meta.get("cost_usd") or 0
            log.seconds += meta.get("seconds") or 0
            log.models.add(meta.get("model", model))
        return out, meta

    out, meta = attempt(brief)
    if out is None:
        results = {uid: {"ok": False, "problems": [f"writer call failed: {meta}"], "bullets": [], "missing": []} for uid in want}
    else:
        results = numbers_check(out, brief, want, info, excluded, summary_vals)
    model_used = meta.get("model", model) if isinstance(meta, dict) else model

    bad = [uid for uid in want if not results[uid]["ok"]]
    if bad:
        for uid in bad:
            log.add("retried", label(uid, dims))
        retry_brief, rinfo = build_brief(plan, plan_dir, gen_id, unit_ids=bad, dims=dims, as_of=as_of,
                                         prior=prior, commentary_inputs=commentary)
        retry_brief["retry"] = {
            "instructions": "Your previous output for these units failed the checks below. "
                            "Rewrite them so every number is in the tables (or correctly derived "
                            "and tagged) and every style limit holds.",
            "problems": {uid: results[uid]["problems"] for uid in bad},
            "previous": {uid: [b["text"] for b in results[uid]["bullets"]] for uid in bad},
        }
        out2, meta2 = attempt(retry_brief)
        if out2 is None:
            for uid in bad:
                results[uid]["problems"].append(f"retry call failed: {meta2}")
        else:
            r2 = numbers_check(out2, retry_brief, bad, rinfo, excluded, summary_vals)
            for uid in bad:
                if r2[uid]["ok"]:
                    results[uid] = r2[uid]
                else:
                    results[uid] = {**r2[uid], "problems": ["first try: " + " | ".join(results[uid]["problems"]),
                                                             "retry: " + " | ".join(r2[uid]["problems"])]}
            if isinstance(meta2, dict):
                model_used = meta2.get("model", model_used)

    for u in to_gen:
        uid = u["id"]
        r = results[uid]
        h = info["hashes"][uid]
        if r["ok"]:
            save(ctx, u, dims, status="ok", bullets=r["bullets"], missing=r["missing"], hashes=h, model=model_used,
                 basis=r.get("basis"))
            log.add("generated", label(uid, dims))
            for b in r["bullets"]:
                if b["unverified"]:
                    log.add("unverified", (label(uid, dims), b["text"]))
        else:
            save(ctx, u, dims, status="failed", bullets=r["bullets"], missing=r["missing"], hashes=h,
                 model=model_used, error=" || ".join(r["problems"])[:2000], basis=r.get("basis"))
            log.add("failed", (label(uid, dims), " || ".join(r["problems"])))
        for m in r["missing"]:
            log.add("missing", (label(uid, dims), m))


def save(ctx, unit, dims, status, bullets=None, missing=None, hashes=None, model=None, error=None, basis=None):
    row = {"unit_id": unit["id"], "generator": str(unit["generator"]), "as_of": ctx["as_of"],
           "source": "generated", "status": status, "bullets": bullets or [], "missing": missing or [],
           "basis": basis or "", "error": error, "input_hash": (hashes or {}).get("input_hash"),
           "plan_hash": (hashes or {}).get("plan_hash"), "model": model,
           "created_at": now_iso(), "created_by": ctx["who"]}
    row.update(dims)
    return ctx["store"].save(row)


# ---------------------------------------------------------------- run log file

def write_run_log(ctx, started: str, validation: dict | None) -> Path:
    log, plan = ctx["log"], ctx["plan"]
    L = [f"# Commentary run: {plan.get('deliverable')}", "",
         f"- Medium: {plan.get('medium')}",
         f"- As of: {ctx.get('as_of') or 'n/a'}",
         f"- Started: {started}  Finished: {now_iso()}",
         f"- Mode: {'batch' if ctx['args'].batch else 'session'}"
         + (f", override: {' '.join(ctx['args'].override)}" if ctx['args'].override else ""),
         f"- Output saved: {', '.join(p.name for p in ctx.get('written') or []) or 'none (nothing changed)'}",
         f"- Writer calls: {log.calls} ({', '.join(sorted(log.models)) or 'none'}), "
         f"{log.seconds:.0f}s of writer time, ${log.cost:.3f}", "",
         "| Outcome | Count |", "| --- | --- |",
         f"| Generated | {len(log.generated)} |", f"| Reused | {len(log.reused)} |",
         f"| Failed | {len(log.failed)} |", f"| Unverified bullets | {len(log.unverified)} |",
         f"| Stale: data restated | {len(log.restated)} |", f"| Stale: plan changed | {len(log.plan_changed)} |",
         f"| Skipped hand edits | {len(log.skipped_edits)} |", f"| Needed a retry | {len(log.retried)} |", ""]

    def section(title, items, fmt=lambda x: x):
        if items:
            L.append(f"## {title}")
            L.append("")
            L.extend(f"- {fmt(i)}" for i in sorted(items, key=str))
            L.append("")

    section("Failed", log.failed, lambda x: f"`{x[0]}`: {x[1]}")
    section("Unverified bullets", log.unverified, lambda x: f"`{x[0]}`: {x[1]}")
    section("Stale: data restated for this as-of (commentary left alone)", log.restated)
    section("Stale: plan changed (commentary left alone)", log.plan_changed)
    section("Skipped hand edits (name the unit to regenerate it)", log.skipped_edits)
    section("Writer says this is missing", log.missing, lambda x: f"`{x[0]}`: {x[1]}")
    section("Generated", log.generated)
    section("Reused", log.reused)
    section("Warnings", log.warnings)
    if validation and validation.get("warnings"):
        section("Plan warnings", validation["warnings"])

    if plan.get("medium") in ("deck", "report") and ctx.get("store"):
        L += ["## Review", "", "Shown version of every unit. Unverified bullets are marked.", ""]
        for u in plan["units"]:
            r = ctx["store"].latest(u["id"], ctx["as_of"], {})
            L.append(f"### {u['id']} ({u.get('placement')})")
            L.append("")
            if not r:
                L.append("_no commentary_")
            elif r["status"] != "ok":
                L.append(f"_failed, will show blank_: {r.get('error')}")
            else:
                L.append(f"v{r['version']}, {r['source']}")
                L.append("")
                for b in r["bullets"]:
                    L.append(f"- {b['text']}" + ("  **[unverified]**" if b.get("unverified") else ""))
            L.append("")
    p = ctx["plan_dir"] / "commentary_run.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


# ---------------------------------------------------------------- setup (dashboards)

def setup_dashboard(plan_dir, shell_name: str) -> Path:
    tpl = (SKILL_DIR / "scripts" / "run_dashboard.py").read_text()
    tpl = tpl.replace("__SKILL_SCRIPTS__", (SKILL_DIR / "scripts").as_posix()).replace("__PLAN__", shell_name)
    out = plan_dir / "run_commentary.py"
    out.write_text(tpl)
    out.chmod(0o755)
    return out


# ---------------------------------------------------------------- main

def run(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--override", nargs="+", metavar="UNIT", help="'all' or unit ids")
    ap.add_argument("--use-version", nargs=2, metavar=("UNIT", "N"))
    ap.add_argument("--dim", action="append", default=[], help="k=v, with --use-version")
    ap.add_argument("--as-of", help="with --use-version; default is the current as-of")
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--lan-id", help="name saved as created_by (default: lan id in CLAUDE.md, else your login)")
    args = ap.parse_args(argv)

    started = now_iso()
    log = RunLog()
    if os.environ.get("COMMENTARY_WRITER_CMD"):
        log.warn("COMMENTARY_WRITER_CMD is set: a test writer replaced the real one for this run")
    try:
        plan, plan_dir = load_plan(args.plan)
    except PlanError as e:
        print(f"SHELL ERROR: {e}")
        return 2
    cfg = load_config()
    ctx = {"plan": plan, "plan_dir": plan_dir, "log": log, "args": args, "cfg": cfg,
           "who": whoami(plan_dir, args.lan_id), "invalid": set(),
           "show_unverified_in_inputs": False}

    validation = validate(plan, plan_dir)
    if validation["plan_errors"] or (validation["unit_errors"] and not args.batch):
        print(format_report(validation))
        if not args.batch:
            print("\nNothing generated. Fix the shell (or answer the questions above) and rerun.")
        ctx["store"] = None
        for e in validation["plan_errors"]:
            log.add("failed", ("<plan>", e))
        write_run_log(ctx, started, validation)
        return 2
    for uid, errs in validation["unit_errors"].items():
        ctx["invalid"].add(uid)
        log.add("failed", (uid, "validation: " + "; ".join(errs)))

    try:
        ctx["as_of"] = read_as_of(plan, plan_dir)
        store = open_store(plan, plan_dir)
    except PlanError as e:
        print(f"SHELL ERROR: {e}")
        return 2
    ctx["store"] = store

    if args.setup:
        if plan.get("medium") != "dashboard":
            print("--setup is for dashboards only (decks and reports run in session).")
            return 2
        p = setup_dashboard(plan_dir, Path(args.plan).name)
        print(f"Batch script: {p}")
        print(f"Outputs will be saved in: {store.dir}")
        return 0

    if args.use_version:
        uid, n = args.use_version[0], int(args.use_version[1])
        dims = dict(kv.split("=", 1) for kv in args.dim)
        r = store.use_version(uid, args.as_of or ctx["as_of"], dims, n, ctx["who"])
        written = store.commit(ctx["who"], f"use-version {uid} {n}")
        print(f"{uid}: version {n} re-saved as version {r['version']} (now shown). Saved: {written[0].name}")
        return 0

    gens = generators(plan)
    order = sorted(gens, key=lambda g: (is_summary(gens[g]), g))
    tasks: list[tuple[str, dict]] = []
    summary_tasks: list[tuple[str, dict]] = []
    for gid in order:
        try:
            combos = combinations(plan, plan_dir, gid, ctx["as_of"])
        except Exception as e:  # noqa: BLE001
            log.add("failed", (f"generator {gid}", f"cannot list combinations: {e}"))
            continue
        if not combos:
            log.add("failed", (f"generator {gid}", f"no dimension combinations found for as-of {ctx['as_of']} "
                               "(check the as-of value matches the period column's format)"))
            continue
        cap = cfg["max_combinations"]
        if len(combos) > cap:
            log.add("failed", (f"generator {gid}",
                               f"{len(combos)} dimension combinations (cap {cap}); stopped, nothing sampled"))
            continue
        (summary_tasks if is_summary(gens[gid]) else tasks).extend((gid, c) for c in combos)

    def safe(t):
        try:
            run_generator(ctx, *t)
        except Exception as e:  # noqa: BLE001  a failed unit never stops the run
            log.add("failed", (f"generator {t[0]} {t[1] or ''}", f"{type(e).__name__}: {e}"))

    with ThreadPoolExecutor(max_workers=cfg["parallel_calls"]) as ex:
        list(ex.map(safe, tasks))
    for t in summary_tasks:
        safe(t)

    reason = "batch" if args.batch else "session"
    if args.override:
        reason += " --override " + " ".join(args.override)
    ctx["written"] = store.commit(ctx["who"], reason)
    p = write_run_log(ctx, started, validation)
    print(f"{plan.get('deliverable')} ({plan.get('medium')}, as of {ctx['as_of'] or 'n/a'}): "
          f"{len(log.generated)} generated, {len(log.reused)} reused, {len(log.failed)} failed, "
          f"{len(log.unverified)} unverified bullets, {len(log.restated) + len(log.plan_changed)} stale warnings, "
          f"{log.calls} writer calls.")
    for w in ctx["written"]:
        print(f"Output saved: {w}")
    if not ctx["written"]:
        print("No output file saved (nothing changed).")
    print(f"Run log: {p}")
    return 1 if log.failed else 0


if __name__ == "__main__":
    sys.exit(run())
