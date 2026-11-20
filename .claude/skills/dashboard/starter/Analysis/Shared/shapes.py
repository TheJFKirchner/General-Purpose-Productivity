"""Sections whose numbers are declared in their .jsx meta: no Python to write.

    export const meta = { id: 's8_paid_by_month', title: 'Paid by month', tables: ['claims'],
                          x: 'service_date', period: 'month', y: ['paid_amount', 'billed_amount'], agg: 'sum', ... };

Worked out here in Python, on the filtered table, like any analytic:
- x: the column to group by. period: 'month', 'quarter' or 'year' groups a date column first.
- y: one column or a list; 'rows' counts rows. agg: sum (default), mean or count (counts rows, no y needed).
- by: a second column; one value column per value of it (a line or a stacked part each).
- top: keep the N largest groups (with by: the N largest series). With by, pareto or waterfall the rest become
  one 'All other' row or series; otherwise they are left out.
- shape: 'share' adds share (% of the total), 'pareto' sorts largest first and adds share (running % of the total),
  'waterfall' gives base, rise, fall, total columns building up to a Total bar, 'totals' (no x) gives one row
  per y column: label, value.
- sort: 'value' (largest first; the default except for dates), 'label', or 'none'.
- compare: 'service_date=2026-04,2026-05' (a column and two of its values; dates match by their start): with
  shape 'waterfall' a bridge from the A total through each group's change to the B total; with 'totals' rows for
  A, B and the change; otherwise one value column for A and one for B. (compare: 'year' or 'prev' is the change
  metric of a dated x.)
A month or date x is kept in time order and gets latest/change metrics. The meta must stay a flat object.

The result: data = { rows: [{column: value}], x, series } (rows feed the copied library item; x and series are
kept for sections written before rows existed) and metrics for the note.
"""
from __future__ import annotations

import re

import pandas as pd

from .periods import change, ratio

class NoData(Exception):
    """No rows for this filter choice: the section shows "Not enough data for this selection"."""


_META = re.compile(r"export\s+const\s+meta\s*=\s*\{([^}]*)\}")
_MONTH = re.compile(r"^\d{4}-\d{2}")
OTHER = "All other"
SHAPES = ("share", "pareto", "waterfall", "totals")


def _get(body: str, key: str) -> str | None:
    m = re.search(rf"(?<![\w$]){key}\s*:\s*(?:['\"]([^'\"]*)['\"]|(-?\d+(?:\.\d+)?))", body)
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def _list(body: str, key: str) -> list[str]:
    m = re.search(rf"(?<![\w$]){key}\s*:\s*\[([^\]]*)\]", body)
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if m else []


_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _short(label: str) -> str:
    """'2025-06' or '2025-06-01' -> 'Jun 25'."""
    return f"{_MON[int(label[5:7]) - 1]} {label[2:4]}"


def spec_from_jsx(src: str) -> dict | None:
    """The declared numbers from a section file's meta, or None when it declares none."""
    m = _META.search(src)
    if not m:
        return None
    body = m.group(1)
    x, sid, shape = _get(body, "x"), _get(body, "id"), (_get(body, "shape") or "").lower() or None
    tables, ignore = _list(body, "tables"), _list(body, "ignore")
    if not sid or not tables or not (x or shape == "totals"):
        return None
    ys = _list(body, "y") or ([_get(body, "y")] if _get(body, "y") else [])
    agg = (_get(body, "agg") or ("sum" if ys else "count")).lower()
    if agg == "count":
        ys = ["rows"]
    top = _get(body, "top")
    raw = _get(body, "compare") or "prev"
    between = None
    if "=" in raw:
        col, vals = raw.split("=", 1)
        between = (col.strip(), [v.strip() for v in vals.split(",") if v.strip()][:2])
    return {"between": between, "id": sid, "table": tables[0], "x": x, "y": ys[0] if len(ys) == 1 else (ys or None), "ys": ys or ["rows"],
            "agg": agg, "by": _get(body, "by"), "ignore": ignore, "compare": "prev" if between else raw.lower(),
            "period": (_get(body, "period") or "").lower() or None, "top": int(float(top)) if top else None,
            "shape": shape, "sort": (_get(body, "sort") or "").lower() or None}


def label_of(spec: dict) -> str:
    if spec["agg"] == "count":
        name = str(spec["table"]).replace("_", " ")
        return name[:1].upper() + name[1:]
    name = str(spec["ys"][0]).replace("_", " ")
    return f"Average {name}" if spec["agg"] == "mean" else name[:1].upper() + name[1:]


def _period(s: pd.Series, period: str | None) -> pd.Series:
    if not period:
        return s
    d = pd.to_datetime(s, errors="coerce")
    if period == "month":
        return d.dt.strftime("%Y-%m")
    if period == "quarter":
        return d.dt.year.astype("Int64").astype(str) + "-Q" + d.dt.quarter.astype("Int64").astype(str)
    if period == "year":
        return d.dt.year.astype("Int64").astype(str)
    raise ValueError(f'meta period must be month, quarter or year (got "{period}")')


def _agg(g, col: str, agg: str):
    return g.size() if col == "rows" else getattr(g[col], "mean" if agg == "mean" else "sum")()


def _clean(v):
    if v is None or (isinstance(v, float) and v != v):
        return None
    if hasattr(v, "item"):
        v = v.item()
    return round(v, 4) if isinstance(v, float) else v


def _label(v: str) -> str:
    """'2026-04' -> 'Apr 2026'; anything else as it is."""
    return f"{_MON[int(v[5:7]) - 1]} {v[:4]}" if re.fullmatch(r"\d{4}-\d{2}", v) else v


def _between(t, spec: dict, df: pd.DataFrame) -> dict:
    """Two values of one column side by side: a waterfall bridge, A/B/change totals, or A and B columns."""
    col, vals = spec["between"]
    if col not in df.columns or len(vals) != 2:
        raise ValueError(f'meta compare must be "<column>=<A>,<B>" with a column of {spec["table"]} (got "{col}={",".join(vals)}")')
    text = df[col].astype(str)
    a, b = vals
    da, db = df[text.str.startswith(a)], df[text.str.startswith(b)]
    if da.empty or db.empty:
        raise NoData(f"no rows for {a if da.empty else b} in {col} for this selection")
    la, lb, y, agg, x, shape = _label(a), _label(b), spec["ys"][0], spec["agg"], spec["x"], spec.get("shape")
    tot = lambda d: float(len(d)) if y == "rows" else float(getattr(d[y], "mean" if agg == "mean" else "sum")())
    ta, tb = tot(da), tot(db)
    metrics = {"start": ta, "end": tb, "start_label": la, "end_label": lb, "change": change(tb, ta), "change_amount": tb - ta}
    if shape == "totals" or not x:
        rows = [{"label": la, "value": _clean(ta)}, {"label": lb, "value": _clean(tb)}, {"label": "Change", "value": _clean(tb - ta)}]
        return {"data": {"rows": rows, "x": [r["label"] for r in rows], "series": {"value": [r["value"] for r in rows]}}, "metrics": metrics}
    ga, gb = _agg(da.groupby(x), y, agg), _agg(db.groupby(x), y, agg)
    both = pd.DataFrame({la: ga, lb: gb}).fillna(0)
    both.index = both.index.map(str)
    if shape != "waterfall":
        both = both.loc[both[lb].sort_values(ascending=False).index]
        if spec.get("top"):
            both = both.iloc[: spec["top"]]
        rows = [{x: i, la: _clean(r[la]), lb: _clean(r[lb])} for i, r in both.iterrows()]
        return {"data": {"rows": rows, "x": list(both.index), "series": {la: [r[la] for r in rows], lb: [r[lb] for r in rows]}}, "metrics": metrics}
    steps = (both[lb] - both[la]).loc[lambda s: s.abs().sort_values(ascending=False).index]
    if spec.get("top") and len(steps) > spec["top"]:
        steps = pd.concat([steps.iloc[: spec["top"]], pd.Series({OTHER: steps.iloc[spec["top"]:].sum()})])
    big = steps.abs().idxmax() if len(steps) else None
    rows, level = [{x: la, "base": 0, "total": _clean(ta), "rise": None, "fall": None, "key": None}], ta
    for name, v in steps.items():
        v = float(v)
        key = name == big and v > 0
        rows.append({x: name, "base": _clean(level if v >= 0 else level + v), "total": None,
                     "rise": _clean(v) if v >= 0 and not key else None, "fall": _clean(-v) if v < 0 else None,
                     "key": _clean(v) if key else None})
        level += v
    rows.append({x: lb, "base": 0, "total": _clean(tb), "rise": None, "fall": None, "key": None})
    metrics.update({"largest_step_label": str(big) if big is not None else None, "largest_step": _clean(float(steps[big])) if big is not None else None})
    return {"data": {"rows": rows, "x": [r[x] for r in rows], "series": {"total": [r["total"] for r in rows]}}, "metrics": metrics}


def compute(t, spec: dict) -> dict:
    """{data: {rows, x, series}, metrics} for a declared section, on the section's filtered table."""
    table, x, ys, agg, by, shape = spec["table"], spec["x"], spec["ys"], spec["agg"], spec["by"], spec.get("shape")
    df = getattr(t, table)
    for flag, c in [("x", x), ("by", by)] + [("y", c) for c in ys if c != "rows"]:
        if c and c not in df.columns:
            raise KeyError(f'meta {flag}: no column "{c}" in {table} (columns: {", ".join(map(str, df.columns))})')
    if agg not in ("sum", "count", "mean"):
        raise ValueError(f'meta agg must be sum, count or mean (got "{agg}")')
    if shape and shape not in SHAPES:
        raise ValueError(f'meta shape must be one of {", ".join(SHAPES)} (got "{shape}")')
    if df.empty:
        raise NoData(f"no {table} rows for this selection")

    if spec.get("between"):
        return _between(t, spec, df)
    if shape == "totals":   # one row per measure: label, value
        rows = [{"label": c, "value": _clean(float(len(df)) if c == "rows" else float(getattr(df[c], "mean" if agg == "mean" else "sum")()))}
                for c in ys]
        return {"data": {"rows": rows, "x": [r["label"] for r in rows], "series": {"value": [r["value"] for r in rows]}},
                "metrics": {r["label"]: r["value"] for r in rows} | {"count": len(rows)}}

    df = df.assign(**{x: _period(df[x], spec.get("period"))}) if spec.get("period") else df
    df = df[df[x].notna()]
    if by:
        g = df.groupby([x, by])
        wide = _agg(g, ys[0], agg).unstack(fill_value=0)
        wide.columns = [str(c) for c in wide.columns]
        if spec.get("top") and len(wide.columns) > spec["top"]:
            keep = wide.sum().sort_values(ascending=False).index[: spec["top"]]
            rest = wide.drop(columns=keep).sum(axis=1)
            wide = wide[keep].assign(**{OTHER: rest})
    else:
        g = df.groupby(x)
        wide = pd.DataFrame({c: _agg(g, c, agg) for c in ys})
    if wide.empty:
        raise NoData(f"no {table} rows for this selection")
    month = bool(_MONTH.match(str(wide.index[0]))) or bool(spec.get("period"))
    row = wide.mean(axis=1) if agg == "mean" and by else (wide.sum(axis=1) if by else wide[ys[0]])
    order = spec.get("sort") or ("label" if month else "value")
    if shape == "pareto" or order == "value":
        row = row.sort_values(ascending=False)
    elif order == "label":
        row = row.sort_index()
    wide = wide.loc[row.index]
    grand = float(row.sum())   # before top: shares are of every row, not of the top N
    if spec.get("top") and not by and len(wide) > spec["top"]:
        rest = wide.iloc[spec["top"]:].sum() if agg != "mean" else wide.iloc[spec["top"]:].mean()
        wide = pd.concat([wide.iloc[: spec["top"]], rest.to_frame(OTHER).T]) if shape in ("pareto", "waterfall") else wide.iloc[: spec["top"]]
        row = wide.sum(axis=1) if by else wide[ys[0]]
    key = (lambda v: str(v)[:10]) if month else str

    rows = [{x: key(i), **{str(c): _clean(v) for c, v in r.items()}} for i, r in wide.iterrows()]
    first = str(wide.columns[0])
    if shape in ("share", "pareto"):
        tot = grand or None
        run = 0.0
        for r, v in zip(rows, row.tolist()):
            run += v
            r["share"] = round((run if shape == "pareto" else v) / tot * 100, 1) if tot else None
    if shape == "waterfall":
        level, out = 0.0, []
        for r in rows:
            v = float(r[first] or 0)
            out.append({x: r[x], "base": _clean(level if v >= 0 else level + v), "rise": _clean(v) if v >= 0 else None,
                        "fall": _clean(-v) if v < 0 else None, "total": None, "key": None})
            level += v
        out.append({x: "Total", "base": 0, "rise": None, "fall": None, "total": _clean(level), "key": None})
        rows = out

    row = row.drop(OTHER, errors="ignore") if len(row) > 1 else row   # metrics speak of real groups, not "All other"
    metrics = {"average": float(df[ys[0]].mean())} if agg == "mean" and ys[0] != "rows" else {"total": grand}
    metrics.update({"largest": float(row.max()), "largest_label": key(row.idxmax())})
    if month:
        labels = [key(v) for v in row.index]
        latest = labels[-1]
        year_ago = f"{int(latest[:4]) - 1}{latest[4:7]}" if latest[:4].isdigit() else None
        ya = next((i for i, lab in enumerate(labels) if lab[:7] == year_ago), None)
        if spec.get("compare") == "year" and ya is not None:
            ch, base = change(row.iloc[-1], row.iloc[ya]), labels[ya]
        else:   # the period before (also when there is no year of history)
            ch, base = (change(row.iloc[-1], row.iloc[-2]), labels[-2]) if len(row) > 1 else (None, None)
        metrics.update({"latest": float(row.iloc[-1]), "latest_label": latest, "change": ch,
                        "change_label": (f"vs {_short(base)}" if _MONTH.match(base) else f"vs {base}") if base else "no earlier period"})
    else:
        if agg != "mean":
            metrics["largest_share"] = ratio(row.max(), grand)
        metrics.update({"smallest": float(row.min()), "smallest_label": key(row.idxmin())})
    metrics["count"] = int(len(row))
    if by and agg != "mean":
        metrics.update({"top_series": str(wide.sum().idxmax()), "top_series_share": ratio(wide.sum().max(), wide.values.sum())})
    series = {(label_of(spec) if not by and len(ys) == 1 else str(c)): [_clean(v) for v in wide[c].round(2).tolist()] for c in wide.columns}
    return {"data": {"rows": rows, "x": [key(v) for v in wide.index], "series": series}, "metrics": metrics}
