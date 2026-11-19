"""Load the table behind the visual (CSV or JSON) and describe it for the agent.

The page gets every row; the agent only gets column names, simple types and a few sample rows.
Types are inferred simply: number, boolean, date (ISO-like strings), else string.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# yyyy-mm-dd, optionally with a time; also yyyy-mm and yyyy/mm/dd.
DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
NUMBER_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
BOOL_WORDS = {"true": True, "false": False, "yes": True, "no": False}
SAMPLE_TEXT_LIMIT = 80


class DataError(Exception):
    """The data file is missing, empty or not a table."""


@dataclass
class Table:
    columns: list[dict] = field(default_factory=list)   # [{"name": ..., "type": ...}]
    rows: list[dict] = field(default_factory=list)

    def samples(self, n: int = 3) -> list[dict]:
        """About n rows spread over the table (first, middle, last), long text shortened."""
        if not self.rows:
            return []
        if len(self.rows) <= n:
            picked = self.rows
        else:
            step = (len(self.rows) - 1) / (n - 1)
            picked = [self.rows[round(i * step)] for i in range(n)]
        return [{k: _short(v) for k, v in row.items()} for row in picked]


def _short(v):
    if isinstance(v, str) and len(v) > SAMPLE_TEXT_LIMIT:
        return v[:SAMPLE_TEXT_LIMIT] + "..."
    return v


def load(path: str | Path) -> Table:
    p = Path(path)
    if not p.is_file():
        raise DataError(f"Data file not found: {p}")
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json" or text.lstrip()[:1] in ("[", "{"):
        return _from_json(text, p)
    return _from_csv(text, p)


def _from_csv(text: str, p: Path) -> Table:
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise DataError(f"{p.name} has no header row.")
    names = [n.strip() for n in reader.fieldnames]
    raw = [{names[i]: (row.get(f) or "").strip() for i, f in enumerate(reader.fieldnames)} for row in reader]
    columns, rows = [], [dict() for _ in raw]
    for name in names:
        values = [r[name] for r in raw]
        kind = _csv_type(values)
        columns.append({"name": name, "type": kind})
        for out, v in zip(rows, values):
            out[name] = _csv_value(v, kind)
    return Table(columns, rows)


def _csv_type(values: list[str]) -> str:
    filled = [v for v in values if v != ""]
    if not filled:
        return "string"
    if all(NUMBER_RE.match(v) for v in filled):
        return "number"
    if all(v.lower() in BOOL_WORDS for v in filled):
        return "boolean"
    if all(DATE_RE.match(v) for v in filled):
        return "date"
    return "string"


def _csv_value(v: str, kind: str):
    if v == "":
        return None
    if kind == "number":
        n = float(v)
        return int(n) if n.is_integer() and re.match(r"^[+-]?\d+$", v) else n
    if kind == "boolean":
        return BOOL_WORDS[v.lower()]
    return v


def _from_json(text: str, p: Path) -> Table:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise DataError(f"{p.name} is not valid JSON: {e}") from None
    if isinstance(data, dict):  # lenient: {"rows": [...]} or {"data": [...]}
        data = data.get("rows", data.get("data"))
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise DataError(f"{p.name} must hold a JSON array of row objects.")
    names: list[str] = []
    for row in data:
        for k in row:
            if k not in names:
                names.append(k)
    rows = [{n: row.get(n) for n in names} for row in data]
    columns = [{"name": n, "type": _json_type([r[n] for r in rows])} for n in names]
    return Table(columns, rows)


def _json_type(values: list) -> str:
    filled = [v for v in values if v is not None and v != ""]
    if not filled:
        return "string"
    if all(isinstance(v, bool) for v in filled):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in filled):
        return "number"
    if all(isinstance(v, str) and DATE_RE.match(v) for v in filled):
        return "date"
    if all(isinstance(v, (dict, list)) for v in filled):
        return "object"
    return "string"
