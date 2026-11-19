"""Sections whose numbers are declared in their .jsx meta: no Python to write.

    export const meta = { id: 's8_paid_by_month', title: 'Paid by month', tables: ['claims'],
                          x: 'service_month', y: 'paid_amount', agg: 'sum', by: 'product', ... };

The numbers are still worked out here in Python, on the filtered table, like any analytic: grouped by x (and by,
one series per value), agg = sum | count | mean of y (count needs no y). A month or date x is kept in time order and
gets latest/change metrics; any other x is sorted largest first. A section with its own @section function in
Analysis/ uses that instead. The meta must stay a flat object (strings, and a list of strings for tables).
"""
from __future__ import annotations

import re

from .periods import change, ratio

class NoData(Exception):
    """No rows for this filter choice: the section shows "Not enough data for this selection"."""


_META = re.compile(r"export\s+const\s+meta\s*=\s*\{([^}]*)\}")
_MONTH = re.compile(r"^\d{4}-\d{2}")


def _get(body: str, key: str) -> str | None:
    m = re.search(rf"(?<![\w$]){key}\s*:\s*['\"]([^'\"]*)['\"]", body)
    return m.group(1) if m else None


def _list(body: str, key: str) -> list[str]:
    m = re.search(rf"(?<![\w$]){key}\s*:\s*\[([^\]]*)\]", body)
    return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)) if m else []


_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _short(label: str) -> str:
    """'2025-06' or '2025-06-01' -> 'Jun 25'."""
    return f"{_MON[int(label[5:7]) - 1]} {label[2:4]}"


def spec_from_jsx(src: str) -> dict | None:
    """{id, table, x, y, agg, by} from a section file's meta, or None when it declares no x."""
    m = _META.search(src)
    if not m:
        return None
    body = m.group(1)
    x, sid = _get(body, "x"), _get(body, "id")
    tables, ignore = _list(body, "tables"), _list(body, "ignore")
    if not x or not sid or not tables:
        return None
    y = _get(body, "y")
    return {"id": sid, "table": tables[0], "x": x, "y": y, "agg": (_get(body, "agg") or ("sum" if y else "count")).lower(),
            "by": _get(body, "by"), "ignore": ignore, "compare": (_get(body, "compare") or "prev").lower()}


def label_of(spec: dict) -> str:
    if spec["agg"] == "count":
        name = str(spec["table"]).replace("_", " ")
        return name[:1].upper() + name[1:]
    name = str(spec["y"]).replace("_", " ")
    return f"Average {name}" if spec["agg"] == "mean" else name[:1].upper() + name[1:]


def compute(t, spec: dict) -> dict:
    """{data: {x, series}, metrics} for a declared section, on the section's filtered table."""
    table, x, y, agg, by = spec["table"], spec["x"], spec["y"], spec["agg"], spec["by"]
    df = getattr(t, table)
    for flag, c in (("x", x), ("y", None if agg == "count" else y), ("by", by)):
        if c and c not in df.columns:
            raise KeyError(f'meta {flag}: no column "{c}" in {table} (columns: {", ".join(map(str, df.columns))})')
    if agg not in ("sum", "count", "mean"):
        raise ValueError(f'meta agg must be sum, count or mean (got "{agg}")')
    g = df.groupby([x, by] if by else x)
    s = g.size() if agg == "count" else getattr(g[y], agg)()
    wide = s.unstack(fill_value=0) if by else s.to_frame(label_of(spec))
    month = len(wide) > 0 and bool(_MONTH.match(str(wide.index[0])))
    if month:
        wide = wide.sort_index()
    row = wide.mean(axis=1) if agg == "mean" else wide.sum(axis=1)
    if not month:
        row = row.sort_values(ascending=False)
        wide = wide.loc[row.index]
    if row.empty:
        raise NoData(f"no {table} rows for this selection")
    key = (lambda v: str(v)[:10]) if month else str
    metrics = {"average": float(df[y].mean())} if agg == "mean" else {"total": float(row.sum())}
    metrics.update({"largest": float(row.max()), "largest_label": key(row.idxmax())})
    if month:
        labels = [key(v) for v in row.index]
        latest = labels[-1]
        year_ago = f"{int(latest[:4]) - 1}{latest[4:7]}"
        ya = next((i for i, lab in enumerate(labels) if lab[:7] == year_ago), None)
        if spec.get("compare") == "year" and ya is not None:
            ch, base = change(row.iloc[-1], row.iloc[ya]), labels[ya]
        else:   # the month before (also when there is no year of history)
            ch, base = (change(row.iloc[-1], row.iloc[-2]), labels[-2]) if len(row) > 1 else (None, None)
        metrics.update({"latest": float(row.iloc[-1]), "latest_label": latest, "change": ch,
                        "change_label": f"vs {_short(base)}" if base else "no earlier month"})
    else:
        if agg != "mean":
            metrics["largest_share"] = ratio(row.max(), row.sum())
        metrics.update({"smallest": float(row.min()), "smallest_label": key(row.idxmin())})
    metrics["count"] = int(len(row))
    if by and agg != "mean":
        metrics.update({"top_series": str(wide.sum().idxmax()), "top_series_share": ratio(wide.sum().max(), wide.values.sum())})
    return {"data": {"x": [key(v) for v in wide.index], "series": {str(c): wide[c].round(2).tolist() for c in wide.columns}},
            "metrics": metrics}
