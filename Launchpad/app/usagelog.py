"""The usage log: one line per agent call, kept per user, and the Usage screen's chart data read back from it.

- Where: <home>/.launchpad/usage/<YYYY-MM>.jsonl (UsageLog.beside(store): a "usage" folder beside settings.json; LAUNCHPAD_HOME
  and the fake demo's temp home move it). No store file = in memory only (most tests); the fake demo never writes a real
  log (hub.py: memory unless its home is a temp folder). Never in a project, never sent anywhere. Kept indefinitely
- Who writes: app/meter.py Meter.add_reply, the one place every agent reply is metered (planner, Explorer, orchestrator,
  builders + folder step agents, Visualizer, CLI chat, Role Reviewer, drafter, workflow stages), right after the reply is
  added to the live totals. The live totals are untouched (app/costs.py still sums them); the log is a record beside them
- Line (JSON, one per call, "\\n"-terminated): v, ts (ISO local time with offset), session (the session id; a CLI chat's
  chat id; a review / drafting call: the agent run's own id), kind (plan | chat | workflow | review | other), label, dir_id,
  folder (absolute), folder_name, run_folder, role (role id: planner, astronaut, orchestrator, builder, visual, pilot,
  reviewer, drafter), agent (display name: "Builder", a folder agent's name, ...), step, stage (a workflow stage's title),
  model, cli (harness id: claude | cursor | fake), engine, cost, input_tokens, output_tokens, cache_read_tokens,
  cache_write_tokens (the reply's own figures, exactly what the meter added), by_model (only when the reply used more than
  one model: [{model, cost, the four counts}], summing to the line's totals; agentlib's usage_by_model, any remainder put
  on the line's model)
- Appending: lock file usage/<month>.jsonl.lock (O_CREAT | O_EXCL, retried; a stale one is broken, as in tally.py), then
  ONE write of the whole line. A file whose last byte is not a newline (a writer that died mid-line) first gets one, so a
  half line never glues onto the next. Several Launchpad processes can append at once
- Reading: a damaged or half-written line is skipped and counted (skipped_lines), never fatal. Size: a file per month, and
  each file is parsed once per launch into small aggregates (per day, session, CLI, model and agent), then only the bytes
  appended since are read. A 7 / 30 / 90-day request reads only the months it needs (plus one month before, so a
  session that began a little before the range still shows its whole cost); "all" reads every month
- build(...) -> the usage_data event (contract: app/server.py header "Usage screen")
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import threading
import time
from pathlib import Path

DIR_NAME = "usage"
VERSION = 1
TOKENS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
MEASURES = (("cost", "Cost", "usd"), ("input_tokens", "Input tokens", "tokens"), ("output_tokens", "Output tokens", "tokens"),
            ("cache_read_tokens", "Cache read tokens", "tokens"), ("cache_write_tokens", "Cache write tokens", "tokens"))
PERIODS = {"7d": 7, "30d": 30, "90d": 90, "all": None}
BUCKETS = ("day", "week")
SPLITS = ("cli", "model", "agent")
DEFAULTS = {"period": "30d", "bucket": "day", "split": "agent"}
KINDS = {"plan": "Plan", "chat": "CLI chat", "workflow": "Workflow run", "review": "Review", "other": "Other"}
MAX_SERIES = 7                 # more groups than this: the 6 largest + "Other"
OTHER_KEY = "__other__"
MAX_SESSIONS = 500
PLANNER_ROLE = "planner"
CLI_LABELS = {"fake": "Fake engine (demo)"}
LOCK_WAIT_S = 5.0
LOCK_STALE_S = 30.0
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- names
def model_label(model: str | None) -> str:
    """A readable model name: "claude-sonnet-4-5-20250929" -> "Sonnet 4.5", "claude-3-5-haiku" -> "Haiku 3.5",
    "opus" -> "Opus"; anything else as written ("" -> "Unknown model")."""
    raw = str(model or "").strip()
    if not raw:
        return "Unknown model"
    s = raw.lower()
    extra = ""
    m = re.search(r"\[(\w+)\]$", s)
    if m:
        extra, s = f" ({m.group(1).upper()})", s[:m.start()]
    s = re.sub(r"^(anthropic[./:])?(claude-)?", "", s)
    s = re.sub(r"-\d{8}$", "", s)
    s = re.sub(r"@.*$|-v\d+(:\d+)?$", "", s)
    parts = s.split("-")
    family = next((p for p in parts if p in ("opus", "sonnet", "haiku")), None)
    if family is None:
        return raw
    nums = [p for p in parts if p.isdigit() and len(p) <= 2]
    return family.capitalize() + (" " + ".".join(nums) if nums else "") + extra


def cli_of(engine: str | None) -> str:
    """The harness id an agentlib engine belongs to (app/agents/planner/choices.py HARNESSES); else the engine's name."""
    from .agents.planner import choices
    e = str(engine or "").strip() or "unknown"
    return next((h["harness"] for h in choices.HARNESSES if h["engine"] == e), e)


def cli_label(cli: str) -> str:
    if cli in CLI_LABELS:
        return CLI_LABELS[cli]
    from .agents.planner import choices
    return choices.harness_label(cli) if choices.harness(cli) else (cli or "Unknown").capitalize()


def agent_group(row: dict) -> str:
    """Split by agent: the display name; calls inside a workflow run are their own groups ("Workflow: Builder")."""
    name = str(row.get("agent") or row.get("role") or "Unknown agent")
    return f"Workflow: {name}" if row.get("kind") == "workflow" else name


# --------------------------------------------------------------------------- one call -> one line
def meter_key(meter) -> str:
    """The session a meter's calls belong to: its session, its CLI chat, else its own run (review, drafting)."""
    return meter.session_id or meter.chat_id or meter.agent_id


def context(hub, meter) -> dict:
    """What a line says about where a call came from: session, kind, label, folder, run folder (from the hub)."""
    info = dict(getattr(meter, "usage_info", None) or {})
    out = {"session": meter_key(meter), "kind": "other", "label": info.get("label") or "", "dir_id": None,
           "folder": None, "folder_name": None, "run_folder": None}
    project = run_folder = did = None
    if meter.chat_id:
        chat = (getattr(hub, "chats", None) or {}).get(meter.chat_id)
        out.update(kind="chat", label=out["label"] or "CLI chat")
        if chat is not None:
            project, run_folder, did = chat.folder.project, chat.folder.path, chat.dir_id
    elif meter.session_id:
        wf = getattr(hub, "workflows", None)
        run = wf.mission(meter.session_id) if wf is not None else None
        ls = (getattr(hub, "sessions", None) or {}).get(meter.session_id)
        if run is not None:
            out.update(kind="workflow", label=out["label"] or (f"{run.wf['name']}, run {run.id}"
                                                               + (" (test run)" if run.test else "")))
            project, run_folder, did = run.folder.project, run.run_folder, run.wf.get("folder")
        elif ls is not None:
            name = ""
            if ls.plan_text:
                from . import plan as plan_mod
                with contextlib.suppress(Exception):
                    name = plan_mod.parse(ls.plan_text)["name"]
            out.update(kind="plan", label=out["label"] or name or "Planning session")
            project, run_folder, did = ls.folder.project, ls.folder.path, ls.dir_id
        else:
            out["kind"] = "workflow" if meter.session_id.startswith("wf-") else "plan"
    else:
        out["kind"] = "review" if meter.role == "reviewer" else "other"
        if not out["label"]:
            out["label"] = "Role review" if meter.role == "reviewer" else "Agent drafting" if meter.role == "drafter" \
                else str(meter.name or meter.role)
    project = project or info.get("folder")
    if project:
        p = Path(project)
        if did is None:
            from .store import dir_id
            with contextlib.suppress(OSError):
                did = dir_id(p)
        out.update(folder=str(p), folder_name=p.name or str(p), dir_id=did)
    if run_folder:
        out["run_folder"] = str(run_folder)
    return out


def line(hub, meter, reply) -> dict:
    """The log line for one metered reply (the same figures Meter.add_reply just added)."""
    usage = reply.usage
    cost = float(reply.cost_usd or 0.0)
    tokens = {k: int(getattr(usage, k, 0) or 0) for k in TOKENS}
    model = str(getattr(reply, "model", None) or "")
    row = {"v": VERSION, "ts": now_iso(), **context(hub, meter), "role": meter.role, "agent": meter.name,
           "step": meter.step, "stage": (getattr(meter, "usage_info", None) or {}).get("stage"),
           "model": model, "cli": cli_of(getattr(reply, "engine", None)), "engine": getattr(reply, "engine", None),
           "cost": round(cost, 9), **tokens}
    by = getattr(reply, "usage_by_model", None) or {}
    if by and not model:
        row["model"] = model = next(iter(by))
    if len(by) > 1 or (by and next(iter(by)) != model):
        parts = []
        for mid, v in by.items():
            u = v.get("usage")
            parts.append({"model": str(mid), "cost": float(v.get("cost_usd") or 0.0),
                          **{k: int(getattr(u, k, 0) or 0) for k in TOKENS}})
        rest = {"cost": cost - sum(p["cost"] for p in parts), **{k: tokens[k] - sum(p[k] for p in parts) for k in TOKENS}}
        if abs(rest["cost"]) > 1e-12 or any(rest[k] for k in TOKENS):      # what the per-model figures did not cover
            mine = next((p for p in parts if p["model"] == model), None)
            if mine is None:
                mine = {"model": model, "cost": 0.0, **{k: 0 for k in TOKENS}}
                parts.append(mine)
            for k, v in rest.items():
                mine[k] += v
        for p in parts:
            p["cost"] = round(p["cost"], 9)
        if len(parts) > 1:
            row["by_model"] = parts
        else:
            row["model"] = parts[0]["model"]
    return row


# --------------------------------------------------------------------------- aggregates
def _parse_row(raw) -> dict | None:
    """A log line as a dict, or None when it is damaged (not JSON, wrong shape, bad numbers)."""
    try:
        row = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(row, dict) or not isinstance(row.get("session"), str) or not row["session"]:
        return None
    try:
        when = dt.datetime.fromisoformat(str(row["ts"]))
        if when.tzinfo is None:
            when = when.astimezone()
        row["_t"] = when.timestamp()
        row["_day"] = dt.datetime.fromtimestamp(row["_t"]).date().isoformat()     # local day
        row["cost"] = float(row.get("cost") or 0.0)
        for k in TOKENS:
            row[k] = int(row.get(k) or 0)
        for p in row.get("by_model") or []:
            p["cost"] = float(p.get("cost") or 0.0)
            for k in TOKENS:
                p[k] = int(p.get(k) or 0)
    except (KeyError, TypeError, ValueError, OverflowError, OSError, AttributeError):
        return None
    if row.get("by_model") is not None and not isinstance(row["by_model"], list):
        return None
    return row


class Aggregate:
    """Small totals built from lines: cells per (local day, session, cli, model label, agent group) and one summary per
    session. Lines are folded in once and dropped."""

    def __init__(self):
        self.cells: dict[tuple, list] = {}       # key -> [cost, in, out, cache_read, cache_write, calls]
        self.sessions: dict[str, dict] = {}
        self.skipped = 0

    def add_raw(self, raw) -> None:
        row = _parse_row(raw)
        if row is None:
            self.skipped += 1
        else:
            self.add(row)

    def add(self, row: dict) -> None:
        cli = str(row.get("cli") or "unknown")
        agent = agent_group(row)
        parts = row.get("by_model") or [{"model": row.get("model"), "cost": row["cost"],
                                         **{k: row[k] for k in TOKENS}}]
        for i, p in enumerate(parts):
            key = (row["_day"], row["session"], cli, model_label(p.get("model")), agent)
            c = self.cells.get(key)
            if c is None:
                c = self.cells[key] = [0.0, 0, 0, 0, 0, 0]
            c[0] += p["cost"]
            for j, k in enumerate(TOKENS, start=1):
                c[j] += p[k]
            c[5] += 1 if i == 0 else 0
        s = self.sessions.get(row["session"])
        if s is None:
            s = self.sessions[row["session"]] = {"id": row["session"], "kind": "other", "label": "", "dir_id": None,
                                                 "folder": None, "folder_name": None, "run_folder": None,
                                                 "first": row["_t"], "last": row["_t"], "label_t": -1.0, "cost": 0.0,
                                                 "planner_cost": 0.0, **{k: 0 for k in TOKENS}, "calls": 0,
                                                 "agents": {}, "models": {}, "clis": {}}
        merge_session(s, row, parts)

    def merge(self, other: "Aggregate") -> None:
        for k, c in other.cells.items():
            mine = self.cells.get(k)
            if mine is None:
                self.cells[k] = list(c)
            else:
                for j in range(6):
                    mine[j] += c[j]
        for sid, o in other.sessions.items():
            s = self.sessions.get(sid)
            if s is None:
                self.sessions[sid] = {**o, "agents": dict(o["agents"]), "models": dict(o["models"]),
                                      "clis": dict(o["clis"])}
                continue
            for k in ("cost", "planner_cost", "calls", *TOKENS):
                s[k] += o[k]
            if o["first"] < s["first"]:
                s["first"] = o["first"]
            if o["last"] > s["last"]:
                s["last"] = o["last"]
            if o["label_t"] >= s["label_t"]:
                for k in ("kind", "label", "label_t", "dir_id", "folder", "folder_name", "run_folder"):
                    if o.get(k):
                        s[k] = o[k]
            for k in ("agents", "models", "clis"):
                s[k].update(o[k])
        self.skipped += other.skipped


def merge_session(s: dict, row: dict, parts: list) -> None:
    s["cost"] += row["cost"]
    if row.get("role") == PLANNER_ROLE:
        s["planner_cost"] += row["cost"]
    for k in TOKENS:
        s[k] += row[k]
    s["calls"] += 1
    s["first"], s["last"] = min(s["first"], row["_t"]), max(s["last"], row["_t"])
    if row["_t"] >= s["label_t"]:                                    # the latest line's description wins
        s["label_t"] = row["_t"]
        if row.get("kind") in KINDS:
            s["kind"] = row["kind"]
        if row.get("label"):
            s["label"] = str(row["label"])
        for k in ("dir_id", "folder", "folder_name", "run_folder"):
            if row.get(k):
                s[k] = str(row[k])
    s["agents"][agent_group(row)] = None
    for p in parts:
        s["models"][model_label(p.get("model"))] = None
    s["clis"][cli_label(str(row.get("cli") or "unknown"))] = None


class _FileState:
    def __init__(self):
        self.offset = 0
        self.agg = Aggregate()


# --------------------------------------------------------------------------- the log
class UsageLog:
    def __init__(self, folder: Path | None):
        self.folder = Path(folder) if folder else None
        self._mem_rows: list[str] = []            # memory mode: the lines as written
        self._mem = _FileState()
        self._files: dict[str, _FileState] = {}
        self._write_lock = threading.Lock()       # appends (event loop; any thread)
        self._read_lock = threading.Lock()        # reads (a worker thread): one at a time, never blocking an append

    @classmethod
    def beside(cls, store) -> "UsageLog":
        """The log beside a Store's settings.json (in memory when the store has no file)."""
        p = getattr(store, "path", None)
        return cls(Path(p).parent / DIR_NAME if p else None)

    # ------------------------------------------------------------ writing
    def month_file(self, when: dt.datetime | None = None) -> Path:
        return self.folder / f"{(when or dt.datetime.now()).strftime('%Y-%m')}.jsonl"

    def append(self, row: dict) -> None:
        """Add one line (one agent call). OSError when the file cannot be written (the caller reports it)."""
        self.append_many([row])

    def append_many(self, rows: list[dict]) -> None:
        """Add lines (each one agent call), one lock and one write per month file (the demo's seed uses it)."""
        texts: dict[Path | None, list[str]] = {}
        for row in rows:
            path = self.month_file(_row_time(row)) if self.folder is not None else None
            texts.setdefault(path, []).append(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str))
        with self._write_lock:
            for path, lines in texts.items():
                if path is None:
                    self._mem_rows.extend(lines)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                data = "".join(t + "\n" for t in lines).encode("utf-8")
                with _locked(path):
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0))
                    try:
                        size = os.fstat(fd).st_size
                        if size:
                            with open(path, "rb") as f:            # a writer that died mid-line: end its line first
                                f.seek(size - 1)
                                if f.read(1) != b"\n":
                                    data = b"\n" + data
                        view = memoryview(data)
                        while view:
                            view = view[os.write(fd, view):]
                    finally:
                        os.close(fd)

    def record(self, hub, meter, reply) -> dict:
        row = line(hub, meter, reply)
        self.append(row)
        return row

    # ------------------------------------------------------------ reading
    def files(self) -> list[Path]:
        if self.folder is None or not self.folder.is_dir():
            return []
        return sorted(p for p in self.folder.glob("*.jsonl") if re.fullmatch(r"\d{4}-\d{2}\.jsonl", p.name))

    def rows(self) -> list[dict]:
        """Every readable line, oldest file first (tests, checks; the screen uses aggregate())."""
        out = []
        raws = list(self._mem_rows) if self.folder is None else [
            r for p in self.files() for r in p.read_bytes().split(b"\n") if r.strip()]
        for raw in raws:
            row = _parse_row(raw)
            if row is not None:
                out.append({k: v for k, v in row.items() if not k.startswith("_")})
        return out

    def aggregate(self, since: dt.date | None = None) -> Aggregate:
        """Totals over the months from `since` (None = every month), brought up to date with what was appended."""
        total = Aggregate()
        with self._read_lock:
            if self.folder is None:
                st = self._mem
                new = self._mem_rows[st.offset:]
                for raw in new:
                    st.agg.add_raw(raw)
                st.offset += len(new)
                total.merge(st.agg)
                return total
            first = since.strftime("%Y-%m") if since else ""
            for p in self.files():
                if p.stem < first:
                    continue
                total.merge(self._refresh(p))
        return total

    def _refresh(self, path: Path) -> Aggregate:
        st = self._files.get(str(path))
        try:
            size = path.stat().st_size
        except OSError:
            return Aggregate()
        if st is None or size < st.offset:                    # new, or replaced / cut: read it again
            st = self._files[str(path)] = _FileState()
        if size > st.offset:
            with open(path, "rb") as f:
                f.seek(st.offset)
                chunk = f.read(size - st.offset)
            end = chunk.rfind(b"\n")
            if end >= 0:                                       # a line still being written waits for its newline
                for raw in chunk[:end].split(b"\n"):
                    if raw.strip():
                        st.agg.add_raw(raw)
                st.offset += end + 1
        return st.agg


def _row_time(row: dict) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(dt.datetime.fromisoformat(str(row.get("ts"))).timestamp())
    except (TypeError, ValueError, OSError, OverflowError):
        return None


@contextlib.contextmanager
def _locked(path: Path):
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except (FileExistsError, PermissionError):
            try:
                stale = time.time() - lock.stat().st_mtime > LOCK_STALE_S
            except OSError:
                stale = False
            if stale or time.monotonic() > deadline:            # a crashed holder: break the lock
                with contextlib.suppress(OSError):
                    lock.unlink()
                deadline = time.monotonic() + LOCK_WAIT_S
                continue
            time.sleep(0.002)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink()


# --------------------------------------------------------------------------- the usage_data event
def clean_request(msg: dict | None) -> dict:
    msg = msg or {}
    out = {k: (str(msg.get(k)) if str(msg.get(k) or "") in allowed else DEFAULTS[k])
           for k, allowed in (("period", PERIODS), ("bucket", BUCKETS), ("split", SPLITS))}
    sid = msg.get("session")
    out["session"] = str(sid) if isinstance(sid, str) and sid.strip() else None
    return out


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def _date_label(d: dt.date, today: dt.date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}" + (f" {d.year}" if d.year != today.year else "")


def buckets_for(start: dt.date, end: dt.date, bucket: str, today: dt.date) -> list[dict]:
    out = []
    if bucket == "day":
        d = start
        while d <= end:
            out.append({"key": d.isoformat(), "label": _date_label(d, today), "start": d.isoformat(),
                        "end": d.isoformat(), "partial": False})
            d += dt.timedelta(days=1)
        return out
    w = _monday(start)
    while w <= end:
        a, b = max(w, start), min(w + dt.timedelta(days=6), end)
        out.append({"key": w.isoformat(), "label": "Week of " + _date_label(w, today), "start": a.isoformat(),
                    "end": b.isoformat(), "partial": (a, b) != (w, w + dt.timedelta(days=6))})
        w += dt.timedelta(days=7)
    return out


def _wire(x: float) -> float:
    return round(float(x or 0.0), 6)


def empty_data(req: dict, *, error: str | None = None, skipped: int = 0, pushed: bool = False) -> dict:
    ev = {"type": "usage_data", "request": req, "range": None, "buckets": [], "series": [],
          "totals": {"cost": 0.0, **{k: 0 for k in TOKENS}, "calls": 0, "sessions": 0}, "sessions": [],
          "sessions_total": 0, "measures": [{"key": k, "label": lbl, "unit": u} for k, lbl, u in MEASURES],
          "skipped_lines": skipped, "pushed": pushed}
    if error:
        ev["error"] = error
    return ev


def build(log: UsageLog, msg: dict | None, *, running=lambda sid: False, today: dt.date | None = None,
          pushed: bool = False) -> dict:
    """usage_data for a usage_get request (contract: app/server.py header "Usage screen"). running(session id) -> bool
    says what is in progress in this launch. Never raises for a bad log: error is set instead."""
    req = clean_request(msg)
    today = today or dt.date.today()
    days = PERIODS[req["period"]]
    start = today - dt.timedelta(days=days - 1) if days else None
    try:
        agg = log.aggregate(since=(start - dt.timedelta(days=31)) if start else None)
    except OSError as e:
        return empty_data(req, error=f"the usage log could not be read ({e})", pushed=pushed)
    if not agg.cells:
        return empty_data(req, skipped=agg.skipped, pushed=pushed)
    narrowed = [(k, c) for k, c in agg.cells.items() if req["session"] is None or k[1] == req["session"]]
    if start is None:
        start = min((dt.date.fromisoformat(k[0]) for k, _ in narrowed), default=None) \
            or min(dt.date.fromisoformat(k[0]) for k in agg.cells)
        start = min(start, today)
    lo, hi = start.isoformat(), today.isoformat()
    buckets = buckets_for(start, today, req["bucket"], today)
    index = {b["key"]: i for i, b in enumerate(buckets)}
    n = len(buckets)

    def bucket_of(day: str) -> int:
        d = dt.date.fromisoformat(day)
        return index[(d if req["bucket"] == "day" else _monday(d)).isoformat()]

    groups: dict[str, dict] = {}
    totals = {"cost": 0.0, **{k: 0 for k in TOKENS}, "calls": 0}
    sessions_in: set[str] = set()
    for (day, sid, cli, model, agent), c in narrowed:
        if not (lo <= day <= hi):
            continue
        key = cli if req["split"] == "cli" else model if req["split"] == "model" else agent
        g = groups.get(key)
        if g is None:
            label = cli_label(cli) if req["split"] == "cli" else key
            g = groups[key] = {"key": key, "label": label,
                               "values": {m: [0.0 if m == "cost" else 0] * n for m, _, _ in MEASURES},
                               "totals": {"cost": 0.0, **{k: 0 for k in TOKENS}, "calls": 0}, "members": []}
        i = bucket_of(day)
        for j, (m, _, _) in enumerate(MEASURES):
            g["values"][m][i] += c[j]
            g["totals"][m] += c[j]
            totals[m] += c[j]
        g["totals"]["calls"] += c[5]
        totals["calls"] += c[5]
        sessions_in.add(sid)
    ranked = sorted(groups.values(), key=lambda g: (-g["totals"]["cost"], g["label"].lower()))
    if len(ranked) > MAX_SERIES:
        named, rest = ranked[:MAX_SERIES - 1], ranked[MAX_SERIES - 1:]
        other = {"key": OTHER_KEY, "label": "Other", "values": {m: [0.0 if m == "cost" else 0] * n for m, _, _ in MEASURES},
                 "totals": {"cost": 0.0, **{k: 0 for k in TOKENS}, "calls": 0}, "members": [g["label"] for g in rest]}
        for g in rest:
            for m, _, _ in MEASURES:
                other["values"][m] = [a + b for a, b in zip(other["values"][m], g["values"][m])]
            for k in other["totals"]:
                other["totals"][k] += g["totals"][k]
        ranked = named + [other]
    for g in ranked:
        g["values"]["cost"] = [_wire(x) for x in g["values"]["cost"]]
        g["totals"]["cost"] = _wire(g["totals"]["cost"])
    totals["cost"] = _wire(totals["cost"])
    totals["sessions"] = len(sessions_in)

    listed_ids = {k[1] for k in agg.cells if lo <= k[0] <= hi}
    listed = []
    for sid in listed_ids:
        s = agg.sessions.get(sid)
        if s is None:
            continue
        listed.append(session_view(s, bool(running(sid))))
    listed.sort(key=lambda s: (not s["running"], -s["_last"]))
    for s in listed:
        s.pop("_last")
    ev = empty_data(req, skipped=agg.skipped, pushed=pushed)
    ev.update(range={"start": lo, "end": hi}, buckets=buckets, series=ranked, totals=totals,
              sessions=listed[:MAX_SESSIONS], sessions_total=len(listed))
    return ev


def _local_iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def session_view(s: dict, running: bool) -> dict:
    folder = {"dir_id": s["dir_id"], "name": s["folder_name"], "path": s["folder"]} if s.get("folder") else None
    kind = s["kind"] if s["kind"] in KINDS else "other"
    return {"id": s["id"], "kind": kind, "kind_label": KINDS[kind], "label": s["label"] or KINDS[kind],
            "folder": folder, "run_folder": s.get("run_folder"), "started_at": _local_iso(s["first"]),
            "last_at": _local_iso(s["last"]), "running": running, "cost": _wire(s["cost"]),
            "planner_cost": _wire(s["planner_cost"]), **{k: s[k] for k in TOKENS}, "calls": s["calls"],
            "agents": list(s["agents"]), "models": list(s["models"]), "clis": list(s["clis"]), "_last": s["last"]}
