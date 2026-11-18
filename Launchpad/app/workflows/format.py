"""The workflow file format: checking, discovery, the page's view of a workflow, and the file the form writes.

- One JSON file per workflow: <connected folder>/workflows/<slug>.json (the single definition; README.md here)
- check(raw, folder, agents) -> (clean definition, warnings). Warnings: {level: error|warning, code, message, stage,
  field}; any error = the workflow cannot run. Structural errors (STRUCTURAL codes) also refuse a form save;
  missing_file / unknown_agent are saved and shown on the card
- view(...) = the `workflow` object of the websocket contract (app/server.py header, "Workflows")
- agent_choices(folder) = what a stage may name: the Builder, the Explorer, then the folder's step-worker agents
- Paths in the file: relative to the workflow's connected folder, or absolute
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..agents import crew

WORKFLOWS_DIR = "workflows"
FORMAT_VERSION = 1
INPUT_KINDS = ("text", "date", "number", "file", "choice")
STAGE_KINDS = ("agent", "review")
CHECK_KINDS = ("tick", "answer")
MARKDOWN = (".md", ".markdown")
INPUT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
KNOWN_TOP = {"format", "name", "description", "output_folder", "unattended_default", "inputs", "files", "stages"}
KNOWN_STAGE = {"kind", "title", "agent", "instruction", "files", "checklist"}
KNOWN_INPUT = {"name", "label", "kind", "required", "default", "options", "help"}
STRUCTURAL = {"invalid_file", "invalid", "no_output_folder"}
STAGE_ROLES = ("builder", "astronaut")          # built-ins that can run a stage: the Builder, the Explorer
MAX_FILE_BYTES = 1_000_000


class WorkflowError(ValueError):
    """A request about a workflow was refused (the message goes to the page as `error`)."""


def slugify(name: str, limit: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:limit].strip("-")
    return s or "workflow"


def resolve(base: Path, raw: str) -> Path:
    """A path from the file (relative to the workflow's folder, or absolute) -> absolute path."""
    p = Path(str(raw).strip()).expanduser()
    return (p if p.is_absolute() else Path(base) / p).resolve()


def warning(level: str, code: str, message: str, stage: int | None = None, field: str | None = None) -> dict:
    return {"level": level, "code": code, "message": message, "stage": stage, "field": field}


# --------------------------------------------------------------------------- agents a stage may name
def agent_choices(folder: Path | None) -> list[dict]:
    """[{name, display_name, purpose, builtin}]: the Builder, the Explorer, then the folder's step workers."""
    out = []
    for e in crew.registry(folder):
        if (e["builtin"] and e["role"] in STAGE_ROLES) or (not e["builtin"] and e["step_worker"]):
            out.append({"name": e["name"], "display_name": e["display_name"], "purpose": e["purpose"],
                        "builtin": e["builtin"]})
    builtins = sorted((a for a in out if a["builtin"]), key=lambda a: a["name"] != crew.DEFAULT_STEP_AGENT)
    return builtins + [a for a in out if not a["builtin"]]


def stage_agent(name: str, folder: Path | None) -> dict | None:
    """The registry entry that runs an agent stage naming `name`, or None (not a stage agent here)."""
    allowed = {a["name"] for a in agent_choices(folder)}
    if name not in allowed:
        return None
    return next((e for e in crew.registry(folder) if e["name"] == name), None)


# --------------------------------------------------------------------------- checking
def _text(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _file_list(raw, where: str, stage: int | None, warns: list) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        warns.append(warning("error", "invalid", f"{where}files must be a list of paths", stage, "files"))
        return []
    out = []
    for item in raw:
        p = _text(item.get("path")) if isinstance(item, dict) else _text(item)
        if not p:
            warns.append(warning("error", "invalid", f"{where}files: every entry must be a path", stage, "files"))
            continue
        if Path(p).suffix.lower() not in MARKDOWN:
            warns.append(warning("error", "invalid", f"{where}attached file '{p}' is not a markdown file "
                                 "(.md or .markdown)", stage, "files"))
            continue
        if p not in out:
            out.append(p)
    return out


def _inputs(raw, warns: list) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        warns.append(warning("error", "invalid", "inputs must be a list", None, "inputs"))
        return []
    out, seen = [], set()
    for k, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            warns.append(warning("error", "invalid", f"input {k} must be an object", None, "inputs"))
            continue
        name = _text(item.get("name"))
        if not INPUT_NAME.match(name):
            warns.append(warning("error", "invalid", f"input {k}: name '{name}' must start with a letter and use "
                                 "only a-z, 0-9 and _", None, "inputs"))
            continue
        if name in seen:
            warns.append(warning("error", "invalid", f"input '{name}' is listed twice", None, "inputs"))
            continue
        seen.add(name)
        kind = _text(item.get("kind")) or "text"
        if kind not in INPUT_KINDS:
            warns.append(warning("error", "invalid", f"input '{name}': kind must be one of "
                                 f"{', '.join(INPUT_KINDS)}", None, "inputs"))
            kind = "text"
        options = [str(o).strip() for o in item.get("options") or [] if str(o).strip()] \
            if isinstance(item.get("options"), list) else []
        if kind == "choice" and not options:
            warns.append(warning("error", "invalid", f"input '{name}': a choice needs options", None, "inputs"))
        required = item.get("required", True)
        default = item.get("default", "")
        out.append({"name": name, "label": _text(item.get("label")) or name, "kind": kind,
                    "required": required if isinstance(required, bool) else True,
                    "default": "" if default is None else str(default), "options": options if kind == "choice" else [],
                    "help": _text(item.get("help"))})
        extra = set(item) - KNOWN_INPUT
        if extra:
            warns.append(warning("warning", "unknown_field", f"input '{name}': unknown field(s) "
                                 f"{', '.join(sorted(extra))} ignored", None, "inputs"))
    return out


def _checklist(raw, k: int, warns: list) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        warns.append(warning("error", "invalid", f"stage {k + 1}: checklist must be a list", k, "checklist"))
        return []
    out = []
    for item in raw:
        if isinstance(item, str):
            item = {"text": item}
        text = _text(item.get("text")) if isinstance(item, dict) else ""
        if not text:
            warns.append(warning("error", "invalid", f"stage {k + 1}: every checklist item needs text", k, "checklist"))
            continue
        kind = _text(item.get("kind")) or "tick"
        if kind not in CHECK_KINDS:
            warns.append(warning("error", "invalid", f"stage {k + 1}: checklist kind must be tick or answer", k,
                                 "checklist"))
            kind = "tick"
        out.append({"text": text, "kind": kind})
    return out


def _stages(raw, warns: list) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        warns.append(warning("error", "invalid", "a workflow needs at least one stage", None, "stages"))
        return []
    out = []
    for k, st in enumerate(raw):
        if not isinstance(st, dict):
            warns.append(warning("error", "invalid", f"stage {k + 1} must be an object", k, None))
            out.append({"kind": "agent", "title": f"Stage {k + 1}", "agent": "", "instruction": "", "files": []})
            continue
        kind = _text(st.get("kind"))
        title = _text(st.get("title"))
        if kind not in STAGE_KINDS:
            warns.append(warning("error", "invalid", f"stage {k + 1}: kind must be agent or review", k, "kind"))
            kind = "agent"
        if not title:
            warns.append(warning("error", "invalid", f"stage {k + 1} needs a title", k, "title"))
            title = f"Stage {k + 1}"
        if kind == "agent":
            agent, instruction = _text(st.get("agent")), _text(st.get("instruction"))
            if not agent:
                warns.append(warning("error", "invalid", f"stage {k + 1} ({title}): choose an agent", k, "agent"))
            if not instruction:
                warns.append(warning("error", "invalid", f"stage {k + 1} ({title}): write an instruction", k,
                                     "instruction"))
            out.append({"kind": kind, "title": title, "agent": agent, "instruction": instruction,
                        "files": _file_list(st.get("files"), f"stage {k + 1}: ", k, warns)})
        else:
            out.append({"kind": kind, "title": title, "checklist": _checklist(st.get("checklist"), k, warns)})
        extra = set(st) - KNOWN_STAGE
        if extra:
            warns.append(warning("warning", "unknown_field", f"stage {k + 1}: unknown field(s) "
                                 f"{', '.join(sorted(extra))} ignored", k, None))
    return out


def check(raw, folder: Path, agents: list[dict] | None = None) -> tuple[dict, list[dict]]:
    """A workflow definition (parsed JSON) -> (clean definition, warnings). agents = agent_choices(folder)."""
    warns: list[dict] = []
    if not isinstance(raw, dict):
        return ({"name": "", "description": "", "output_folder": "", "unattended_default": False, "inputs": [],
                 "files": [], "stages": []},
                [warning("error", "invalid_file", "the file must hold one JSON object")])
    name = _text(raw.get("name"))
    if not name:
        warns.append(warning("error", "invalid", "a workflow needs a name", None, "name"))
    output = _text(raw.get("output_folder"))
    if not output:
        warns.append(warning("error", "no_output_folder", "choose an output folder for the run records", None,
                             "output_folder"))
    ud = raw.get("unattended_default", False)
    if not isinstance(ud, bool):
        warns.append(warning("error", "invalid", "unattended_default must be true or false", None,
                             "unattended_default"))
        ud = False
    clean = {"name": name, "description": _text(raw.get("description")), "output_folder": output,
             "unattended_default": ud, "inputs": _inputs(raw.get("inputs"), warns),
             "files": _file_list(raw.get("files"), "", None, warns), "stages": _stages(raw.get("stages"), warns)}
    extra = set(raw) - KNOWN_TOP
    if extra:
        warns.append(warning("warning", "unknown_field", f"unknown field(s) {', '.join(sorted(extra))} ignored"))
    # links that must exist + agents that must be stage agents here
    agents = agent_choices(folder) if agents is None else agents
    names = {a["name"] for a in agents}
    for p in clean["files"]:
        if not resolve(folder, p).is_file():
            warns.append(warning("error", "missing_file", f"attached file not found: {p}", None, "files"))
    for k, st in enumerate(clean["stages"]):
        if st["kind"] != "agent":
            continue
        for p in st["files"]:
            if not resolve(folder, p).is_file():
                warns.append(warning("error", "missing_file", f"stage {k + 1} ({st['title']}): attached file not "
                                     f"found: {p}", k, "files"))
        if st["agent"] and st["agent"] not in names:
            warns.append(warning("error", "unknown_agent", f"stage {k + 1} ({st['title']}): agent '{st['agent']}' "
                                 "is not a stage agent in this folder", k, "agent"))
    return clean, warns


def structural(warns: list[dict]) -> list[str]:
    """The warnings that refuse a form save (missing files and unknown agents are saved)."""
    return [w["message"] for w in warns if w["level"] == "error" and w["code"] in STRUCTURAL]


def blocking(warns: list[dict]) -> list[str]:
    return [w["message"] for w in warns if w["level"] == "error"]


# --------------------------------------------------------------------------- the page's view
def _attached(folder: Path, p: str) -> dict:
    r = resolve(folder, p)
    return {"path": p, "resolved": str(r), "exists": r.is_file(), "name": r.name}


def view(clean: dict, warns: list[dict], *, dir_id: str, folder: Path, folder_name: str, slug: str,
         agents: list[dict]) -> dict:
    """The contract's `workflow` object (without running_run_id / last_run_id: the manager adds them)."""
    by_name = {a["name"]: a for a in agents}
    stages = []
    for k, st in enumerate(clean["stages"]):
        if st["kind"] == "agent":
            a = by_name.get(st["agent"])
            stages.append({"index": k, "kind": "agent", "title": st["title"], "agent": st["agent"],
                           "agent_display": a["display_name"] if a else st["agent"],
                           "agent_purpose": a["purpose"] if a else "other", "instruction": st["instruction"],
                           "files": [_attached(folder, p) for p in st["files"]]})
        else:
            stages.append({"index": k, "kind": "review", "title": st["title"],
                           "checklist": [dict(c) for c in st["checklist"]]})
    out = clean["output_folder"]
    return {"id": f"{dir_id}/{slug}", "slug": slug, "name": clean["name"] or slug,
            "description": clean["description"], "folder": dir_id, "folder_name": folder_name,
            "path": f"{WORKFLOWS_DIR}/{slug}.json", "output_folder": out,
            "output_path": str(resolve(folder, out)) if out else "",
            "unattended_default": clean["unattended_default"], "inputs": [dict(i) for i in clean["inputs"]],
            "files": [_attached(folder, p) for p in clean["files"]], "stages": stages, "warnings": warns,
            "can_run": not blocking(warns)}


def read_file(path: Path) -> tuple[object, list[dict]]:
    """-> (parsed JSON or None, warnings) for one workflow file."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None, [warning("error", "invalid_file", "the file is over 1 MB")]
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return None, [warning("error", "invalid_file", f"cannot read the file: {e}")]
    try:
        return json.loads(text), []
    except json.JSONDecodeError as e:
        return None, [warning("error", "invalid_file", f"not valid JSON: {e.msg} (line {e.lineno}, column {e.colno})")]


def load(path: Path, *, dir_id: str, folder: Path, folder_name: str, agents: list[dict]) -> tuple[dict, dict]:
    """One workflow file -> (view, clean definition)."""
    raw, warns = read_file(path)
    if warns:
        clean = {"name": "", "description": "", "output_folder": "", "unattended_default": False, "inputs": [],
                 "files": [], "stages": []}
    else:
        clean, warns = check(raw, folder, agents)
    return view(clean, warns, dir_id=dir_id, folder=folder, folder_name=folder_name, slug=path.stem,
                agents=agents), clean


def files_in(folder: Path) -> list[Path]:
    d = Path(folder) / WORKFLOWS_DIR
    if not d.is_dir():
        return []
    return sorted((p for p in d.glob("*.json") if p.is_file()), key=lambda p: p.name.lower())


def file_text(clean: dict) -> str:
    """What the form writes: the clean definition, keys in a fixed order, 2-space indent."""
    data = {"format": FORMAT_VERSION, "name": clean["name"], "description": clean["description"],
            "output_folder": clean["output_folder"], "unattended_default": clean["unattended_default"],
            "inputs": clean["inputs"], "files": clean["files"], "stages": clean["stages"]}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
