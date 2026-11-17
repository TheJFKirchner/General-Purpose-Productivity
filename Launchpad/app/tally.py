"""Undefined roles: the per-user tally of plan steps that ran on the Builder under a role name.

- File: <home>/.launchpad/roles.json, beside settings.json (Tally.beside(store)); path None = in memory only (a Hub
  without a user file, most tests). The fake demo's store lives in its own temp home, so --fake never writes the
  real tally. Review case files go to <home>/.launchpad/role-cases/ (cases_dir)
- Writes (every change): take the lock file roles.json.lock (O_CREAT | O_EXCL, retried; one older than LOCK_STALE_S
  or held past LOCK_WAIT_S is broken), re-read the file, apply the change, write a temp file, os.replace it. Two
  Launchpad processes therefore never lose each other's updates. Reads re-read the file too
- What is recorded (record_use, called from the step runner): a plan step with a `role` that ran on the Builder, and
  a step naming an agent that does not exist (tallied under that name). A step run by a registered agent is never
  recorded. The key is the role name; skills are evidence under it (one role used with several skills = one entry)
- Entry: name, base_agent (who ran the steps: "Builder"), purpose (that agent's purpose), skills seen, folders used in
  [{dir_id, name}], uses_total, first_used, last_used, up to MAX_SAMPLES distinct sample step instructions, verdict
  (the user's last decision: define | keep | not_yet, when, uses at the time, the reviewer's own verdict, case file),
  dismissed, last_review, and the last MAX_USES uses
- Use: id, seq, at, dir_id, folder, project (absolute path, for the reviewer), extra_projects (the session's additional
  folders, absolute, for the reviewer's skill discovery; never sent to the page), session_id, run, step, title, skills,
  outcome (done | failed | blocked), questions (asked by the worker), assumptions (logged for the step), timed_out
  (questions that timed out), sent_back (the plan was revised after that run; filled in by mark_sent_back),
  named_agent (true = tallied under a missing agent's name)
- Visibility (visibility()): listed once used THRESHOLD times; dismissed = hidden until used again; after a keep or
  not_yet decision hidden ("resting") until RESURFACE_USES more uses or a new failed / blocked / sent-back use; a
  define decision stays listed ("defining") until the agent is created, which removes the entry; merge folds one
  entry into another (uses, samples, skills, folders; counts add up)
- seq: a counter in the file, +1 per change; uses and verdicts carry it so "after the verdict" never depends on
  clock resolution
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

FILE_NAME = "roles.json"
CASES_DIR = "role-cases"
THRESHOLD = 2                 # listed once used this many times
RESURFACE_USES = 5            # after keep / not_yet: back after this many more uses
MAX_USES = 20                 # uses kept per role
MAX_SAMPLES = 3               # distinct sample step instructions kept per role
SAMPLE_CHARS = 1500
PLANNER_ROLE_NAMES = 20       # role names the planner is shown (most recently used)
OUTCOMES = ("done", "failed", "blocked")
PROBLEM_OUTCOMES = ("failed", "blocked")
DECISIONS = ("define", "keep", "not_yet")
LOCK_WAIT_S = 5.0
LOCK_STALE_S = 30.0


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _empty() -> dict:
    return {"version": 1, "seq": 0, "roles": {}}


def in_temp(path: Path | None) -> bool:
    """Is `path` inside the system temp folder (the fake demo's own home, test folders)? None (memory) counts as yes."""
    if path is None:
        return True
    try:
        Path(path).resolve().relative_to(Path(tempfile.gettempdir()).resolve())
        return True
    except (ValueError, OSError):
        return False


def is_problem(use: dict) -> bool:
    return use.get("outcome") in PROBLEM_OUTCOMES or bool(use.get("sent_back"))


def visibility(entry: dict) -> dict:
    """-> {state, visible, uses_to_list, resurfaced}. state: few_uses | dismissed | resting | defining | listed."""
    n = int(entry.get("uses_total") or 0)
    out = {"state": "listed", "visible": True, "uses_to_list": 0, "resurfaced": False}
    if n < THRESHOLD:
        return {**out, "state": "few_uses", "visible": False, "uses_to_list": THRESHOLD - n}
    if entry.get("dismissed"):
        return {**out, "state": "dismissed", "visible": False, "uses_to_list": 1}
    v = entry.get("verdict") or {}
    if v.get("decision") in ("keep", "not_yet"):
        since = [u for u in entry.get("uses") or [] if int(u.get("seq") or 0) > int(v.get("seq") or 0)]
        more = n - int(v.get("uses_at") or 0)
        if more >= RESURFACE_USES or any(is_problem(u) for u in since):
            return {**out, "resurfaced": True}
        return {**out, "state": "resting", "visible": False, "uses_to_list": RESURFACE_USES - more}
    if v.get("decision") == "define":
        return {**out, "state": "defining"}
    return out


def role_note(names: list[str]) -> str:
    """The role names the planner is shown in its first message (most recently used first)."""
    if not names:
        return "Role names in use: none yet."
    return "Role names in use (reuse one when it fits; most recent first): " + ", ".join(names)


class TallyError(ValueError):
    """A tally change that cannot be made (unknown role, bad merge); the message is shown to the user."""


class Tally:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._mem = _empty()                          # in-memory store when there is no file

    @classmethod
    def beside(cls, store) -> "Tally":
        """The tally beside a Store's settings.json (in memory when the store has no file)."""
        p = getattr(store, "path", None)
        return cls(Path(p).parent / FILE_NAME if p else None)

    @property
    def home(self) -> Path | None:
        return self.path.parent if self.path else None

    @property
    def cases_dir(self) -> Path | None:
        """Per-user folder for review case files (None in memory)."""
        return self.path.parent / CASES_DIR if self.path else None

    # ---------------------------------------------------------------- file access
    def _read(self) -> dict:
        if self.path is None:
            return self._mem
        for _ in range(50):
            try:
                text = self.path.read_text(encoding="utf-8")
                break
            except FileNotFoundError:
                return _empty()
            except PermissionError:                    # Windows: the file is being replaced right now
                time.sleep(0.02)
        else:
            raise OSError(f"cannot read {self.path.name}")
        try:
            data = json.loads(text)
        except ValueError:
            return _empty()                            # a broken file starts fresh (overwritten on the next change)
        if not isinstance(data, dict) or not isinstance(data.get("roles"), dict):
            return _empty()
        data.setdefault("seq", 0)
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix="roles-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        for i in range(50):
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:                    # Windows: a reader has the file open for a moment
                time.sleep(0.02)
        os.replace(tmp, self.path)

    @contextlib.contextmanager
    def _locked(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
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
                if stale or time.monotonic() > deadline:   # a crashed holder: break the lock
                    with contextlib.suppress(OSError):
                        lock.unlink()
                    deadline = time.monotonic() + LOCK_WAIT_S
                    continue
                time.sleep(0.005)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                lock.unlink()

    def _update(self, change):
        """change(data, seq) -> result; applied to a fresh read of the file under the lock, then saved."""
        if self.path is None:
            self._mem["seq"] = int(self._mem.get("seq") or 0) + 1
            return change(self._mem, self._mem["seq"])
        with self._locked():
            data = self._read()
            data["seq"] = int(data.get("seq") or 0) + 1
            result = change(data, data["seq"])
            self._write(data)
            return result

    # ---------------------------------------------------------------- reads
    def entries(self) -> list[dict]:
        """Every entry (a copy), most recently used first."""
        roles = copy.deepcopy(list(self._read()["roles"].values()))
        return sorted(roles, key=lambda e: int(e.get("last_seq") or 0), reverse=True)

    def get(self, name: str) -> dict | None:
        e = self._read()["roles"].get(str(name or ""))
        return copy.deepcopy(e) if e else None

    def recent_names(self, limit: int = PLANNER_ROLE_NAMES) -> list[str]:
        """Role names, most recently used first (what the planner is shown)."""
        return [e["name"] for e in self.entries()][:limit]

    # ---------------------------------------------------------------- changes
    def record_use(self, name: str, *, use: dict, sample: str = "", base_agent: str = "Builder",
                   purpose: str = "building") -> dict:
        """One step that ran under role `name` -> the updated entry. use: the fields listed in the module header
        (id, seq and at are filled in here). A dismissed role comes back (used again)."""
        name = str(name or "").strip()
        if not name:
            raise TallyError("give the role name")

        def change(data, seq):
            at = now_iso()
            e = data["roles"].setdefault(name, {
                "name": name, "base_agent": base_agent, "purpose": purpose, "skills": [], "folders": [],
                "uses_total": 0, "first_used": at, "last_used": at, "last_seq": seq, "samples": [], "verdict": None,
                "dismissed": False, "last_review": None, "uses": []})
            u = {"id": "u" + secrets.token_hex(4), "seq": seq, "at": at, "dir_id": None, "folder": "", "project": "",
                 "session_id": "", "run": None, "step": None, "title": "", "skills": [], "outcome": "done",
                 "questions": 0, "assumptions": 0, "timed_out": 0, "sent_back": False, "named_agent": False}
            u.update({k: v for k, v in (use or {}).items() if k not in ("id", "seq", "at")})
            if u["outcome"] not in OUTCOMES:
                u["outcome"] = "failed"
            e["uses"] = (e.get("uses") or []) + [u]
            e["uses"] = e["uses"][-MAX_USES:]
            e["uses_total"] = int(e.get("uses_total") or 0) + 1
            e["last_used"], e["last_seq"] = at, seq
            e["base_agent"], e["purpose"] = base_agent, purpose
            e["dismissed"] = False
            e["skills"] = list(dict.fromkeys(list(e.get("skills") or []) + list(u.get("skills") or [])))
            if u.get("dir_id") and not any(f.get("dir_id") == u["dir_id"] for f in e.get("folders") or []):
                e["folders"] = (e.get("folders") or []) + [{"dir_id": u["dir_id"], "name": u.get("folder") or ""}]
            text = str(sample or "").strip()[:SAMPLE_CHARS]
            if text and all(s.get("text") != text for s in e.get("samples") or []):
                e["samples"] = ((e.get("samples") or []) + [{"text": text, "session_id": u["session_id"],
                                                             "step": u["step"], "title": u["title"], "at": at,
                                                             "seq": seq}])[-MAX_SAMPLES:]
            return copy.deepcopy(e)
        return self._update(change)

    def mark_sent_back(self, session_id: str, run: int | None) -> int:
        """The plan of `session_id` was revised after run `run`: mark those uses sent back -> how many changed."""
        def change(data, seq):
            n = 0
            for e in data["roles"].values():
                for u in e.get("uses") or []:
                    if u.get("session_id") == session_id and u.get("run") == run and not u.get("sent_back"):
                        u["sent_back"] = True
                        n += 1
            return n
        if not any(u.get("session_id") == session_id and u.get("run") == run and not u.get("sent_back")
                   for e in self._read()["roles"].values() for u in e.get("uses") or []):
            return 0                                   # nothing to mark: no write
        return self._update(change)

    def dismiss(self, name: str) -> dict:
        def change(data, seq):
            e = self._need(data, name)
            e["dismissed"] = True
            return copy.deepcopy(e)
        return self._update(change)

    def merge(self, source: str, into: str) -> dict:
        """Fold entry `source` into `into` (uses, samples, skills, folders; counts add up) -> the merged entry."""
        if str(source) == str(into):
            raise TallyError("choose two different roles to merge")

        def change(data, seq):
            src, dst = self._need(data, source), self._need(data, into)
            dst["uses"] = sorted((dst.get("uses") or []) + (src.get("uses") or []),
                                 key=lambda u: int(u.get("seq") or 0))[-MAX_USES:]
            dst["uses_total"] = int(dst.get("uses_total") or 0) + int(src.get("uses_total") or 0)
            samples = sorted((dst.get("samples") or []) + (src.get("samples") or []), key=lambda s: int(s.get("seq") or 0))
            seen, kept = set(), []
            for s in reversed(samples):
                if s.get("text") not in seen:
                    seen.add(s.get("text"))
                    kept.append(s)
            dst["samples"] = list(reversed(kept[:MAX_SAMPLES]))
            dst["skills"] = list(dict.fromkeys(list(dst.get("skills") or []) + list(src.get("skills") or [])))
            have = {f.get("dir_id") for f in dst.get("folders") or []}
            dst["folders"] = (dst.get("folders") or []) + [f for f in src.get("folders") or [] if f.get("dir_id") not in have]
            dst["first_used"] = min(str(dst.get("first_used") or ""), str(src.get("first_used") or "")) or dst.get("first_used")
            if int(src.get("last_seq") or 0) > int(dst.get("last_seq") or 0):
                dst["last_used"], dst["last_seq"] = src.get("last_used"), src.get("last_seq")
            del data["roles"][src["name"]]
            return copy.deepcopy(dst)
        return self._update(change)

    def remove(self, name: str) -> bool:
        """Drop an entry (the role was defined as an agent) -> whether it existed."""
        if self.get(name) is None:
            return False

        def change(data, seq):
            return data["roles"].pop(str(name), None) is not None
        return self._update(change)

    def set_decision(self, name: str, decision: str, *, reviewer_verdict: str | None = None,
                     case_file: str | None = None) -> dict:
        """The user's decision after a review (it may differ from the reviewer's verdict)."""
        if decision not in DECISIONS:
            raise TallyError(f"decision must be one of {', '.join(DECISIONS)}")

        def change(data, seq):
            e = self._need(data, name)
            e["verdict"] = {"decision": decision, "reviewer_verdict": reviewer_verdict, "at": now_iso(), "seq": seq,
                            "uses_at": int(e.get("uses_total") or 0), "case_file": case_file}
            e["dismissed"] = False
            return copy.deepcopy(e)
        return self._update(change)

    def set_review(self, name: str, review: dict) -> dict | None:
        """Remember the latest review of a role (verdict, case file, cost); None when the entry is gone."""
        if self.get(name) is None:
            return None

        def change(data, seq):
            e = data["roles"].get(str(name))
            if e is None:
                return None
            e["last_review"] = dict(review, at=now_iso())
            return copy.deepcopy(e)
        return self._update(change)

    @staticmethod
    def _need(data: dict, name: str) -> dict:
        e = data["roles"].get(str(name or ""))
        if e is None:
            raise TallyError(f"no role '{name}' in the tally")
        return e

    # ---------------------------------------------------------------- the UI list
    def list_event(self, reviewing: dict | None = None) -> dict:
        """roles_list: every entry with its visibility (the page shows the visible ones under "Used but not
        defined"); reviewing = {role: review_id} of reviews in progress."""
        reviewing = reviewing or {}
        out = []
        for e in self.entries():
            vis = visibility(e)
            out.append({"name": e["name"], "base_agent": e.get("base_agent"), "purpose": e.get("purpose"),
                        "skills": list(e.get("skills") or []), "folders": list(e.get("folders") or []),
                        "uses_total": int(e.get("uses_total") or 0), "first_used": e.get("first_used"),
                        "last_used": e.get("last_used"),
                        "samples": [{k: s.get(k) for k in ("text", "session_id", "step", "title", "at")}
                                    for s in e.get("samples") or []],
                        "verdict": ({k: e["verdict"].get(k) for k in ("decision", "reviewer_verdict", "at",
                                                                     "uses_at", "case_file")}
                                    if e.get("verdict") else None),
                        "dismissed": bool(e.get("dismissed")), "last_review": e.get("last_review"),
                        "uses": [{k: v for k, v in u.items() if k not in ("seq", "project", "extra_projects")}
                                 for u in reversed(e.get("uses") or [])],
                        "problems": sum(1 for u in e.get("uses") or [] if is_problem(u)),
                        **vis, "reviewing": e["name"] in reviewing, "review_id": reviewing.get(e["name"])})
        return {"type": "roles_list", "threshold": THRESHOLD, "resurface_uses": RESURFACE_USES, "entries": out}
