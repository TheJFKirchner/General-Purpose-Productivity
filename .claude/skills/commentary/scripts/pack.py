#!/usr/bin/env python3
"""Packer: the only code that touches data files.

Reads a generator's tables, enforces limits (fails loudly, never truncates),
filters to a dashboard dimension combination, adds derived columns, builds the
brief and computes per-unit input hashes.

Usage (debugging): pack.py <commentary_shell.json> <generator> [--dim k=v ...]
prints the brief that would be sent to the writer.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    SKILL_DIR, TIME_NAME_RE, generators, is_summary, load_plan, plan_hash,
    read_table, resolve_table, sha, table_name, time_dimension, units_for,
)

MAX_ROWS = 50
MAX_COLS = 15
TOTAL_LABEL_RE = re.compile(r"^(total|all|grand total|overall|other total)$", re.I)
NO_SHARE_RE = re.compile(r"(rate|pct|percent|per_|_per|avg|average|ratio|pmpm|pmpy|margin|mean|median|score|index|share)", re.I)


class PackError(Exception):
    pass


# ---------------------------------------------------------------- tables

def _is_numeric(s) -> bool:
    import pandas as pd
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def time_column(df, hints: list[str]) -> str | None:
    for h in hints:
        if h and h in df.columns:
            return h
    for c in df.columns:
        if TIME_NAME_RE.search(str(c)):
            return c
    return None


def key_columns(df, time_col: str | None) -> list[str]:
    keys = [c for c in df.columns if not _is_numeric(df[c])]
    if time_col and time_col in df.columns and time_col not in keys:
        keys.insert(0, time_col)
    return keys


def filter_to_combo(df, dims: dict, time_dim: str | None, as_of):
    """Equality filter on each dimension; the period dimension keeps history up to the as-of."""
    out = df
    for d, v in dims.items():
        if d not in out.columns:
            continue
        if d == time_dim:
            out = out[out[d].astype(str) <= str(v)]
        else:
            out = out[out[d].astype(str) == str(v)]
    return out


def derive(df, time_col: str | None):
    """Add common derived columns so most numbers the writer uses become direct."""
    import pandas as pd

    df = df.copy()
    measures = [c for c in df.columns if _is_numeric(df[c]) and c != time_col]
    keys = [c for c in df.columns if not _is_numeric(df[c]) and c != time_col]
    added: dict[str, str] = {}
    if not measures or len(df) < 2:
        return df, added

    if time_col:
        df = df.sort_values(keys + [time_col], kind="stable").reset_index(drop=True)
        grouped = df.groupby(keys, sort=False) if keys else None
        if (grouped.size().max() if grouped is not None else len(df)) < 2:
            return df, added
        for m in measures:
            src = grouped[m] if grouped is not None else df[m]
            prev = src.shift(1)
            df[f"{m}_chg"] = df[m] - prev
            pct = (df[m] - prev) / prev.abs() * 100
            df[f"{m}_pct_chg"] = pct.replace([math.inf, -math.inf], float("nan"))
            added[f"{m}_chg"] = f"{m} minus the previous {time_col} (same group)"
            added[f"{m}_pct_chg"] = f"percent change in {m} versus the previous {time_col} (same group), in percent"
    # side-by-side period columns (x_oct / x_sep, x_curr / x_prior): add change columns
    for new, old in _period_pairs(measures):
        stem = _stem(new)
        df[f"{stem}_chg"] = df[new] - df[old]
        df[f"{stem}_pct_chg"] = ((df[new] - df[old]) / df[old].abs() * 100).replace([math.inf, -math.inf], float("nan"))
        added[f"{stem}_chg"] = f"{new} minus {old}"
        added[f"{stem}_pct_chg"] = f"percent change from {old} to {new}, in percent"

    if not time_col and keys:
        body = ~df[keys[0]].astype(str).str.match(TOTAL_LABEL_RE)
        first = True
        for m in measures:
            col = df[m]
            if not NO_SHARE_RE.search(str(m)) and (col.dropna() >= 0).all():
                total = col[body].sum()
                if total:
                    df[f"{m}_share_pct"] = col / total * 100
                    added[f"{m}_share_pct"] = f"{m} as a percent of the table total (total rows excluded)"
            if first:
                rank = col.where(body).rank(ascending=False, method="min")
                df[f"{m}_rank"] = rank.astype("Int64")
                added[f"{m}_rank"] = f"rank by {m}, 1 = largest (total rows excluded)"
                first = False
    return df, added


_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_PAIR_WORDS = [("curr", "prior"), ("current", "prior"), ("cur", "prev"), ("current", "previous"),
               ("cy", "py"), ("this", "last"), ("ty", "ly"), ("new", "old")]


def _split(col: str):
    if "_" not in col:
        return None, None
    stem, suf = col.rsplit("_", 1)
    return stem, suf.lower()


def _stem(col: str) -> str:
    return _split(col)[0]


def _period_pairs(measures: list[str]) -> list[tuple[str, str]]:
    """Pairs (newer, older) of columns that share a stem and differ by a period suffix."""
    by_stem: dict[str, dict[str, str]] = {}
    for m in measures:
        stem, suf = _split(str(m))
        if stem:
            by_stem.setdefault(stem, {})[suf] = m
    pairs = []
    for stem, sufs in by_stem.items():
        found = False
        for a, b in _PAIR_WORDS:
            if a in sufs and b in sufs:
                pairs.append((sufs[a], sufs[b]))
                found = True
                break
        if found:
            continue
        ms = [s for s in sufs if s in _MONTHS]
        if len(ms) == 2:
            i, j = _MONTHS.index(ms[0]), _MONTHS.index(ms[1])
            # adjacent months, allowing the dec -> jan wrap
            if (i - j) % 12 == 1:
                pairs.append((sufs[ms[0]], sufs[ms[1]]))
            elif (j - i) % 12 == 1:
                pairs.append((sufs[ms[1]], sufs[ms[0]]))
    return pairs


def _cell(v):
    import pandas as pd
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        # keep enough precision that the writer's own rounding is the only rounding
        return round(v, 4) if abs(v) < 1e6 else round(v, 2)
    if isinstance(v, (int, str, bool)):
        return v
    return str(v)


def table_payload(df, keys: list[str], derived: dict) -> dict:
    return {
        "columns": [str(c) for c in df.columns],
        "key_columns": [str(k) for k in keys],
        "derived_columns": derived,
        "rows": [[_cell(v) for v in row] for row in df.itertuples(index=False, name=None)],
    }


def load_tables(plan: dict, plan_dir: Path, refs: list[str], dims: dict | None = None,
                as_of=None) -> dict[str, dict]:
    """Read, filter, check limits and derive. Raises PackError naming table and limit."""
    dims = dims or {}
    td = time_dimension(plan)
    hints = [td, (plan.get("as_of") or {}).get("field")]
    out: dict[str, dict] = {}
    for ref in refs:
        name = table_name(ref)
        if name in out:
            continue
        p = resolve_table(plan, plan_dir, ref)
        df = read_table(p)
        df = filter_to_combo(df, dims, td, as_of)
        if len(df) == 0:
            raise PackError(f"table {name}: no rows for {dims or 'this run'}")
        if len(df) > MAX_ROWS:
            raise PackError(
                f"table {name}: {len(df)} rows (limit {MAX_ROWS}). Aggregate upstream "
                "(top N plus 'other') and rerun. Nothing was truncated.")
        if len(df.columns) > MAX_COLS:
            raise PackError(f"table {name}: {len(df.columns)} columns (limit {MAX_COLS}). Drop or pivot columns upstream.")
        tc = time_column(df, hints)
        df2, added = derive(df, tc) if plan.get("derive", True) else (df, {})
        out[name] = table_payload(df2, key_columns(df2, tc), added)
    return out


# ---------------------------------------------------------------- brief

def read_samples(gen: dict, plan_dir: Path) -> list[str]:
    texts = []
    for s in gen.get("samples") or []:
        for base in (plan_dir, SKILL_DIR):
            p = base / s
            if p.exists():
                texts.append(p.read_text().strip())
                break
    return texts


def build_brief(plan: dict, plan_dir: Path, gen_id: str, unit_ids: list[str] | None = None,
                dims: dict | None = None, as_of=None, prior: dict | None = None,
                commentary_inputs: dict | None = None) -> tuple[dict, dict]:
    """Return (brief, info). info carries per-unit input/plan hashes and the tables (for the number check)."""
    gens = generators(plan)
    gen = gens[str(gen_id)]
    units = units_for(plan, gen_id)
    if unit_ids is not None:
        units = [u for u in units if u["id"] in unit_ids]
    summary = is_summary(gen)

    tables: dict[str, dict] = {}
    if not summary:
        refs = [t for u in units for t in u.get("tables", [])]
        tables = load_tables(plan, plan_dir, refs, dims, as_of)

    samples = read_samples(gen, plan_dir)
    brief_units = []
    hashes = {}
    for u in units:
        tnames = [table_name(t) for t in u.get("tables", [])] if not summary else []
        bu = {
            "id": u["id"],
            "placement": u.get("placement"),
            "covers": u.get("covers"),
            "style": u.get("style"),
            "tables": tnames,
        }
        if u.get("notes") and not summary:
            bu["notes"] = u["notes"]
        if gen.get("use_prior") and prior and prior.get(u["id"]):
            bu["prior"] = prior[u["id"]]
        brief_units.append(bu)
        ph = plan_hash(u, gen)
        data = {n: tables[n] for n in tnames} if not summary else (commentary_inputs or {})
        hashes[u["id"]] = {
            "plan_hash": ph,
            "input_hash": sha({"tables": data, "samples": samples, "plan": ph}),
        }

    brief = {
        "medium": plan.get("medium"),
        "audience": gen.get("audience"),
        "as_of": as_of,
        "dimension_values": dims or {},
        "samples": samples,
        "units": brief_units,
    }
    if plan.get("question"):
        brief["question"] = plan["question"]
    if summary:
        brief["commentary"] = commentary_inputs or {}
        brief["note"] = ("This is a summary. Write only from the commentary given. "
                         "Every number must come from that commentary.")
    else:
        brief["tables"] = tables
    return brief, {"hashes": hashes, "tables": tables, "summary": summary}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("generator")
    ap.add_argument("--dim", action="append", default=[], help="k=v dimension value")
    ap.add_argument("--as-of")
    args = ap.parse_args(argv)
    plan, plan_dir = load_plan(args.plan)
    dims = dict(kv.split("=", 1) for kv in args.dim)
    try:
        brief, _ = build_brief(plan, plan_dir, args.generator, dims=dims, as_of=args.as_of)
    except PackError as e:
        print(f"PACK ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(brief, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
