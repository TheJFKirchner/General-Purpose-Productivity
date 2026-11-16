"""Git repos panel back end: find the repos in the connected folders, read their status, commit and push.

- Git is a plain back-end utility here (subprocess with argument lists, never a shell); no agent, no agentlib
- Repos are detected in every connected folder: the folder itself when it holds `.git`, else repos up to two levels
  below it (skipping .git, node_modules, virtual environments, .launchpad; never descending into a repo). A repo
  reachable from two connected folders is listed once (under the first)
- Every request names a repo by an id this module issued in its own scan; file paths must lie inside that repo and be
  among its changed files; git runs with literal pathspecs, GIT_TERMINAL_PROMPT=0 and a timeout on every call
- Never: force push, pull, switch branch, reset, rewrite history. Push = `git push` to the branch's own upstream
- Remote URLs are reduced to host / owner / repo (credentials never leave this module); git's error text has any
  credentials in URLs removed and is trimmed
- All functions here block (they run git): the hub calls them with asyncio.to_thread
- Events: see the app/server.py header (git_repos, git_result)
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", ".launchpad"}
MAX_DEPTH = 2                      # repos up to this many levels below a connected folder
MAX_FILES = 300                    # changed files listed per repo (the rest only counted in `more`)
MAX_COUNT_BYTES = 20_000_000       # an untracked file larger than this is shown as binary (no line count)
T_READ, T_COMMIT, T_NET = 20, 60, 120     # seconds: status calls, add / commit, fetch / push
MAX_ERROR = 600
# git's "who are you" failure carries the OS user and machine name: replaced by a short message
IDENTITY_RE = re.compile(r"identity unknown|unable to auto-detect email address|empty ident name", re.I)
IDENTITY_MSG = "Git has no name and email set for commits. Set them once with git config, then try again."


class GitError(Exception):
    """A problem to show in the panel (message already trimmed and free of credentials)."""


class GitMissing(GitError):
    pass


def git_path() -> str | None:
    return shutil.which("git")


def available() -> bool:
    return git_path() is not None


def clean_text(text: str) -> str:
    """git's own text for the panel: credentials in URLs removed, trimmed."""
    t = re.sub(r"(://)[^/@\s]*@", r"\1", str(text or "")).strip()
    return t if len(t) <= MAX_ERROR else t[:MAX_ERROR].rstrip() + "..."


def _env() -> dict:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0",          # a missing credential fails instead of waiting for a prompt
                "GCM_INTERACTIVE": "never",          # Git Credential Manager: no dialog
                "GIT_OPTIONAL_LOCKS": "0",           # reading status must not take the index lock
                "GIT_LITERAL_PATHSPECS": "1"})       # a path is a path, never a pattern
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def _git(repo: Path, *args: str, timeout: float = T_READ) -> tuple[int, bytes, str]:
    """Run `git -C repo args` -> (return code, stdout bytes, cleaned stderr). A timeout is reported as code -1."""
    exe = git_path()
    if exe is None:
        raise GitMissing("Git is not installed (or not on the PATH).")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        p = subprocess.run([exe, "-C", str(repo), *args], capture_output=True, stdin=subprocess.DEVNULL,
                           timeout=timeout, env=_env(), creationflags=flags)
    except subprocess.TimeoutExpired:
        return -1, b"", f"git took longer than {int(timeout)} seconds and was stopped."
    except FileNotFoundError:
        raise GitMissing("Git is not installed (or not on the PATH).") from None
    return p.returncode, p.stdout, clean_text(p.stderr.decode("utf-8", "replace") or p.stdout.decode("utf-8", "replace"))


# ---------------------------------------------------------------- remote URL -> display parts
def parse_remote(name: str, url: str) -> dict:
    """{name, host, owner, repo} for display; no credentials, no local paths (a local remote shows its folder name)."""
    u = (url or "").strip()
    host, rest = "", u
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^/@]*@)?\[?([^/:\]]+)\]?(?::\d+)?/(.*)$", u, re.I)
    if m:
        host, rest = m.group(1), m.group(2)
    else:
        s = re.match(r"^(?:[^@/\\:]+@)?([^:/\\]{2,}):(?!\\)(.*)$", u)          # scp-like: git@host:owner/repo
        if s:
            host, rest = s.group(1), s.group(2)
    parts = [p for p in re.split(r"[\\/]", rest.split("?")[0]) if p]
    repo = re.sub(r"\.git$", "", parts[-1]) if parts else ""
    owner = "/".join(parts[:-1]) if host and len(parts) > 1 else ""
    return {"name": name, "host": host, "owner": owner, "repo": repo}


# ---------------------------------------------------------------- detection
def find_repos(root: Path) -> list[Path]:
    """Repos in a connected folder: itself if it holds .git, else repos up to MAX_DEPTH levels below it."""
    found: list[Path] = []

    def walk(d: Path, depth: int) -> None:
        if (d / ".git").exists():
            found.append(d)
            return                                   # never descend into a repo
        if depth >= MAX_DEPTH:
            return
        try:
            kids = sorted((e for e in os.scandir(d) if e.is_dir(follow_symlinks=False) and e.name not in SKIP_DIRS),
                          key=lambda e: e.name.lower())
        except OSError:
            return
        for e in kids:
            walk(Path(e.path), depth + 1)

    walk(root, 0)
    return found


def repo_id(path: Path) -> str:
    return "g" + hashlib.sha1(os.path.normcase(str(path)).encode("utf-8")).hexdigest()[:12]


def _inside(repo: Path, rel: str) -> bool:
    if not rel or "\0" in rel or Path(rel).is_absolute() or re.match(r"^[A-Za-z]:", rel):
        return False
    try:
        (repo / rel).resolve().relative_to(repo.resolve())
    except (ValueError, OSError):
        return False
    return True


# ---------------------------------------------------------------- reading one repo
def _count_untracked(repo: Path, rel: str) -> tuple[int, bool]:
    """(lines, binary) of an untracked file: all lines count as added."""
    f = repo / rel
    try:
        if f.is_symlink() or not f.is_file():
            return 0, False
        if f.stat().st_size > MAX_COUNT_BYTES:
            return 0, True
        lines, last, first = 0, b"", True
        with open(f, "rb") as fh:
            while chunk := fh.read(1 << 20):
                if first and b"\0" in chunk[:8192]:
                    return 0, True
                first = False
                lines += chunk.count(b"\n")
                last = chunk[-1:]
        return lines + (1 if last and last != b"\n" else 0), False
    except OSError:
        return 0, False


def _numstat(repo: Path) -> dict[str, tuple[int | None, int | None]]:
    """Tracked changes vs HEAD (staged and unstaged together): path -> (added, removed), (None, None) for binary."""
    unborn = _git(repo, "rev-parse", "--verify", "-q", "HEAD")[0] != 0
    args = ["diff", "--cached"] if unborn else ["diff", "HEAD"]
    rc, out, _ = _git(repo, *args, "--numstat", "-z", "--no-renames", "--no-ext-diff", "--no-textconv")
    stats: dict[str, tuple[int | None, int | None]] = {}
    if rc != 0:
        return stats
    for rec in out.decode("utf-8", "replace").split("\0"):
        m = re.match(r"^(\d+|-)\t(\d+|-)\t(.*)$", rec, re.S)
        if m:
            a, r, p = m.groups()
            stats[p] = (None, None) if a == "-" else (int(a), int(r))
    return stats


def _letter(xy: str) -> str:
    x, y = xy[0], xy[1]
    if x == "A":
        return "A"
    if "D" in (x, y):
        return "D"
    return "M"


def read_repo(path: Path, rid: str, dir_id: str, folder_name: str, rel: str) -> dict:
    """Status of one repo as the git_repos / git_result payload (never raises for a git problem: `error` is set)."""
    repo = {"repo_id": rid, "name": path.name, "dir_id": dir_id, "folder_name": folder_name, "rel": rel,
            "branch": None, "detached": False, "remote": None, "upstream": None, "linked": False, "ahead": 0,
            "behind": 0, "clean": True, "files": [], "more": 0, "added": 0, "removed": 0, "error": None}
    rc, out, err = _git(path, "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all", "--no-renames")
    if rc != 0:
        repo["error"] = err or "git status failed."
        return repo
    head, upstream, ab = None, None, None
    entries: list[tuple[str, str]] = []                      # (path, status letter)
    toks = out.decode("utf-8", "replace").split("\0")
    i = 0
    while i < len(toks):
        rec = toks[i]
        i += 1
        if not rec:
            continue
        if rec.startswith("# branch.head "):
            head = rec[len("# branch.head "):]
        elif rec.startswith("# branch.upstream "):
            upstream = rec[len("# branch.upstream "):]
        elif rec.startswith("# branch.ab "):
            m = re.match(r"# branch\.ab \+(\d+) -(\d+)", rec)
            if m:
                ab = (int(m.group(1)), int(m.group(2)))
        elif rec[0] == "1":
            f = rec.split(" ", 8)
            if len(f) == 9:
                entries.append((f[8], _letter(f[1])))
        elif rec[0] == "2":                                  # a rename (not asked for): path, then the old path
            f = rec.split(" ", 9)
            if len(f) == 10:
                entries.append((f[9], "M"))
            i += 1
        elif rec[0] == "u":
            f = rec.split(" ", 10)
            if len(f) == 11:
                entries.append((f[10], "U"))
        elif rec[0] == "?":
            entries.append((rec[2:], "?"))
    repo["detached"] = head == "(detached)"
    repo["branch"] = None if head in (None, "(detached)") else head
    repo["upstream"] = upstream
    if ab:
        repo["ahead"], repo["behind"] = ab
    remote = _remote_of(path, repo["branch"])
    if remote:
        repo["remote"] = remote
    repo["linked"] = bool(upstream and ab and remote)
    entries.sort(key=lambda e: e[0])
    repo["clean"] = not entries
    stats = _numstat(path) if entries else {}
    files = []
    for p, st in entries[:MAX_FILES]:
        if st == "?":
            added, binary = _count_untracked(path, p)
            files.append({"path": p, "status": "?", "added": 0 if binary else added, "removed": 0, "binary": binary})
        else:
            a, r = stats.get(p, (0, 0))
            files.append({"path": p, "status": st, "added": a or 0, "removed": r or 0, "binary": a is None})
    repo["files"] = files
    repo["more"] = max(0, len(entries) - MAX_FILES)
    repo["added"] = sum(f["added"] for f in files)
    repo["removed"] = sum(f["removed"] for f in files)
    return repo


def _remote_of(path: Path, branch: str | None) -> dict | None:
    """The remote the branch tracks (else origin, else the first one), as display parts."""
    rc, out, _ = _git(path, "remote")
    names = out.decode("utf-8", "replace").split() if rc == 0 else []
    if not names:
        return None
    name = None
    if branch:
        rc, out, _ = _git(path, "config", "--get", f"branch.{branch}.remote")
        tracked = out.decode("utf-8", "replace").strip() if rc == 0 else ""
        if tracked in names:
            name = tracked
    name = name or ("origin" if "origin" in names else names[0])
    rc, out, _ = _git(path, "remote", "get-url", name)
    return parse_remote(name, out.decode("utf-8", "replace").strip()) if rc == 0 else {"name": name, "host": "", "owner": "", "repo": ""}


# ---------------------------------------------------------------- the service
class GitRepos:
    """Repo registry (ids issued by the last scan) and the operations the hub exposes.
    `folders()` returns the connected folders as [{dir_id, path, name}]."""

    def __init__(self, folders: Callable[[], list[dict]]):
        self.folders = folders
        self.repos: dict[str, tuple[Path, str, str, str]] = {}     # id -> (path, dir_id, folder name, rel)

    def scan(self) -> dict:
        """git_repos event: every repo with its status."""
        if not available():
            self.repos = {}
            return {"type": "git_repos", "available": False, "repos": []}
        found: dict[str, tuple[Path, str, str, str]] = {}
        for d in self.folders():
            root = Path(d["path"])
            if not root.is_dir():
                continue
            root = root.resolve()
            for p in find_repos(root):
                rid = repo_id(p.resolve())
                if rid in found:
                    continue                                       # already listed under an earlier folder
                rel = p.relative_to(root).as_posix()
                found[rid] = (p.resolve(), d["dir_id"], d.get("name") or root.name, rel)
        self.repos = found
        with ThreadPoolExecutor(max_workers=4) as pool:
            repos = list(pool.map(lambda kv: read_repo(kv[1][0], kv[0], kv[1][1], kv[1][2], kv[1][3]), found.items()))
        return {"type": "git_repos", "available": True, "repos": repos}

    def _known(self, rid: str) -> tuple[Path, str, str, str]:
        if rid not in self.repos:
            raise GitError("That repo is not in the list any more. Press Rescan.")
        meta = self.repos[rid]
        if not meta[0].is_dir():
            raise GitError("That repo's folder is gone. Press Rescan.")
        return meta

    def _read(self, rid: str) -> dict:
        path, did, fname, rel = self._known(rid)
        return read_repo(path, rid, did, fname, rel)

    def run(self, op: str, msg: dict) -> dict:
        """One operation -> git_result event {repo_id, op, ok, committed, message, repo}. Never raises."""
        rid = str(msg.get("repo_id") or "")
        res = {"type": "git_result", "repo_id": rid, "op": op, "ok": False, "committed": False, "message": "", "repo": None}
        try:
            if not available():
                raise GitMissing("Git is not installed (or not on the PATH).")
            path, *_ = self._known(rid)
            if op == "refresh":
                res["ok"] = True
            elif op == "fetch":
                self._need_linked(rid)
                self._check(_git(path, "fetch", timeout=T_NET))
                res.update(ok=True, message="Checked the remote.")
            elif op == "push":
                res.update(ok=True, message=self._push(path, rid))
            elif op == "commit":
                res["committed"] = self._commit(path, rid, msg.get("message"), msg.get("paths"))
                res.update(ok=True, message="Committed.")
                if msg.get("push"):
                    try:
                        res["message"] = "Committed. " + self._push(path, rid)
                    except GitError as e:
                        res.update(ok=False, message=f"Committed, but the push failed: {e}")
            else:
                raise GitError("Unknown git operation.")
        except GitError as e:
            res.update(ok=False, message=clean_text(str(e)))
        try:
            res["repo"] = self._read(rid)
        except GitError:
            pass
        return res

    # --- helpers
    @staticmethod
    def _check(r: tuple[int, bytes, str]) -> None:
        if r[0] != 0:
            raise GitError(r[2] or "git failed.")

    def _need_linked(self, rid: str) -> dict:
        repo = self._read(rid)
        if repo["error"]:
            raise GitError(repo["error"])
        if not repo["linked"]:
            raise GitError("This repo is not linked to a remote branch, so there is nothing to check or push.")
        return repo

    def _push(self, path: Path, rid: str) -> str:
        repo = self._need_linked(rid)
        if not repo["ahead"]:
            return "Nothing to push."
        # push.default=upstream: the current branch to the branch it tracks, whatever it is called; never forced
        self._check(_git(path, "-c", "push.default=upstream", "push", timeout=T_NET))
        return "Pushed."

    def _commit(self, path: Path, rid: str, message, paths) -> bool:
        text = message.strip() if isinstance(message, str) else ""
        if not text:
            raise GitError("Type a commit message first.")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            raise GitError("Tick at least one file to commit.")
        if len(paths) > MAX_FILES:
            raise GitError("Too many files at once.")
        repo = self._read(rid)
        if repo["error"]:
            raise GitError(repo["error"])
        changed = {f["path"] for f in repo["files"]}
        chosen: list[str] = []
        for p in paths:
            if not _inside(path, p):
                raise GitError(f"Refused: {p!r} is not inside this repo.")
            if p not in changed:
                raise GitError(f"Refused: {p!r} is not a changed file of this repo (refresh and try again).")
            if p not in chosen:
                chosen.append(p)
        # the index as it is now (a tree object); a failed attempt puts it back exactly
        rc, out, _ = _git(path, "write-tree")
        before = out.decode("utf-8", "replace").strip() if rc == 0 else ""
        try:
            self._check(_git(path, "add", "-A", "--", *chosen, timeout=T_COMMIT))
            # a path-limited commit: anything else the user had staged stays staged, uncommitted
            r = _git(path, "commit", "-m", text, "--", *chosen, timeout=T_COMMIT)
            if r[0] != 0:
                if IDENTITY_RE.search(r[2]):
                    raise GitError(IDENTITY_MSG)
                raise GitError(r[2] or "git failed.")
        except GitError:
            if before:
                _git(path, "read-tree", before, timeout=T_COMMIT)
            raise
        return True
