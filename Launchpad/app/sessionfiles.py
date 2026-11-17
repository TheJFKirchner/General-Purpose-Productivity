"""The session folder: <project>/.launchpad/<session-id>/ (one planning conversation plus its run).

    plan.md               the plan (app/plan.py format)
    flight-log.md         useful files found so far: link + one line why (Explorer results + step agents' tool)
    steps/step-NN.md      one report per builder step (written by code from submit_report)
    assumptions.md        every assumption, incl. timer auto-answers (written by code)
    operations-manual.md  routing lessons per sub-agent + its tool-call count and cost (written by code)
    report.md             the final report (orchestrator's summary + code-added assumptions, issues, costs)
    activity.log          every finished tool call: time | status | agent | tool | one-line summary
    decisions.md          decisions the user made in the app (visual picks)
    visuals/              every rendered visual option (<set>-<option>[-rN].html)

- .launchpad/ holds a .gitignore of '*' so it ignores itself in git
- The folder is created on first write; deliverables never go here
- All paths shown to agents / the UI are relative to the project folder, with forward slashes (files in an
  additional folder: absolute)
- extra = the session's additional folders (fixed at start): they count as inside the project for agents' paths,
  the Builder's write guard and the flight log; session records stay in the primary folder
"""
from __future__ import annotations

import datetime as dt
import os
import secrets
from pathlib import Path

ROOT_NAME = ".launchpad"


def new_session_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except (ValueError, OSError):
        return False


def one_line(text: str, limit: int = 300) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


class SessionFolder:
    def __init__(self, project: Path, session_id: str, extra: list[Path] | tuple = ()):
        self.project = Path(project).resolve()
        self.extra = [Path(e).resolve() for e in extra if Path(e).resolve() != self.project]
        self.id = session_id
        self.root = self.project / ROOT_NAME
        self.path = self.root / session_id
        self.plan = self.path / "plan.md"
        self.flight_log = self.path / "flight-log.md"
        self.assumptions = self.path / "assumptions.md"
        self.ops_manual = self.path / "operations-manual.md"
        self.steps = self.path / "steps"
        self.report = self.path / "report.md"
        self.activity = self.path / "activity.log"
        self.decisions = self.path / "decisions.md"
        self._logged: set[tuple[str, int]] = set()

    # ------------------------------------------------------------------ helpers
    def rel(self, p: Path | str) -> str:
        """Project-relative path with forward slashes (absolute if outside the project)."""
        p = Path(p)
        try:
            return p.resolve().relative_to(self.project).as_posix()
        except ValueError:
            return str(p)

    @property
    def folders(self) -> list[Path]:
        """The session's working folders: primary first, then the additional ones."""
        return [self.project, *self.extra]

    def resolve_in_project(self, p: str) -> Path | None:
        """A path given by an agent (relative = to the primary folder) -> absolute path inside one of the session's
        folders, else None."""
        if not str(p or "").strip():
            return None
        cand = Path(p)
        if not cand.is_absolute():
            cand = self.project / cand
        return cand.resolve() if any(inside(cand, f) for f in self.folders) else None

    def ensure(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        gi = self.root / ".gitignore"
        if not gi.exists():
            gi.write_text("# Launchpad session folders: local only\n*\n", encoding="utf-8")
        self.path.mkdir(exist_ok=True)
        return self.path

    def _append(self, file: Path, title: str, text: str) -> None:
        self.ensure()
        new = not file.exists()
        with file.open("a", encoding="utf-8", newline="\n") as f:
            if new:
                f.write(f"# {title}\n\nSession {self.id}\n\n")
            f.write(text.rstrip("\n") + "\n")

    def read(self, file: Path) -> str:
        try:
            return file.read_text(encoding="utf-8")
        except OSError:
            return ""

    # ------------------------------------------------------------------ plan
    def write_plan(self, text: str) -> Path:
        self.ensure()
        self.plan.write_text(text, encoding="utf-8", newline="\n")
        return self.plan

    # ------------------------------------------------------------------ flight log
    def add_flight_log(self, path: str, why: str, *, line: int | None = None, source: str) -> bool:
        """One link + why. False if the path is outside the project, missing, or already logged."""
        target = self.resolve_in_project(path)
        if target is None or not target.exists():
            return False
        rel = self.rel(target)
        key = (rel, int(line or 0))
        if key in self._logged:
            return False
        self._logged.add(key)
        label = f"{rel}:{line}" if line else rel
        try:
            link = os.path.relpath(target, self.path).replace(os.sep, "/")
        except ValueError:                                   # another drive (Windows): absolute link
            link = target.as_posix()
        self._append(self.flight_log, "Flight log",
                     f"- [{label}]({link}) — {one_line(why, 240)} _({source})_")
        return True

    # ------------------------------------------------------------------ assumptions / operations manual
    def add_assumption(self, text: str, *, agent: str, step: int | None, source: str) -> str:
        where = f"step {step}" if step else "planning"
        entry = f"- [{where}] {agent}: {one_line(text, 400)} _({source})_"
        self._append(self.assumptions, "Assumptions", entry)
        return entry

    def add_operations(self, *, agent: str, role: str, step: int | None, notes: str, tool_calls: int,
                       cost_usd: float) -> None:
        where = f" · step {step}" if step else ""
        body = one_line(notes, 600) if str(notes or "").strip() else "(no routing problems noted)"
        self._append(self.ops_manual, "Operations manual",
                     f"## {agent} ({role}{where})\n- tool calls: {tool_calls} · cost: ${cost_usd:.4f}\n- {body}\n")

    def add_decision(self, text: str) -> None:
        """A decision the user made in the app (e.g. a visual pick)."""
        self._append(self.decisions, "Decisions", f"- {one_line(text, 600)}")

    def add_activity(self, line: str) -> None:
        """One finished tool call: 'started | status | agent | tool | summary' (no file contents)."""
        self.ensure()
        with self.activity.open("a", encoding="utf-8", newline="\n") as f:
            f.write(line.rstrip("\n") + "\n")

    # ------------------------------------------------------------------ step reports / final report
    def step_path(self, n: int) -> Path:
        return self.steps / f"step-{n:02d}.md"

    def write_step_report(self, n: int, title: str, report: dict, *, agent: str, tool_calls: int,
                          cost_usd: float) -> Path:
        self.ensure()
        self.steps.mkdir(exist_ok=True)

        def bullets(items) -> list[str]:
            return [f"- {one_line(i, 600)}" for i in items] or ["- none"]

        lines = [f"# Step {n}: {title}", "",
                 f"Status: **{report['status']}** · builder: {agent} · tool calls: {tool_calls} · cost: ${cost_usd:.4f}",
                 "", "## Built"]
        lines += [f"- **{one_line(b['item'], 200)}**: {one_line(b['does'], 600)}" for b in report["built"]] or ["- nothing"]
        lines += ["", "## Assumptions", *bullets(report["assumptions"]), "",
                  "## Issues", *bullets(report["issues"]), "",
                  "## Notes for the orchestrator", one_line(report["notes_for_orchestrator"], 2000) or "none", "",
                  "## Routing notes", one_line(report["routing_notes"], 2000) or "none", ""]
        p = self.step_path(n)
        p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return p

    def write_report(self, markdown: str) -> Path:
        self.ensure()
        self.report.write_text(markdown, encoding="utf-8", newline="\n")
        return self.report

    def archive_run(self, k: int) -> None:
        """Before a second run in the same session: move steps/ and report.md into run-<k>/."""
        dest = self.path / f"run-{k}"
        moved = False
        for p in (self.steps, self.report):
            if p.exists():
                dest.mkdir(exist_ok=True)
                p.rename(dest / p.name)
                moved = True
        if not moved and dest.exists():
            dest.rmdir()

    def earlier_sessions(self, limit: int = 5) -> list[str]:
        """Project-relative folders of earlier sessions (newest first)."""
        if not self.root.is_dir():
            return []
        dirs = sorted((d for d in self.root.iterdir() if d.is_dir() and d.name != self.id), reverse=True)
        return [self.rel(d) for d in dirs[:limit]]
