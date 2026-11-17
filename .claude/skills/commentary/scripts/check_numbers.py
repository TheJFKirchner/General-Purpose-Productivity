#!/usr/bin/env python3
"""Shape check and number check for writer output.

Shape: output parses, every brief unit appears once, no extra ids, style limits
hold (bullet count, words per bullet).

Numbers: every number in a bullet is one of three kinds.
  direct     – the number is in the unit's tables (rounding tolerance) → blocks if not
  derived    – writer names op + inputs; script recomputes            → blocks if wrong
  unverified – not in the tables, not recomputable                   → kept, flagged
A number the writer did not tag is treated as direct. Numbers that appear only
in prior commentary or samples are excluded from the lookup set.
Claims without numbers are never blocked.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

SCALE_WORDS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "mn": 1e6, "million": 1e6,
               "b": 1e9, "bn": 1e9, "billion": 1e9}

NUM_RE = re.compile(
    r"(?<![\w.\-/])"                      # not glued to a word, decimal or date
    r"(?P<sign>[-−+])?"
    r"(?P<cur>[$£€])?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<scale>thousand|million|billion|mm|mn|bn|[kKmMbB])(?![A-Za-z]))?"
    r"(?P<pct>\s?(?:%|percent\b|pp\b|percentage points?\b|bps\b|basis points\b))?"
    r"(?:[x×](?![A-Za-z0-9]))?"           # a multiple: 3.9x
    r"(?![\w\-/]|\.\d)"
)
DATE_RE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
YEAR_CTX_RE = re.compile(
    rf"(?:{MONTHS}|\bq[1-4]|\bfy|\bh[12]|\bcy|\b(?:in|since|from|to|through|during|of|vs\.?|versus|by|until|for|and))\s*'?$",
    re.I)


@dataclass
class Num:
    raw: str
    value: float          # as shown, unsigned, without scale (4.2 for "4.2%", 1.2 for "$1.2M")
    decimals: int
    scale: float = 1.0
    pct: bool = False
    pp: bool = False
    bps: bool = False
    is_year: bool = False
    start: int = 0


def parse_numbers(text: str) -> list[Num]:
    masked = DATE_RE.sub(lambda m: " " * len(m.group(0)), text)
    out: list[Num] = []
    for m in NUM_RE.finditer(masked):
        num = m.group("num")
        val = float(num.replace(",", ""))
        dec = len(num.split(".")[1]) if "." in num else 0
        scale = SCALE_WORDS.get((m.group("scale") or "").lower(), 1.0)
        unit = (m.group("pct") or "").strip().lower()
        n = Num(raw=m.group(0).strip(), value=val, decimals=dec, scale=scale,
                pct=unit.startswith("%") or unit.startswith("percent"),
                pp=unit.startswith("pp") or unit.startswith("percentage"),
                bps=unit.startswith("bps") or unit.startswith("basis"), start=m.start())
        before = masked[:m.start()]
        if (not m.group("cur") and scale == 1.0 and not unit and dec == 0 and "," not in num
                and 1990 <= val <= 2100):
            n.is_year = bool(YEAR_CTX_RE.search(before.rstrip()))
        out.append(n)
    return out


def _close(shown: Num, candidate: float) -> bool:
    if candidate is None or (isinstance(candidate, float) and math.isnan(candidate)):
        return False
    tol = 0.5 * 10 ** (-shown.decimals) + 1e-9
    cands = [abs(candidate)]
    if shown.pct or shown.pp:
        cands.append(abs(candidate) * 100)  # fraction stored, percent shown
    if shown.bps:
        cands += [abs(candidate) * 10000, abs(candidate) * 100]
    for c in cands:
        if abs(c / shown.scale - shown.value) <= tol:
            return True
    return False


def matches_any(shown: Num, values) -> bool:
    return any(_close(shown, v) for v in values)


# ---------------------------------------------------------------- lookups

def table_values(tables: dict[str, dict]) -> list[float]:
    vals: list[float] = []
    for t in tables.values():
        skip = {i for i, c in enumerate(t["columns"]) if str(c).endswith("_rank")}
        for row in t["rows"]:
            for ci, v in enumerate(row):
                if ci in skip or isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    if not (isinstance(v, float) and math.isnan(v)):
                        vals.append(float(v))
                elif isinstance(v, str):
                    for part in re.findall(r"\d+(?:\.\d+)?", v):  # years, months in labels
                        vals.append(float(part))
    return vals


def resolve_ref(ref, tables: dict[str, dict]) -> float | None:
    """A table:row_key:column reference → that cell's value. Literal numbers are not refs."""
    if not isinstance(ref, str) or ref.count(":") < 2:
        return None
    tname, rest = ref.split(":", 1)
    rkey, col = rest.rsplit(":", 1)
    t = tables.get(tname)
    if not t or col not in t["columns"]:
        return None
    ci = t["columns"].index(col)
    rows = t["rows"]
    row = None
    if rkey.startswith("#") and rkey[1:].isdigit():
        i = int(rkey[1:]) - 1
        row = rows[i] if 0 <= i < len(rows) else None
    else:
        want = [s.strip().lower() for s in rkey.split("|")]
        kidx = [t["columns"].index(k) for k in t.get("key_columns", []) if k in t["columns"]]
        for r in rows:
            keys = [str(r[i]).strip().lower() for i in kidx]
            if keys == want or (len(want) == 1 and want[0] in keys and
                                sum(1 for rr in rows if want[0] in [str(rr[i]).strip().lower() for i in kidx]) == 1):
                row = r
                break
    if row is None:
        return None
    v = row[ci]
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


UP_WORDS = re.compile(r"\b(rose|rise|rises|rising|up|increased?|increases|increasing|grew|grow|grows|growth|gained?|gains|higher|jumped|jump|climbed|climb|added|adding|spiked?)\b", re.I)
DOWN_WORDS = re.compile(r"\b(fell|fall|falls|falling|down|decreased?|decreases|declined?|declines|dropped|drop|drops|lower|slipped|slip|shrank|shrink|lost|cut|eased|reduced?)\b", re.I)


def direction_conflict(text: str, n: "Num", signed: float | None) -> str | None:
    """Block "rose 4%" when the change is negative, and "fell 4%" when it is positive.

    Looks only at the words just before the number, and only for signed changes.
    """
    if signed is None or signed == 0:
        return None
    window = text[max(0, n.start - 40):n.start]
    window = re.split(r"[.;:,(]", window)[-1]  # same clause only
    up, down = UP_WORDS.findall(window), DOWN_WORDS.findall(window)
    if signed < 0 and up and not down:
        return f"{n.raw}: text says {up[-1]!r} but the change is negative ({round(signed, 4)})"
    if signed > 0 and down and not up:
        return f"{n.raw}: text says {down[-1]!r} but the change is positive ({round(signed, 4)})"
    return None


CHANGE_COL = re.compile(r"(_chg|_pct_chg|_change|_diff|_delta)$", re.I)


def compute(op: str, xs: list[float]) -> float | None:
    try:
        if op == "difference" or op == "pp_change":
            return xs[0] - xs[1]
        if op == "pct_change":
            return (xs[0] - xs[1]) / abs(xs[1]) * 100
        if op == "share":
            return xs[0] / xs[1] * 100
        if op == "ratio":
            return xs[0] / xs[1]
        if op == "sum":
            return sum(xs)
    except (IndexError, ZeroDivisionError, TypeError):
        return None
    return None


# ---------------------------------------------------------------- checks

@dataclass
class BulletResult:
    text: str
    status: str = "ok"            # ok | blocked
    unverified: bool = False
    problems: list[str] = field(default_factory=list)
    verified_values: list[float] = field(default_factory=list)


def check_bullet(bullet: dict, lookup: list[float], tables: dict[str, dict],
                 excluded: list[float] | None = None) -> BulletResult:
    text = bullet.get("text", "")
    res = BulletResult(text=text)
    shown = parse_numbers(text)
    tags = list(bullet.get("numbers") or [])
    used = [False] * len(tags)

    for n in shown:
        # match to a writer tag by value
        tag = None
        for i, t in enumerate(tags):
            if used[i]:
                continue
            try:
                tv = abs(float(t.get("value")))
            except (TypeError, ValueError):
                continue
            if abs(tv - n.value) <= 0.5 * 10 ** (-n.decimals) + 1e-9 or abs(tv - n.value * n.scale) < 1e-6 * max(1, tv):
                tag, used[i] = t, True
                break
        kind = (tag or {}).get("kind", "direct")

        if n.is_year and not tag:
            if matches_any(n, lookup):
                continue
            # a bare year that is not in the data: treat as a label, not a figure
            continue

        if kind == "derived":
            op = tag.get("op")
            ins = tag.get("inputs") or []
            xs = [resolve_ref(r, tables) for r in ins]
            # literal numeric inputs must themselves be values in the tables
            xs = [x if x is not None else
                  (float(r) if isinstance(r, (int, float)) and not isinstance(r, bool)
                   and any(abs(float(r) - v) <= 1e-6 * max(1.0, abs(v)) for v in lookup) else None)
                  for r, x in zip(ins, xs)]
            if not op or not ins or any(x is None for x in xs):
                if matches_any(n, lookup):  # mis-tagged, but the number is in the tables
                    res.verified_values.append(n.value * n.scale)
                    continue
                bad = [r for r, x in zip(ins, xs) if x is None]
                res.status = "blocked"
                res.problems.append(f"{n.raw}: derived but inputs could not be found ({', '.join(map(str, bad)) or 'none given'})")
                continue
            val = compute(op, xs)
            if val is not None and _close(n, val):
                conflict = direction_conflict(text, n, val) if op in ("difference", "pct_change", "pp_change") else None
                if conflict:
                    res.status = "blocked"
                    res.problems.append(conflict)
                    continue
                res.verified_values.append(val)
                continue
            if matches_any(n, lookup):  # mis-tagged, but the number is in the tables
                res.verified_values.append(n.value * n.scale)
                continue
            res.status = "blocked"
            res.problems.append(f"{n.raw}: {op} of {xs} gives {val if val is None else round(val, 4)}, not {n.raw}")
            continue

        if kind == "unverified":
            res.unverified = True
            res.problems.append(f"{n.raw}: tagged unverified by the writer")
            continue

        # direct with a reference the script can resolve: it must match that cell
        ref = (tag or {}).get("ref")
        cell = resolve_ref(ref, tables) if ref else None
        if cell is not None:
            if _close(n, cell):
                col = ref.rsplit(":", 1)[-1]
                conflict = direction_conflict(text, n, cell) if CHANGE_COL.search(col) else None
                if conflict:
                    res.status = "blocked"
                    res.problems.append(conflict)
                    continue
                res.verified_values.append(cell)
                continue
            res.status = "blocked"
            res.problems.append(f"{n.raw}: does not match the cell it cites ({ref} = {cell})")
            continue

        # direct (tagged without a usable ref, or untagged): any cell of the unit's tables
        if matches_any(n, lookup):
            res.verified_values.append(n.value * n.scale)
            continue
        if excluded and matches_any(n, excluded):
            res.status = "blocked"
            res.problems.append(f"{n.raw}: appears only in prior commentary or samples, not in this period's tables")
            continue
        res.status = "blocked"
        res.problems.append(f"{n.raw}: not found in the unit's tables")
    return res


SOURCE_MAX_WORDS = 75


def check_shape(output: dict, brief: dict) -> tuple[list[str], dict[str, list[str]]]:
    """Return (global problems, per-unit problems)."""
    gp: list[str] = []
    up: dict[str, list[str]] = {}
    if not isinstance(output, dict) or not isinstance(output.get("units"), list):
        return ["output has no `units` list"], {}
    want = {u["id"]: u for u in brief["units"]}
    seen = set()
    for u in output["units"]:
        uid = u.get("id")
        if uid not in want:
            gp.append(f"unit id `{uid}` is not in the brief")
            continue
        if uid in seen:
            up.setdefault(uid, []).append("unit returned twice")
        seen.add(uid)
        st = want[uid].get("style") or {}
        bullets = u.get("bullets")
        if not isinstance(bullets, list) or not bullets:
            up.setdefault(uid, []).append("no bullets")
            continue
        limit = 1 if st.get("format") == "paragraph" else st.get("bullets", 99)
        if len(bullets) > limit:
            up.setdefault(uid, []).append(f"{len(bullets)} bullets (limit {limit})")
        mw = st.get("max_words", 999)
        for i, b in enumerate(bullets):
            if not isinstance(b, dict) or not isinstance(b.get("text"), str) or not b["text"].strip():
                up.setdefault(uid, []).append(f"bullet {i + 1} has no text")
                continue
            words = len(b["text"].split())
            if words > mw:
                up.setdefault(uid, []).append(f"bullet {i + 1} is {words} words (limit {mw}): \"{b['text'][:60]}…\"")
        src = u.get("source")
        if isinstance(src, str) and len(src.split()) > SOURCE_MAX_WORDS:
            up.setdefault(uid, []).append(f"source is {len(src.split())} words (limit {SOURCE_MAX_WORDS}, "
                                          "two to three sentences)")
    for uid in want:
        if uid not in seen:
            up.setdefault(uid, []).append("unit missing from output")
    return gp, up
