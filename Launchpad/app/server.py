"""Launchpad app server: serves the Orbit page and connects it to the hub over a localhost websocket.

- Security: binds 127.0.0.1; websocket needs ?code=<access code> and Origin http://127.0.0.1:<port>
- All agent work lives in the hub (app/hub.py); this file only moves JSON in and out
- Websocket contract (authoritative; the prototype header follows it)
- Agent display names: Planner, Explorer (role astronaut), Orchestrator, Builder, Visualizer (role visual),
  Claude Code (role pilot); folder agents: their name with dashes as spaces ("copy-reviewer" -> "Copy reviewer")
  here -> UI
    snapshot {current_session_id, sessions:[{session_id, dir_id, cwd, folder, chat:[...], report_sent, running, total_cost_usd,
              planner_cost_usd, visual_sets:[...], plan_revision, draft_pending, runs, autopilot,
              model, promoted, reason, by}], chats:[{id, dir_id, mode, model, cwd, busy, history:[{role: user|assistant, markdown}]}]}
             (first event on every connection; then the replay events below)
             planner chat entries: {role: user|assistant|system, text} · {role: round, round:{id, round, questions}}
             · {role: answers, roundId, answers, skipped}
    planner_message {text, session_id} · typing {on} · question_round {id, round, questions:[{id,title,body,rec,options}]}
    usage {scope: "app", tokens, cost, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}
          (= the plain sum of every agent_usage, all sessions and chats incl. the planner; tokens = the four counts,
           mostly cache reads; input_tokens = uncached input only) · crew {agents:[{name, role, status, session_id}]}
    plan_meta {name, mode, status} · system {text, session_id?, chat_id?}
    session_started {session_id, folder, dir_id, cwd}  (cwd = the connected folder the session runs in)
    settings {directories:[{dir_id, path, name, exists, is_default, busy}], values:{<setting>: {value,
              applies: now|new_sessions, overridden_by_launch}}, can_pick_directory}  (on connect and after any change)
      - settings: question_timeout_s, permission_timeout_s, visual_model (now); autopilot_default,
        planner_start_model, planner_top_model, promotion_window_turns, promotion_criteria_path, pilot_model
        (new_sessions). Stored in <home>/.launchpad/settings.json; a launch option overrides for that launch
        (overridden_by_launch) until the setting is changed from the page
    directory_picked {path: string|null}  (reply to pick_directory; the page then sends add_directory)
    dir_listing {root, path, entries:[{name, type: dir|file, size, mtime, kind: markdown|text|binary|too_large|null,
                editable}]}  (dirs: kind null)
    file_content {root, path, kind, text?, size, mtime, version, editable, applies: now|new_sessions|null,
                  validates_as: agent|plan|null}
    file_saved {root, path, version, backup_id (null for a new file), applies}
    file_error {root, path, code: conflict|invalid|not_allowed|not_found|too_large|binary, message,
                current?: {text, version}}  (current on conflict)
    backups {root, path, items:[{backup_id, saved_at, size}]}  (newest first)
    plan_draft {session_id, path, markdown, steps:[{n, title, agent, agent_display, agent_purpose, agent_fallback?}],
                revision, previous_runs}
      - agent = the step's agent name, null = the Builder; agent_display = who will run it ("Builder" when null);
        agent_purpose = that agent's purpose (planning|exploring|building|reviewing; "building" for the Builder):
        colour steps by this, not by a folder's crew_list;
        agent_fallback: true = the named agent is missing / broken / not a step worker here, so the Builder runs it
      - revision counts drafts in the session (1, 2, ...); previous_runs > 0 = a revised plan after a run (send-back).
        Every new draft can be approved, also after a finished run; a reconnect replays a pending draft after the
        finished run's run_started / run_finished
    run_started {session_id, name, steps:[{n, title, status, agent, agent_display, agent_purpose, agent_fallback?}], run, revision,
                 autopilot}
      - plan_approve answers: run_started (success), or system {text, session_id}: "No draft plan to approve yet." /
        "This session's run is already going." / "There is no new draft to approve: ..." (already ran)
      - a second run in a session first moves steps/ and report.md into run-<k>/
    planner_model {session_id, model, promoted: bool, reason: string|null, by: "criteria"|"user"|null}
      - sent at session start (replayed on reconnect) and on promotion; starts on the start model (default sonnet),
        promoted at most once to the target (default opus): by the planner within its first N turns, or by the user
    autopilot {session_id, on}  (after set_autopilot; on = every builder permission request approved without a card)
    step_update {session_id, n, status: todo|in_progress|blocked|done|failed, agent, agent_display, agent_purpose,
                 agent_fallback?,
                 built?, report_path?}
      - from in_progress on, agent_display = the agent actually running the step (after any fallback); a fallback
        is also an issue in the step report and report.md (Steps table has an Agent column)
    queue_item {id, session_id, chat_id, kind: question|permission|plan|info, agent, agent_id, step, title, body,
                rec, options?, blocking, timeout_s, expires_at}
      - agent = plain display name of the step's agent ("Builder", or a folder agent's); the page adds the step
      - run items: session_id set, chat_id null; chat items: chat_id set, session_id null, timeout_s null
      - permission: rec null (no recommended choice), plus tool; run cards also command; chat cards also
        suggestions:[{label, remember: session|project_local}]; body = command or path summary
      - builder permission cards: timeout_s = the permission timeout (default 180), expires_at set, blocking false;
        raised for deny-listed shell commands and for writes outside the project / into .launchpad/ or .git/
      - plan (chats): markdown = the proposed plan
    queue_resolved {id, answer, by: user|timer|autopilot}
      - builder permission timer: {answer: "deny", by: "timer"}; autopilot switched on: {answer: "allow", by: "autopilot"}
    agent_usage {session_id, chat_id, agent_id, role: planner|astronaut|orchestrator|builder|pilot|visual|drafter, name, step,
                 status: working|idle|done, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                 cost_usd, tool_calls, by_model?: [{model, cost_usd, input_tokens, output_tokens, cache_read_tokens,
                 cache_write_tokens}]}  (+ old planner-header fields); one Explorer (role astronaut) per session, idle between trips;
                 the planner's by_model splits its one usage entry across models (e.g. Sonnet, then Opus)
                 - role builder = any step agent (the Builder or a folder agent; name = its display name)
                 - role drafter = the agent drafter (agent_draft): session_id and chat_id both null; counted in the
                   app-wide usage only
    activity {id, session_id, chat_id, agent_id, role, name, step, tool, summary, status: started|done|denied|failed, ts,
              auto?: true (final event of a call autopilot approved)}
             (one per tool call: "started", then the same id with the final status; summary = command / path /
              pattern / short label, max 140 chars, never file contents; recent ones replayed on reconnect;
              finished calls also go to <session or chat folder>/activity.log)
    run_finished {session_id, status: done|stopped|failed, report_path, markdown, total_cost_usd, planner_cost_usd}
      - session total = orchestrator + builders + astronauts + visual agent; the planner is separate (planner_cost_usd), the same
        definition in report.md and the snapshot
    crew_list {dir_id, tool_choices:[tool names the new-agent form may offer], agents:[{name, display_name, role,
               purpose: planning|exploring|building|reviewing, uses, builtin, description, model, source_path,
               instructions, builtin_tools, custom_tools:[{name, description}], mcp_servers, disallowed_tools, warnings,
               gated_tools, setup: lean|project, engine_prompt, prompt_note, root, path (relative), editable,
               step_worker? (folder agents), promotion? (planner): {start_model, target_model, window_turns,
               criteria (markdown), criteria_path, root, path, editable}}]}
      - the six built-ins first (builtin true, root "app"), then the agents of the connected folder dir_id
        (builtin false, role null, root = dir_id, path ".claude/agents/<file>.md", purpose from the file's
        `purpose:` field, default building; a broken file is listed with its problems in warnings and
        step_worker false). Built-in purposes: Planner + Visualizer planning, Explorer exploring, Builder +
        Orchestrator + Claude Code building
      - uses = times the agent was started (per user, survives restarts; keyed by agent name)
      - folder agents as Launchpad runs them: exploring / reviewing = read-only (no write, edit or shell tools);
        building = the Builder's gated tools and checks; custom_tools = Launchpad's step tools
      - sent again after a save of one of the app's files, after agent_create / agent_remove, and after a save of a
        folder's .claude/agents/*.md (that folder's list)
    agent_uses {name, uses}  (whenever a count changes: planner session started, explore, step, run, visual render,
                Claude Code chat's first turn)
    agent_drafted {ok: true, dir_id, fields: {name, description, purpose, model, tools:[..], instructions}}
                  | {ok: false, dir_id?, error}   (reply to agent_draft; fields are a suggestion the user edits)
    agent_saved {ok: true, dir_id, name} then crew_list | {ok: false, dir_id?, error, problems:[..]}
    agent_removed {ok: true, dir_id, name} then crew_list | {ok: false, dir_id?, name?, error}
    chat_started {chat_id, mode, model, cwd, dir_id, from_session_id?} · chat_typing {chat_id, on} · chat_delta {chat_id, text}
      - from_session_id: set when chat_from_plan opened the chat (mode "plan"); the plan follows as
        chat_message {chat_id, role: user, markdown} (also in the snapshot history), then the usual turn events
    chat_message {chat_id, role: assistant|user, markdown}  (role user only for text the page did not type: chat_from_plan) · chat_mode {chat_id, mode} (authoritative, incl. engine changes)
    chat_done {chat_id, status: ok|stopped|failed, error?}
    visual_set {session_id, set_id, brief, options:[{id, label, status: rendering|ready|failed, html?, error?, path?,
                drawn_with}], picked_id, library, drawn_with, libraries:[..], library_note}
                (on creation and whenever any option changes; always the full set; html only when ready)
      - library = what the planner asked for (a key below when known, else the name it gave; null = not asked, ECharts);
        drawn_with = the key the html needs (echarts | chartjs | d3 | plotly | bokeh); libraries = keys available for
        the session's folder (echarts, chartjs, d3 always; plotly / bokeh when installed in the folder's .venv or
        Launchpad's own environment); library_note = "drawn in ECharts, styled like <library>" when it fell back, else null
      - html = one fragment; charts use the library's global (echarts, Chart, d3, Plotly, Bokeh; no script tag for it):
        the page fetches GET /vendor/lib/<drawn_with>.js and inlines it into the sealed frame
      - snapshot sessions[].visual_sets = the same objects (without "type")
    agent_usage / activity for the visual agent: role "visual" (one per session; activity tool "render" per option)
  UI -> here
    user_message {text} · round_answer {roundId, answers, skipped?} · plan_approve {session_id}
    queue_response {id, answer} (questions) | {id, decision: allow|deny|always, remember?: session|project_local,
                   mode?: default|accept_edits (plan approval), message?: string (deny / reject feedback)}
    queue_dismiss {id} · get_crew {dir_id?} (default: the current session's folder) · report_to_planner {session_id}
    run_stop {session_id} · new_session {dir_id?}
    chat_new {dir_id?} · chat_message {chat_id, text} · chat_set_mode {chat_id, mode: default|accept_edits|plan} · chat_stop {chat_id}
    visual_pick {session_id, set_id, option_id (null clears)} · visual_tweak {session_id, set_id, option_id, text}
    visual_retry {session_id, set_id, option_id}
    planner_promote {session_id}  (promote the planner by hand, any time; refused if already promoted or off)
    agent_draft {dir_id, text} -> agent_drafted  (one cheap one-shot call: haiku, no tools; nothing saved)
    agent_create {dir_id, fields: {name, description, purpose: exploring|building|reviewing, model?, tools:[..],
                  instructions}} -> agent_saved  (writes <folder>/.claude/agents/<name>.md after the agent-file
                  validation; refused: planning purpose, a built-in name, an existing agent or file, read-only
                  purpose with Write / Edit / Bash; empty tools = the purpose's default set)
    agent_remove {dir_id, name} -> agent_removed  (folder agents only; the file is backed up like a save, restorable
                  via list_backups / restore_backup {root: dir_id, path: ".claude/agents/<name>.md"})
    chat_from_plan {session_id} -> chat_started (mode plan, from_session_id) in the session's folder, the plan sent as
                  the first message; the draft stays approvable. Refused (system) if the session has no draft
    set_autopilot {session_id, on: bool}
    get_settings {} · set_settings {patch: {<setting>: value, default_dir_id?: dir_id ("Make default")}}
    add_directory {path} · remove_directory {dir_id} (refused while busy; never deletes anything) · pick_directory {}
    list_dir {root, path} · read_file {root, path} · save_file {root, path, text, base_version}
    list_backups {root, path} · restore_backup {root, path, backup_id}
      - root = a connected folder's dir_id, or "app" (Launchpad's agent files + promotion criteria); path relative,
        "" = top; resolved paths must stay inside the root (symlinks and .. checked); only .md files are editable;
        files over 1 MB or binary are listed but never sent; restore = a save of the backup (current kept as backup);
        saves keep the file's own line endings (CRLF stays CRLF; new files LF)
      - fake demo: root "app" serves a temporary copy of the agent files and criteria, never the real ones  (before launch and during a run; on also approves the run's open cards)
  HTTP
    GET / (page; Content-Security-Policy inherited by the visual frames: no network beyond this app)
      = frontend/dist/index.html (React build) when it exists, else prototype/launchpad-orbit.html (vanilla)
    GET /classic (always the vanilla page, same headers) · GET /assets/<file> (hashed React build files from
      frontend/dist/assets; same origin, nosniff, fixed content types)
    GET /vendor/echarts.min.js (Apache ECharts 6.1.0, vendored; same access rules as the page) · GET /favicon.ico · GET /health
    GET /vendor/lib/<key>.js  (a visual library as one JavaScript file; details in app/vendor/README.md)
      - echarts | chartjs | d3: vendored in app/vendor, same access rules as the page
      - plotly | bokeh: ?code=<access code>&dir=<dir_id> (dir optional: without it only Launchpad's own environment);
        the bundled JavaScript inside the installed Python package (never run as Python), path-checked; 403 bad
        code, 404 not installed / unknown folder; several files (Bokeh) are joined by the line /*lp:next-script*/
        and the page gives each its own script tag
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse, Response

from . import visuals
from .hub import Hub
from .settings import Settings

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "prototype" / "launchpad-orbit.html"
FRONTEND_DIST = ROOT / "frontend" / "dist"          # React build (committed); read per request so a rebuild needs no restart
# Content types for build files, set explicitly (Windows' registry can map .js to text/plain, which nosniff then blocks)
ASSET_TYPES = {".js": "application/javascript", ".mjs": "application/javascript", ".css": "text/css",
               ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
               ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon", ".json": "application/json",
               ".map": "application/json", ".txt": "text/plain; charset=utf-8"}
ASSET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ECHARTS = Path(__file__).resolve().parent / "vendor" / "echarts.min.js"
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="#3B3FB6"/>'
           '<circle cx="16" cy="16" r="5" fill="#E8664A"/></svg>')


def create_app(port: int, code: str, settings: Settings, store=None, overridden=()) -> FastAPI:
    app = FastAPI()
    hub = Hub(settings, store=store, overridden=set(overridden or ()))
    app.state.hub = hub
    origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    # The page's policy is inherited by the locked-down frames it creates for visuals (srcdoc / blob frames):
    # nothing may reach the network beyond this app; the websocket only on this port
    csp = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data: blob:; font-src 'self' data:; "
           f"connect-src 'self' ws://127.0.0.1:{port} ws://localhost:{port}; frame-src 'self' blob: data:; "
           "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'none'")
    page_headers = {"Content-Security-Policy": csp, "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}

    asset_headers = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                     "Cache-Control": "public, max-age=31536000, immutable", "Cross-Origin-Resource-Policy": "same-origin"}

    @app.get("/")
    async def page():
        # the React build when it exists, else the vanilla page; both get the same policy headers
        built = FRONTEND_DIST / "index.html"
        return FileResponse(built if built.is_file() else PAGE, media_type="text/html", headers=page_headers)

    @app.get("/classic")
    async def classic():
        return FileResponse(PAGE, media_type="text/html", headers=page_headers)

    @app.get("/assets/{name}")
    async def asset(name: str):
        # one plain file name inside frontend/dist/assets (hashed by Vite, so it can be cached for good)
        kind = ASSET_TYPES.get(Path(name).suffix.lower())
        if not kind or not ASSET_NAME.match(name):
            raise HTTPException(status_code=404)
        folder = (FRONTEND_DIST / "assets").resolve()
        target = (folder / name).resolve()
        if target.parent != folder or not target.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(target, media_type=kind, headers=asset_headers)

    @app.get("/vendor/echarts.min.js")
    async def echarts():
        # same access rules as the page (127.0.0.1 only, no code); readable by opaque-origin sandboxed frames
        return FileResponse(ECHARTS, media_type="application/javascript", headers={
            "X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*", "Cross-Origin-Resource-Policy": "cross-origin"})

    @app.get("/vendor/lib/{key}.js")
    async def vendor_lib(key: str, request: Request):
        # a visual library for the sealed frames; the page fetches it and inlines it (frames never fetch)
        lib = visuals.LIBRARIES.get(key)
        if lib is None:
            raise HTTPException(status_code=404)
        headers = {"X-Content-Type-Options": "nosniff"}
        project = None
        if lib.bundled:
            headers.update({"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*",
                            "Cross-Origin-Resource-Policy": "cross-origin"})
        else:                                           # a file from an installed package: the page's code only
            if request.query_params.get("code") != code:
                raise HTTPException(status_code=403)
            did = request.query_params.get("dir")
            if did:
                try:
                    project = hub.directory(did)[1]
                except ValueError:
                    raise HTTPException(status_code=404) from None
            headers.update({"Cache-Control": "private, no-store", "Cross-Origin-Resource-Policy": "same-origin"})
        files = visuals.library_files(key, project)
        if not files:
            raise HTTPException(status_code=404)
        if len(files) == 1:
            return FileResponse(files[0], media_type="application/javascript", headers=headers)
        # several files (Bokeh + its plotting API): one response; the page splits it into one script tag per file
        body = visuals.LIB_PART_SEPARATOR.encode().join(f.read_bytes() for f in files)
        return Response(body, media_type="application/javascript", headers=headers)

    @app.get("/favicon.ico")
    async def favicon():
        return Response(FAVICON, media_type="image/svg+xml")

    @app.get("/health")
    async def health():
        return PlainTextResponse("ok")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        if websocket.query_params.get("code") != code or websocket.headers.get("origin") not in origins:
            await websocket.close(code=4403)
            return
        await websocket.accept()

        async def send(obj: dict) -> None:
            await websocket.send_text(json.dumps(obj, default=str))

        await hub.connect(send)
        tasks: set[asyncio.Task] = set()
        try:
            while True:
                try:
                    msg = json.loads(await websocket.receive_text())
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                t = asyncio.create_task(hub.handle(msg))      # keep receiving while a turn runs
                tasks.add(t)
                t.add_done_callback(tasks.discard)
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(send)

    @app.on_event("shutdown")
    async def _shutdown():
        await hub.close()

    return app
