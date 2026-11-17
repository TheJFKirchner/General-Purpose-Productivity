#!/usr/bin/env python3
"""The project's shared findings file: add, list, check, confirm, drop.

Run from anywhere inside a project (a folder holding project_plan.md), or pass --project <folder>.

  findings.py init                      create findings.json; list the plan's goals
  findings.py goals                     the plan's goals and how many findings each has
  findings.py add --goal G1 --kind durable|refreshing --bearing answers|supports|contradicts|changes-plan
                  --statement "..." --means "..." --evidence "script=...;section=s2;table=...;figures=...;commentary=C3"
                  [--evidence ...] [--stated-by "who or which document"] [--as-of 2026-05]
                  [--by "analysis skill"] [--approved "name, date"] [--replaces F2]
                  [--assumes "a threshold or definition the analyst chose"] [--open "what someone still has to confirm"]
  findings.py answer G1 --status answered|conditional|open --text "one line that meets the goal's Success"
  findings.py approve F1 F2 --by "name, date"
  findings.py list [--goal G1] [--all]  print findings (active and stale; --all adds dropped and replaced)
  findings.py check                     citations still exist? data changed? goals without findings?
  findings.py confirm F2 [--statement "..."] [--means "..."] [--as-of 2026-06]
  findings.py drop F2 --reason "..."

Every change rewrites findings.md, the readable view. A STOP: line says what to fix.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

PLAN_NAME = "project_plan.md"
FILE_NAME = "findings.json"
VIEW_NAME = "findings.md"
KINDS = ("durable", "refreshing")
BEARINGS = ("answers", "supports", "contradicts", "changes-plan")
ANSWER_STATUS = ("answered", "conditional", "open")
UNCONFIRMED = "not yet confirmed by the user"
STOPWORDS = set("the a an of to in on for and or is are was were be it its that this with as by at from not no than "
                "which what has have had will would can there their they them into over under about".split())
EVIDENCE_KEYS = ("script", "section", "table", "figures", "commentary", "deliverable")
MAX_STATEMENT = 300
GOAL_ROW = re.compile(r"^\s*(?:\||[-*]|#{1,6})?\s*\**\s*([GQ]\d+)\b\**\s*[|:.)\-]?\s*(.*)$")


class Stop(Exception):
    pass


# ---------- project and plan ----------

def find_project(arg: str | None) -> Path:
    if arg:
        p = Path(arg).resolve()
        if not (p / PLAN_NAME).exists():
            raise Stop(f"{p} has no {PLAN_NAME}. A project is the folder that holds the plan.")
        return p
    here = Path.cwd().resolve()
    for p in [here, *here.parents]:
        if (p / PLAN_NAME).exists():
            return p
    raise Stop(f"no {PLAN_NAME} in this folder or above it. Run inside a project, or pass --project <folder>.")


def read_goals(project: Path) -> dict[str, str]:
    goals: dict[str, str] = {}
    for line in (project / PLAN_NAME).read_text(encoding="utf-8").splitlines():
        m = GOAL_ROW.match(line)
        if m and m.group(1) not in goals:
            text = m.group(2).strip().strip("|").split("|")[0].strip().strip("*").strip()
            goals[m.group(1)] = text
    if not goals:
        raise Stop(f"{PLAN_NAME} names no goals. Give each goal or question an id at the start of its row or "
                   "line: G1, G2 ... (or Q1, Q2 ...). Findings are filed against these ids.")
    return goals


def load(project: Path) -> dict:
    f = project / FILE_NAME
    if not f.exists():
        raise Stop(f"no {FILE_NAME} in {project}. Run: findings.py init")
    return json.loads(f.read_text(encoding="utf-8"))


def save(project: Path, doc: dict, goals: dict[str, str]) -> None:
    (project / FILE_NAME).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (project / VIEW_NAME).write_text(render(doc, goals, project), encoding="utf-8")


# ---------- evidence ----------

def fingerprint(path: Path) -> str:
    """Hash of a table's contents (not its bytes, so a rerun with the same data does not look like a change)."""
    try:
        if path.suffix.lower() in (".parquet", ".csv"):
            import pandas as pd
            df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
            h = hashlib.sha1("|".join(map(str, df.columns)).encode())
            h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
            return h.hexdigest()[:16]
    except Exception:
        pass
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def parse_evidence(project: Path, raw: str) -> dict:
    ev: dict[str, str] = {}
    for part in raw.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise Stop(f'evidence part "{part.strip()}" needs key=value. Keys: {", ".join(EVIDENCE_KEYS)}')
        k, v = part.split("=", 1)
        k, v = k.strip().lower(), v.strip()
        if k not in EVIDENCE_KEYS:
            raise Stop(f'unknown evidence key "{k}". Keys: {", ".join(EVIDENCE_KEYS)}')
        ev[k] = v
    if "script" not in ev:
        raise Stop("evidence needs script=<the file whose code produced it>, as a path from the project folder.")
    for k in ("script", "table", "deliverable"):
        if k in ev:
            p = (project / ev[k]).resolve()
            if not p.exists():
                raise Stop(f"evidence {k}={ev[k]} does not exist under {project}. Paths start at the project folder.")
            try:
                ev[k] = p.relative_to(project).as_posix()
            except ValueError:
                raise Stop(f"evidence {k}={ev[k]} is outside the project folder.")
    if "table" in ev:
        if "figures" not in ev:
            raise Stop("evidence with a table needs figures=<which rows and columns>, so a reader can find the number.")
        if re.search(r"\d+\.\d+|\d{1,3}(?:,\d{3})+|\b\d{5,}\b", ev["figures"]):
            raise Stop(f'figures="{ev["figures"]}" quotes values. Name the rows and columns only '
                       '("Lakeside Surgical row, columns large_claims and total_paid"): values go out of date on a refresh.')
        ev["fingerprint"] = fingerprint(project / ev["table"])
    return ev


# ---------- view ----------

def cite(e: dict) -> str:
    if "stated_by" in e:
        return f"Stated by {e['stated_by']} (not checked against data)"
    bits = []
    if e.get("section"):
        bits.append(f"section {e['section']}")
    bits.append(f"`{e['script']}`")
    if e.get("table"):
        bits.append(f"table `{e['table']}` ({e.get('figures', '')})")
    elif e.get("figures"):
        bits.append(e["figures"])
    if e.get("commentary"):
        bits.append(f"commentary {e['commentary']}")
    return ", ".join(bits)


def esc(s: str) -> str:
    return str(s).replace("|", "/").replace("\n", " ")


def deliverable_of(project: Path, e: dict) -> str | None:
    """The deliverable folder a piece of evidence sits in: analyses/<name>, presentations/<name>, dashboard."""
    d = e.get("deliverable")
    if not d and e.get("script"):
        parts = e["script"].split("/")
        if parts[0] in ("analyses", "presentations") and len(parts) > 2:
            d = "/".join(parts[:2])
        elif parts[0] == "dashboard":
            d = "dashboard"
    return d


def work_line(project: Path, d: str) -> str:
    bits = [f"`{d}/`"]
    reports = sorted((project / d / "output").glob("*.html")) if (project / d / "output").is_dir() else []
    if reports:
        bits.append(f"report [{reports[-1].name}]({d}/output/{reports[-1].name})")
    if (project / d / "README.md").exists():
        bits.append(f"what was tested and ruled out: [{d}/README.md]({d}/README.md)")
    return ", ".join(bits)


def render(doc: dict, goals: dict[str, str], project: Path | None = None) -> str:
    fs = doc["findings"]
    live_all = [f for f in fs if f["status"] in ("active", "stale")]
    unconf = [f["id"] for f in live_all if f.get("approved", UNCONFIRMED) == UNCONFIRMED]
    stale = [f["id"] for f in live_all if f["status"] == "stale" or f.get("recheck")]
    out = ["# Findings", "",
           f"Generated from `{FILE_NAME}` by the findings skill. Do not edit; use `findings.py`.", "",
           "What the work has learned against each goal in `project_plan.md`, and where each thing came from. "
           "Durable: a conclusion expected to hold when the data refreshes. Refreshing: true for the data period it names.", "",
           f"- Findings in use: {len(live_all)}.",
           "- Not yet confirmed by the user: " + (", ".join(unconf) if unconf else "none") + ".",
           "- Data changed since written (stale or recheck; not to be used until confirmed): "
           + (", ".join(stale) if stale else "none") + ".", ""]
    changed = [(h["date"], f) for f in fs for h in f.get("history", [])[-1:]]
    changed += [(f.get("dropped_on", ""), f) for f in fs if f["status"] in ("dropped", "replaced") and f.get("dropped_on")]
    if changed:
        last = max(d for d, _ in changed)
        out += [f"## Changed on {last}", ""]
        for d, f in changed:
            if d != last:
                continue
            if f["status"] == "dropped":
                out.append(f"- {f['id']} ({f['goal']}) dropped ({esc(f.get('reason', ''))}). It said: {esc(f['statement'])}")
            elif f["status"] == "replaced":
                out.append(f"- {f['id']} ({f['goal']}) replaced by {f.get('replaced_by')}. It said: {esc(f['statement'])}")
            else:
                h = f["history"][-1]
                out.append(f"- {f['id']} ({f['goal']}) reworded" + (f": {esc(h['why'])}" if h.get("why") else "") + ". Before"
                           + (f" (as of {h['as_of']})" if h.get("as_of") else "") + f": {esc(h['was'])}")
        out.append("")
    answers = doc.get("answers", {})
    ids = list(goals) + sorted({f["goal"] for f in fs if f["goal"] not in goals})
    for g in ids:
        mine = [f for f in fs if f["goal"] == g and f["status"] in ("active", "stale")]
        out += [f"## {g}: {goals.get(g, '(no longer in the plan)')}", ""]
        a = answers.get(g)
        if a:
            out += [f"**Answer so far ({a['status']}):** {a['text']}", ""]
        else:
            out += ["**Answer so far:** none recorded.", ""]
        if not mine:
            out += ["No findings.", ""]
            continue
        out += ["| ID | Finding | What it means for the goal | Rests on / still to confirm | Kind | Where it comes from |",
                "| --- | --- | --- | --- | --- | --- |"]
        for f in mine:
            fid = f["id"] + (" **STALE**" if f["status"] == "stale" else "") + (" **RECHECK**" if f.get("recheck") else "")
            kind = f["kind"] + (f", as of {f['as_of']}" if f.get("as_of") else "")
            cav = [f"Assumes: {x}" for x in f.get("assumes", [])] + [f"To confirm: {x}" for x in f.get("open", [])]
            src = "<br>".join(cite(e) for e in f["evidence"])
            out.append(f"| {fid} | {esc(f['statement'])} | {f['bearing']}: {esc(f['means'])} | "
                       f"{esc('<br>'.join(cav)) if cav else ''} | {kind} | {esc(src)} |")
        out.append("")
        if project:
            ds = []
            for f in mine:
                for e in f["evidence"]:
                    d = deliverable_of(project, e)
                    if d and d not in ds:
                        ds.append(d)
            for d in ds:
                out.append(f"Work behind this: {work_line(project, d)}")
            if ds:
                out.append("")
    gone = [f for f in fs if f["status"] in ("dropped", "replaced")]
    if gone:
        out += ["## No longer used", ""]
        out += [f"- {f['id']} ({f['goal']}, {f['status']}"
                + (f" by {f['replaced_by']}" if f.get("replaced_by") else "")
                + f"): {esc(f['statement'])}" + (f" Reason: {esc(f['reason'])}" if f.get("reason") else "")
                for f in gone]
        out.append("")
    return "\n".join(out)

def show(fs: list[dict]) -> None:
    for f in fs:
        tag = f["status"].upper() if f["status"] != "active" else "active"
        asof = f", as of {f['as_of']}" if f.get("as_of") else ""
        print(f"{f['id']}  {f['goal']}  {f['kind']}{asof}  [{tag}{'; recheck' if f.get('recheck') else ''}]")
        print(f"    {f['statement']}")
        print(f"    {f['bearing']}: {f['means']}")
        for x in f.get("assumes", []):
            print(f"    assumes: {x}")
        for x in f.get("open", []):
            print(f"    to confirm: {x}")
        for e in f["evidence"]:
            print(f"    from: {cite(e)}")
        print(f"    approved: {f.get('approved', UNCONFIRMED)}")


# ---------- commands ----------

def cmd_init(a, project):
    goals = read_goals(project)
    f = project / FILE_NAME
    if f.exists():
        print(f"{FILE_NAME} already exists; left as it is.")
        doc = load(project)
    else:
        doc = {"plan": PLAN_NAME, "max_per_goal": 5, "findings": []}
    save(project, doc, goals)
    print(f"Project: {project}")
    for g, t in goals.items():
        print(f"  {g}  {t}")
    print(f"At most {doc['max_per_goal']} live findings per goal (max_per_goal in {FILE_NAME}; the user may change it).")


def cmd_goals(a, project):
    goals, doc = read_goals(project), load(project)
    for g, t in goals.items():
        live = [f for f in doc["findings"] if f["goal"] == g and f["status"] in ("active", "stale")]
        stale = sum(f["status"] == "stale" for f in live)
        print(f"{g}  {len(live)} finding(s){f', {stale} stale' if stale else ''}  {t}")


def cmd_add(a, project):
    goals, doc = read_goals(project), load(project)
    if a.goal not in goals:
        raise Stop(f"{a.goal} is not a goal in {PLAN_NAME} (it has: {', '.join(goals)}). Something that bears on no "
                   "goal is not a finding: leave it in the deliverable's own notes, or ask the user whether the plan should change.")
    st = " ".join(a.statement.split())
    means = " ".join(a.means.split())
    if len(st) > MAX_STATEMENT:
        raise Stop(f"statement is {len(st)} characters; the limit is {MAX_STATEMENT}. One finding is one or two sentences. "
                   "Two things learned: two findings, if both bear on a goal.")
    if len(means) < 15:
        raise Stop("--means must say what this changes or settles for the goal, in a sentence.")
    words = lambda s: {w for w in re.findall(r"[a-z0-9$%.]+", s.lower()) if w not in STOPWORDS}  # noqa: E731
    mw = words(means)
    if mw and len(mw & words(st)) / len(mw) > 0.6:
        raise Stop("--means mostly repeats the statement. Say the consequence for the goal: what can now be decided, "
                   "done or ruled out. No consequence: it is not a finding.")
    if not a.evidence and not a.stated_by:
        raise Stop("a finding cites where it came from: --evidence \"script=...;section=...;table=...;figures=...\", "
                   "or --stated-by \"who or which document\" when no data backs it.")
    evidence = [parse_evidence(project, raw) for raw in a.evidence or []]
    if a.stated_by:
        evidence.append({"stated_by": a.stated_by})
    if a.kind == "refreshing":
        if not a.as_of:
            raise Stop("a refreshing finding needs --as-of <the data period or snapshot it is true for>.")
        if not any("table" in e for e in evidence):
            raise Stop("a refreshing finding needs evidence with table=..., so a data change can be detected.")
    same = [f for f in doc["findings"] if f["status"] in ("active", "stale") and f["statement"].lower() == st.lower()]
    if same:
        raise Stop(f"{same[0]['id']} already says this.")
    replaced = None
    if a.replaces:
        replaced = next((f for f in doc["findings"] if f["id"] == a.replaces), None)
        if not replaced:
            raise Stop(f"--replaces {a.replaces}: no such finding.")
    live = [f for f in doc["findings"] if f["goal"] == a.goal and f["status"] in ("active", "stale") and f is not replaced]
    cap = int(doc.get("max_per_goal", 5))
    if len(live) >= cap:
        raise Stop(f"{a.goal} already has {len(live)} findings (limit {cap}): {', '.join(f['id'] for f in live)}. "
                   "Decide which matters more: add with --replaces <id>, or drop one first. Do not raise the limit yourself.")
    n = 1 + max([int(f["id"][1:]) for f in doc["findings"]] or [0])
    new = {"id": f"F{n}", "goal": a.goal, "kind": a.kind, "bearing": a.bearing, "statement": st, "means": means,
           "evidence": evidence, "status": "active", "added": dt.date.today().isoformat()}
    if a.as_of:
        new["as_of"] = a.as_of
    if a.by:
        new["by"] = a.by
    if a.assumes:
        new["assumes"] = [" ".join(x.split()) for x in a.assumes]
    if a.open:
        new["open"] = [" ".join(x.split()) for x in a.open]
    new["approved"] = a.approved or UNCONFIRMED
    if replaced:
        replaced["status"], replaced["replaced_by"] = "replaced", new["id"]
        replaced["dropped_on"] = dt.date.today().isoformat()
    doc["findings"].append(new)
    save(project, doc, goals)
    print(f"Added {new['id']} under {a.goal}" + (f", replacing {replaced['id']}" if replaced else "") + ".")
    if a.kind == "durable" and re.search(r"\d", st) and not re.search(r"\b(19|20)\d\d\b", st):
        print("note: a durable finding with a figure and no period. Say the period the figure belongs to, "
              "or make it refreshing.")


def cmd_list(a, project):
    goals, doc = read_goals(project), load(project)
    keep = ("active", "stale", "dropped", "replaced") if a.all else ("active", "stale")
    fs = [f for f in doc["findings"] if f["status"] in keep and (not a.goal or f["goal"] == a.goal)]
    if not fs:
        print("No findings" + (f" under {a.goal}" if a.goal else "") + ".")
    show(fs)
    stale = [f["id"] for f in fs if f["status"] == "stale" or f.get("recheck")]
    if stale:
        print(f"\nData changed since written; not to be used until confirmed: {', '.join(stale)}")
    save(project, doc, goals)


def cmd_check(a, project):
    goals, doc = read_goals(project), load(project)
    problems = 0
    for f in doc["findings"]:
        if f["status"] not in ("active", "stale"):
            continue
        if f["goal"] not in goals:
            print(f"{f['id']}: its goal {f['goal']} is no longer in the plan. Move it (drop and add) or drop it.")
            problems += 1
        changed = False
        for e in f["evidence"]:
            for k in ("script", "table"):
                if k in e and not (project / e[k]).exists():
                    print(f"{f['id']}: cited {k} {e[k]} no longer exists.")
                    problems += 1
            if "table" in e and (project / e["table"]).exists() and fingerprint(project / e["table"]) != e.get("fingerprint"):
                changed = True
        if changed and f["kind"] == "refreshing" and f["status"] != "stale":
            f["status"] = "stale"
            print(f"{f['id']}: STALE. Its table changed since it was written (as of {f.get('as_of')}). "
                  f"Read the new figures, then: findings.py confirm {f['id']} --statement \"...\" --as-of ..., or drop it.")
            problems += 1
        elif changed and f["kind"] == "refreshing":
            print(f"{f['id']}: still stale.")
            problems += 1
        elif changed and f["kind"] == "durable" and not f.get("recheck"):
            f["recheck"] = True
            print(f"{f['id']}: durable, but its evidence changed. Check it still holds, then: findings.py confirm {f['id']}")
            problems += 1
        elif changed:
            print(f"{f['id']}: durable, recheck still pending.")
            problems += 1
    for g, t in goals.items():
        has = any(f["goal"] == g and f["status"] in ("active", "stale") for f in doc["findings"])
        if not has:
            print(f"{g}: no findings yet. ({t})")
        elif g not in doc.get("answers", {}):
            print(f"{g}: has findings but no answer line. findings.py answer {g} --status ... --text \"...\"")
            problems += 1
    save(project, doc, goals)
    print("Check done: " + (f"{problems} thing(s) to deal with." if problems else "citations exist and no cited data has changed."))


def cmd_confirm(a, project):
    goals, doc = read_goals(project), load(project)
    f = next((x for x in doc["findings"] if x["id"] == a.id), None)
    if not f:
        raise Stop(f"no finding {a.id}.")
    if f["status"] == "stale" and f["kind"] == "refreshing" and not (a.statement and a.as_of and a.means and a.why):
        raise Stop("a stale refreshing finding is confirmed whole, read again against the new tables: --statement \"...\" "
                   "--means \"...\" --as-of ... --why \"what changed in the data\". Repeat old wording only where it is still true. "
                   "Also --evidence if the rows or columns moved, --assumes / --open if those changed.")
    if a.statement:
        st = " ".join(a.statement.split())
        if len(st) > MAX_STATEMENT:
            raise Stop(f"statement is {len(st)} characters; the limit is {MAX_STATEMENT}.")
        if st != f["statement"]:
            f.setdefault("history", []).append({"date": dt.date.today().isoformat(), "was": f["statement"],
                                                "as_of": f.get("as_of", ""), "why": a.why or ""})
        f["statement"] = st
    if a.means:
        f["means"] = " ".join(a.means.split())
    if a.as_of:
        f["as_of"] = a.as_of
    if a.evidence:
        f["evidence"] = [parse_evidence(project, raw) for raw in a.evidence]
    if a.assumes is not None:
        f["assumes"] = [" ".join(x.split()) for x in a.assumes if x.strip().lower() not in ("", "none")]
    if a.open is not None:
        f["open"] = [" ".join(x.split()) for x in a.open if x.strip().lower() not in ("", "none")]
    for e in f["evidence"]:
        if "table" in e and (project / e["table"]).exists():
            e["fingerprint"] = fingerprint(project / e["table"])
    f["status"] = "active"
    f.pop("recheck", None)
    f["confirmed"] = dt.date.today().isoformat()
    save(project, doc, goals)
    print(f"{a.id} confirmed against the current data.")


def cmd_answer(a, project):
    goals, doc = read_goals(project), load(project)
    if a.goal not in goals:
        raise Stop(f"{a.goal} is not a goal in {PLAN_NAME} (it has: {', '.join(goals)}).")
    text = " ".join(a.text.split())
    if len(text) > MAX_STATEMENT:
        raise Stop(f"answer is {len(text)} characters; the limit is {MAX_STATEMENT}. One or two sentences.")
    live = [f for f in doc["findings"] if f["goal"] == a.goal and f["status"] == "active"]
    if a.status != "open" and not live:
        raise Stop(f"{a.goal} has no active findings. An answer rests on findings; with none the status is open.")
    doc.setdefault("answers", {})[a.goal] = {"status": a.status, "text": text, "updated": dt.date.today().isoformat()}
    save(project, doc, goals)
    print(f"Answer line for {a.goal} saved ({a.status}).")
    waiting = [f["id"] for f in live if f.get("open")]
    if a.status == "answered" and waiting:
        print(f"note: {', '.join(waiting)} still have items to confirm. If any could change this answer, the status is conditional.")


def cmd_approve(a, project):
    goals, doc = read_goals(project), load(project)
    for fid in a.ids:
        f = next((x for x in doc["findings"] if x["id"] == fid), None)
        if not f:
            raise Stop(f"no finding {fid}.")
        f["approved"] = a.by
    save(project, doc, goals)
    print(f"Approved by {a.by}: {', '.join(a.ids)}")


def cmd_drop(a, project):
    goals, doc = read_goals(project), load(project)
    f = next((x for x in doc["findings"] if x["id"] == a.id), None)
    if not f:
        raise Stop(f"no finding {a.id}.")
    f["status"], f["reason"], f["dropped_on"] = "dropped", a.reason, dt.date.today().isoformat()
    save(project, doc, goals)
    print(f"{a.id} dropped. It stays in the file under 'No longer used'.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="project folder (default: found from the current folder)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("goals").set_defaults(fn=cmd_goals)
    p = sub.add_parser("add")
    p.add_argument("--goal", required=True)
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--bearing", required=True, choices=BEARINGS)
    p.add_argument("--statement", required=True)
    p.add_argument("--means", required=True)
    p.add_argument("--evidence", action="append")
    p.add_argument("--stated-by")
    p.add_argument("--as-of")
    p.add_argument("--by")
    p.add_argument("--approved")
    p.add_argument("--replaces")
    p.add_argument("--assumes", action="append")
    p.add_argument("--open", action="append")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("answer")
    p.add_argument("goal")
    p.add_argument("--status", required=True, choices=ANSWER_STATUS)
    p.add_argument("--text", required=True)
    p.set_defaults(fn=cmd_answer)
    p = sub.add_parser("approve")
    p.add_argument("ids", nargs="+")
    p.add_argument("--by", required=True)
    p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("list")
    p.add_argument("--goal")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_list)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    p = sub.add_parser("confirm")
    p.add_argument("id")
    p.add_argument("--statement")
    p.add_argument("--means")
    p.add_argument("--as-of")
    p.add_argument("--why", help="what changed in the data")
    p.add_argument("--evidence", action="append", help="replaces the evidence")
    p.add_argument("--assumes", action="append", help="replaces the list; pass none to clear")
    p.add_argument("--open", action="append", help="replaces the list; pass none to clear")
    p.set_defaults(fn=cmd_confirm)
    p = sub.add_parser("drop")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_drop)
    a = ap.parse_args(argv)
    try:
        a.fn(a, find_project(a.project))
    except Stop as e:
        print(f"STOP: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
