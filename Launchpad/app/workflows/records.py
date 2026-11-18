"""The files a workflow run leaves in its run folder (a person's record): result files, review records, the run summary.

- Every file of a test run starts with a "Test run" line
- Written by code only (agents hand their result over with submit_report; app/workflows/runner.py)
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .. import costs
from ..sessionfiles import one_line

TEST_LINE = "> **Test run.** This record comes from a test run; the test folder is emptied at the start of the next one."


def when(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return dt.datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def _head(run, title: str) -> list[str]:
    lines = [f"# {title}", ""]
    if run.test:
        lines += [TEST_LINE, ""]
    return lines


def _bullets(items) -> list[str]:
    return [f"- {one_line(i, 600)}" for i in items] or ["- none"]


def result_text(run, stage: dict, *, attempt: int, report: dict, agent: str, tool_calls: int, cost_usd: float,
                notes: list[dict]) -> str:
    """One agent stage's result file: header, the agent's result markdown, then issues / assumptions / data files."""
    lines = _head(run, f"Stage {stage['index'] + 1}: {stage['title']}")
    lines += [f"Workflow: {run.wf['name']} · run {run.id}" + (" (test run)" if run.test else ""),
              f"Agent: {agent} · attempt {attempt} · status **{report['status']}** · tool calls: {tool_calls} · "
              f"cost: {costs.usd(cost_usd)}", f"Written: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    for nb in notes:
        lines += [f"> Re-run after review \"{nb['review_title']}\" sent it back ({nb['name']}): "
                  f"{one_line(nb['note'], 600)}", ""]
    lines += ["## Result", "", (report.get("result") or "").strip() or "(no result text)", "",
              "## Issues", *_bullets(report.get("issues") or []), "",
              "## Assumptions", *_bullets(report.get("assumptions") or []), ""]
    if report.get("files"):
        lines += ["## Data files written", *_bullets(report["files"]), ""]
    return "\n".join(lines)


def review_text(run, stage: dict, record: dict, results: list[tuple[str, str]]) -> str:
    """A review record: who signed, when, the decision, the checklist with answers, what was reviewed."""
    lines = _head(run, f"Review: {stage['title']}")
    decision = "Approved" if record["decision"] == "approve" else "Sent back"
    lines += [f"Workflow: {run.wf['name']} · run {run.id}" + (" (test run)" if run.test else ""),
              f"Stage {stage['index'] + 1} · signed by **{record['name']}** · {when(record['at'])}", "",
              f"## Decision", decision + (f" to stage {record['back_to'] + 1} "
                                          f"({run.stages[record['back_to']]['title']})"
                                          if record["decision"] == "send_back" else ""), "",
              "## Note", record["note"] or "none", "", "## Checklist"]
    if not record["answers"]:
        lines.append("- (no checklist: a plain stop and sign-off)")
    for a in record["answers"]:
        if a["kind"] == "tick":
            mark = "[x]" if a["ticked"] else "[ ]"
            lines.append(f"- {mark} {a['text']}" + (f" — {one_line(a['answer'], 600)}" if a["answer"] else ""))
        else:
            lines.append(f"- {a['text']}\n  - Answer: {one_line(a['answer'], 1000) or '(not answered)'}")
    lines += ["", "## Results reviewed"]
    lines += [f"- {t}: {Path(p).name}" for t, p in results] or ["- none"]
    return "\n".join(lines) + "\n"


def summary_text(run) -> str:
    """run-summary.md: everything a person wants to know about the run, rewritten at every change."""
    status = {"running": "In progress", "awaiting_review": "Waiting for a review", "done": "Done",
              "failed": "Failed", "stopped": "Stopped"}.get(run.status, run.status)
    lines = _head(run, f"Run summary: {run.wf['name']}" + (" (test run)" if run.test else ""))
    lines += [f"- Workflow: {run.wf['name']} ({run.wf['path']} in {run.wf['folder_name']})",
              f"- Run: {run.id}" + (" · **test run**" if run.test else ""),
              f"- Status: **{status}**" + (f" ({run.error})" if run.error else ""),
              f"- Started: {when(run.started_at)} · finished: {when(run.finished_at)}",
              f"- Unattended: {'yes (agent questions answered with their recommendation, permission requests approved; reviews still stop)' if run.unattended else 'no'}",
              f"- Run folder: {run.run_folder}", f"- Cost: {costs.usd(run.cost())}", "", "## Inputs"]
    if run.inputs:
        labels = {i["name"]: i["label"] for i in run.wf["inputs"]}
        lines += [f"- {labels.get(k, k)} ({k}): {v or '(empty)'}" for k, v in run.inputs.items()]
    else:
        lines.append("- none")
    lines += ["", "## Stages", "", "| # | Stage | Kind | Status | Result / record | Cost |", "|---|---|---|---|---|---|"]
    for st in run.stages:
        if st["kind"] == "agent":
            res = Path(st["result_file"]).name if st["result_file"] else "-"
        else:
            res = Path(st["review"]["record_file"]).name if st.get("review") else "-"
        lines.append(f"| {st['index'] + 1} | {st['title']} | {st['kind']}"
                     f"{' · ' + st['agent_display'] if st['kind'] == 'agent' else ''} | {st['status']} | {res} | "
                     f"{costs.usd(st['cost_usd'], symbol=False) if st['kind'] == 'agent' else '-'} |")
    rejected = [(st, a) for st in run.stages for a in st["attempts"] if a["rejected"]]
    if rejected:
        lines += ["", "## Rejected results (kept)"]
        lines += [f"- Stage {st['index'] + 1} attempt {a['attempt']}: {Path(a['result_file']).name}"
                  + (f" — {one_line(a['note'], 300)}" if a["note"] else "") for st, a in rejected]
    reviews = [(st, r) for st in run.stages for r in st["reviews"]]
    if reviews:
        lines += ["", "## Reviews"]
        lines += [f"- {st['title']}: {'approved' if r['decision'] == 'approve' else 'sent back to stage ' + str(r['back_to'] + 1)}"
                  f" by {r['name']} at {when(r['at'])} ({Path(r['record_file']).name})" for st, r in reviews]
    lines += ["", "## Attached files read at the start"]
    lines += [f"- {a['path']} ({a['chars']} characters)" for a in run.attachments] or ["- none"]
    data = run.data_files()
    lines += ["", "## Data files in the run folder"]
    lines += [f"- {p}" for p in data] or ["- none"]
    if run.autopilot_log:
        lines += ["", "## Approved without a card (unattended / autopilot)", *_bullets(run.autopilot_log)]
    return "\n".join(lines) + "\n"
