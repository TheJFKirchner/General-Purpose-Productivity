"""File Explorer back end: browse connected directories and the app's own editable files; edit markdown by hand.

- Roots: a connected directory (dir_id) or "app" (whitelist: app/agents/<folder>/agent.md of every built-in incl.
  the agent drafter, and app/agents/planner/promotion.md). Every path is resolved (symlinks, "..") and must stay inside its root / be a whitelisted file
- Kinds: markdown (.md) | text | binary (NUL bytes or not UTF-8) | too_large (> MAX_BYTES); only markdown and
  text are sent; only markdown is editable
- Save: conflict-safe (base_version = hash of the content the page opened; changed on disk -> conflict with the
  current content); agent files (.claude/agents/*.md, app/agents/<folder>/agent.md) and plan files are validated first; the previous content
  is kept as a backup in <LAUNCHPAD_HOME>/backups/<root>/<path>/<timestamp>.md (outside projects and git)
- Agent files and the criteria apply to NEW sessions (agents load at session start)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path

from agentlib.loaders import frontmatter

from . import plan as plan_mod
from .agents import crew
from .agents.crew import PURPOSES
from .store import launchpad_home

MAX_BYTES = 1_000_000
MAX_ENTRIES = 2000
MODEL_ALIASES = {"opus", "sonnet", "haiku", "inherit"}
# agent definition files: a folder agent (.claude/agents/<name>.md) or a built-in (app/agents/<folder>/agent.md)
AGENT_FILE = re.compile(r"(^|/)\.claude/agents/[^/]+\.md$|^app/agents/[^/]+/agent\.md$")
_TOOL = re.compile(r"^(?:ask_user|mcp__[\w-]+(?:__[\w*-]+)?|[A-Z]\w*(?:\(.*\))?)$")


class FileError(Exception):
    def __init__(self, code: str, message: str, current: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.current = code, message, current


def version_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def app_whitelist(settings=None) -> dict[str, Path]:
    """Relative path (posix) -> absolute path of the app's own editable files."""
    return crew.editable_files()


def kind_of(path: Path, size: int) -> str:
    if size > MAX_BYTES:
        return "too_large"
    try:
        with path.open("rb") as f:
            head = f.read(4096)
    except OSError:
        return "binary"
    if b"\x00" in head:
        return "binary"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        if e.start < len(head) - 4:              # not just a multi-byte character cut at the 4 KB boundary
            return "binary"
    return "markdown" if path.suffix.lower() == ".md" else "text"


class Files:
    def __init__(self, hub):
        self.hub = hub

    # ---------------------------------------------------------------- roots and paths
    def _dir_root(self, root: str) -> Path:
        entry = self.hub.store.get(root)
        if entry is None:
            raise FileError("not_allowed", "that folder is not connected")
        return Path(entry["path"]).resolve()

    def resolve(self, root: str, path: str) -> tuple[Path, str]:
        """(absolute path, relative posix path) inside the root, else FileError not_allowed."""
        rel = str(path or "").replace("\\", "/").strip("/")
        if root == "app":
            wl = app_whitelist()
            if rel in wl:
                return wl[rel], rel
            if rel == "" or any(k.startswith(rel + "/") for k in wl):
                return (crew.APP_ROOT / rel).resolve(), rel    # a virtual folder on the way to whitelisted files
            raise FileError("not_allowed", "only Launchpad's own editable files can be opened here")
        base = self._dir_root(root)
        target = (base / rel).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise FileError("not_allowed", "that path is outside the connected folder") from None
        return target, rel

    def _editable(self, root: str, rel: str, path: Path) -> bool:
        return path.suffix.lower() == ".md" and (root != "app" or rel in app_whitelist())

    @staticmethod
    def _applies(root: str, rel: str) -> str:
        if root == "app" or AGENT_FILE.search(rel):
            return "new_sessions"
        return "now"

    @staticmethod
    def _validates_as(rel: str, text: str | None) -> str | None:
        if AGENT_FILE.search(rel):
            return "agent"
        if rel.endswith("plan.md") and (text or "").lstrip().startswith("---") and re.search(r"(?m)^plan:", text or ""):
            return "plan"
        return None

    # ---------------------------------------------------------------- list / read
    def list_dir(self, root: str, path: str) -> dict:
        target, rel = self.resolve(root, path)
        entries = []
        if root == "app":
            wl = app_whitelist()
            prefix = rel + "/" if rel else ""
            names: dict[str, str] = {}
            for k in wl:
                if k.startswith(prefix):
                    head = k[len(prefix):].split("/", 1)
                    names[head[0]] = "dir" if len(head) > 1 else "file"
            for name, typ in sorted(names.items(), key=lambda x: (x[1] != "dir", x[0].lower())):
                p = (crew.APP_ROOT / prefix / name).resolve()
                entries.append(self._entry(root, prefix + name, p, typ))
        else:
            if not target.is_dir():
                raise FileError("not_found", "no such folder")
            base = self._dir_root(root)
            try:
                kids = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except OSError as e:
                raise FileError("not_allowed", f"cannot list that folder: {e}") from None
            for p in kids[:MAX_ENTRIES]:
                try:
                    p.resolve().relative_to(base)              # skip links that lead outside the folder
                except (ValueError, OSError):
                    continue
                child = f"{rel}/{p.name}" if rel else p.name
                entries.append(self._entry(root, child, p, "dir" if p.is_dir() else "file"))
        return {"type": "dir_listing", "root": root, "path": rel, "entries": entries}

    def _entry(self, root: str, rel: str, p: Path, typ: str) -> dict:
        try:
            st = p.stat()
        except OSError:
            return {"name": p.name, "type": typ, "size": 0, "mtime": None, "kind": None, "editable": False}
        e = {"name": p.name, "type": typ, "size": st.st_size if typ == "file" else 0,
             "mtime": dt.datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")}
        if typ == "file":
            e["kind"] = kind_of(p, st.st_size)
            e["editable"] = e["kind"] == "markdown" and self._editable(root, rel, p)
        else:
            e["kind"], e["editable"] = None, False
        return e

    def read(self, root: str, path: str) -> dict:
        target, rel = self.resolve(root, path)
        if not target.is_file():
            raise FileError("not_found", "no such file")
        st = target.stat()
        kind = kind_of(target, st.st_size)
        base = {"type": "file_content", "root": root, "path": rel, "kind": kind, "size": st.st_size,
                "mtime": dt.datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")}
        if kind in ("binary", "too_large"):
            raise FileError(kind, "binary file: not shown" if kind == "binary"
                            else f"larger than {MAX_BYTES // 1000} KB: not shown")
        data = target.read_bytes()
        text = data.decode("utf-8", errors="replace")
        editable = kind == "markdown" and self._editable(root, rel, target)
        return {**base, "text": text, "version": version_of(data), "editable": editable,
                "applies": self._applies(root, rel) if editable else None,
                "validates_as": self._validates_as(rel, text) if editable else None}

    # ---------------------------------------------------------------- save / backups
    def save(self, root: str, path: str, text: str, base_version: str | None) -> dict:
        target, rel = self.resolve(root, path)
        if target.suffix.lower() != ".md" or not self._editable(root, rel, target):
            raise FileError("not_allowed", "only markdown (.md) files can be edited; this one is view-only")
        text = str(text or "")
        if target.exists() and target.is_file():
            text = keep_line_endings(text, target.read_bytes())
        data = text.encode("utf-8")
        if len(data) > MAX_BYTES:
            raise FileError("too_large", f"larger than {MAX_BYTES // 1000} KB")
        if target.exists():
            current = target.read_bytes()
            if version_of(current) != (base_version or ""):
                raise FileError("conflict", "the file changed on disk since it was opened",
                                current={"text": current.decode("utf-8", errors="replace"), "version": version_of(current)})
        elif base_version:
            raise FileError("conflict", "the file was deleted on disk since it was opened", current={"text": "", "version": None})
        self.validate(rel, text)
        backup_id = self._backup(root, rel, target) if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"type": "file_saved", "root": root, "path": rel, "version": version_of(data), "backup_id": backup_id,
                "applies": self._applies(root, rel)}

    def validate(self, rel: str, text: str) -> None:
        kind = self._validates_as(rel, text) or (
            "plan" if rel.endswith("plan.md") and text.lstrip().startswith("---") else None)
        if kind == "agent":
            problems = agent_problems(text)
        elif kind == "plan":
            problems = plan_mod.validate(text)
        else:
            return
        if problems:
            raise FileError("invalid", f"not saved: {'; '.join(problems)}")

    def _backup_dir(self, root: str, rel: str) -> Path:
        safe = re.sub(r"[^\w.-]+", "_", rel)
        return launchpad_home() / "backups" / root / safe

    def _backup(self, root: str, rel: str, target: Path) -> str:
        d = self._backup_dir(root, rel)
        d.mkdir(parents=True, exist_ok=True)
        bid = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        (d / f"{bid}.md").write_bytes(target.read_bytes())
        return bid

    def backups(self, root: str, path: str) -> dict:
        _, rel = self.resolve(root, path)
        d = self._backup_dir(root, rel)
        items = []
        if d.is_dir():
            for p in sorted(d.glob("*.md"), reverse=True):
                bid = p.stem
                try:
                    saved = dt.datetime.strptime(bid, "%Y%m%d-%H%M%S-%f").astimezone().isoformat(timespec="seconds")
                except ValueError:
                    continue
                items.append({"backup_id": bid, "saved_at": saved, "size": p.stat().st_size})
        return {"type": "backups", "root": root, "path": rel, "items": items}

    def restore(self, root: str, path: str, backup_id: str) -> dict:
        target, rel = self.resolve(root, path)
        if not re.fullmatch(r"\d{8}-\d{6}-\d{6}", str(backup_id or "")):
            raise FileError("not_found", "no such backup")
        src = self._backup_dir(root, rel) / f"{backup_id}.md"
        if not src.is_file():
            raise FileError("not_found", "no such backup")
        current = target.read_bytes() if target.exists() else b""
        return self.save(root, path, src.read_text(encoding="utf-8"), version_of(current) if target.exists() else None)


def keep_line_endings(text: str, current: bytes) -> str:
    """The browser sends LF; write the file back in its own style (CRLF if most of its lines end so).
    New files keep LF."""
    crlf = current.count(b"\r\n")
    lf = current.count(b"\n") - crlf
    norm = text.replace("\r\n", "\n")
    return norm.replace("\n", "\r\n") if crlf > lf else norm


def agent_problems(text: str) -> list[str]:
    """Problems with an agent definition file (standard front matter); [] = fine."""
    try:
        meta, body = frontmatter.parse(text, "agent file")
    except Exception as e:  # noqa: BLE001 -- AgentFileError or YAML trouble: report it plainly
        return [str(e)]
    problems = []
    if not text.lstrip().startswith("---"):
        problems.append("the file needs a front matter block between --- lines")
    for key in ("name", "description"):
        if not str(meta.get(key) or "").strip():
            problems.append(f"front matter: '{key}' missing")
    if meta.get("name") and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(meta["name"])):
        problems.append("name: lowercase letters, digits and dashes only")
    tools = meta.get("tools")
    if tools is not None:
        items = frontmatter.as_list(tools) or []
        bad = [t for t in items if not _TOOL.match(t)]
        if bad:
            problems.append(f"tools: not a tool name: {', '.join(bad)}")
    model = meta.get("model")
    if model is not None and not (str(model) in MODEL_ALIASES or re.fullmatch(r"claude-[\w.\[\]-]+", str(model))):
        problems.append(f"model: '{model}' is not opus, sonnet, haiku, inherit or a claude-... model id")
    purpose = meta.get("purpose")                  # Launchpad's own field (the CLI harnesses ignore it)
    if purpose is not None and str(purpose).strip().lower() not in PURPOSES:
        problems.append(f"purpose: '{purpose}' is not {', '.join(PURPOSES)}")
    return problems
