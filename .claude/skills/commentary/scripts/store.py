#!/usr/bin/env python3
"""Load and save commentary as output files: one file per run.

Every run (and every hand edit or roll-back) that changes something writes one
new JSON file into commentary_outputs/ beside the shell. The file is a copy of
the shell with the commentary written into each unit, and it is complete: the
newest file alone holds everything currently shown. Older files are the history.

  Decks, reports:  commentary_outputs/commentary_<YYYYMMDD-HHMMSS>.json
  Dashboards:      commentary_outputs/commentary_<snapshot>_<YYYYMMDD-HHMMSS>.json
                   one file per snapshot (as-of); every other filter lives inside it

Files are never changed after they are written. Inside the scripts each piece of
commentary is a "row": unit_id + as_of (snapshot) + dimension values + version.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PlanError, all_dimensions, generators, now_iso  # noqa: E402

OUTPUT_DIR = "commentary_outputs"
ENTRY_FIELDS = ["version", "source", "status", "bullets", "basis", "missing", "error", "input_hash", "plan_hash",
                "model", "created_at", "created_by"]
ROW_FIELDS = ["unit_id", "generator", "as_of", *ENTRY_FIELDS]


def _norm(v):
    return "none" if v is None else str(v)


def _file_part(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9.\-]+", "-", str(s)).strip("-") or "x"


def _rows_from_file(data: dict, dims: list[str]) -> list[dict]:
    """Flatten one output file into rows. Also reads the old {"rows": [...]} format."""
    if "rows" in data and "units" not in data:
        rows = [dict(r) for r in data["rows"]]
    else:
        rows = []
        snap = _norm(data.get("snapshot"))
        for u in data.get("units", []):
            for e in u.get("commentary", []):
                r = {f: e.get(f) for f in ENTRY_FIELDS}
                r.update(unit_id=u["id"], generator=str(u.get("generator")), as_of=snap)
                r.update({k: str(v) for k, v in (e.get("filters") or {}).items()})
                rows.append(r)
    for r in rows:
        r["as_of"] = _norm(r.get("as_of"))
        r["version"] = int(r.get("version") or 1)
        r["bullets"] = r.get("bullets") or []
        r["missing"] = r.get("missing") or []
        for d in dims:
            r.setdefault(d, "all")  # a filter added later: older commentary gets "all"
    return rows


def output_files(out_dir: Path) -> list[Path]:
    """All output files, oldest first (by saved_at, then name)."""
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        return []
    found = []
    for p in out_dir.glob("commentary_*.json"):
        try:
            saved = json.loads(p.read_text()).get("saved_at") or ""
        except (OSError, json.JSONDecodeError):
            continue
        found.append((saved, p.name, p))
    return [p for _, _, p in sorted(found)]


def read_output_rows(path: Path, dims: list[str] | None = None) -> list[dict]:
    """Rows from one output file, or from the newest file in a folder (used for prior editions)."""
    path = Path(path)
    if path.is_dir():
        files = output_files(path)
        if not files:
            return []
        path = files[-1]
    return _rows_from_file(json.loads(path.read_text()), dims or [])


class OutputStore:
    def __init__(self, plan: dict, plan_dir: Path):
        self.plan = plan
        self.dir = Path(plan_dir) / OUTPUT_DIR
        self.dims = all_dimensions(plan)
        self._lock = threading.RLock()
        self._pending: set[str] = set()
        seen, rows = set(), []
        for p in output_files(self.dir):
            for r in _rows_from_file(json.loads(p.read_text()), self.dims):
                k = (*self.key(r["unit_id"], r["as_of"], r), r["version"])
                if k not in seen:  # carried-forward commentary appears in many files
                    seen.add(k)
                    rows.append(r)
        self._rows = rows

    # ------------------------------------------------------------ reading

    def key(self, unit_id, as_of, dims: dict | None) -> tuple:
        dims = dims or {}
        return (unit_id, _norm(as_of), *[_norm(dims.get(d, "all")) for d in self.dims])

    def rows(self) -> list[dict]:
        return self._rows

    def versions(self, unit_id, as_of, dims=None) -> list[dict]:
        k = self.key(unit_id, as_of, dims)
        rs = [r for r in self._rows if self.key(r["unit_id"], r["as_of"], r) == k]
        return sorted(rs, key=lambda r: r["version"])

    def latest(self, unit_id, as_of, dims=None) -> dict | None:
        v = self.versions(unit_id, as_of, dims)
        return v[-1] if v else None

    def latest_all(self, as_of=None) -> list[dict]:
        best: dict[tuple, dict] = {}
        for r in self._rows:
            if as_of is not None and r["as_of"] != _norm(as_of):
                continue
            k = self.key(r["unit_id"], r["as_of"], r)
            if k not in best or r["version"] > best[k]["version"]:
                best[k] = r
        return list(best.values())

    def describe(self) -> str:
        return f"output files in {self.dir}"

    # ------------------------------------------------------------ writing

    def save(self, row: dict) -> dict:
        """Add a new version in memory. Nothing is written until commit()."""
        with self._lock:
            dims = {d: row.get(d, "all") for d in self.dims}
            prev = self.latest(row["unit_id"], row.get("as_of"), dims)
            full = {f: row.get(f) for f in ROW_FIELDS}
            full.update({d: _norm(dims[d]) for d in self.dims})
            full["as_of"] = _norm(row.get("as_of"))
            full["version"] = (prev["version"] + 1) if prev else 1
            full["created_at"] = full.get("created_at") or now_iso()
            self._rows.append(full)
            self._pending.add(full["as_of"])
            return full

    def use_version(self, unit_id, as_of, dims, n: int, who: str) -> dict:
        old = next((r for r in self.versions(unit_id, as_of, dims) if r["version"] == n), None)
        if not old:
            raise PlanError(f"{unit_id}: no version {n} for as_of={as_of} {dims or ''}")
        row = dict(old)
        row.update(created_at=now_iso(), created_by=who, error=f"re-saved from version {n}")
        return self.save(row)

    def commit(self, who: str, reason: str, at: datetime | None = None) -> list[Path]:
        """Write one new output file per snapshot changed since the last commit.
        `at` (UTC) backdates the file; only for converting older saved commentary."""
        with self._lock:
            written = [self._write(snap, who, reason, at) for snap in sorted(self._pending)]
            self._pending.clear()
            return written

    def _write(self, snap: str, who: str, reason: str, at: datetime | None = None) -> Path:
        gens = generators(self.plan)
        latest = self.latest_all(snap)
        by_unit: dict[str, list[dict]] = {}
        for r in latest:
            by_unit.setdefault(r["unit_id"], []).append(r)
        units = []
        shell_ids = [u["id"] for u in self.plan.get("units", [])]
        for u in self.plan.get("units", []):
            udims = gens.get(str(u.get("generator")), {}).get("dimensions") or []
            units.append({"id": u["id"], "generator": str(u.get("generator")), "placement": u.get("placement"),
                          "covers": u.get("covers"), "filters": udims,
                          "commentary": self._entries(by_unit.get(u["id"], []))})
        for uid in sorted(set(by_unit) - set(shell_ids)):  # removed from the shell: kept, marked
            rs = by_unit[uid]
            units.append({"id": uid, "generator": rs[0].get("generator"), "removed_from_shell": True,
                          "commentary": self._entries(rs)})
        now = at or datetime.now(timezone.utc)
        data = {"deliverable": self.plan.get("deliverable"), "medium": self.plan.get("medium"),
                "snapshot": None if snap == "none" else snap,
                "saved_at": now.isoformat(timespec="microseconds"), "saved_by": who, "reason": reason,
                "units": units}
        self.dir.mkdir(parents=True, exist_ok=True)
        stem = "commentary_" + ("" if snap == "none" else _file_part(snap) + "_") + now.strftime("%Y%m%d-%H%M%S")
        path, i = self.dir / f"{stem}.json", 2
        while path.exists():
            path, i = self.dir / f"{stem}-{i}.json", i + 1
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, default=str))
        tmp.replace(path)
        self._write_simple(snap, units)
        return path

    def _write_simple(self, snap: str, units: list[dict]) -> Path:
        """The output to place: one item per commentary, {"id", "commentary", "source"}.
        Beside the shell: commentary.json, or commentary_<snapshot>.json for dashboards.
        A unit with filters has one item per filter combination, with a "filters" key."""
        items = []
        for u in units:
            if u.get("removed_from_shell"):
                continue
            for e in u.get("commentary", []):
                ok = e.get("status") == "ok"
                bullets = e.get("bullets") or []
                source = (e.get("basis") or "").strip()
                if not ok:
                    source = "Not written: it failed its checks. See commentary_run.md."
                else:
                    n = sum(1 for b in bullets if b.get("unverified"))
                    if n:
                        source = (source + f" {n} figure(s) could not be checked against the tables.").strip()
                item = {"id": u["id"]}
                if e.get("filters"):
                    item["filters"] = e["filters"]
                item["commentary"] = [b.get("text", "") for b in bullets] if ok else []
                item["source"] = source
                items.append(item)
        if all(re.fullmatch(r"C\d+", str(i["id"])) for i in items):
            items.sort(key=lambda i: int(i["id"][1:]))  # stable: filter combinations keep their order
        name = "commentary.json" if snap == "none" else f"commentary_{_file_part(snap)}.json"
        path = self.dir.parent / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return path

    def _entries(self, rows: list[dict]) -> list[dict]:
        out = []
        for r in sorted(rows, key=lambda r: [r.get(d, "all") for d in self.dims]):
            filters = {d: r[d] for d in self.dims if r.get(d, "all") != "all"}
            out.append({"filters": filters, **{f: r.get(f) for f in ENTRY_FIELDS}})
        return out


def open_store(plan: dict, plan_dir: Path) -> OutputStore:
    return OutputStore(plan, plan_dir)
