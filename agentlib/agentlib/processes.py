"""Operating-system processes: look at a process tree and end it. Engine-neutral, uses psutil.

- process_started_at(pid) -> float | None: when the process started (seconds since the epoch), None if gone.
  Keep it with a pid: the helpers below take it as started_at= and refuse a process whose start time differs
  (the pid was reused by an unrelated program)
- describe_process(pid, started_at=None) -> ProcessInfo | None; list_descendants(pid, started_at=None) ->
  [ProcessInfo] (children, grandchildren, ...; [] if the pid is gone or the start time differs)
- end_process_tree(pid, started_at=None, timeout_s=3, include_root=True) -> KillResult: lists every descendant
  FIRST, then ends the root and all of them. Never raises for a process that is already gone (a second call is
  harmless); refuses (KillResult.refused) a start-time mismatch, this program itself or one of its parents,
  and the system's own processes
- Session.kill() (session.py) calls this for an engine session's own process (capability process_control)

Platforms: on Windows there is no signal to a group and no graceful stop: each process is ended outright
(psutil's terminate is TerminateProcess there). On Mac / Linux each gets SIGTERM, then SIGKILL after timeout_s.
Children found while waiting (a process started one just before it was ended) are swept up too. Remaining
gap: a process started by a descendant in the instant between the listing and that descendant's end, which
on Mac / Linux is re-parented away and can no longer be traced to the tree.

CPU: ProcessInfo.cpu_percent is psutil's per-process figure (100 = one full core; can exceed 100 on several
cores). psutil measures it between two looks at the same process: the first listing of a process gives 0.0,
later listings (this module keeps the process objects) give the use since the previous listing. Pass
cpu_interval_s > 0 to measure over that pause instead (blocks for it once per call).
"""
from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field

import psutil

START_TOLERANCE_S = 1.0             # started_at matches if within this (callers may store it rounded)
_POLL_S = 0.05
_SYSTEM_PIDS = {0, 4} if sys.platform == "win32" else {0, 1}
_SEEN: dict[tuple[int, float], psutil.Process] = {}     # (pid, create_time) -> Process, for cpu_percent
_SEEN_MAX = 4096


@dataclass
class ProcessInfo:
    """One process, as seen at one moment. JSON-safe via to_dict()."""
    pid: int
    parent_pid: int | None
    name: str
    command: str                     # full command line ("" if the system would not say); not shortened
    started_at: float                # seconds since the epoch (pass back as started_at=)
    cpu_percent: float               # 100 = one full core (see the module docstring for the first reading)
    mem_mb: float                    # resident memory
    status: str                      # psutil status: "running", "sleeping", "zombie", ...

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KillResult:
    """What end_process_tree() / Session.kill() did."""
    pid: int | None                  # the root asked for (None: the session had no process)
    ok: bool                         # nothing refused and nothing left alive
    ended: list[ProcessInfo] = field(default_factory=list)   # what was ended, as it looked just before
    survivors: list[int] = field(default_factory=list)       # pids still alive after the wait
    refused: str | None = None       # why nothing was done (start time differs, this program, system)
    already_gone: bool = False       # the root was not running (nothing to do)

    def to_dict(self) -> dict:
        return {"pid": self.pid, "ok": self.ok, "ended": [p.to_dict() for p in self.ended],
                "survivors": list(self.survivors), "refused": self.refused, "already_gone": self.already_gone}


def bad_start_time(started_at) -> str | None:
    """Why started_at cannot be used as a start time (None = usable): it must be a real, finite, positive number
    of seconds (int or float, not bool). NaN would match every process, so it is refused, like strings."""
    if isinstance(started_at, bool) or not isinstance(started_at, (int, float)):
        return f"start time {started_at!r} is not a number"
    if not math.isfinite(started_at) or started_at <= 0:
        return f"start time {started_at!r} is not a usable time"
    return None


def _bad_pid(pid) -> str | None:
    if isinstance(pid, bool) or not isinstance(pid, int):
        return f"pid {pid!r} is not a whole number"
    if pid <= 0:
        return f"pid {pid} is not a process id"
    return None


def _open(pid, started_at) -> tuple[psutil.Process | None, str | None]:
    """(process, None) | (None, None) when gone or pid None | (None, reason) when refused: a bad pid or start
    time (checked BEFORE anything is compared), or the start time differs. started_at None = no check."""
    if pid is None:
        return None, None
    bad = _bad_pid(pid) or (bad_start_time(started_at) if started_at is not None else None)
    if bad:
        return None, bad
    try:
        p = psutil.Process(pid)
        created = p.create_time()
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return None, None
    except psutil.AccessDenied:
        return None, f"process {pid}: access denied"
    if started_at is not None and not abs(created - float(started_at)) <= START_TOLERANCE_S:
        return None, f"process {pid} is a different program now (start time differs: the pid was reused)"
    return p, None


def process_started_at(pid: int | None) -> float | None:
    """When the process started (seconds since the epoch); None if it is not running (or cannot be read)."""
    p, _ = _open(pid, None)
    try:
        return p.create_time() if p is not None else None
    except psutil.Error:
        return None


def is_running(pid: int | None, *, started_at: float | None = None) -> bool:
    """pid is running (not a zombie) and, if started_at is given, is the same process (start time matches)."""
    p, _ = _open(pid, started_at)
    return p is not None and _alive(p)


def _tracked(p: psutil.Process) -> psutil.Process:
    """The kept Process object for p (so cpu_percent measures since the previous listing)."""
    try:
        key = (p.pid, p.create_time())
    except psutil.Error:
        return p
    kept = _SEEN.get(key)
    if kept is None:
        if len(_SEEN) >= _SEEN_MAX:
            for k in list(_SEEN)[: _SEEN_MAX // 2]:
                _SEEN.pop(k, None)
        _SEEN[key] = kept = p
    return kept


def _info(p: psutil.Process) -> ProcessInfo | None:
    try:
        with p.oneshot():
            name = p.name()
            started = p.create_time()
            try:
                ppid = p.ppid()
            except psutil.Error:
                ppid = None
            try:
                command = " ".join(p.cmdline())
            except (psutil.AccessDenied, psutil.ZombieProcess):
                command = ""
            try:
                cpu = float(p.cpu_percent(interval=None))
            except psutil.AccessDenied:
                cpu = 0.0
            try:
                mem = p.memory_info().rss / (1024 * 1024)
            except psutil.AccessDenied:
                mem = 0.0
            try:
                status = str(p.status())
            except psutil.Error:
                status = "unknown"
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return None
    except psutil.AccessDenied:
        return ProcessInfo(pid=p.pid, parent_pid=None, name="?", command="", started_at=0.0, cpu_percent=0.0,
                           mem_mb=0.0, status="unknown")
    return ProcessInfo(pid=p.pid, parent_pid=ppid, name=name, command=command or name, started_at=started,
                       cpu_percent=round(cpu, 1), mem_mb=round(mem, 1), status=status)


def _measure(procs: list[psutil.Process], cpu_interval_s: float) -> list[ProcessInfo]:
    procs = [_tracked(p) for p in procs]
    if cpu_interval_s > 0:
        for p in procs:
            try:
                p.cpu_percent(interval=None)       # start the measurement for each, then one shared pause
            except psutil.Error:
                pass
        time.sleep(cpu_interval_s)
    return [i for i in map(_info, procs) if i is not None]


def describe_process(pid: int | None, *, started_at: float | None = None,
                     cpu_interval_s: float = 0.0) -> ProcessInfo | None:
    """One process; None if it is not running or its start time differs from started_at."""
    p, _ = _open(pid, started_at)
    if p is None:
        return None
    found = _measure([p], cpu_interval_s)
    return found[0] if found else None


def _descendants(p: psutil.Process) -> list[psutil.Process]:
    try:
        return p.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return []
    except psutil.AccessDenied:
        return []


def list_descendants(pid: int | None, *, started_at: float | None = None,
                     cpu_interval_s: float = 0.0) -> list[ProcessInfo]:
    """Every process started (directly or further down) by pid, root not included; [] if pid is not running
    or its start time differs from started_at. Order: psutil's (depth first)."""
    p, _ = _open(pid, started_at)
    if p is None:
        return []
    me = os.getpid()
    return _measure([c for c in _descendants(p) if c.pid != me], cpu_interval_s)


def child_pids() -> set[int]:
    """Pids of this program's direct children right now (engines diff it around starting a process)."""
    try:
        return {c.pid for c in psutil.Process().children()}
    except psutil.Error:
        return set()


def new_child(before: set[int], name_hints: tuple[str, ...] = ()) -> int | None:
    """The one direct child started since child_pids() returned `before`, if it can be told for certain: exactly
    one new live child, or exactly one whose name contains a hint. Else None (e.g. two started at once)."""
    try:
        new = [c for c in psutil.Process().children() if c.pid not in before and _alive(c)]
    except psutil.Error:
        return None
    if len(new) > 1 and name_hints:
        def named(c):
            try:
                return any(h in c.name().lower() for h in name_hints)
            except psutil.Error:
                return False
        new = [c for c in new if named(c)]
    return new[0].pid if len(new) == 1 else None


def _protected(pid: int) -> str | None:
    if pid in _SYSTEM_PIDS:
        return f"process {pid} belongs to the operating system"
    me = psutil.Process()
    if pid == me.pid:
        return "refusing to end this program itself"
    try:
        if pid in {a.pid for a in me.parents()}:
            return f"process {pid} started this program; ending it would end this program too"
    except psutil.Error:
        pass
    return None


def _alive(p: psutil.Process) -> bool:
    """Running and not a zombie. Never waits on (reaps) a child: its owner (e.g. asyncio) does that."""
    try:
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except psutil.AccessDenied:
        return True


def _wait(procs: list[psutil.Process], timeout_s: float) -> list[psutil.Process]:
    """Poll until all are gone or timeout_s passes; -> the ones still alive."""
    deadline = time.monotonic() + max(0.0, timeout_s)
    alive = [p for p in procs if _alive(p)]
    while alive and time.monotonic() < deadline:
        time.sleep(_POLL_S)
        alive = [p for p in alive if _alive(p)]
    return alive


def _signal(procs: list[psutil.Process], hard: bool) -> None:
    for p in procs:
        try:
            p.kill() if hard else p.terminate()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass
        except psutil.AccessDenied:
            pass


def end_process_tree(pid: int | None, *, started_at: float | None = None, timeout_s: float = 3.0,
                     include_root: bool = True) -> KillResult:
    """End pid and everything it started. Descendants are listed BEFORE anything is ended, so none is
    orphaned unseen. Windows: each process ended outright. Mac / Linux: SIGTERM, wait up to timeout_s, then
    SIGKILL (and another short wait). include_root=False ends only the descendants (leftover commands of a
    process that should keep running). Safe to call again: a root that is gone -> ok, already_gone.
    A pid or started_at that is not a proper value (string, bool, NaN, infinity, negative) is refused, never
    raised and never treated as "no check"; started_at=None means no start-time check."""
    if pid is None:
        return KillResult(pid=None, ok=True, already_gone=True)
    if isinstance(pid, bool) or not isinstance(pid, int):
        return KillResult(pid=None, ok=False, refused=_bad_pid(pid))
    if started_at is not None and bad_start_time(started_at):
        return KillResult(pid=pid, ok=False, refused=bad_start_time(started_at))
    refused = _protected(pid)
    if refused:
        return KillResult(pid=pid, ok=False, refused=refused)
    root, refused = _open(pid, started_at)
    if refused:
        return KillResult(pid=pid, ok=False, refused=refused)
    if root is None:
        return KillResult(pid=pid, ok=True, already_gone=True)
    me = os.getpid()
    kids = [c for c in _descendants(root) if c.pid != me and c.pid not in _SYSTEM_PIDS]
    targets = ([root] if include_root else []) + kids
    snapshot = {i.pid: i for i in map(_info, targets) if i is not None}
    seen = {p.pid for p in targets}

    # root first, so it cannot start replacements when its children go; then the rest, top down
    _signal(targets, hard=sys.platform == "win32")
    alive = _wait(targets, timeout_s)
    for _ in range(3):                         # children started just before their parent was told to stop
        extra = [c for p in alive for c in _descendants(p) if c.pid not in seen and c.pid != me]
        if not extra:
            break
        for c in extra:
            seen.add(c.pid)
            info = _info(c)
            if info is not None:
                snapshot[c.pid] = info
        _signal(extra, hard=sys.platform == "win32")
        targets += extra
        alive = _wait(alive + extra, timeout_s if sys.platform != "win32" else 1.0)
    if alive:
        _signal(alive, hard=True)
        alive = _wait(alive, max(1.0, timeout_s / 2))
    left = {p.pid for p in alive}
    ended = [info for p_id, info in snapshot.items() if p_id not in left]
    return KillResult(pid=pid, ok=not left, ended=ended, survivors=sorted(left))
