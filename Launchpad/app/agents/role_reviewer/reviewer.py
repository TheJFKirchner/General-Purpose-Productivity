"""The Role Reviewer (helper `role_reviewer`): an independent, read-only review of one undefined role from the tally.

- Started from the Crew tab (review_start {role}); one review at a time per role (a second request -> review_refused);
  a review that errors -> review_failed and the entry stays reviewable
- Agent: app/agents/role_reviewer/agent.md (Read, Grep, Glob only: no write, edit, shell or ask_user), structured
  output REVIEW_SCHEMA. Engine = the planner's chosen CLI (choices.planner_engine; --fake forces fake), model = the
  setting reviewer_model (default sonnet). Read / Grep / Glob are gated: every call is checked in code against the
  paths of its brief (the session folders of the role's uses, the skills' folders, the Builder's definition, each
  folder's .claude/agents); anything else is denied, so it cannot read the code the workers wrote
- Brief (first message, build_brief): every tally line; the session records to open only for the OPEN_RECENT most
  recent uses plus every failed / blocked / sent-back use (plan.md section, step report, that step's question files,
  assumptions, the run's report; activity.log only for the problem uses); a session folder that is gone is said so;
  the SKILL.md of each skill the role used; the Builder's definition and the defined agents of each folder used
- Questions: at most MAX_QUESTIONS, asked as question cards through Incoming.ask (session_id and chat_id null,
  review_id + role on the card; never auto-answered; after question_timeout_s the answer is NO_ANSWER); the answers go
  back in a second turn and the reviewer returns the final case
- Metered with the standard Meter (role "reviewer", session_id None): its cost counts in the app-wide total only
- Case: one section per test (finding, evidence, strength), verdict, reason, skill notes (keep) or a proposal (define),
  questions + answers, tokens and cost (costs.meter_usage). Saved as markdown in <home>/.launchpad/role-cases/
  <role>-<stamp>.md; the user's decision is written into it; on define + agent_create a copy goes to
  <folder>/.claude/agent-cases/<agent>.md (outside .claude/agents/, so no agent loader reads it)
- draft_context(): the case as extra context for the agent drafter on the define path
"""
from __future__ import annotations

import asyncio
import datetime as dt
import re
import secrets
from pathlib import Path

from agentlib import AgentError, PermissionDecision
from agentlib.events import Done, ToolCall

from ... import costs
from ... import skills as skills_mod
from ...activity import summarize
from ...meter import Meter
from ...sessionfiles import ROOT_NAME, inside, one_line
from ...tally import is_problem, now_iso
from .. import crew
from ..folder_agents import ADDABLE_PURPOSES
from ..planner import choices

ROLE = "role_reviewer"
OPEN_RECENT = 5                       # session records opened for the most recent uses (plus every problem use)
MAX_QUESTIONS = 3
TURN_TIMEOUT_S = 900
READ_TOOLS = ["Read", "Grep", "Glob"]
CASE_COPY_DIR = ".claude/agent-cases"          # beside .claude/agents/, never inside it
NO_ANSWER = "No answer (the question timed out)"
TESTS = (("value", "Clear value"), ("logic", "Logic beyond the skill"), ("history", "Clear usage history"),
         ("fixes", "Mistakes or issues it would fix"), ("independent", "Independent view: is a subagent the right fix?"))
STRENGTHS = ("none", "weak", "moderate", "strong")
VERDICTS = ("define", "keep", "not_yet")
VERDICT_LABELS = {"define": "Define an agent", "keep": "Keep as skill plus Builder", "not_yet": "Not yet"}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "tests": {"type": "array", "minItems": 5, "maxItems": 5, "items": {
            "type": "object",
            "properties": {
                "test": {"type": "string", "enum": [k for k, _ in TESTS]},
                "finding": {"type": "string", "description": "1-3 sentences"},
                "evidence": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"quote": {"type": "string", "description": "short exact quote"},
                                   "source": {"type": "string",
                                              "description": "session <id> step <n> | tally U<k> | sample S<k> | "
                                                             "SKILL.md <name> | user answer"}},
                    "required": ["quote", "source"], "additionalProperties": False}},
                "strength": {"type": "string", "enum": list(STRENGTHS)},
            },
            "required": ["test", "finding", "evidence", "strength"], "additionalProperties": False}},
        "history_thin": {"type": "boolean"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason": {"type": "string", "description": "1-3 sentences naming the deciding tests"},
        "skill_notes": {"type": "string", "description": "keep: bullets on what the skill should cover; else empty"},
        "proposal": {"type": "object", "properties": {
            "name": {"type": "string"}, "purpose": {"type": "string", "enum": [*ADDABLE_PURPOSES, ""]},
            "description": {"type": "string"}, "instructions": {"type": "string"}},
            "required": ["name", "purpose", "description", "instructions"], "additionalProperties": False,
            "description": "define: the proposed agent; else empty strings"},
        "questions": {"type": "array", "maxItems": MAX_QUESTIONS, "items": {
            "type": "object",
            "properties": {"test": {"type": "string", "enum": [k for k, _ in TESTS]},
                           "question": {"type": "string"}, "why": {"type": "string"},
                           "recommended": {"type": "string"}},
            "required": ["test", "question", "why", "recommended"], "additionalProperties": False}},
    },
    "required": ["tests", "history_thin", "verdict", "reason", "skill_notes", "proposal", "questions"],
    "additionalProperties": False,
}


class ReviewError(Exception):
    """The review could not produce a case; the message is shown to the user."""


# --------------------------------------------------------------------------- the brief
def _when(iso) -> str:
    return str(iso or "")[:16].replace("T", " ")


def tally_line(k: int, u: dict) -> str:
    skills = ", ".join(u.get("skills") or []) or "none"
    tag = " | tallied under a missing agent's name" if u.get("named_agent") else ""
    return (f"U{k} | {_when(u.get('at'))} | folder {u.get('folder') or '?'} | session {u.get('session_id') or '?'} | "
            f"run {u.get('run')} | step {u.get('step')} \"{one_line(u.get('title'), 80)}\" | skills {skills} | "
            f"ended {u.get('outcome')} | questions {int(u.get('questions') or 0)} | "
            f"assumptions {int(u.get('assumptions') or 0)} | timed out {int(u.get('timed_out') or 0)} | "
            f"sent back {'yes' if u.get('sent_back') else 'no'}{tag}")


def _question_files(sess: Path, report: Path, step: int) -> list[Path]:
    """That step's question files: those the run's report.md links (else every file), whose Step section is step."""
    qdir = sess / "questions"
    if not qdir.is_dir():
        return []
    try:
        text = report.read_text(encoding="utf-8")
    except OSError:
        text = ""
    names = list(dict.fromkeys(re.findall(r"\]\((?:\.\./)?questions/([^)\s]+\.md)\)", text)))
    files = [qdir / n for n in names] if names else sorted(qdir.glob("*.md"))
    out = []
    for f in files:
        try:
            body = f.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(rf"^## Step\s*\nStep {int(step)}\s*$", body, re.M):
            out.append(f)
    return out


def session_records(u: dict) -> dict:
    """Where one use's records are: {folder, missing} or {folder, plan, step, report, assumptions, activity,
    questions}. A run's steps and report move to run-<k>/ when the next run starts."""
    sess = Path(str(u.get("project") or "")) / ROOT_NAME / str(u.get("session_id") or "")
    if not u.get("project") or not u.get("session_id") or not sess.is_dir():
        return {"folder": sess, "missing": True}
    run, n = u.get("run"), int(u.get("step") or 0)
    archived = sess / f"run-{run}" if run else None
    base = archived if archived is not None and archived.is_dir() else sess
    report = base / "report.md"
    return {"folder": sess, "missing": False, "plan": sess / "plan.md", "step": base / "steps" / f"step-{n:02d}.md",
            "report": report, "assumptions": sess / "assumptions.md", "activity": sess / "activity.log",
            "questions": _question_files(sess, report, n)}


def _p(path: Path) -> str:
    return Path(path).as_posix()


def _exists(path: Path) -> str:
    return _p(path) if Path(path).exists() else f"{_p(path)} (not written)"


def build_brief(entry: dict) -> tuple[str, list[Path], dict]:
    """-> (first message, paths the reviewer may read, what was opened: {opened, missing, uses})."""
    uses = list(entry.get("uses") or [])                    # oldest first
    numbered = list(enumerate(uses, 1))
    recent = {u["id"] for u in uses[-OPEN_RECENT:]}
    problems = {u["id"] for u in uses if is_problem(u)}
    roots: list[Path] = []
    opened, missing = [], []
    v = entry.get("verdict") or {}
    head = [f"Role under review: {entry['name']}",
            f"Base agent: {entry.get('base_agent') or 'Builder'} (purpose {entry.get('purpose') or 'building'}) · "
            f"uses: {int(entry.get('uses_total') or 0)} in total, last {len(uses)} recorded below · folders: "
            + (", ".join(f.get("name") or "?" for f in entry.get("folders") or []) or "none"),
            "Skills seen: " + (", ".join(entry.get("skills") or []) or "none"),
            "Last decision: " + (f"{v.get('decision')} on {_when(v.get('at'))} at {v.get('uses_at')} uses" if v else "none"),
            "", "## Tally (one line per recorded use; U1 = oldest)", *[tally_line(k, u) for k, u in numbered]]
    samples = entry.get("samples") or []
    head += ["", "## Saved sample step instructions"]
    for k, s in enumerate(samples, 1):
        head += [f"S{k} (session {s.get('session_id')}, step {s.get('step')}):", str(s.get("text") or "").strip(), ""]
    if not samples:
        head += ["none", ""]
    head += [f"## Session records to open (the {OPEN_RECENT} most recent uses + every failed, blocked or sent-back use)"]
    for k, u in reversed(numbered):
        if u["id"] not in recent and u["id"] not in problems:
            continue
        rec = session_records(u)
        if rec["missing"]:
            missing.append(f"U{k}")
            head.append(f"U{k}: session folder gone ({_p(rec['folder'])}): work from its tally line and the samples.")
            continue
        opened.append(f"U{k}")
        roots.append(rec["folder"])
        n = u.get("step")
        head += [f"U{k} (session {u.get('session_id')}, run {u.get('run')}, step {n}):",
                 f"- plan.md: {_exists(rec['plan'])} (section \"### Step {n}\"; the session's latest draft: if it no "
                 "longer matches the tally title, rely on the samples)",
                 f"- step report: {_exists(rec['step'])}",
                 "- question files: " + (", ".join(_p(q) for q in rec["questions"]) or "none"),
                 f"- assumptions: {_exists(rec['assumptions'])} (lines starting \"- [step {n}]\")",
                 f"- run report: {_exists(rec['report'])}"]
        if u["id"] in problems:
            head.append(f"- activity.log: {_exists(rec['activity'])} (problem use)")
    if not opened and not missing:
        head.append("none")
    folders = []
    for u in reversed(uses):
        # the same folders a session discovers skills in (app/skills.py): the primary, then its additional folders
        for raw in [u.get("project"), *(u.get("extra_projects") or [])]:
            p = Path(str(raw or ""))
            if raw and p.is_dir() and p not in folders:
                folders.append(p)
    found = skills_mod.discover(folders) if folders else []
    head += ["", "## Skills the role used (compare with the instructions the planner kept adding)"]
    for name in entry.get("skills") or []:
        hit = next((s for s in found if s["name"] == name), None)
        if hit is None:
            head.append(f"- {name}: SKILL.md not found in the folders used")
        else:
            head.append(f"- {name}: {_p(Path(hit['path']))}")
            roots.append(Path(hit["path"]).parent)
    if not entry.get("skills"):
        head.append("none")
    builder_file = crew.agent_file("builder")
    roots.append(builder_file)
    head += ["", "## The Builder and the defined agents (does something already cover this role?)",
             f"- Builder definition: {_p(builder_file)}"]
    for folder in folders:
        agents = [e for e in crew.folder_agents(folder)]
        head.append(f"- Folder {folder.name}: " + ("; ".join(
            f"{e['name']} ({e['purpose']}): {one_line(e['description'], 140)} [{_p(e['path'])}]" for e in agents)
            or "no agents defined"))
        if agents:
            roots.append(folder / ".claude" / "agents")
    head += ["", "Read only the paths listed above. Then return the case."]
    return "\n".join(head), roots, {"opened": opened, "missing": missing, "uses": len(uses)}


def path_guard(roots: list[Path]):
    """on_permission for the reviewer: Read / Grep / Glob only inside the brief's paths; everything else denied."""
    def allowed(raw) -> bool:
        if not str(raw or "").strip():
            return False
        p = Path(str(raw))
        return any(inside(p, r) if r.is_dir() else p.resolve() == r.resolve() for r in roots)

    def check(req):
        args = req.input or {}
        if req.tool == "Read" and allowed(args.get("file_path")):
            return "allow"
        if req.tool in ("Grep", "Glob") and allowed(args.get("path")):
            return "allow"
        return PermissionDecision("deny", message=(
            "Outside your evidence: read only the paths listed in your brief (Grep / Glob need one of them as path). "
            "Never open project code or deliverables."))
    return check


# --------------------------------------------------------------------------- the case
def _clean_case(data: dict) -> dict:
    """The reviewer's reply -> a complete case body (every test present, known values only)."""
    data = data if isinstance(data, dict) else {}
    got = {t.get("test"): t for t in data.get("tests") or [] if isinstance(t, dict)}
    sections = []
    for key, title in TESTS:
        t = got.get(key) or {}
        strength = t.get("strength") if t.get("strength") in STRENGTHS else "none"
        evidence = [{"quote": one_line(e.get("quote"), 400), "source": one_line(e.get("source"), 120)}
                    for e in t.get("evidence") or [] if isinstance(e, dict) and str(e.get("quote") or "").strip()]
        sections.append({"test": key, "title": title,
                         "finding": str(t.get("finding") or "").strip() or "Not addressed by the reviewer.",
                         "evidence": evidence[:8], "strength": strength})
    verdict = data.get("verdict") if data.get("verdict") in VERDICTS else "not_yet"
    prop = data.get("proposal") if isinstance(data.get("proposal"), dict) else {}
    proposal = None
    if verdict == "define":
        proposal = {"name": str(prop.get("name") or "").strip(), "purpose": str(prop.get("purpose") or "").strip(),
                    "description": str(prop.get("description") or "").strip(),
                    "instructions": str(prop.get("instructions") or "").strip()}
    return {"sections": sections, "verdict": verdict, "reason": str(data.get("reason") or "").strip(),
            "history_thin": bool(data.get("history_thin")),
            "skill_notes": str(data.get("skill_notes") or "").strip() if verdict == "keep" else "",
            "proposal": proposal}


def _questions(data: dict) -> list[dict]:
    out = []
    for q in (data or {}).get("questions") or []:
        if isinstance(q, dict) and str(q.get("question") or "").strip():
            out.append({"test": q.get("test") if q.get("test") in dict(TESTS) else "", "question": one_line(q["question"], 300),
                        "why": one_line(q.get("why"), 400), "recommended": one_line(q.get("recommended"), 300)})
    return out[:MAX_QUESTIONS]


def case_markdown(case: dict) -> str:
    u = case.get("usage") or {}
    dec = case.get("decision")
    out = [f"# Role review: {case['role']}", "",
           f"Date: {_when(case['date'])} · Reviewer: {case['reviewer']['name']} ({case['reviewer']['label']}) · "
           f"Tokens: {int(u.get('tokens') or 0):,} · Cost: {costs.usd(u.get('cost') or 0)}",
           f"Uses: {case['uses_total']} in total, {case['uses_recorded']} recorded · session records opened: "
           + (", ".join(case["opened"]) or "none") + " · session folders gone: " + (", ".join(case["missing"]) or "none"),
           "", f"## Verdict (reviewer): {VERDICT_LABELS[case['verdict']]}", case["reason"] or "(no reason given)"]
    if case.get("history_thin"):
        out += ["", "History is thin: the reviewer leaned to \"not yet\"."]
    out += ["", "## Decision (user): " + (f"{VERDICT_LABELS[dec['decision']]} · {_when(dec['at'])}" if dec else "pending")]
    if dec and dec.get("agent"):
        out.append(f"Agent created: {dec['agent']} (folder {dec.get('folder') or '?'})")
    for k, s in enumerate(case["sections"], 1):
        out += ["", f"## {k}. {s['title']}", s["finding"], "", f"Strength: {s['strength']}"]
        out += [f"- \"{e['quote']}\" ({e['source']})" for e in s["evidence"]] or ["- no evidence quoted"]
    if case.get("skill_notes"):
        out += ["", "## What the skill should cover", case["skill_notes"]]
    if case.get("proposal"):
        p = case["proposal"]
        out += ["", "## Proposed agent", f"- Name: {p['name'] or '(none)'}", f"- Purpose: {p['purpose'] or '(none)'}",
                f"- Description: {p['description'] or '(none)'}", "", "Instructions beyond the skill:",
                p["instructions"] or "(none)"]
    if case.get("questions"):
        out += ["", "## Questions to the user"]
        for q in case["questions"]:
            out += [f"- {q['question']} ({q['test'] or 'general'})", f"  - Why: {q['why']}",
                    f"  - Recommended: {q['recommended']}", f"  - Answer: {q.get('answer') or NO_ANSWER}"]
    return "\n".join(out).rstrip() + "\n"


def write_case(case: dict, folder: Path | None) -> Path | None:
    """Save (or rewrite) the case file in the per-user cases folder; None when there is no folder (in memory)."""
    if folder is None:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{case['case_id']}.md"
    path.write_text(case_markdown(case), encoding="utf-8", newline="\n")
    return path


def write_case_copy(case: dict, project: Path, agent_name: str) -> Path:
    """The case beside the new agent: <folder>/.claude/agent-cases/<agent>.md (never read as an agent)."""
    d = Path(project) / CASE_COPY_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{agent_name}.md"
    path.write_text(case_markdown(case), encoding="utf-8", newline="\n")
    return path


def draft_context(entry: dict | None, case: dict | None) -> str:
    """Extra context for the agent drafter on the define path: the role's samples and skills, and the reviewer's
    proposal (name, purpose, description, instructions beyond the skill). Empty when there is nothing."""
    lines = []
    if entry:
        lines.append(f"Role: {entry['name']} (used {int(entry.get('uses_total') or 0)} times on the Builder)")
        lines.append("Skills it used (the agent gets these; do not repeat them): " + (", ".join(entry.get("skills") or []) or "none"))
        for k, s in enumerate(entry.get("samples") or [], 1):
            lines.append(f"Sample step {k}: {one_line(s.get('text'), 600)}")
    p = (case or {}).get("proposal")
    if p:
        lines += [f"Reviewer's proposed name: {p.get('name') or '(none)'}",
                  f"Reviewer's proposed purpose: {p.get('purpose') or '(none)'}",
                  f"Reviewer's proposed description: {p.get('description') or '(none)'}",
                  "Instructions the agent needs beyond the skill:", str(p.get("instructions") or "(none)")]
    if case and case.get("reason"):
        lines.append(f"Why the reviewer recommends it: {one_line(case['reason'], 400)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- one review
def _short_path(summary: str) -> str:
    parts = re.split(r"[\\/]", str(summary or ""))
    return "/".join(parts[-3:]) if len(parts) > 3 else str(summary or "")


def load_agent(*, engine: str, project: Path, model: str | None, on_permission):
    """The reviewer as it runs: its file's Read / Grep / Glob, every call gated (on_permission = path_guard), write /
    edit / shell tools denied outright, no ask_user, structured output REVIEW_SCHEMA."""
    agent = crew.load(ROLE, engine=engine, project=project, model=model, output_schema=REVIEW_SCHEMA,
                      gated_tools=list(READ_TOOLS), on_permission=on_permission, timeout_s=TURN_TIMEOUT_S,
                      include_ask_user=False)
    agent.disallowed_tools = list(dict.fromkeys(list(agent.disallowed_tools or []) + list(crew.WRITE_SHELL)))
    agent.resolved_tools()
    return agent


async def run_review(hub, name: str, review_id: str, progress) -> dict:
    """One review of role `name` -> the case (not yet decided). progress(phase, text) sends review_progress.
    ReviewError when no case could be produced (the caller sends review_failed)."""
    entry = hub.tally.get(name)
    if entry is None:
        raise ReviewError(f"no role '{name}' in the tally")
    brief, roots, seen = build_brief(entry)
    settings = hub.settings
    engine = choices.planner_engine(settings)
    model = getattr(settings, "reviewer_model", None) or "sonnet"
    harness = choices.chosen_harness(settings)
    cwd = hub.tally.home if hub.tally.home and hub.tally.home.is_dir() else settings.project
    agent = load_agent(engine=engine, project=cwd, model=model, on_permission=path_guard(roots))
    meter = Meter(hub, session_id=None, role="reviewer", name=crew.display(ROLE))
    meter.path_roots = list(roots)
    last_use = (entry.get("uses") or [{}])[-1] or {}                # stored oldest first
    meter.usage_info = {"label": f"Role review: {name}", "folder": last_use.get("project")}   # the usage log
    await meter.set_status("working")
    questions: list[dict] = []

    async def turn(s, message: str, phase: str):
        reply = None
        async for ev in s.stream(message):
            await meter.feed(ev)
            if isinstance(ev, ToolCall):
                await progress(phase, f"Reading {_short_path(summarize(ev.name, ev.input))}")
            elif isinstance(ev, Done):
                reply = ev.reply
        if reply is None or reply.status == "error" or not isinstance(reply.data, dict):
            raise ReviewError(f"the reviewer gave no usable case ({getattr(reply, 'error', None) or 'no reply'})")
        return reply.data

    try:
        await progress("reading", f"Reading the evidence: {seen['uses']} recorded uses, session records for "
                                  f"{len(seen['opened'])}" + (f", {len(seen['missing'])} session folders gone"
                                                               if seen["missing"] else ""))
        async with agent.session() as s:
            data = await turn(s, brief, "reading")
            questions = _questions(data)
            if questions:
                await progress("asking", f"{len(questions)} question{'s' if len(questions) > 1 else ''} for you")
                await meter.set_status("waiting")
                answers = await asyncio.gather(*(_ask(hub, review_id, name, q) for q in questions))
                await meter.set_status("working")
                for q, a in zip(questions, answers):
                    q["answer"] = a
                await progress("finalising", "Finalising the case with your answers")
                msg = ("Answers from the user:\n" + "\n".join(f"- {q['question']} -> {q['answer']}" for q in questions)
                       + "\nReturn the final case (same shape) with questions [].")
                data = await turn(s, msg, "finalising")
    except AgentError as e:
        await meter.add_reply(e.reply)
        raise ReviewError(f"the reviewer failed: {e.short}") from None
    finally:
        await meter.set_status("done")
    case = {"case_id": f"{name}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}",
            "review_id": review_id, "role": name, "date": now_iso(),
            "reviewer": {"name": crew.display(ROLE), "harness": harness, "model": model,
                         "label": choices.label(harness, model)},
            "uses_total": int(entry.get("uses_total") or 0), "uses_recorded": seen["uses"],
            "opened": seen["opened"], "missing": seen["missing"], **_clean_case(data),
            "questions": questions, "usage": costs.meter_usage(meter), "decision": None}
    return case


async def _ask(hub, review_id: str, role: str, q: dict) -> str:
    """One reviewer question as a question card (never auto-answered; NO_ANSWER after the question timeout)."""
    answer, _by, _ = await hub.incoming.ask(
        kind="question", agent=crew.display(ROLE), title=q["question"],
        body=q["why"] or "The evidence cannot answer this.", rec=q["recommended"] or None,
        timeout_s=hub.settings.question_timeout_s, timer_answer=NO_ANSWER,
        extra={"review_id": review_id, "role": role, "test": q["test"]})
    return str(answer) if answer else NO_ANSWER


# --------------------------------------------------------------------------- the hub's side
class Reviews:
    """Reviews in progress and the latest case per role (kept for a reconnect); one review at a time per role."""

    def __init__(self, hub):
        self.hub = hub
        self.running: dict[str, str] = {}          # role -> review_id
        self.cases: dict[str, dict] = {}           # role -> latest case (with decision once made)
        self.tasks: set[asyncio.Task] = set()

    def events(self) -> list[dict]:
        """For a reconnecting page: the latest case of each role."""
        return [self.case_event(c) for c in self.cases.values()]

    @staticmethod
    def case_event(case: dict) -> dict:
        return {"type": "review_case", "review_id": case["review_id"], "role": case["role"], "case": case}

    async def start(self, name: str) -> str | None:
        """review_start: refused (review_refused) while one runs for the role or when the role is unknown."""
        hub = self.hub
        name = str(name or "").strip()
        if name in self.running:
            await hub.emit({"type": "review_refused", "role": name, "review_id": self.running[name],
                            "error": "A review of this role is already running."})
            return None
        if hub.tally.get(name) is None:
            await hub.emit({"type": "review_refused", "role": name, "review_id": None,
                            "error": f"There is no role '{name}' in the tally."})
            return None
        rid = "rv" + secrets.token_hex(4)
        self.running[name] = rid
        settings = hub.settings
        await hub.emit({"type": "review_started", "review_id": rid, "role": name,
                        "model": getattr(settings, "reviewer_model", None) or "sonnet",
                        "harness": choices.chosen_harness(settings)})
        await hub.emit_roles()
        try:
            async def progress(phase: str, text: str) -> None:
                await hub.emit({"type": "review_progress", "review_id": rid, "role": name, "phase": phase,
                                "text": one_line(text, 200)})
            case = await run_review(hub, name, rid, progress)
            path = write_case(case, hub.tally.cases_dir)
            case["case_file"] = path.name if path else None
            self.cases[name] = case
            hub.tally.set_review(name, {"review_id": rid, "verdict": case["verdict"], "case_file": case["case_file"],
                                        "cost": case["usage"]["cost"], "tokens": case["usage"]["tokens"]})
            await hub.emit(self.case_event(case))
        except Exception as e:  # noqa: BLE001 -- any failure leaves the role reviewable
            msg = str(e) if isinstance(e, ReviewError) else f"{type(e).__name__}: {e}"
            await hub.emit({"type": "review_failed", "review_id": rid, "role": name, "error": one_line(msg, 400)})
        finally:
            self.running.pop(name, None)
            await hub.emit_roles()
        return rid

    async def decide(self, name: str, decision: str) -> dict:
        """review_decide: record the user's decision (may differ from the reviewer's verdict) on the entry and in
        the case file -> the case (or {} when the role had no review this launch)."""
        hub = self.hub
        case = self.cases.get(name) or {}
        entry = hub.tally.set_decision(name, decision, reviewer_verdict=case.get("verdict"),
                                       case_file=case.get("case_file"))
        if case:
            case["decision"] = {"decision": decision, "at": entry["verdict"]["at"]}
            write_case(case, hub.tally.cases_dir)
        await hub.emit({"type": "review_decided", "role": name, "decision": decision,
                        "reviewer_verdict": case.get("verdict"), "review_id": case.get("review_id"),
                        "case_file": case.get("case_file")})
        await hub.emit_roles()
        return case

    def defined(self, name: str, agent: str, project: Path, folder_name: str) -> str | None:
        """agent_create succeeded for a role: note it in the case, save the copy beside the agent -> the copy's
        folder-relative path (None when the role had no case this launch)."""
        case = self.cases.get(name)
        if not case:
            return None
        dec = case.get("decision") or {"decision": "define", "at": now_iso()}
        case["decision"] = {**dec, "decision": "define", "agent": agent, "folder": folder_name}
        write_case(case, self.hub.tally.cases_dir)
        path = write_case_copy(case, project, agent)
        return f"{CASE_COPY_DIR}/{path.name}"
