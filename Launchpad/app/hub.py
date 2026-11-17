"""The hub: every Launchpad session, the Incoming queue, usage meters, and event broadcast to the UI.

- One LaunchSession = one planning conversation (+ its run); unique id; folder <project>/.launchpad/<id>/
- Several sessions can be in flight: new_session starts a fresh planner while earlier runs keep going
- user_message / round_answer go to the current session's planner
- Regular sessions (CLI chats: PilotChat, app/agents/claude_code/pilot.py) live beside them in `chats`
- Folders: a session or chat runs in its primary folder (cwd) plus the folders ticked as additional (minus the
  primary), fixed when it starts (extra_dirs); the session's skills are discovered from those folders (app/skills.py)
- UI -> here: user_message, round_answer, plan_approve, queue_response, queue_dismiss, get_crew,
  report_to_planner, run_stop, new_session, chat_new, chat_message, chat_set_mode, chat_stop,
  visual_pick, visual_tweak, visual_retry, set_autopilot, set_auto_answers, planner_promote, planner_choose, cli_choose,
  agent_draft, agent_create, agent_remove, chat_from_plan, set_agent_skills,
  git_scan, git_refresh, git_fetch, git_commit, git_push (Repos panel, app/gitrepos.py)
- Agent use counter: count_use(name) -> store + agent_uses event (planner session, explore, step, run, visual
  render, CLI chat)
- Planner picker (app/agents/planner/choices.py): planner_choose -> a planner nobody has written to yet takes any
  available choice at once; a running one only promotion (its top model); anything else is remembered for the next
  new plan (settings planner_harness / planner_start_model, per user). planner_choice is sent on connect and after
  every change of a planner setting or of the app's files (the rules text)
- CLI chat picker (app/agents/claude_code/choices.py, same table): cli_choose -> remembered per user (pilot_harness /
  pilot_model); chats nobody has written to yet reload at once (chat_model), chats in progress keep theirs (the
  choice is for the next new chat). cli_choice is sent on connect and after every change of those settings
- Auto answers (per session, off by default, `auto_answers` on LaunchSession): set_auto_answers; BUILDERS ONLY: while
  on, every question a plan-step worker asks (blocking too) is answered at once with the worker's own recommendation
  and shows as an auto_answer line in Incoming (auto_answered; kept in auto_lines for a reconnect, never in the
  planner chat). Planner rounds, CLI chat questions and permission cards are never touched. Turning it on answers
  the waiting step questions too
- Totals: emit_totals sends every cost total (usage scope app / session / chat; app/costs.py sums, nothing else does)
- Undefined roles (app/tally.py, per-user file beside settings.json; in memory without a user file, and always in
  memory under --fake unless that home is a temp folder): record_role_use (from the step runner) adds a use; a draft
  written after a run marks that run's uses sent back; roles_get / role_dismiss / role_merge change the list
  (roles_list); review_start / review_decide run the Role Reviewer (app/agents/role_reviewer/reviewer.py Reviews);
  agent_draft {role} adds the case as drafter context, agent_create {role} removes the entry and saves the case copy
- Connections (app/connections/): test_connection {id} runs that tool's own test script -> connection_test
- MCP library (app/mcplib.py, per-user mcp.json beside settings.json; in memory without a user file and under --fake
  unless that home is a temp folder; imports app/mcpimport.py): get_mcp, save_mcp_server, remove_mcp_server,
  test_mcp_server, list_mcp_imports, import_mcp_servers, set_agent_mcp -> mcp_library (+ mcp_imports). A server is
  tested on add, on edit, on request, and every server once in the background when the app starts
  (start_background: server startup, else the first connection). give_mcp(agent, who) right before any crew agent
  starts: its assigned servers whose last test passed; each skipped one is a system warning in that session / chat
  (once per owner, server and reason)
- here -> UI: see app/server.py header (contract)
"""
from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path
import sys
import traceback
from collections import deque

from . import connections
from . import costs
from . import mcpimport, mcplib
from . import plan as plan_mod
from . import skills as skills_mod
from . import tally as tally_mod
from .activity import log_line
from .agents import crew, folder_agents
from .agents.claude_code import choices as cli_choices
from .agents.claude_code.pilot import PilotChat
from .agents.drafter import drafter
from .agents.orchestrator.run import Run
from .agents.planner import choices
from .agents.planner.planner import PlannerChat, promotion_criteria
from .agents.role_reviewer.reviewer import Reviews, draft_context
from .agents.visualizer.visuals import VisualBoard
from .files import FileError, Files
from .gitrepos import GitRepos
from .incoming import Incoming
from .sessionfiles import SessionFolder, new_session_id
from .settings import Settings
from .store import SPECS, Store

ACTIVITY_SNAPSHOT = 300          # recent activity events replayed to a reconnecting UI
AUTO_LINES_SNAPSHOT = 200        # recent auto_answer lines (builder questions answered by Auto answers) replayed too


class LaunchSession:
    def __init__(self, hub: "Hub", project: Path | None = None, dir_id: str | None = None):
        self.hub = hub
        self.id = new_session_id()
        self.dir_id = dir_id or hub.default_dir
        self.extra_ids, extra = hub.extra_dirs(self.dir_id)      # additional folders, fixed for the session
        self.folder = SessionFolder(project or hub.settings.project, self.id, extra)   # agents, guard, records
        self.skills = skills_mod.discover(self.folder.folders, [self.dir_id, *self.extra_ids])
        self.skill_dirs = skills_mod.skill_dirs(self.folder.folders)
        self.plan_text: str | None = None
        self.run: Run | None = None
        self.run_count = 0
        self.draft_revision = 0                    # +1 per saved draft (write_plan)
        self.approved_revision = 0                 # the draft revision the latest run was started from
        self.report_sent = False                   # run report already handed to the planner
        self.autopilot = hub.settings.autopilot_default   # approve every builder permission request (no card)
        self.auto_answers = False                  # answer every question that has a recommendation with it
        self.astronaut_meter = None                # one Explorer per session (app/agents/explorer/astronaut.py)
        self.visuals = VisualBoard(self)           # visual sidecar sets (app/agents/visualizer/visuals.py)
        self.chat = PlannerChat(self)

    @property
    def running(self) -> bool:
        return self.run is not None and self.run.task is not None and not self.run.task.done()

    def started_event(self) -> dict:
        return {"type": "session_started", "session_id": self.id, "folder": self.folder.rel(self.folder.path),
                "dir_id": self.dir_id, "cwd": str(self.folder.project), "additional_dir_ids": list(self.extra_ids)}

    def skill_names(self) -> set[str]:
        return {s["name"] for s in skills_mod.active(self.skills)}

    def step_skill_fields(self, step: dict) -> dict:
        """skills (+ skills_unknown: named but not in this session's folders, ignored at run time) for UI events;
        nothing when the step names no skills (events as before)."""
        named = list(step.get("skills") or [])
        if not named:
            return {}
        unknown = [n for n in named if n not in self.skill_names()]
        return {"skills": named, **({"skills_unknown": unknown} if unknown else {})}


    def draft_event(self) -> dict:
        p = plan_mod.parse(self.plan_text)
        reg = crew.registry(self.folder.project)
        return {"type": "plan_draft", "session_id": self.id, "path": self.folder.rel(self.folder.plan),
                "markdown": self.plan_text,
                "steps": [{"n": s["n"], "title": s["title"], **crew.step_fields(s.get("agent"), self.folder.project, reg),
                           **self.step_skill_fields(s), **({"role": s["role"]} if s.get("role") else {})}
                          for s in p["steps"]],
                "revision": self.draft_revision, "previous_runs": self.run_count}

    def agent_note(self, text: str) -> str:
        """Tool-result line for steps naming an agent the run would not use (it falls back to the Builder)."""
        bad, unknown, roles = [], [], []
        have = self.skill_names()
        workers = {e["name"] for e in crew.step_agents(self.folder.project)}
        for s in plan_mod.parse(text)["steps"]:
            if s.get("agent"):
                _, reason = crew.resolve_step_agent(s["agent"], self.folder.project)
                if reason:
                    bad.append(f"step {s['n']}: {reason}")
            if s.get("role") in workers:
                roles.append(f"step {s['n']}: '{s['role']}'")
            unknown += [f"step {s['n']}: {n}" for n in s.get("skills") or [] if n not in have]
        out = ""
        if bad:
            names = ", ".join(e["name"] for e in crew.step_agents(self.folder.project))
            out += (" Note: " + "; ".join(bad) + f". Those steps would run on the Builder; step agents: {names}. "
                    "Fix with edit_plan (set_step agent) if that is not intended.")
        if unknown:
            out += (" Note: unknown skills (ignored at run time): " + "; ".join(unknown) + ". Skills: "
                    + (", ".join(sorted(have)) or "none") + ". Fix with edit_plan (set_step skills).")
        if roles:
            out += (" Note: role names that are listed step agents: " + "; ".join(roles) + ". Set agent to that name "
                    "instead (edit_plan set_step agent).")
        return out

    @property
    def draft_pending(self) -> bool:
        """A saved draft that has not been approved yet (also true for a revision written after a run)."""
        return bool(self.plan_text) and self.draft_revision > self.approved_revision

    async def save_plan(self, fields: dict) -> str:
        """write_plan tool: render + validate + save the draft; ValueError goes back to the planner."""
        if self.running:
            raise ValueError("a run is in progress for this session; wait until it finishes")
        steps = fields.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps must be a non-empty list")
        text = plan_mod.render(name=str(fields.get("name") or "").strip() or "Untitled plan",
                               goal=str(fields.get("goal") or ""), steps=[s if isinstance(s, dict) else {} for s in steps],
                               session=self.id)
        problems = plan_mod.validate(text)
        if problems:
            raise ValueError("plan not saved: " + "; ".join(problems))
        await self._store_draft(text)
        return (f"Draft {self.draft_revision} saved; the user sees it in the plan card and presses Approve to start "
                "the run. Reply in one or two lines (what the plan covers or what to decide), no recap."
                + self.agent_note(text))

    async def edit_plan(self, edits: list) -> str:
        """edit_plan tool: targeted edits to the current draft, re-validated like write_plan; a new revision."""
        if self.running:
            raise ValueError("a run is in progress for this session; wait until it finishes")
        if not self.plan_text:
            raise ValueError("there is no draft yet; call write_plan first")
        if not isinstance(edits, list) or not edits:
            raise ValueError("give a non-empty list of edits")
        try:
            text, done = plan_mod.apply_edits(self.plan_text, edits, session=self.id)
        except plan_mod.PlanError as e:
            raise ValueError(str(e)) from None
        await self._store_draft(text)
        return (f"Draft {self.draft_revision} saved ({'; '.join(done)}). The user sees the plan card: reply in one "
                "or two lines on what changed, no recap." + self.agent_note(text))

    async def _store_draft(self, text: str) -> None:
        self.folder.write_plan(text)
        self.plan_text = text
        self.draft_revision += 1
        if self.run_count:                         # a revised plan after a run = that run was sent back (tally)
            await self.hub.mark_sent_back(self.id, self.run_count)
        await self.hub.emit(self.draft_event())
        await self.hub.emit({"type": "plan_meta", "session_id": self.id, "name": plan_mod.parse(text)["name"],
                             "mode": "Plan", "status": "Draft"})


class Hub:
    def __init__(self, settings: Settings, store: Store | None = None, overridden: set | None = None):
        self.settings = settings
        self.store = store or Store(None)               # in memory unless launch.py hands over the user's file
        self.default_dir = self.store.add(settings.project)["dir_id"]   # --cwd / the launch folder
        self.overridden: set[str] = set(overridden or ())    # settings a launch option overrides this launch
        self.picker = None                               # launch.py sets a native folder picker (window mode)
        self.files = Files(self)
        self.git = GitRepos(self.store.directories)      # the Repos panel (app/gitrepos.py)
        self.git_locks: dict[str, asyncio.Lock] = {}     # one operation at a time per repo
        self.clients: dict[object, asyncio.Lock] = {}
        self.meters: list = []
        self.recent_activity: deque = deque(maxlen=ACTIVITY_SNAPSHOT)
        self.auto_lines: deque = deque(maxlen=AUTO_LINES_SNAPSHOT)     # auto_answer events, replayed on connect
        self.incoming = Incoming(self)
        self.tally = tally_mod.Tally.beside(self.store)  # undefined roles, beside settings.json (app/tally.py)
        if settings.engine == "fake" and not tally_mod.in_temp(self.tally.path):
            self.tally = tally_mod.Tally(None)           # the demo never writes a real tally
        self.reviews = Reviews(self)                     # Role Reviewer runs + latest cases
        self.mcp = mcplib.McpLibrary.beside(self.store)  # MCP library, beside settings.json (app/mcplib.py)
        if settings.engine == "fake" and not tally_mod.in_temp(self.mcp.path):
            self.mcp = mcplib.McpLibrary(None)           # the demo never writes a real MCP library
        self.mcp_started = False                         # background test of every server (once per launch)
        self.mcp_warned: set = set()                     # (owner, who, server, reason) warnings already shown
        self.connection_tests: set[str] = set()          # connection tests running now
        self.background: set[asyncio.Task] = set()
        self.mcp_tasks: dict[str, asyncio.Task] = {}      # server name -> its running (or last) test
        self.sessions: dict[str, LaunchSession] = {}   # in the order the front end letters them (Run A, B, ...)
        self.chats: dict[str, PilotChat] = {}       # regular sessions (Pilot), several may coexist
        self.current: LaunchSession = self._new()

    def directory(self, did: str | None) -> tuple[str, Path]:
        """(dir_id, path) of a connected directory; default (last used) when did is None."""
        did = did or self.default_dir
        entry = self.store.get(did)
        if entry is None:
            raise ValueError("that folder is not connected")
        path = Path(entry["path"])
        if not path.is_dir():
            raise ValueError(f"folder not found on disk: {path}")
        return did, path.resolve()

    def extra_dirs(self, primary: str | None) -> tuple[list[str], list[Path]]:
        """The additional folders for a session or chat whose primary is `primary`: (dir_ids, paths); ticked
        folders minus the primary, only those that exist on disk."""
        ids, paths = [], []
        for did in self.store.additional_ids():
            entry = self.store.get(did)
            if did == primary or entry is None or not Path(entry["path"]).is_dir():
                continue
            ids.append(did)
            paths.append(Path(entry["path"]).resolve())
        return ids, paths

    def busy(self, did: str) -> bool:
        """A run, a planner turn or a chat turn is going in that directory."""
        return (any(ls.dir_id == did and (ls.running or ls.chat.lock.locked()) for ls in self.sessions.values())
                or any(c.dir_id == did and c.lock.locked() for c in self.chats.values()))

    def settings_event(self) -> dict:
        extra = set(self.store.additional_ids())
        dirs = [{"dir_id": d["dir_id"], "path": d["path"], "name": d["name"], "exists": Path(d["path"]).is_dir(),
                 "is_default": d["dir_id"] == self.default_dir, "is_additional": d["dir_id"] in extra,
                 "busy": self.busy(d["dir_id"])}
                for d in self.store.directories()]
        values = {k: {"value": getattr(self.settings, k), "applies": spec[2], "overridden_by_launch": k in self.overridden}
                  for k, spec in SPECS.items()}
        return {"type": "settings", "directories": dirs, "values": values, "can_pick_directory": self.picker is not None,
                "additional_dir_ids": self.store.additional_ids()}

    def run_name(self, session_id: str) -> str:
        """The app's own letter for a session's run ("A", "B", ... "AA"), as the front end shows it ("Run A")."""
        n = list(self.sessions).index(session_id) + 1 if session_id in self.sessions else 0
        s = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def _new(self, did: str | None = None) -> LaunchSession:
        did, path = self.directory(did)
        ls = LaunchSession(self, path, did)
        self.sessions[ls.id] = ls
        return ls

    # ---------------------------------------------------------------- broadcast
    async def emit(self, ev: dict) -> None:
        for send, lock in list(self.clients.items()):
            try:
                async with lock:
                    await send(ev)
            except Exception:  # noqa: BLE001 -- a closed socket must not break the run
                self.clients.pop(send, None)

    async def count_use(self, name: str) -> None:
        """One more start of agent `name`: saved in the per-user store, then agent_uses {name, uses}."""
        if not name:
            return
        uses = self.store.add_use(str(name))
        await self.emit({"type": "agent_uses", "name": str(name), "uses": uses})

    async def activity(self, ev: dict, *, started: str | None = None) -> None:
        """One activity event: kept for the reconnect snapshot, logged to activity.log when finished, sent."""
        if ev.get("role") == "visual" and ev.get("tool") == "render" and ev["status"] == "started":
            await self.count_use(crew.builtin_name("visual"))     # one count per visual drawn
        self.recent_activity.append(ev)
        if ev["status"] != "started":
            owner = self.sessions.get(ev.get("session_id") or "") or self.chats.get(ev.get("chat_id") or "")
            if owner is not None:
                owner.folder.add_activity(log_line(ev, started or ev["ts"]))
        await self.emit(ev)

    def session_costs(self, session_id: str) -> tuple[float, float]:
        """A session's cost: (total = every agent but the planner, planner). The rule lives in app/costs.py."""
        return costs.session_split(self.meters, session_id)

    def snapshot_event(self) -> dict:
        return {"type": "snapshot", "current_session_id": self.current.id,
                "sessions": [{"session_id": ls.id, "dir_id": ls.dir_id, "cwd": str(ls.folder.project),
                              "folder": ls.folder.rel(ls.folder.path), "chat": list(ls.chat.history),
                              "report_sent": ls.report_sent, "running": ls.running,
                              "total_cost_usd": costs.wire(self.session_costs(ls.id)[0]),
                              "planner_cost_usd": costs.wire(self.session_costs(ls.id)[1]),
                              "visual_sets": ls.visuals.snapshot(),
                              "plan_revision": ls.draft_revision, "draft_pending": ls.draft_pending,
                              "runs": ls.run_count, "autopilot": ls.autopilot, "auto_answers": ls.auto_answers,
                              **{k: v for k, v in ls.chat.model_event().items() if k not in ("type", "session_id")}}
                             for ls in self.sessions.values()],
                "chats": [c.snapshot() for c in self.chats.values()]}

    async def emit_totals(self, meter=None) -> None:
        """Every total the page shows, summed here only (app/costs.py): usage scope app, plus the scope of the meter
        that just changed (its session: total + planner share; its CLI chat); no meter = all of them (on connect)."""
        await self.emit(costs.app_usage(self.meters))
        if meter is None:
            for sid in self.sessions:
                await self.emit(costs.session_usage(self.meters, sid))
            for cid in self.chats:
                await self.emit(costs.chat_usage(self.meters, cid))
        elif meter.session_id:
            await self.emit(costs.session_usage(self.meters, meter.session_id))
        elif meter.chat_id:
            await self.emit(costs.chat_usage(self.meters, meter.chat_id))

    async def emit_crew(self) -> None:
        agents = [{"name": m.name, "role": m.role, "status": m.status, "session_id": m.session_id}
                  for m in self.meters if m.status != "done" or (m.role == "planner" and m.session_id == self.current.id)]
        await self.emit({"type": "crew", "agents": agents})

    async def connect(self, send) -> None:
        """New UI connection: register and send a snapshot of everything in flight."""
        self.clients[send] = asyncio.Lock()
        engine = "fake engine (demo, zero tokens)" if self.settings.engine == "fake" else self.current.chat.agent.model
        snapshot = [self.snapshot_event(), self.settings_event(), self.choice_event(), self.cli_choice_event(),
                    {"type": "plan_meta", "name": "Launchpad", "mode": "Chat", "status": "Ready"},
                    {"type": "system", "text": f"Connected to the planner ({engine}). Project: {self.settings.project.name}."}]
        for ls in self.sessions.values():
            snapshot.append(ls.started_event())
            snapshot.append(ls.chat.model_event())
            if ls.run is not None:
                snapshot.append({"type": "run_started", "session_id": ls.id, "name": ls.run.plan["name"],
                                 "steps": ls.run.steps_payload(),
                                 "run": ls.run_count, "revision": ls.approved_revision, "autopilot": ls.autopilot})
                if not ls.running:
                    snapshot.append({"type": "run_finished", "session_id": ls.id, "status": ls.run.status,
                                     "report_path": ls.folder.rel(ls.folder.report), "markdown": ls.run.report_markdown,
                                     "total_cost_usd": costs.wire(ls.run.total_cost),
                                     "planner_cost_usd": costs.wire(ls.run.planner_cost)})
            if ls.draft_pending:                   # incl. a revised draft written after a finished run
                snapshot.append(ls.draft_event())
        if len(self.sessions) > 1:
            snapshot.append(self.current.started_event())       # last one = the current session
        snapshot += [c.started_event() for c in self.chats.values()]
        snapshot.append(self.roles_event())
        snapshot.append(self.mcp_event())
        snapshot += self.reviews.events()
        snapshot += [m.event() for m in self.meters] + self.incoming.open_events() + list(self.auto_lines) + list(self.recent_activity)
        lock = self.clients[send]
        async with lock:
            for ev in snapshot:
                await send(ev)
        await self.emit_crew()
        await self.emit_totals()
        self.start_background()

    def disconnect(self, send) -> None:
        self.clients.pop(send, None)

    # ---------------------------------------------------------------- UI messages
    async def handle(self, msg: dict) -> None:
        try:
            await self._handle(msg)
        except Exception as e:  # noqa: BLE001 -- show the problem instead of losing it in a task
            print(f"Launchpad error handling {msg.get('type')}:", file=sys.stderr)
            traceback.print_exc()                  # also in the console, so nothing is lost if the page misses it
            await self.system(f"Launchpad error ({msg.get('type')}): {type(e).__name__}: {e}")

    async def _handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind in ("user_message", "round_answer"):
            await self.current.chat.handle(msg)
        elif kind == "plan_approve":
            await self.approve(str(msg.get("session_id") or self.current.id))
        elif kind == "queue_response":
            if not await self.incoming.respond(msg):
                await self.emit({"type": "system", "text": "That request is no longer open."})
        elif kind == "queue_dismiss":
            pass                                                  # info cards need no answer
        elif kind == "get_crew":
            try:
                await self.emit(self.crew_event(msg.get("dir_id")))
            except ValueError as e:
                await self.system(f"Crew: {e}")
        elif kind in ("agent_draft", "agent_create", "agent_remove"):
            await self._agent_message(kind, msg)
        elif kind in ("roles_get", "role_dismiss", "role_merge", "review_start", "review_decide"):
            await self._role_message(kind, msg)
        elif kind == "test_connection":
            await self.test_connection(str(msg.get("id") or ""))
        elif kind in ("get_mcp", "save_mcp_server", "remove_mcp_server", "test_mcp_server", "list_mcp_imports",
                      "import_mcp_servers", "set_agent_mcp"):
            await self._mcp_message(kind, msg)
        elif kind == "set_agent_skills":
            try:
                self.store.set_agent_skills(str(msg.get("name") or ""), skills_mod.clean_setting(msg.get("skills")))
                await self.emit(self.crew_event(msg.get("dir_id")))
            except ValueError as e:
                await self.system(f"Crew: {e}")
        elif kind == "chat_from_plan":
            try:
                await self.chat_from_plan(str(msg.get("session_id") or self.current.id))
            except ValueError as e:
                await self.system(f"Send plan to CLI: {e}", str(msg.get("session_id") or "") or None)
        elif kind == "report_to_planner":
            await self.report_to_planner(str(msg.get("session_id") or self.current.id))
        elif kind == "run_stop":
            await self.stop(str(msg.get("session_id") or self.current.id))
        elif kind == "new_session":
            try:
                await self.new_session(msg.get("dir_id"))
            except ValueError as e:
                await self.system(f"New session: {e}")
        elif kind in ("get_settings", "set_settings", "add_directory", "remove_directory", "pick_directory"):
            await self._settings_message(kind, msg)
        elif kind in ("list_dir", "read_file", "save_file", "list_backups", "restore_backup"):
            await self._file_message(kind, msg)
        elif kind in ("git_scan", "git_refresh", "git_fetch", "git_commit", "git_push"):
            await self._git_message(kind, msg)
        elif kind == "planner_promote":
            ls = self.sessions.get(str(msg.get("session_id") or self.current.id))
            if ls is None:
                await self.system("That session is not open.")
                return
            try:
                await ls.chat.promote(by="user")
            except ValueError as e:
                await self.system(f"Planner: {e}", ls.id)
        elif kind == "planner_choose":
            await self.planner_choose(msg)
        elif kind == "cli_choose":
            await self.cli_choose(msg)
        elif kind == "set_autopilot":
            await self.set_autopilot(str(msg.get("session_id") or self.current.id), bool(msg.get("on")))
        elif kind == "set_auto_answers":
            await self.set_auto_answers(str(msg.get("session_id") or self.current.id), bool(msg.get("on")))
        elif kind in ("visual_pick", "visual_tweak", "visual_retry"):
            ls = self.sessions.get(str(msg.get("session_id") or ""))
            if ls is None:
                await self.system("That session is not open.")
                return
            try:
                if kind == "visual_pick":
                    oid = msg.get("option_id")
                    await ls.visuals.pick(str(msg.get("set_id")), None if oid is None else str(oid))
                elif kind == "visual_tweak":
                    await ls.visuals.tweak(str(msg.get("set_id")), str(msg.get("option_id")), str(msg.get("text", "")))
                else:
                    await ls.visuals.retry(str(msg.get("set_id")), str(msg.get("option_id")))
            except ValueError as e:
                await self.system(f"Visuals: {e}", ls.id)
        elif kind == "chat_new":
            try:
                await self.chat_new(msg.get("dir_id"))
            except ValueError as e:
                await self.system(f"New chat: {e}")
        elif kind in ("chat_message", "chat_set_mode", "chat_stop"):
            chat = self.chats.get(str(msg.get("chat_id") or ""))
            if chat is None:
                await self.system("That chat is not open.")
            elif kind == "chat_message":
                await chat.message(str(msg.get("text", "")))
            elif kind == "chat_set_mode":
                await chat.set_mode(str(msg.get("mode", "")))
            else:
                await chat.stop()

    async def chat_new(self, dir_id: str | None = None, *, mode: str | None = None, extra: dict | None = None) -> PilotChat:
        did, path = self.directory(dir_id)
        chat = PilotChat(self, path, did)
        if mode:
            chat.agent.permission_mode = chat.mode = mode       # before the first turn: the session starts in it
        self._used(did)
        self.chats[chat.id] = chat
        await self.emit({**chat.started_event(), **(extra or {})})
        await chat.meter.push()
        return chat

    async def chat_from_plan(self, session_id: str) -> PilotChat:
        """Send plan to CLI: a new CLI chat in the session's folder, in Plan mode, with the plan as
        its first message (an alternative to Approve; the draft stays approvable)."""
        ls = self.sessions.get(session_id)
        if ls is None:
            raise ValueError("that session is not open")
        if not ls.plan_text:
            raise ValueError("there is no plan draft in that session yet")
        chat = await self.chat_new(ls.dir_id, mode="plan", extra={"from_session_id": ls.id})
        text = (f"Here is a plan drafted with the Launchpad planner (saved at {ls.folder.rel(ls.folder.plan)}). "
                "Check it against the project, then propose how you will carry it out.\n\n" + ls.plan_text.strip())
        await chat.message(text, echo=True)
        return chat

    # ---------------------------------------------------------------- agents (Crew)
    def crew_event(self, dir_id: str | None = None) -> dict:
        """crew_list for a connected folder (default: the current session's): built-ins + its own agents."""
        did, path = self.directory(dir_id or self.current.dir_id)
        extra_ids, extra = self.extra_dirs(did)
        found = skills_mod.discover([path, *extra], [did, *extra_ids])
        return crew.crew_list(self.settings.engine, self.settings.project, self.settings, self.store,
                              folder=path, dir_id=did, skills_found=found)

    async def registry_changed(self, dir_id: str) -> None:
        """A folder's agents were added, edited or removed: fresh crew_list; its planners hear it on their next turn."""
        for ls in self.sessions.values():
            if ls.dir_id == dir_id:
                ls.chat.registry_changed()
        await self.emit(self.crew_event(dir_id))

    async def _agent_message(self, kind: str, msg: dict) -> None:
        reply = {"agent_draft": "agent_drafted", "agent_create": "agent_saved", "agent_remove": "agent_removed"}[kind]
        try:
            did, path = self.directory(msg.get("dir_id"))
        except ValueError as e:
            await self.emit({"type": reply, "ok": False, "error": str(e), **({"problems": []} if kind == "agent_create" else {})})
            return
        role = str(msg.get("role") or "").strip() or None          # define path: the tally role being defined
        try:
            if kind == "agent_draft":
                text, context = str(msg.get("text") or ""), ""
                if role:
                    context = draft_context(self.tally.get(role), self.reviews.cases.get(role))
                    text = text.strip() or f"An agent for the recurring role '{role}'."
                fields, usage = await drafter.draft_with_usage(self, path, text, context)
                await self.emit({"type": reply, "ok": True, "dir_id": did, "fields": fields, "usage": usage,
                                 **({"role": role} if role else {})})
            elif kind == "agent_create":
                name = folder_agents.create(self.files, did, path, msg.get("fields") or {})
                extra = await self._role_defined(role, name, path) if role or self.tally.get(name) else {}
                await self.emit({"type": reply, "ok": True, "dir_id": did, "name": name, **extra})
                await self.registry_changed(did)
            else:
                name = folder_agents.remove(self.files, did, path, str(msg.get("name") or ""))
                await self.emit({"type": reply, "ok": True, "dir_id": did, "name": name})
                await self.registry_changed(did)
        except folder_agents.AgentFormError as e:
            ev = {"type": reply, "ok": False, "dir_id": did, "error": str(e), **({"role": role} if role else {})}
            if kind == "agent_create":
                ev["problems"] = e.problems
            elif kind == "agent_remove":
                ev["name"] = str(msg.get("name") or "")
            await self.emit(ev)

    # ---------------------------------------------------------------- undefined roles (tally + Role Reviewer)
    def roles_event(self) -> dict:
        return self.tally.list_event(self.reviews.running)

    async def emit_roles(self) -> None:
        try:
            await self.emit(self.roles_event())
        except OSError as e:                                      # an unreadable tally file must not break anything
            await self.system(f"Roles: could not read the tally ({e})")

    async def record_role_use(self, name: str, *, use: dict, sample: str) -> None:
        """One plan step ran on the Builder under role `name` (or a missing agent's name): tally it, then roles_list.
        Never raises: a tally that cannot be written must not stop a run."""
        try:
            self.tally.record_use(name, use=use, sample=sample, base_agent=crew.display("builder"),
                                  purpose=crew.BUILTIN_PURPOSE["builder"])
        except (OSError, tally_mod.TallyError) as e:
            await self.system(f"Roles: the use of '{name}' was not recorded ({e})")
            return
        await self.emit_roles()

    async def mark_sent_back(self, session_id: str, run: int) -> None:
        try:
            changed = self.tally.mark_sent_back(session_id, run)
        except OSError:
            return
        if changed:
            await self.emit_roles()

    async def _role_defined(self, role: str | None, agent: str, path: Path) -> dict:
        """agent_create succeeded: the role's entry goes (and an entry named like the new agent), the case is saved
        beside the agent -> extra agent_saved fields {role, case_path}."""
        out: dict = {}
        if role:
            out["role"] = role
            copy = self.reviews.defined(role, agent, path, path.name)
            if copy:
                out["case_path"] = copy
            self.tally.remove(role)
        if agent != role:
            self.tally.remove(agent)
        await self.emit_roles()
        return out

    async def _role_message(self, kind: str, msg: dict) -> None:
        role = str(msg.get("role") or "").strip()
        try:
            if kind == "roles_get":
                pass
            elif kind == "role_dismiss":
                self.tally.dismiss(role)
            elif kind == "role_merge":
                self.tally.merge(role, str(msg.get("into") or "").strip())
                if role in self.reviews.cases:
                    self.reviews.cases.pop(role)
            elif kind == "review_start":
                await self.reviews.start(role)            # sends its own events, roles_list included
                return
            elif kind == "review_decide":
                await self.reviews.decide(role, str(msg.get("decision") or ""))
                return
        except tally_mod.TallyError as e:
            await self.system(f"Roles: {e}")
        await self.emit_roles()

    # ---------------------------------------------------------------- connections + MCP library
    async def test_connection(self, cid: str) -> None:
        """One CLI tool's own test script (app/connections/) -> connection_test. One run per tool at a time."""
        if connections.find(cid) is None:
            await self.emit({"type": "connection_test", "id": cid, "installed": False, "version": None,
                             "reachable": None, "usable": False, "detail": f"Unknown connection '{cid}'."})
            return
        if cid in self.connection_tests:
            return                                          # the running test's result answers this click too
        self.connection_tests.add(cid)
        try:
            await self.emit(await connections.run(cid, self.settings.engine))
        finally:
            self.connection_tests.discard(cid)

    def mcp_event(self, error: str | None = None) -> dict:
        extra = {"connections": connections.listing(), "import_sources": mcpimport.listing()}
        if error:
            extra["error"] = error
        try:
            return self.mcp.event(**extra)
        except OSError as e:                                # an unreadable file must not break the page
            return {"type": "mcp_library", "servers": [], "assignments": {}, **extra,
                    "error": f"could not read the MCP library ({e})"}

    def _spawn(self, coro) -> asyncio.Task:
        t = asyncio.get_running_loop().create_task(coro)
        self.background.add(t)
        t.add_done_callback(self.background.discard)
        return t

    def start_background(self) -> None:
        """Re-test every server in the library once per launch, in the background (statuses arrive as mcp_library)."""
        if self.mcp_started:
            return
        self.mcp_started = True
        if self.mcp.names():
            self._spawn(self.mcp_test_all())

    def mcp_start_test(self, name: str, *, restart: bool = False, gate=None) -> asyncio.Task:
        """One test task per server. A test already running answers a new request too; restart (after a save)
        cancels it and tests the new config once it has stopped."""
        running = self.mcp_tasks.get(name)
        if running is not None and not running.done():
            if not restart:
                return running
            running.cancel()
        t = self._spawn(self.mcp_test(name, after=running if restart else None, gate=gate))
        self.mcp_tasks[name] = t
        return t

    async def mcp_idle(self) -> None:
        """Wait until no MCP test is running (tests, shutdown)."""
        while any(not t.done() for t in self.mcp_tasks.values()):
            await asyncio.gather(*self.mcp_tasks.values(), return_exceptions=True)

    async def mcp_test(self, name: str, *, after: asyncio.Task | None = None, gate=None) -> None:
        """Start the server, list its tools, stop it (agentlib, zero tokens): status testing, then the result."""
        if after is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await after
        async with gate or contextlib.nullcontext():
            server = self.mcp.get(name)
            if server is None:
                return
            self.mcp.testing.add(name)
            await self.emit(self.mcp_event())
            try:
                try:
                    result = await mcplib.TESTER(mcplib.agent_config(server))
                except Exception as e:  # noqa: BLE001 -- a tester bug is a failed test, never a crash
                    result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                now = self.mcp.get(name)
                if now is not None and (now.get("kind"), now.get("config")) == (server.get("kind"), server.get("config")):
                    self.mcp.set_result(name, result)       # not edited or removed meanwhile
            finally:
                self.mcp.testing.discard(name)
            await self.emit(self.mcp_event())

    async def mcp_test_all(self, limit: int = 4) -> None:
        gate = asyncio.Semaphore(limit)
        tasks = [self.mcp_start_test(n, gate=gate) for n in self.mcp.names()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _mcp_message(self, kind: str, msg: dict) -> None:
        name = str(msg.get("name") or "").strip()
        try:
            if kind == "save_mcp_server":
                saved = self.mcp.save(msg.get("server") or {}, msg.get("original_name"))
                orig = str(msg.get("original_name") or "").strip()
                if orig and orig != saved and orig in self.mcp_tasks:
                    self.mcp_tasks.pop(orig).cancel()       # renamed: the old name's test is moot
                await self.emit(self.mcp_event())           # the saved server (untested) at once
                self.mcp_start_test(saved, restart=True)    # tested on add and on edit (testing, then the result)
                return
            if kind == "remove_mcp_server":
                self.mcp.remove(name)
                if name in self.mcp_tasks:
                    self.mcp_tasks.pop(name).cancel()
            elif kind == "test_mcp_server":
                if self.mcp.get(name) is None:
                    raise ValueError(f"there is no server named '{name}'")
                self.mcp_start_test(name)                   # sends mcp_library (testing), then the result
                return
            elif kind == "list_mcp_imports":
                sid = str(msg.get("source") or "")
                folders = [Path(d["path"]) for d in self.store.directories() if Path(d["path"]).is_dir()]
                cands = await asyncio.to_thread(mcpimport.candidates, sid, folders)
                await self.emit({"type": "mcp_imports", "source": sid,
                                 "servers": mcpimport.page_view(cands, set(self.mcp.names()))})
                return
            elif kind == "import_mcp_servers":
                await self._mcp_import(str(msg.get("source") or ""), msg.get("names"))
                return
            elif kind == "set_agent_mcp":
                self.mcp.set_agent(str(msg.get("agent") or ""), msg.get("servers"))
        except ValueError as e:
            await self.emit(self.mcp_event(error=str(e)))
            if kind != "save_mcp_server":
                await self.system(f"MCP: {e}")
            return
        await self.emit(self.mcp_event())

    async def _mcp_import(self, sid: str, names) -> None:
        """Copy the ticked candidates into the library (a name already there is skipped), then test each one."""
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ValueError("names must be a list of server names")
        folders = [Path(d["path"]) for d in self.store.directories() if Path(d["path"]).is_dir()]
        cands = {c["name"]: c for c in await asyncio.to_thread(mcpimport.candidates, sid, folders)}
        added, problems = [], []
        for n in dict.fromkeys(names):
            c = cands.get(n)
            if c is None:
                problems.append(f"{n}: no longer found in {mcpimport.source(sid)['name']}")
            elif self.mcp.get(n) is not None:
                problems.append(f"{n}: already in the library (skipped)")
            else:
                try:
                    added.append(self.mcp.save({"name": n, "kind": c["kind"], "config": c["config"]}))
                except ValueError as e:
                    problems.append(f"{n}: {e}")
        if problems:
            await self.system("MCP import: " + "; ".join(problems))
        await self.emit(self.mcp_event(error="; ".join(problems) if problems and not added else None))
        for n in added:
            self.mcp_start_test(n)

    async def give_mcp(self, agent, *, who: str, session_id: str | None = None, chat_id: str | None = None,
                       name: str | None = None) -> list[str]:
        """Right before `agent` starts: its assigned MCP servers whose last test passed (crew.attach_mcp). Each
        skipped server -> one system warning in that session / chat (once per owner, agent, server and reason);
        returns the warning lines (the step runner also puts them in the step report). Never raises."""
        try:
            skipped = crew.attach_mcp(self, agent, name)
        except Exception as e:  # noqa: BLE001 -- an unreadable library must not stop a run
            skipped = [{"server": "(library)", "reason": f"the MCP library could not be read ({e})"}]
        lines = []
        for s in skipped:
            text = f"MCP server '{s['server']}' was not given to the {who}: {s['reason']}. It runs without it."
            lines.append(text)
            key = (session_id or chat_id, who, s["server"], s["reason"])
            if key in self.mcp_warned:
                continue
            self.mcp_warned.add(key)
            ev = {"type": "system", "text": text}
            if session_id:
                ev["session_id"] = session_id
            if chat_id:
                ev["chat_id"] = chat_id
            await self.emit(ev)
        return lines

    async def _settings_message(self, kind: str, msg: dict) -> None:
        try:
            if kind == "set_settings":
                patch = dict(msg.get("patch") or {})
                if "default_dir_id" in patch:                             # "Make default"
                    did = str(patch.pop("default_dir_id") or "")
                    if not self.store.get(did):
                        raise ValueError("that folder is not connected")
                    self._used(did)
                if "additional_dir_ids" in patch:                         # the "Additional" ticks
                    self.store.set_additional(patch.pop("additional_dir_ids"))
                if "planner_harness" in patch:
                    self._check_harness(patch["planner_harness"])
                if patch.get("pilot_harness"):                           # empty = the launch engine's CLI
                    self._check_harness(patch["pilot_harness"])
                clean = self._apply_settings(patch)                      # validated + saved; live
                if any(k in choices.PLANNER_SETTINGS for k in clean):
                    await self.planner_settings_changed()
                if any(k in cli_choices.CLI_SETTINGS for k in clean):
                    await self.cli_settings_changed()
            elif kind == "add_directory":
                self.store.add(msg.get("path") or "")
            elif kind == "remove_directory":
                did = str(msg.get("dir_id") or "")
                if self.busy(did):
                    raise ValueError("a session is running in that folder; stop it first")
                self.store.remove(did)                                   # never touches the disk folder
                if self.default_dir == did:
                    self.default_dir = self.store.default_id()
            elif kind == "pick_directory":
                path = await asyncio.to_thread(self.picker) if self.picker else None
                await self.emit({"type": "directory_picked", "path": path})
                return
        except ValueError as e:
            await self.system(f"Settings: {e}")
        await self.emit(self.settings_event())

    async def _file_message(self, kind: str, msg: dict) -> None:
        root, path = str(msg.get("root") or ""), str(msg.get("path") or "")
        try:
            if kind == "list_dir":
                await self.emit(self.files.list_dir(root, path))
            elif kind == "read_file":
                await self.emit(self.files.read(root, path))
            elif kind == "list_backups":
                await self.emit(self.files.backups(root, path))
            else:
                if kind == "save_file":
                    ev = self.files.save(root, path, msg.get("text"), msg.get("base_version"))
                else:
                    ev = self.files.restore(root, path, msg.get("backup_id"))
                await self.emit(ev)
                if root == "app":                                        # agent files / criteria changed
                    await self.emit(self.crew_event())
                    await self.emit(self.choice_event())                 # the picker's rules text
                elif re.match(r"^\.claude/agents/[^/]+\.md$", ev.get("path") or ""):   # a folder agent edited
                    await self.registry_changed(root)
        except FileError as e:
            err = {"type": "file_error", "root": root, "path": path, "code": e.code, "message": e.message}
            if e.current is not None:
                err["current"] = e.current
            await self.emit(err)
        except OSError as e:
            await self.emit({"type": "file_error", "root": root, "path": path, "code": "not_found", "message": str(e)})

    async def _git_message(self, kind: str, msg: dict) -> None:
        """Repos panel: git runs off the event loop (app/gitrepos.py); one operation at a time per repo."""
        if kind == "git_scan":
            await self.emit(await asyncio.to_thread(self.git.scan))
            return
        rid = str(msg.get("repo_id") or "")
        lock = self.git_locks.setdefault(rid, asyncio.Lock())
        async with lock:
            await self.emit(await asyncio.to_thread(self.git.run, kind[len("git_"):], msg))

    # ---------------------------------------------------------------- planner picker
    def choice_event(self) -> dict:
        """planner_choice: harness-and-model options (availability from agentlib), the remembered choice for new
        plans, auto-promote and the promotion rules (read-only text)."""
        try:
            text, path = promotion_criteria(self.settings)
            rules = {"markdown": text, "path": crew.shown_path(path)}
        except OSError:
            rules = {"markdown": "", "path": None}
        return choices.choice_event(self.settings, rules, self.overridden)

    def _apply_settings(self, patch: dict) -> dict:
        """Validate + save setting values (per user) and apply them to this launch (over a launch option)."""
        clean = self.store.set_values(patch)
        for k, v in clean.items():
            setattr(self.settings, k, v)                         # live; new sessions read it at start
            self.overridden.discard(k)
        return clean

    @staticmethod
    def _check_harness(name) -> None:
        if not choices.harness(str(name or "")):
            raise ValueError(f"unknown harness {name!r}")
        if not choices.harness_available(str(name)):
            raise ValueError(f"{choices.harness_label(str(name))} is {choices.NOT_AVAILABLE}")

    async def planner_settings_changed(self) -> None:
        """A planner setting changed: planners nobody has written to yet reload with it (their planner_model is sent
        again); then a fresh planner_choice."""
        for ls in self.sessions.values():
            if not ls.chat.started:
                ls.chat.configure()
                await self.emit(ls.chat.model_event())
        await self.emit(self.choice_event())

    async def planner_choose(self, msg: dict) -> None:
        """The picker: option_id (choices.option_id) for session_id (default the current one). Not started yet ->
        remembered and applied at once; the session's top model while it runs on its start model -> promotion by
        hand (nothing remembered); anything else -> remembered for the next new plan (the page says so)."""
        ls = self.sessions.get(str(msg.get("session_id") or "")) or self.current
        opt = choices.find(str(msg.get("option_id") or ""), self.settings)
        if opt is None or not opt["available"]:
            what = opt["label"] + " is " + choices.NOT_AVAILABLE if opt else "unknown choice"
            await self.system(f"Planner: {what}.", ls.id)
            await self.emit(self.choice_event())
            return
        if self.settings.planner_model:
            await self.system("Planner: the model is pinned for this launch (--model); start Launchpad without it "
                              "to choose.", ls.id)
            await self.emit(self.choice_event())
            return
        chat = ls.chat
        if (chat.started and opt["harness"] == chat.harness and opt["model"] == chat.top_model
                and opt["model"] != chat.model and chat.can_promote()):
            try:
                await chat.promote(by="user")                    # sends planner_model
            except ValueError as e:
                await self.system(f"Planner: {e}", ls.id)
                await self.emit(chat.model_event())
            return
        self._apply_settings({"planner_harness": opt["harness"], "planner_start_model": opt["model"]})
        await self.planner_settings_changed()

    # ---------------------------------------------------------------- CLI chat picker
    def cli_choice_event(self) -> dict:
        """cli_choice: the CLI chat's CLI-and-model options (same table as the planner's) and what the next new chat
        starts on (settings pilot_harness + pilot_model, per user)."""
        return cli_choices.choice_event(self.settings, self.overridden)

    async def cli_settings_changed(self) -> None:
        """pilot_harness / pilot_model changed: chats nobody has written to yet reload with it (chat_model); chats in
        progress keep theirs (the choice is for the next new chat); then a fresh cli_choice."""
        for chat in self.chats.values():
            if not chat.started:
                chat.configure()
                await self.emit(chat.model_event())
        await self.emit(self.cli_choice_event())

    async def cli_choose(self, msg: dict) -> None:
        """The CLI chat's picker: option_id (choices.option_id) -> remembered per user (pilot_harness + pilot_model);
        chats nobody has written to take it at once, a chat in progress keeps its own (the page says so). Independent
        of the planner's choice."""
        opt = cli_choices.find(str(msg.get("option_id") or ""), self.settings)
        if opt is None or not opt["available"]:
            what = opt["label"] + " is " + choices.NOT_AVAILABLE if opt else "unknown choice"
            await self.system(f"CLI: {what}.")
            await self.emit(self.cli_choice_event())
            return
        self._apply_settings({"pilot_harness": opt["harness"], "pilot_model": opt["model"]})
        await self.cli_settings_changed()

    async def system(self, text: str, session_id: str | None = None) -> None:
        await self.emit({"type": "system", "text": text, **({"session_id": session_id} if session_id else {})})

    def _used(self, did: str) -> None:
        """The default directory = the last one a session or chat started in (saved for the next launch)."""
        self.default_dir = did
        self.store.set_default(did)

    async def new_session(self, dir_id: str | None = None) -> LaunchSession:
        self.current = self._new(dir_id)
        self._used(self.current.dir_id)
        await self.emit(self.current.started_event())
        await self.emit(self.current.chat.model_event())
        await self.emit({"type": "plan_meta", "session_id": self.current.id, "name": "New session",
                         "mode": "Chat", "status": "Ready"})
        await self.emit_crew()
        await self.system("New planning session. Earlier runs keep going.", self.current.id)
        return self.current

    async def approve(self, session_id: str) -> None:
        ls = self.sessions.get(session_id)
        if ls is None or not ls.plan_text:
            await self.system("No draft plan to approve yet.", session_id)
            return
        if ls.running:
            await self.system("This session's run is already going.", session_id)
            return
        if not ls.draft_pending:
            await self.system("There is no new draft to approve: the current plan already ran. Ask the planner "
                              "for a revised plan first.", session_id)
            return
        ls.approved_revision = ls.draft_revision
        if ls.run_count:
            ls.folder.archive_run(ls.run_count)
        text = plan_mod.set_status(ls.plan_text, plan_status="approved")
        for s in plan_mod.parse(text)["steps"]:
            text = plan_mod.set_status(text, step=s["n"], step_status="todo")
        ls.folder.write_plan(text)
        ls.plan_text = text
        ls.run_count += 1
        ls.run = Run(ls)
        await self.emit({"type": "run_started", "session_id": ls.id, "name": ls.run.plan["name"],
                         "steps": ls.run.steps_payload(),
                         "run": ls.run_count, "revision": ls.approved_revision, "autopilot": ls.autopilot})
        await self.emit({"type": "plan_meta", "session_id": ls.id, "name": ls.run.plan["name"],
                         "mode": "Run", "status": "Running"})
        ls.run.task = asyncio.create_task(ls.run.go(), name=f"launchpad-run-{ls.id}")

    async def set_autopilot(self, session_id: str, on: bool) -> None:
        """Valid before launch and during a run. Turning it on approves the run's open permission cards."""
        ls = self.sessions.get(session_id)
        if ls is None:
            await self.system("That session is not open.")
            return
        ls.autopilot = on
        await self.emit({"type": "autopilot", "session_id": ls.id, "on": on})
        if on:
            await self.incoming.resolve_open(ls.id, kind="permission", answer="allow", by="autopilot")

    async def set_auto_answers(self, session_id: str, on: bool) -> None:
        """Per-session switch, for builders only. Turning it on answers the plan-step questions already waiting."""
        ls = self.sessions.get(session_id)
        if ls is None:
            await self.system("That session is not open.")
            return
        ls.auto_answers = on
        await self.emit({"type": "auto_answers", "session_id": ls.id, "on": on})
        if on:
            await self.incoming.auto_open(ls.id)

    async def auto_answered(self, session_id: str, *, id: str, agent: str, step: int | None, title: str,
                            answer: str) -> None:
        """One plan-step question decided by its worker under Auto answers: one auto_answer line, shown in Incoming
        (kept for a reconnect; never in the planner chat)."""
        ls = self.sessions.get(session_id)
        if ls is None:
            return
        ev = {"type": "auto_answer", "session_id": ls.id, "id": id, "agent": agent, "step": step, "title": title,
              "answer": answer}
        self.auto_lines.append(ev)
        await self.emit(ev)

    async def stop(self, session_id: str) -> None:
        ls = self.sessions.get(session_id)
        if ls is None or not ls.running:
            await self.system("No run is going in that session.", session_id)
            return
        await self.incoming.cancel_session(session_id)
        ls.run.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ls.run.task

    async def report_to_planner(self, session_id: str) -> None:
        ls = self.sessions.get(session_id)
        if ls is None or ls.run is None or ls.running:
            await self.system("There is no finished run report for that session yet.", session_id)
            return
        self.current = ls
        ls.report_sent = True
        msg = (f"[Launchpad] The run finished ({ls.run.status}). Report ({ls.folder.rel(ls.folder.report)}):\n\n"
               f"{ls.run.report_markdown}\n\nSummarise it in a few lines and ask the user what to change next.")
        await ls.chat.handle({"type": "user_message", "text": msg, "history": "Run report sent to the planner."})

    async def close(self) -> None:
        for t in list(self.background):
            t.cancel()
        for ls in self.sessions.values():
            await ls.visuals.close()
            if ls.running:
                ls.run.task.cancel()
            with contextlib.suppress(Exception):
                await ls.chat.close()
        for chat in self.chats.values():
            if chat.turn_task is not None:
                chat.turn_task.cancel()
            await chat.close()
