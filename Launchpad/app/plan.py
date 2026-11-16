"""plan.md: render, parse and validate (plain Python; a plan is checked before it is saved).

Format = YAML header block + markdown body:

    ---
    plan: <name>
    status: draft | approved
    date: "YYYY-MM-DD"
    session: "<session id>"
    steps:                                                   (one line per step)
    - {n: 1, title: "...", after: [], status: "todo"}
    - {n: 2, title: "...", after: [1], status: "todo", agent: "copy-reviewer", skills: ["sql-style"]}   (both optional)
    ---
    # <name>
    ## Goal
    ## Steps
    ### Step 1: <title>
    <details>
    Done when: <criteria>

- write_plan gives structured fields -> render() builds the text -> validate() must return [] before saving
- The header doubles as the run scoreboard: code updates step status as the run goes (set_status())
- agent (optional, per step): the agent name that takes the step (a folder agent from the registry, app/agents/crew.py);
  absent = the Builder. Only written when set, so plans without agents look exactly as before
- skills (optional, per step): skill names the step's worker gets on top of its own allowlist (app/skills.py); only
  written when set. Older plans' `skill: <name or null>` is read as skills [<name>] / []
"""
from __future__ import annotations

import datetime as dt
import json
import re

import yaml

PLAN_STATUSES = ("draft", "approved")
STEP_STATUSES = ("todo", "in_progress", "blocked", "done", "failed")
MAX_STEPS = 20
AGENT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_SKILL_NAME = 80


def _skills_of(s: dict) -> list[str]:
    """A header step's skill names: `skills` (list), else the older single `skill` (string or null)."""
    v = s.get("skills")
    if v is None:
        v = [s["skill"]] if isinstance(s.get("skill"), str) and s["skill"].strip() else []
    return [str(x).strip() for x in v] if isinstance(v, list) else v


def clean_skills(v) -> list[str]:
    """write_plan / edit_plan skills -> list of names (a single string counts as one name)."""
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        raise PlanError("skills must be a list of skill names")
    return list(dict.fromkeys(str(x).strip() for x in v if str(x).strip()))


class PlanError(ValueError):
    """The plan is malformed; message lists every problem."""


def _dump_header(meta: dict) -> str:
    """Header block body: one line per key, one line per step (JSON values are valid YAML)."""
    out = []
    for k, v in meta.items():
        if k == "steps":
            out.append("steps:")
            for s in v or []:
                out.append("- {" + ", ".join(f"{sk}: {json.dumps(sv, ensure_ascii=False, default=str)}"
                                             for sk, sv in s.items()) + "}")
        else:
            out.append(f"{k}: {json.dumps(v, ensure_ascii=False, default=str)}")
    return "\n".join(out)


def split(text: str) -> tuple[dict, str]:
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        raise PlanError("plan.md must start with a '---' header block")
    lines = text.split("\n")
    try:
        end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---")
    except StopIteration:
        raise PlanError("header block opened with '---' but never closed") from None
    try:
        meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as e:
        raise PlanError(f"bad YAML header: {e}") from None
    if not isinstance(meta, dict):
        raise PlanError("header must be key: value pairs")
    return meta, "\n".join(lines[end + 1:])


def validate(text: str) -> list[str]:
    """Problems with a plan.md text; [] = valid."""
    try:
        meta, body = split(text)
    except PlanError as e:
        return [str(e)]
    problems = []
    for key in ("plan", "status", "date", "session", "steps"):
        if not meta.get(key):
            problems.append(f"header: '{key}' missing")
    if meta.get("status") and meta["status"] not in PLAN_STATUSES:
        problems.append(f"header: status must be one of {PLAN_STATUSES}")
    steps = meta.get("steps") or []
    if not isinstance(steps, list):
        return problems + ["header: steps must be a list"]
    if len(steps) > MAX_STEPS:
        problems.append(f"too many steps ({len(steps)}; max {MAX_STEPS})")
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            problems.append(f"step {i}: must be a mapping")
            continue
        if s.get("n") != i:
            problems.append(f"step {i}: n must be {i} (steps are numbered 1, 2, 3 ...)")
        if not str(s.get("title") or "").strip():
            problems.append(f"step {i}: title missing")
        if s.get("status", "todo") not in STEP_STATUSES:
            problems.append(f"step {i}: status must be one of {STEP_STATUSES}")
        after = s.get("after") or []
        if not isinstance(after, list) or any(not isinstance(a, int) or not 1 <= a < i for a in after):
            problems.append(f"step {i}: after must list earlier step numbers")
        agent = s.get("agent")
        if agent is not None and (not isinstance(agent, str) or not AGENT_NAME.match(agent)):
            problems.append(f"step {i}: agent must be an agent name (lowercase letters, digits and dashes)")
        skills = _skills_of(s)
        if not isinstance(skills, list) or any(not x or len(x) > MAX_SKILL_NAME or "\n" in x for x in skills):
            problems.append(f"step {i}: skills must be a list of skill names")
        if not re.search(rf"^### Step {i}:", body, re.M):
            problems.append(f"step {i}: body has no '### Step {i}:' section")
    return problems


def parse(text: str) -> dict:
    """-> {name, status, date, session, steps:[{n, title, skills, after, status, agent}], body}; PlanError if
    invalid. agent = None when the step names none (the Builder); skills = [] when it names none."""
    problems = validate(text)
    if problems:
        raise PlanError("; ".join(problems))
    meta, body = split(text)
    steps = [{"n": s["n"], "title": str(s["title"]).strip(), "skills": _skills_of(s),
              "after": list(s.get("after") or []), "status": s.get("status", "todo"),
              "agent": s.get("agent") or None} for s in meta["steps"]]
    return {"name": str(meta["plan"]), "status": meta["status"], "date": str(meta["date"]),
            "session": str(meta["session"]), "steps": steps, "body": body}


def step_text(text: str, n: int) -> str:
    """The '### Step n:' section of the body (up to the next step heading)."""
    _, body = split(text)
    m = re.search(rf"^### Step {n}:.*?(?=^### Step \d+:|\Z)", body, re.M | re.S)
    return m.group(0).strip() if m else ""


def render(*, name: str, goal: str, steps: list[dict], session: str, status: str = "draft",
           date: str | None = None) -> str:
    """steps: [{title, details, done_when, skills?, after?, agent?}] -> plan.md text (not yet validated)."""
    header = {
        "plan": name.strip(),
        "status": status,
        "date": date or dt.date.today().isoformat(),
        "session": session,
        "steps": [_header_step(i, s) for i, s in enumerate(steps, 1)],
    }
    out = ["---", _dump_header(header), "---",
           f"# {name.strip()}", "", "## Goal", goal.strip(), "", "## Steps", ""]
    for i, s in enumerate(steps, 1):
        out += [f"### Step {i}: {str(s.get('title', '')).strip()}", str(s.get("details", "")).strip(), ""]
        if str(s.get("done_when", "")).strip():
            out += [f"Done when: {str(s['done_when']).strip()}", ""]
    return "\n".join(out).rstrip() + "\n"


def _header_step(i: int, s: dict) -> dict:
    out = {"n": i, "title": str(s.get("title", "")).strip(),
           "after": [int(a) for a in (s.get("after") or [])], "status": s.get("status", "todo")}
    agent = str(s.get("agent") or "").strip()
    if agent:
        out["agent"] = agent
    skills = clean_skills(s.get("skills") if s.get("skills") is not None else s.get("skill"))
    if skills:
        out["skills"] = skills
    return out


def set_status(text: str, *, plan_status: str | None = None, step: int | None = None,
               step_status: str | None = None) -> str:
    """Rewrite the header with a new plan status and/or one step's status; body untouched."""
    meta, body = split(text)
    if plan_status:
        meta["status"] = plan_status
    if step is not None and step_status:
        for s in meta.get("steps") or []:
            if s.get("n") == step:
                s["status"] = step_status
    return f"---\n{_dump_header(meta)}\n---\n{body}"


# --------------------------------------------------------------------------- targeted edits (edit_plan)
EDIT_OPS = ("replace", "rename", "set_goal", "set_step", "add_step", "remove_step", "move_step")


def to_fields(text: str) -> dict:
    """plan.md -> {name, goal, steps:[{title, details, done_when, skills, after, agent}]} (the inverse of render)."""
    p = parse(text)
    body = p["body"]
    m = re.search(r"^## Goal\s*\n(.*?)(?=^## Steps|\Z)", body, re.M | re.S)
    goal = m.group(1).strip() if m else ""
    steps = []
    for s in p["steps"]:
        sec = step_text(text, s["n"]).split("\n", 1)
        rest = sec[1] if len(sec) > 1 else ""
        done = re.search(r"^Done when:\s*(.*)$", rest, re.M)
        details = (rest[:done.start()] + rest[done.end():]) if done else rest
        steps.append({"title": s["title"], "details": details.strip(),
                      "done_when": done.group(1).strip() if done else "",
                      "skills": list(s.get("skills") or []), "after": list(s["after"]), "agent": s.get("agent")})
    return {"name": p["name"], "goal": goal, "steps": steps}


def apply_edits(text: str, edits: list[dict], *, session: str) -> tuple[str, list[str]]:
    """Apply targeted edits in order -> (new plan text, one-line summary per edit).

    Step numbers in each edit refer to the plan as it is when that edit is applied (edits apply in order).
    Any bad edit, or a result that fails validate(), raises PlanError naming the problem; nothing is changed."""
    f = to_fields(text)
    steps = [dict(s, _id=i) for i, s in enumerate(f["steps"], 1)]       # stable ids keep dependencies right
    for s in steps:
        s["after"] = [steps[a - 1]["_id"] for a in s["after"]]
    next_id = len(steps) + 1
    done: list[str] = []

    def idx(n, what="step"):
        if not isinstance(n, int) or not 1 <= n <= len(steps):
            raise PlanError(f"{what} {n!r} does not exist (steps are 1-{len(steps)})")
        return n - 1

    def ids(after):
        if after is None:
            return None
        if not isinstance(after, list):
            raise PlanError("after must be a list of step numbers")
        return [steps[idx(a, "after step")]["_id"] for a in after]

    for i, e in enumerate(edits or [], 1):
        e = e or {}
        op = e.get("op")
        try:
            if op not in EDIT_OPS:
                raise PlanError(f"op must be one of {', '.join(EDIT_OPS)}")
            if op == "rename":
                if not str(e.get("name", "")).strip():
                    raise PlanError("give the new name")
                f["name"] = str(e["name"]).strip()
                done.append(f'renamed to "{f["name"]}"')
            elif op == "set_goal":
                if not str(e.get("goal", "")).strip():
                    raise PlanError("give the new goal")
                f["goal"] = str(e["goal"]).strip()
                done.append("goal rewritten")
            elif op == "replace":
                find, new = str(e.get("find", "")), str(e.get("replace", ""))
                if not find:
                    raise PlanError("give the exact text to find")
                spots = [("goal", f, "goal")] + [(f"step {k}", s, key) for k, s in enumerate(steps, 1)
                                                 for key in ("title", "details", "done_when")]
                total = sum(str(obj.get(key) or "").count(find) for _, obj, key in spots)
                if total != 1:
                    raise PlanError(f"the text to find occurs {total} times; it must occur exactly once "
                                    "(quote more of the passage)")
                where, obj, key = next(x for x in spots if find in str(x[1].get(x[2]) or ""))
                obj[key] = str(obj[key]).replace(find, new)
                done.append(f"edited {where}")
            elif op == "set_step":
                s = steps[idx(e.get("n"))]
                for key in ("title", "details", "done_when"):
                    if e.get(key) is not None:
                        s[key] = str(e[key]).strip()
                if e.get("agent") is not None:                      # "" = back to the Builder
                    s["agent"] = str(e["agent"]).strip() or None
                if e.get("skills") is not None:                     # [] = none
                    s["skills"] = clean_skills(e["skills"])
                if e.get("after") is not None:
                    s["after"] = ids(e["after"])
                done.append(f"changed step {e.get('n')}")
            elif op == "add_step":
                if not str(e.get("title", "")).strip() or not str(e.get("details", "")).strip():
                    raise PlanError("a new step needs title and details")
                pos = e.get("position") or len(steps) + 1
                if not isinstance(pos, int) or not 1 <= pos <= len(steps) + 1:
                    raise PlanError(f"position must be 1-{len(steps) + 1}")
                new = {"title": str(e["title"]).strip(), "details": str(e["details"]).strip(),
                       "done_when": str(e.get("done_when") or "").strip(), "skills": clean_skills(e.get("skills")),
                       "agent": str(e.get("agent") or "").strip() or None,
                       "after": ids(e.get("after")) or [], "_id": next_id}
                next_id += 1
                steps.insert(pos - 1, new)
                done.append(f'added step {pos} "{new["title"]}"')
            elif op == "remove_step":
                k = idx(e.get("n"))
                gone = steps[k]["_id"]
                users = [j for j, s in enumerate(steps, 1) if gone in s["after"] and j != k + 1]
                if users:
                    raise PlanError(f"step(s) {', '.join(map(str, users))} depend on step {k + 1}: change their "
                                    "after (set_step) first, or remove them too")
                title = steps.pop(k)["title"]
                done.append(f'removed step {k + 1} "{title}"')
            elif op == "move_step":
                k = idx(e.get("n"))
                to = e.get("to")
                if not isinstance(to, int) or not 1 <= to <= len(steps):
                    raise PlanError(f"to must be 1-{len(steps)}")
                steps.insert(to - 1, steps.pop(k))
                done.append(f"moved step {k + 1} to position {to}")
        except PlanError as err:
            raise PlanError(f"edit {i} ({op}): {err}. The draft was not changed.") from None
    pos_of = {s["_id"]: n for n, s in enumerate(steps, 1)}
    out_steps = [{"title": s["title"], "details": s["details"], "done_when": s["done_when"],
                  "skills": list(s.get("skills") or []), "agent": s.get("agent"),
                  "after": sorted(pos_of[a] for a in s["after"])} for s in steps]

    new_text = render(name=f["name"], goal=f["goal"], steps=out_steps, session=session)
    problems = validate(new_text)
    if problems:
        raise PlanError("the edits would leave the plan invalid: " + "; ".join(problems) + ". The draft was not "
                        "changed; fix the order or the dependencies (set_step with after) and try again.")
    return new_text, done
