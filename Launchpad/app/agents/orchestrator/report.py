"""report.md for a finished run (written by code, never by an agent): the orchestrator's summary, built list and
open issues, plus the steps table, every assumption, autopilot approvals, the run's question files, step issues and per-agent costs.
Also refreshes run.total_cost / run.planner_cost (sent with run_finished)."""
from __future__ import annotations

import datetime as dt

from ... import costs
from ...sessionfiles import one_line
from .. import crew


def render_report(run, status: str, issue: str | None) -> str:
    """report.md of a finished run: summary, built, steps table, assumptions, autopilot approvals, issues, costs."""
    final = run.final or {"summary": "", "built": [], "issues": []}
    f = run.folder
    out = [f"# Report: {run.plan['name']}", "",
           f"Session {run.ls.id} · status **{status}** · {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
           "## Summary", final["summary"] or "(The run ended without an orchestrator summary.)", "",
           "## Built"]
    out += [f"- {b}" for b in final["built"]] or ["- (none listed by the orchestrator)"]
    out += ["", "### Steps", "", "| Step | Title | Agent | Status | Report |", "|---|---|---|---|---|"]
    for n, s in run.steps.items():
        link = f"[step-{n:02d}.md](steps/step-{n:02d}.md)" if n in run.reports else "-"
        who = s.get("agent_display") or crew.display("builder")
        if s.get("agent_fallback"):
            who += f" (fallback: {s.get('agent')} not available)"
        out.append(f"| {n} | {s['title']} | {who} | {s['status']} | {link} |")
    out += ["", "## Assumptions"]
    logged = [ln for ln in f.read(f.assumptions).splitlines() if ln.startswith("- ")]
    out += [ln for ln in logged if not ln.endswith("_(autopilot)_")] or ["- none"]
    if run.autopilot_log:
        out += ["", "## Approved by autopilot (no card shown)"] + [f"- {x}" for x in run.autopilot_log]
    asked = f.questions_of_run(run.ls.run_count)
    if asked:
        out += ["", "## Questions"]
        for q in asked:
            how = {"auto": "decided by the agent, Auto answers on", "timer": "timed out"}.get(q["how"], "answered by the user")
            out.append(f"- [{q['name']}](questions/{q['name']}): {one_line(q['title'], 120)} ({how}: {one_line(q['answer'], 80)})")
    issues = list(final["issues"]) + ([issue] if issue else [])
    for n in sorted(run.results):
        issues += [f"Step {n}: {i}" for i in run.results[n]["issues"]]
    out += ["", "## Issues"] + ([f"- {one_line(i, 600)}" for i in issues] or ["- none"])
    out += ["", "## Costs per agent", "",
            "| Agent | Role | Step | Input (uncached) | Output | Cache read | Cache write | Tool calls | Cost (USD) |",
            "|---|---|---|---|---|---|---|---|---|"]
    session_meters = [m for m in run.hub.meters if m.session_id == run.ls.id]
    run_meters = [m for m in session_meters if m.role != "planner"]
    for m in run_meters:
        u = m.usage
        out.append(f"| {m.name} | {m.role} | {m.step or '-'} | {u.input_tokens} | {u.output_tokens} | "
                   f"{u.cache_read_tokens} | {u.cache_write_tokens} | {m.tool_calls} | {costs.usd(m.cost_usd, symbol=False)} |")
    run.total_cost, run.planner_cost = run.hub.session_costs(run.ls.id)
    out += ["", f"Session total (orchestrator, step agents, explorer, visualizer): **{costs.usd(run.total_cost)}**",
            f"Planner (separate, not in the session total): {costs.usd(run.planner_cost)}", ""]
    return "\n".join(out)
