"""Run-time lookup for dashboards. Copy or import this into the dashboard app.

The dashboard never generates. At startup it loads the newest output file for
each snapshot from commentary_outputs/ (each file is complete for its snapshot).
When a filter changes, each unit looks up its commentary using only its own
generator's filters; other filters are ignored. Nothing found means blank.

    rt = CommentaryRuntime.from_outputs("commentary_shell.json")      # once, at startup
    rt.lookup("lob_trend", {"paid_month": "2026-10", "line_of_business": "Medicare", "region": "West"})

Standalone on purpose: needs only the standard library, the shell and the
commentary_outputs folder.
"""
from __future__ import annotations

import json
from pathlib import Path


def newest_output_rows(out_dir) -> list[dict]:
    """Rows from the newest output file of every snapshot in out_dir."""
    newest: dict[str, tuple] = {}
    for p in Path(out_dir).glob("commentary_*.json"):
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        snap = "none" if data.get("snapshot") is None else str(data["snapshot"])
        k = (data.get("saved_at") or "", p.name)
        if snap not in newest or k > newest[snap][0]:
            newest[snap] = (k, data)
    rows = []
    for snap, (_, data) in newest.items():
        for u in data.get("units", []):
            for e in u.get("commentary", []):
                rows.append({**{k: str(v) for k, v in (e.get("filters") or {}).items()},
                             "unit_id": u["id"], "as_of": snap, "version": int(e.get("version") or 1),
                             "status": e.get("status"), "bullets": e.get("bullets") or []})
    return rows


class CommentaryRuntime:
    def __init__(self, unit_dims: dict[str, list[str]], unit_time_bound: dict[str, bool], rows: list[dict],
                 show_unverified: bool = False):
        self.unit_dims = unit_dims
        self.show_unverified = show_unverified
        # latest version per key, failed rows included, so a failed refresh shows blank
        # rather than falling back to older text. Units without the period filter
        # only read commentary from the newest snapshot.
        latest_as_of = max((str(r["as_of"]) for r in rows), default=None)
        best: dict[tuple, dict] = {}
        for r in rows:
            uid = r["unit_id"]
            if not unit_time_bound.get(uid) and str(r["as_of"]) != latest_as_of:
                continue
            k = (uid, *(str(r.get(d)) for d in unit_dims.get(uid, [])))
            cur = best.get(k)
            if cur is None or r["version"] > cur["version"]:
                best[k] = r
        best = {k: r for k, r in best.items() if r.get("status") == "ok"}
        self.index = best

    @classmethod
    def from_plan(cls, plan_path, rows, show_unverified=None):
        plan = json.loads(Path(plan_path).read_text())
        gens = {str(k): v for k, v in plan["generators"].items()}
        td = (plan.get("as_of") or {}).get("dimension") or (plan.get("as_of") or {}).get("field")
        unit_dims, bound = {}, {}
        for u in plan["units"]:
            dims = gens[str(u["generator"])].get("dimensions") or []
            unit_dims[u["id"]] = dims
            bound[u["id"]] = td in dims
        if show_unverified is None:
            show_unverified = bool(plan.get("show_unverified", False))
        return cls(unit_dims, bound, rows, show_unverified)

    @classmethod
    def from_outputs(cls, plan_path, out_dir=None, show_unverified=None):
        """Load from the commentary_outputs folder beside the shell (or out_dir)."""
        out_dir = out_dir or Path(plan_path).resolve().parent / "commentary_outputs"
        return cls.from_plan(plan_path, newest_output_rows(out_dir), show_unverified)

    def lookup(self, unit_id: str, filters: dict) -> list[str]:
        dims = self.unit_dims.get(unit_id, [])
        r = self.index.get((unit_id, *(str(filters.get(d)) for d in dims)))
        if not r:
            return []
        return [b["text"] for b in r["bullets"] if self.show_unverified or not b.get("unverified")]

    def to_export(self) -> dict:
        """Compact structure baked into standalone HTML exports."""
        out = {"dims": self.unit_dims, "rows": {}}
        for k, r in self.index.items():
            uid, vals = k[0], k[1:]
            key = "|".join(f"{d}={v}" for d, v in zip(self.unit_dims.get(uid, []), vals))
            texts = [b["text"] for b in r["bullets"] if self.show_unverified or not b.get("unverified")]
            out["rows"].setdefault(uid, {})[key] = texts
        return out
