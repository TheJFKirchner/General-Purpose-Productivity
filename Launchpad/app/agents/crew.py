"""Launchpad's agents: standard agent definition files + Launchpad-only tools handed over at load time.

- Files hold standard front matter only (usable in Claude Code / agentlib elsewhere, minus our tools)
- load(role, ...) = load_claude_agent(file) + Launchpad tools appended to the file's tool list
- Built-in definitions: app/agents/<folder>/agent.md (ROLES / HELPERS map role -> folder); the planner's promotion
  criteria: app/agents/planner/promotion.md
- Display names are plain (Planner, Explorer, Orchestrator, Builder, Visualizer, Claude Code); role keys and
  front-matter names stay as they were (astronaut = the Explorer, pilot = Claude Code, visual = the Visualizer)
- Purposes: planning | exploring | building | reviewing (built-ins: BUILTIN_PURPOSE; folder agents: a `purpose:`
  front-matter field, default building)
- Registry = the six built-ins + the connected folder's `.claude/agents/*.md` (folder agents). Step workers (what a
  plan step may name) = the Builder + folder agents that are exploring / building / reviewing and load cleanly
- Folder agents run as step workers: exploring / reviewing are read-only (no write, edit or shell tools whatever
  the file lists); building ones get the Builder's gated tools, permission cards, guards and shell deny list
- crew_list event: Agent.describe() (agentlib) + display_name, role, purpose, uses, builtin; plus folder agents
"""
from __future__ import annotations

import re
from pathlib import Path

from agentlib import Agent, load_claude_agent
from agentlib.loaders import frontmatter

ROOT = Path(__file__).resolve().parents[2]      # the Launchpad folder
APP_ROOT = ROOT                    # where the app's editable files live (a temp copy in the fake demo)
AGENTS_DIR = ROOT / "app" / "agents"
AGENTS_REL = "app/agents"          # AGENTS_DIR relative to APP_ROOT (paths shown in the UI)
CRITERIA_REL = f"{AGENTS_REL}/planner/promotion.md"
DEFINITION = "agent.md"            # each built-in's definition file inside its folder


def use_app_root(root: Path) -> None:
    """Serve the agent files and the promotion criteria from `root` (same layout) instead of the real ones."""
    global APP_ROOT, AGENTS_DIR
    from .planner import planner
    APP_ROOT = Path(root).resolve()
    AGENTS_DIR = APP_ROOT / AGENTS_REL
    planner.CRITERIA_FILE = APP_ROOT / CRITERIA_REL


# role -> its folder under app/agents, its front-matter name (fallback when the file is broken), display name
ROLES = {
    "planner": {"folder": "planner", "name": "launchpad-planner", "display": "Planner"},
    "astronaut": {"folder": "explorer", "name": "launchpad-astronaut", "display": "Explorer"},
    "orchestrator": {"folder": "orchestrator", "name": "launchpad-orchestrator", "display": "Orchestrator"},
    "builder": {"folder": "builder", "name": "launchpad-builder", "display": "Builder"},
    "pilot": {"folder": "claude_code", "name": "launchpad-pilot", "display": "Claude Code"},
    "visual": {"folder": "visualizer", "name": "launchpad-visual", "display": "Visualizer"},
}

# App helpers: loaded like the crew, editable in the File Explorer, but not crew cards and not in the registry
HELPERS = {
    "drafter": {"folder": "drafter", "name": "launchpad-drafter", "display": "Agent drafter"},
}


def definition_rel(role: str) -> str:
    """A built-in's definition path relative to the app root: 'app/agents/<folder>/agent.md'."""
    return f"{AGENTS_REL}/{(ROLES.get(role) or HELPERS[role])['folder']}/{DEFINITION}"


def editable_files(root: Path | None = None) -> dict[str, Path]:
    """The app's own editable files (every built-in definition + the promotion criteria): relative posix path ->
    absolute path under root (default APP_ROOT). The File Explorer's "app" root and the fake demo's copy use this."""
    base = Path(root) if root is not None else APP_ROOT
    agents = base / AGENTS_REL if root is not None else AGENTS_DIR
    out = {definition_rel(role): (agents / (ROLES.get(role) or HELPERS[role])["folder"] / DEFINITION).resolve()
           for role in list(ROLES) + list(HELPERS)}
    out[CRITERIA_REL] = (base / CRITERIA_REL).resolve()
    return out


PURPOSES = ("planning", "exploring", "building", "reviewing")
BUILTIN_PURPOSE = {"planner": "planning", "visual": "planning", "astronaut": "exploring",
                   "builder": "building", "orchestrator": "building", "pilot": "building"}
STEP_PURPOSES = ("exploring", "building", "reviewing")       # folder agents with these can take plan steps
READ_ONLY_PURPOSES = ("exploring", "reviewing")
DEFAULT_PURPOSE = "building"                                 # folder agent file without a purpose field
DEFAULT_STEP_AGENT = ROLES["builder"]["name"]                # launchpad-builder

# Tools the "new agent" form may offer (tick boxes)
TOOL_CHOICES = ["Read", "Grep", "Glob", "Write", "Edit", "Bash", "WebFetch", "WebSearch"]
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")             # file writes (the Builder checks the target)
WRITE_SHELL = WRITE_TOOLS + ("Bash",)      # never given to read-only agents; gated for building ones (every call checked)
BUILDER_GATED = ["Write", "Edit", "Bash"]                                  # the Builder's own gated tools
BUILDER_DEFAULT_TOOLS = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]  # building folder agent with no tools line
READ_DEFAULT_TOOLS = ["Read", "Grep", "Glob"]                              # read-only folder agent with no tools line
AGENT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

PROMPT_NOTES = {
    "lean": "Own prompt only (lean setup): this file's text and the tools listed; no project settings.",
    "lean+engine": ("Claude Code system prompt with this file's text appended; only the tools listed; no project "
                    "CLAUDE.md, settings, skills or connectors (lean)."),
    "project": ("Claude Code system prompt, all built-in tools, and the launch folder's own CLAUDE.md, user and "
                "project settings (permission rules), skills and hooks; permissions are Claude Code's own. "
                "None of Launchpad's builder guards."),
    "folder-building": ("Step worker from this folder: Claude Code system prompt with this file's text appended "
                        "(lean); the Builder's permission cards, write guard and shell deny list apply."),
    "folder-read-only": ("Step worker from this folder, read-only: Claude Code system prompt with this file's text "
                         "appended (lean); no write, edit or shell tools, whatever the file lists."),
}

# Agents that wait inside a tool call (explore, questions, permission cards): stop the CLI from moving a long
# tool call to the background (Claude Code auto-backgrounds MCP calls after ~2 min in some modes)
WAITING_ENV = {"CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS": "0"}


def shown_path(path) -> str | None:
    """Paths sent to the UI: relative to the Launchpad root (forward slashes) when inside it, else absolute."""
    if not path:
        return None
    p = Path(path).resolve()
    try:
        return p.relative_to(APP_ROOT).as_posix()
    except ValueError:
        return str(p)


def criteria_root(path, store=None) -> dict:
    """Where the File Explorer can open the criteria file: the app's own copy, a connected folder, or nowhere."""
    p = Path(path).resolve()
    if p == (APP_ROOT / CRITERIA_REL).resolve():
        return {"root": "app", "path": CRITERIA_REL, "editable": True}
    for d in (store.directories() if store else []):
        try:
            rel = p.relative_to(Path(d["path"]).resolve()).as_posix()
            return {"root": d["dir_id"], "path": rel, "editable": p.suffix.lower() == ".md"}
        except ValueError:
            continue
    return {"root": None, "path": None, "editable": False}


def display(role: str) -> str:
    """Plain display name; the page adds the step itself."""
    return (ROLES.get(role) or HELPERS[role])["display"]


def agent_file(role: str) -> Path:
    return AGENTS_DIR / (ROLES.get(role) or HELPERS[role])["folder"] / DEFINITION


def load(role: str, *, engine: str, project: Path, tools: list = (), model: str | None = None,
         setup: str = "lean", **overrides) -> Agent:
    """Load the role's file; append Launchpad's own tools (Tool objects) to the file's tool list."""
    agent = load_claude_agent(agent_file(role), engine=engine, setup=setup, cwd=project, model=model, **overrides)
    if tools:                                  # no Launchpad tools: keep the file's list (None = not specified)
        agent.tools = list(agent.tools or []) + list(tools)
    agent.resolved_tools()                     # fail now on a bad tool list
    return agent


# --------------------------------------------------------------------------- registry
def folder_display(name: str) -> str:
    """Display name of a folder agent: 'copy-reviewer' -> 'Copy reviewer'."""
    s = str(name).replace("-", " ").replace("_", " ").strip()
    return (s[:1].upper() + s[1:]) if s else str(name)


def builtin_name(role: str) -> str:
    """The agent name (front matter) of a built-in role; its registered name if the file has none."""
    fallback = (ROLES.get(role) or HELPERS[role])["name"]
    try:
        meta, _ = frontmatter.read(agent_file(role))
        return str(meta.get("name") or fallback)
    except Exception:  # noqa: BLE001 -- a broken built-in file still has a name for the registry
        return fallback


def builtin_names() -> set[str]:
    both = {**ROLES, **HELPERS}
    return {builtin_name(r) for r in both} | {r["name"] for r in both.values()}


def _builtin_entries() -> list[dict]:
    out = []
    for role, r in ROLES.items():
        path = agent_file(role)
        try:
            meta, _ = frontmatter.read(path)
        except Exception:  # noqa: BLE001
            meta = {}
        out.append({"name": str(meta.get("name") or r["name"]), "display_name": r["display"],
                    "purpose": BUILTIN_PURPOSE[role], "description": str(meta.get("description") or "").strip(),
                    "builtin": True, "role": role, "path": path, "rel": definition_rel(role),
                    "model": None if meta.get("model") in (None, "inherit") else str(meta.get("model")),
                    "problems": [], "step_worker": role == "builder"})
    return out


def folder_agents(folder: Path | None) -> list[dict]:
    """The connected folder's own agents (.claude/agents/*.md), built-in names skipped (e.g. Launchpad's own
    folder). Broken files are listed with their problems and never run."""
    from ..files import agent_problems
    if folder is None:
        return []
    d = Path(folder) / ".claude" / "agents"
    if not d.is_dir():
        return []
    taken = builtin_names()
    out, seen = [], set()
    for path in sorted(d.glob("*.md"), key=lambda p: p.name.lower()):
        if not path.is_file() or path.stem in taken:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            text, problems = "", [f"cannot read the file: {e}"]
        else:
            problems = agent_problems(text)
        try:
            meta, _ = frontmatter.parse(text, "agent file")
        except Exception:  # noqa: BLE001
            meta = {}
        name = str(meta.get("name") or path.stem).strip()
        if name in taken or name in seen:
            continue
        seen.add(name)
        purpose = str(meta.get("purpose") or DEFAULT_PURPOSE).strip().lower()
        if purpose not in PURPOSES:
            purpose = DEFAULT_PURPOSE
        out.append({"name": name, "display_name": folder_display(name), "purpose": purpose,
                    "description": str(meta.get("description") or "").strip(), "builtin": False, "role": None,
                    "path": path.resolve(), "rel": f".claude/agents/{path.name}",
                    "model": None if meta.get("model") in (None, "inherit") else str(meta.get("model")),
                    "problems": problems, "step_worker": not problems and purpose in STEP_PURPOSES})
    return out


def registry(folder: Path | None) -> list[dict]:
    """Every agent: the six built-ins, then the folder's own agents."""
    return _builtin_entries() + folder_agents(folder)


def step_agents(folder: Path | None) -> list[dict]:
    """Who can take a plan step: the Builder first, then the folder's step workers."""
    return [e for e in registry(folder) if e["step_worker"]]


def resolve_step_agent(name: str | None, folder: Path | None, reg: list[dict] | None = None) -> tuple[dict, str | None]:
    """A plan step's agent -> (registry entry that will run it, fallback reason or None). Missing, broken or
    non-step agents fall back to the Builder. reg: a registry already built (several steps at once)."""
    reg = reg if reg is not None else registry(folder)
    builder = next(e for e in reg if e["role"] == "builder")
    if not name or name == builder["name"]:
        return builder, None
    hit = next((e for e in reg if e["name"] == name), None)
    if hit is None:
        return builder, f"the plan named agent '{name}', which does not exist in this folder"
    if hit["problems"]:
        return builder, f"agent '{name}' has a broken file ({'; '.join(hit['problems'])[:200]})"
    if not hit["step_worker"]:
        return builder, f"agent '{name}' is a {hit['purpose']} agent, not a step worker"
    return hit, None


def step_fields(name: str | None, folder: Path | None, reg: list[dict] | None = None) -> dict:
    """agent / agent_display / agent_purpose (+ agent_fallback) for one plan step in UI events; display and purpose
    are those of the agent that will run it (the Builder, purpose building, on a fallback)."""
    entry, reason = resolve_step_agent(name, folder, reg)
    out = {"agent": name or None, "agent_display": entry["display_name"], "agent_purpose": entry["purpose"]}
    if reason:
        out["agent_fallback"] = True
    return out


def registry_note(folder: Path | None) -> str:
    """The step-agent list as the planner sees it (in its first message; again when it changes)."""
    lines = [f"- {e['name']} ({e['purpose']}): {_short(e['description'])}" for e in step_agents(folder)]
    return ("Step agents (a plan step may name one in `agent`; no agent = " + DEFAULT_STEP_AGENT + "):\n"
            + "\n".join(lines))


def _short(text: str, limit: int = 160) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- folder agents as step workers
def _base(rule: str) -> str:
    m = re.match(r"^\s*([A-Za-z_][\w]*)", str(rule))
    return m.group(1) if m else str(rule).strip()


def step_worker_tools(file_tools: list | None, purpose: str) -> tuple[list[str], list[str], list[str]]:
    """A folder agent's tool list as Launchpad runs it -> (tools, gated, disallowed).

    read-only (exploring / reviewing): every write / edit / shell tool removed and denied;
    building: write / edit / shell tools offered but gated (each call reaches the Builder's checks), pattern rules
    such as Bash(git push:*) reduced to the bare tool so nothing skips the deny list. ask_user is dropped (step
    workers ask through ask_question)."""
    read_only = purpose in READ_ONLY_PURPOSES
    if file_tools is None:
        file_tools = list(READ_DEFAULT_TOOLS if read_only else BUILDER_DEFAULT_TOOLS)
    tools: list[str] = []
    for t in file_tools:
        if not isinstance(t, str) or t == "ask_user":
            continue
        base = _base(t)
        if base in WRITE_SHELL:
            if read_only:
                continue
            t = base
        if t not in tools:
            tools.append(t)
    if read_only:
        return tools, [], list(WRITE_SHELL)
    return tools, [t for t in tools if t in WRITE_SHELL], []


def load_step_worker(entry: dict, *, engine: str, project: Path, tools: list, **overrides) -> Agent:
    """A folder agent as a step worker: its file + Launchpad's step tools, purpose-based permissions, the
    Builder's model when the file says inherit."""
    meta, _ = frontmatter.read(entry["path"])
    file_model = meta.get("model")
    model = builtin_model("builder") if file_model in (None, "inherit") else None
    agent = load_claude_agent(entry["path"], engine=engine, setup="lean", cwd=project, model=model,
                              include_ask_user=False, engine_prompt=True, **overrides)
    file_tools, gated, disallowed = step_worker_tools(agent.tools, entry["purpose"])
    agent.tools = file_tools + list(tools)
    agent.gated_tools = gated
    agent.disallowed_tools = list(dict.fromkeys(list(agent.disallowed_tools or []) + disallowed))
    agent.resolved_tools()
    return agent


def builtin_model(role: str) -> str | None:
    try:
        meta, _ = frontmatter.read(agent_file(role))
    except Exception:  # noqa: BLE001
        return None
    m = meta.get("model")
    return None if m in (None, "inherit") else str(m)


# --------------------------------------------------------------------------- crew_list
def crew_list(engine: str, project: Path, settings=None, store=None, *, folder: Path | None = None,
              dir_id: str | None = None) -> dict:
    """crew_list event: each agent as Launchpad runs it (tools built with a dummy context; nothing runs), then the
    folder's own agents. folder = the connected folder whose agents are included (default: project)."""
    from ..settings import Settings
    from .builder.builder import builder_tools
    from .claude_code.pilot import pilot_overrides
    from .explorer.astronaut import ASTRONAUT_SCHEMA
    from .orchestrator.run import orchestrator_tools
    from .planner.planner import planner_models, planner_tools, promotion_criteria
    settings = settings or Settings(project=project, engine=engine)
    folder = Path(folder or project)
    uses = store.uses() if store is not None else {}
    start, top = planner_models(settings)
    criteria, criteria_path = promotion_criteria(settings)
    built = {
        "planner": load("planner", engine=engine, project=project, model=start,
                        tools=planner_tools(None, criteria=criteria if start != top else None)),
        "astronaut": load("astronaut", engine=engine, project=project, output_schema=ASTRONAUT_SCHEMA),
        "orchestrator": load("orchestrator", engine=engine, project=project, tools=orchestrator_tools(None)),
        "builder": load("builder", engine=engine, project=project, tools=builder_tools(None),
                        gated_tools=list(BUILDER_GATED), engine_prompt=True),
        "pilot": load("pilot", engine=engine, project=project, **pilot_overrides(engine)),
        "visual": load("visual", engine=engine, project=project, save_conversation=False),
    }
    agents = []
    for role, a in built.items():
        d = a.describe()
        d["custom_tools"] = [{"name": t["name"], "description": t["description"]} for t in d["custom_tools"]]
        agents.append({"name": d["name"], "display_name": ROLES[role]["display"], "role": role,
                       "purpose": BUILTIN_PURPOSE[role], "uses": uses.get(d["name"], 0), "builtin": True,
                       "description": d["description"], "model": d["model"], "source_path": shown_path(d["source_path"]), "root": "app",
                       "path": shown_path(d["source_path"]), "editable": True,
                       "instructions": d["instructions"], "builtin_tools": d["builtin_tools"],
                       "custom_tools": d["custom_tools"], "mcp_servers": d["mcp_servers"],
                       "disallowed_tools": d["disallowed_tools"], "warnings": d["warnings"],
                       "gated_tools": list(a.gated_tools) if engine != "fake" or role != "pilot" else [],
                       "setup": a.setup, "engine_prompt": a.setup == "project" or a.engine_prompt,
                       "prompt_note": PROMPT_NOTES["lean+engine" if a.setup == "lean" and a.engine_prompt else a.setup]})
    for a in agents:
        if a["role"] == "planner":
            a["promotion"] = {"start_model": start, "target_model": top,
                              "window_turns": settings.promotion_window_turns if start != top else 0,
                              "criteria": criteria, "criteria_path": shown_path(criteria_path),
                              **criteria_root(criteria_path, store)}
    for e in folder_agents(folder):
        agents.append(_folder_card(e, engine=engine, folder=folder, dir_id=dir_id, uses=uses))
    return {"type": "crew_list", "dir_id": dir_id, "agents": agents, "tool_choices": list(TOOL_CHOICES)}


def _folder_card(e: dict, *, engine: str, folder: Path, dir_id: str | None, uses: dict) -> dict:
    """crew_list entry for a folder agent (same fields as the built-ins where they apply)."""
    from .builder.builder import builder_tools
    card = {"name": e["name"], "display_name": e["display_name"], "role": None, "purpose": e["purpose"],
            "uses": uses.get(e["name"], 0), "builtin": False, "description": e["description"], "model": e["model"],
            "source_path": str(e["path"]), "root": dir_id, "path": e["rel"], "editable": True,
            "instructions": "", "builtin_tools": [], "custom_tools": [], "mcp_servers": {}, "disallowed_tools": [],
            "warnings": list(e["problems"]), "gated_tools": [], "setup": "lean", "engine_prompt": True,
            "prompt_note": PROMPT_NOTES["folder-read-only" if e["purpose"] in READ_ONLY_PURPOSES else "folder-building"],
            "step_worker": e["step_worker"]}
    if e["problems"]:
        try:
            card["instructions"] = frontmatter.parse(e["path"].read_text(encoding="utf-8"), "agent file")[1]
        except Exception:  # noqa: BLE001
            pass
        return card
    try:
        a = load_step_worker(e, engine=engine, project=folder, tools=builder_tools(None))
    except Exception as err:  # noqa: BLE001 -- a file the loader refuses: show why on the card
        card["warnings"].append(str(err))
        card["step_worker"] = False
        return card
    d = a.describe()
    card.update({"model": d["model"], "instructions": d["instructions"], "builtin_tools": d["builtin_tools"],
                 "custom_tools": [{"name": t["name"], "description": t["description"]} for t in d["custom_tools"]],
                 "mcp_servers": d["mcp_servers"], "disallowed_tools": d["disallowed_tools"],
                 "warnings": d["warnings"], "gated_tools": list(a.gated_tools)})
    return card
