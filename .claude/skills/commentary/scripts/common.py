"""Shared helpers for the commentary skill scripts.

Nothing in here calls the writer. Plan loading, paths, hashing, table reading
and small utilities only.
"""
from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import os
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"

MEDIUMS = ("deck", "report", "dashboard")
PLACEHOLDER_RE = re.compile(r"\{\{\s*commentary:([A-Za-z0-9_\-\.]+)\s*\}\}")
TIME_NAME_RE = re.compile(r"(month|period|date|quarter|year|week|day)", re.I)


class PlanError(Exception):
    """A problem that stops the whole plan (not just one unit)."""


# ---------------------------------------------------------------- config

def load_config() -> dict:
    cfg = {
        "default_model": "sonnet",
        "max_combinations": 50,
        "parallel_calls": 4,
        "writer_timeout_s": 300,
    }
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    return cfg


# ---------------------------------------------------------------- plan

def load_plan(plan_path: str | Path) -> tuple[dict, Path]:
    plan_path = Path(plan_path).resolve()
    if not plan_path.exists():
        raise PlanError(f"plan not found: {plan_path}")
    try:
        plan = json.loads(plan_path.read_text())
    except json.JSONDecodeError as e:
        raise PlanError(f"plan is not valid JSON: {e}") from e
    return plan, plan_path.parent


def data_dir(plan: dict, plan_dir: Path) -> Path:
    return (plan_dir / plan.get("data_dir", "data")).resolve()


def table_name(path: str) -> str:
    return Path(path).stem


def resolve_table(plan: dict, plan_dir: Path, ref: str) -> Path:
    """Resolve a table reference (a path, or a bare name inside the data dir)."""
    p = Path(ref)
    if p.suffix.lower() in (".csv", ".parquet"):
        return (plan_dir / p).resolve()
    dd = data_dir(plan, plan_dir)
    for ext in (".parquet", ".csv"):
        cand = dd / f"{ref}{ext}"
        if cand.exists():
            return cand.resolve()
    return (dd / f"{ref}.parquet").resolve()


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def read_table(path: Path):
    import pandas as pd

    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise PlanError(f"unsupported table type {path.suffix} ({path.name}); use Parquet or CSV")


def generators(plan: dict) -> dict[str, dict]:
    return {str(k): (v or {}) for k, v in (plan.get("generators") or {}).items()}


def units_for(plan: dict, gen_id: str) -> list[dict]:
    return [u for u in plan.get("units", []) if str(u.get("generator")) == str(gen_id)]


def is_summary(gen: dict) -> bool:
    return gen.get("inputs") == "commentary" or bool(gen.get("summary"))


def all_dimensions(plan: dict) -> list[str]:
    seen: list[str] = []
    for g in generators(plan).values():
        for d in g.get("dimensions", []) or []:
            if d not in seen:
                seen.append(d)
    return seen


def time_dimension(plan: dict) -> str | None:
    """The commentary dimension that tracks the as-of period, if any.

    Pinned to the as-of value at each refresh, so older periods keep their own
    commentary. Declared with as_of.dimension; falls back to a dimension whose
    name equals the as-of field.
    """
    a = plan.get("as_of") or {}
    if a.get("dimension"):
        return a["dimension"]
    if a.get("field") and a["field"] in all_dimensions(plan):
        return a["field"]
    return None


# ---------------------------------------------------------------- hashing

def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode()).hexdigest()[:16]


def gen_settings(gen: dict) -> dict:
    return {k: gen.get(k) for k in ("audience", "samples", "use_prior", "dimensions", "model", "inputs", "summary")}


def plan_hash(unit: dict, gen: dict) -> str:
    d = {
        "covers": unit.get("covers"),
        "style": unit.get("style"),
        "tables": unit.get("tables"),
        "generator": gen_settings(gen),
    }
    if unit.get("notes"):  # only when present, so older saved hashes still match
        d["notes"] = unit["notes"]
    return sha(d)


# ---------------------------------------------------------------- identity

def find_claude_md(start: Path) -> Path | None:
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        f = p / "CLAUDE.md"
        if f.exists():
            return f
    home = Path.home() / ".claude" / "CLAUDE.md"
    return home if home.exists() else None


def lan_id(plan_dir: Path, override: str | None = None) -> str | None:
    if override:
        return override
    f = find_claude_md(plan_dir)
    if not f:
        return None
    m = re.search(r"lan[ _\-]?id\s*[:=]\s*`?([A-Za-z0-9_\.\-]+)`?", f.read_text(), re.I)
    return m.group(1) if m else None


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def whoami(plan_dir: Path, override: str | None = None) -> str:
    return lan_id(plan_dir, override) or os.environ.get("USER") or getpass.getuser()


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_").lower()


def combo_label(dims: dict) -> str:
    if not dims:
        return "all"
    return "__".join(f"{k}={slug(str(v))}" for k, v in sorted(dims.items()))
