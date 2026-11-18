"""Launchpad app server: serves the Orbit page and connects it to the hub over a localhost websocket.

- Security: binds 127.0.0.1; websocket needs ?code=<access code> and Origin http://127.0.0.1:<port>
- All agent work lives in the hub (app/hub.py); this file only moves JSON in and out
- Websocket contract below (authoritative: the front end in frontend/ follows it)
- Agent display names: Planner, Explorer (role astronaut), Orchestrator, Builder, Visualizer (role visual),
  CLI (role pilot, the plain chat in the CLI harness); folder agents: their name with dashes as spaces ("copy-reviewer" -> "Copy reviewer")
  here -> UI
    snapshot {current_session_id, sessions:[{session_id, dir_id, cwd, folder, chat:[...], report_sent, running, total_cost_usd,
              planner_cost_usd, visual_sets:[...], plan_revision, draft_pending, runs, autopilot, auto_answers,
              model, promoted, reason, by, + the other planner_model fields}], chats:[{id, dir_id, additional_dir_ids, mode, model,
              harness, label, option_id, started, cwd, busy, history:[{role: user|assistant, markdown}]}]}
             (first event on every connection; then the replay events below)
             planner chat entries: {role: user|assistant|system, text} · {role: round, round:{id, round, questions}}
             · {role: answers, roundId, answers, skipped}
    planner_message {text, session_id} · typing {on} · question_round {id, round, questions:[{id,title,body,rec,options}]}
    usage {scope: "app", tokens, cost, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
           by_role: {<role>: cost}}
          (= the plain sum of every agent, all sessions and chats incl. the planner; tokens = the four counts,
           mostly cache reads; input_tokens = uncached input only; by_role = the cost per agent role)
    usage {scope: "session", session_id, cost, planner_cost, agents, input_tokens, output_tokens, cache_read_tokens,
           cache_write_tokens}  (that session's total = every agent but the planner; planner_cost = the planner's own
           share, never inside cost; agents and the token counts are those same agents'; steps: {"<n>": {cost,
           tool_calls, agents, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}} = the builders
           (step agents) of each step)
    usage {scope: "chat", chat_id, cost, tokens, tool_calls, agents, input_tokens, output_tokens, cache_read_tokens,
           cache_write_tokens}  (that CLI chat's totals)
      - cost totals: ALL cost figures the page shows are summed here only (app/costs.py; one rule for which roles count)
        and sent live: the scope of the agent that just changed (always app; its session or its chat), and every scope
        on connect. The page adds nothing up: it displays these, and the per-agent agent_usage figures as they are.
        snapshot total_cost_usd / planner_cost_usd and run_finished carry the same session figures
      - crew {agents:[{name, role, status, session_id}]}
    plan_meta {name, mode, status} · system {text, session_id?, chat_id?}
    session_started {session_id, folder, dir_id, cwd, additional_dir_ids}
      - cwd = the session's primary folder (its working directory); additional_dir_ids = the folders ticked as
        additional when it started, minus the primary (agents get them as add_dirs; fixed for the session)
    settings {directories:[{dir_id, path, name, exists, is_default, is_additional, busy}], values:{<setting>: {value,
              applies: now|new_sessions, overridden_by_launch}}, can_pick_directory, additional_dir_ids}
              (on connect and after any change)
      - is_default = the primary folder (where the next session or chat runs unless the folder menu picks another);
        is_additional / additional_dir_ids = folders ticked as additional (global, per user; a session uses them minus
        its own primary; new sessions and chats only)
      - settings: question_timeout_s, permission_timeout_s, visual_model, reviewer_model (the Role Reviewer's model,
        default sonnet; launch option --reviewer-model) (now); autopilot_default,
        planner_start_model, planner_top_model, planner_harness (default claude), planner_auto_promote (default
        true), promotion_window_turns, promotion_criteria_path, pilot_model, pilot_harness (default null = the
        launch engine's CLI) (new_sessions; a planner nobody has written to yet is reloaded with a new planner
        setting at once, a CLI chat nobody has written to with a new pilot setting; planner_harness / pilot_harness
        must be a known harness that is available, else system "Settings: ..."). Stored in <home>/.launchpad/settings.json; a launch option overrides for that launch
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
    git_repos {available: bool, repos:[{repo_id, name, dir_id, folder_name, rel, branch (null = detached), detached,
              remote: {name, host, owner, repo}|null, upstream: "origin/main"|null, linked, ahead, behind, clean,
              files:[{path, status: M|A|D|U|?, added, removed, binary}], more, added, removed, error}]}
              (reply to git_scan: every repo in every connected folder, with its status; available false = git is not
              installed, repos [])
      - detection (app/gitrepos.py): the connected folder itself when it holds .git, else repos up to two levels below
        it; .git, node_modules, .venv, venv, env, .launchpad are skipped and a repo is never entered; a repo reachable
        from two connected folders is listed once (under the first). rel = path below dir_id's folder ("." = itself)
      - repo_id = an id the server issued in its last scan (every git message must use one); remote = display parts
        only (credentials and local paths never sent); linked = a remote and an upstream branch exist (else "not
        linked": commit only); changed files = tracked changes vs HEAD (staged + unstaged) + untracked (all lines
        counted as added); binary files: binary true, counts 0; paths relative to the repo, "/" separators; at most
        300 listed (more = how many were left out); added / removed = totals over the listed files; error = git's
        own text when the repo could not be read
    git_result {repo_id, op: refresh|fetch|commit|push, ok, committed, message, repo}
              (reply to git_refresh / git_fetch / git_commit / git_push; repo = the re-read repo object as above, null
              when the id is unknown; message = a short success note, or on failure git's own text with credentials
              removed, trimmed; committed true when a commit was made even if the push after it failed)
    plan_draft {session_id, path, markdown, steps:[{n, title, agent, agent_display, agent_purpose, agent_fallback?,
                skills?, skills_unknown?, role?}], revision, previous_runs}
      - skills = skill names the plan names for the step (absent when none): its worker gets them on top of its own
        allowlist; skills_unknown = those not found in the session's folders (ignored at run time; show greyed)
      - role = the step's role slug (absent when none; never together with a non-null agent): a specialism the planner
        named for a step no listed agent fits; the step runs on the Builder and is tallied under it (see roles_list).
        Show it as a chip on the step
      - agent = the step's agent name, null = the Builder; agent_display = who will run it ("Builder" when null);
        agent_purpose = that agent's purpose (planning|exploring|building|reviewing|other; "building" for the Builder):
        colour steps by this, not by a folder's crew_list;
        agent_fallback: true = the named agent is missing / broken / not a step worker here, so the Builder runs it
      - revision counts drafts in the session (1, 2, ...); previous_runs > 0 = a revised plan after a run (send-back).
        Every new draft can be approved, also after a finished run; a reconnect replays a pending draft after the
        finished run's run_started / run_finished
    run_started {session_id, name, steps:[{n, title, status, agent, agent_display, agent_purpose, agent_fallback?,
                 skills?, skills_unknown?, role?}], run, revision, autopilot}
      - plan_approve answers: run_started (success), or system {text, session_id}: "No draft plan to approve yet." /
        "This session's run is already going." / "There is no new draft to approve: ..." (already ran)
      - a second run in a session first moves steps/ and report.md into run-<k>/
    planner_model {session_id, model, promoted: bool, reason: string|null, by: "criteria"|"user"|null, harness,
                   start_model, top_model, label, option_id, auto_promote: bool, started: bool, switchable_to:[option ids]}
      - sent at session start (replayed on reconnect), on its first message, on promotion and when an unstarted
        planner is reloaded; starts on the start model (default sonnet), promoted at most once to the top model
        (default opus): by the planner within its first N turns (only when auto_promote), or by the user
      - label = "<harness> · <model>" now (e.g. "Claude · Sonnet"); option_id = "<harness>:<model>" now;
        auto_promote = this session may promote itself; started = someone wrote to it (harness and start model fixed);
        switchable_to = picker options it can move to now: every available one before its first message, else only
        its top model while it can still be promoted (= promotion by hand); [] otherwise
    planner_choice {options:[{id: "<harness>:<model>", harness, harness_label, model, model_label, label, available,
                    note: "not available yet"|null}], choice: {option_id, harness, model, label}, auto_promote,
                    top_model, top_label, promotion_off, pinned: model|null, overridden:[setting names],
                    rules: {markdown, path}}
      - the planner picker (under the planner's chat box). options come from app/agents/planner/choices.py:
        harnesses x models, available = agentlib says the harness's engine is (the Cursor engine is a stub: listed,
        disabled); the configured start / top models are always listed for Claude. choice = what the next new plan
        starts on (settings planner_harness + planner_start_model, per user); a session whose start option differs
        and that has started shows it as "applies to your next new plan". promotion_off = start = top; pinned =
        --model (no choosing); rules = the promotion criteria text (read-only in the picker)
      - sent on connect and after any change of a planner setting (picker, set_settings) or of the app's files
      - the page groups options by harness: a "CLI" dropdown (harness = "CLI" in the UI; unavailable ones listed,
        not selectable), then that CLI's models; changing the CLI picks its first model
    cli_choice {options:[same shape as planner_choice options], choice: {option_id, harness, model, label},
                overridden:[setting names]}
      - the CLI chat's picker (under the CLI chat's box; same grouping as the planner's, no auto-promote / New
        plan). options come from the same table (app/agents/claude_code/choices.py over planner/choices.py
        HARNESSES), plus the configured pilot_model for the chosen CLI. choice = what the next new chat starts on
        (settings pilot_harness + pilot_model, per user; defaults: the launch engine's CLI and the CLI agent file's
        model); independent of the planner's choice. Sent on connect and after any change of pilot_harness /
        pilot_model (picker, set_settings)
    autopilot {session_id, on}  (after set_autopilot; on = every builder permission request approved without a card)
    step_update {session_id, n, status: todo|in_progress|blocked|done|failed, agent, agent_display, agent_purpose,
                 agent_fallback?, skills?, skills_unknown?, role?,
                 built?, report_path?}
      - from in_progress on, agent_display = the agent actually running the step (after any fallback); a fallback
        is also an issue in the step report and report.md (Steps table has an Agent column)
    queue_item {id, session_id, chat_id, kind: question|permission|plan|info|review, agent, agent_id, step, title,
                body, rec, options?, blocking, timeout_s, expires_at}
      - kind review = a workflow run waiting for a review sign-off (see Workflows > Missions below)
      - agent = plain display name of the step's agent ("Builder", or a folder agent's); the page adds the step
      - run items: session_id set, chat_id null; chat items: chat_id set, session_id null, timeout_s null
      - permission: rec null (no recommended choice), plus tool; run cards also command; chat cards also
        suggestions:[{label, remember: session|project_local}]; body = command or path summary
      - builder permission cards: timeout_s = the permission timeout (default 180), expires_at set, blocking false;
        raised for deny-listed shell commands and for writes outside the project / into .launchpad/ or .git/
      - plan (chats): markdown = the proposed plan
      - Role Reviewer questions (at most 3 per review): kind question, session_id null, chat_id null, agent "Role
        Reviewer", plus review_id, role (the role under review), test (value|logic|history|fixes|independent or "");
        rec = the reviewer's recommended answer; timeout_s = the question timeout (on expiry the answer is "No answer (the
        question timed out)", by timer, never the recommendation); NEVER auto-answered (Auto answers is for builders).
        Show them with the review in the Crew tab; answer with queue_response {id, answer}
    queue_resolved {id, answer, by: user|timer|autopilot|auto}
      - builder permission timer: {answer: "deny", by: "timer"}; autopilot switched on: {answer: "allow", by: "autopilot"};
        a waiting plan-step question when Auto answers is switched on: {answer: <the worker's recommendation>, by: "auto"}
    auto_answers {session_id, on}  (after set_auto_answers; also snapshot sessions[].auto_answers, off by default)
    auto_answer {session_id, id, agent, step, title, answer}
      - one plan-step worker's question decided under Auto answers: the worker's own recommended answer was taken (no card
        was shown, or the waiting card is settled). The page shows a compact, marked line in Incoming (question + answer,
        "Decided by the <agent> (Auto answers on)"). id = the question's queue id; step = the step. NOT in the planner
        chat. The most recent ones are replayed on connect (before activity)
      - rules: BUILDERS ONLY: questions asked by plan-step workers (the Builder and folder / other agents running a step),
        blocking ones too, always with the worker's own recommended answer (ask_question rejects an empty recommended
        answer or reason with a tool error, so every question has one); the step stays in_progress (never blocked).
        Planner question rounds and CLI chat questions are never auto-answered; permission cards and plan proposals are
        never affected (that is Autopilot)
    question files (no event): every answered question (planner round questions, one file each; builder questions; CLI
        chat questions) and every timed-out one is saved by code as <session folder>/questions/NNN-<slug>.md (number
        unique in the session, found from disk, so it survives a restart; a CLI chat's own folder holds its questions):
        Question, Asked by + when, Step, Run, Options offered, Answer ("No answer (timed out)" when it timed out),
        Justification (reason, recommended answer, the user's note, the assumption taken), How it was answered (by the
        user / "Decided by the Builder (Auto answers on)" / timed out). Skipped planner questions get no file. Files stay in
        questions/ across runs; report.md has a "Questions" section linking the files of its run
    agent_usage {session_id, chat_id, agent_id, role: planner|astronaut|orchestrator|builder|pilot|visual|drafter|reviewer, name, step,
                 status: working|idle|done, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                 cost_usd, tool_calls, by_model?: [{model, cost_usd, input_tokens, output_tokens, cache_read_tokens,
                 cache_write_tokens}]}  (+ old planner-header fields); one Explorer (role astronaut) per session, idle between trips;
                 the planner's by_model splits its one usage entry across models (e.g. Sonnet, then Opus)
                 - role builder = any step agent (the Builder or a folder agent; name = its display name)
                 - role drafter = the agent drafter (agent_draft): session_id and chat_id both null; counted in the
                   app-wide usage only
                 - role reviewer = the Role Reviewer (review_start; name "Role Reviewer"): session_id and chat_id both
                   null; counted in the app-wide usage only (by_role.reviewer); its Read / Grep / Glob calls appear as
                   activity events with role reviewer and no session
    activity {id, session_id, chat_id, agent_id, role, name, step, tool, summary, status: started|done|denied|failed, ts,
              auto?: true (final event of a call autopilot approved)}
             (one per tool call: "started", then the same id with the final status; summary = command / path /
              pattern / short label, max 140 chars, never file contents; recent ones replayed on reconnect;
              finished calls also go to <session or chat folder>/activity.log)
    run_finished {session_id, status: done|stopped|failed, report_path, markdown, total_cost_usd, planner_cost_usd}
      - session total = orchestrator + builders + astronauts + visual agent; the planner is separate (planner_cost_usd), the same
        definition in report.md and the snapshot
    crew_list {dir_id, tool_choices:[tool names the new-agent form may offer], agents:[{name, display_name, role,
               purpose: planning|exploring|building|reviewing|other, uses, builtin, description, model, source_path,
               instructions, builtin_tools, custom_tools:[{name, description}], mcp_servers, disallowed_tools, warnings,
               gated_tools, setup: lean|project, engine_prompt, prompt_note, root, path (relative), editable,
               step_worker? (folder agents), skill_setting, promotion? (planner): {start_model, target_model,
               auto_promote, window_turns (0 when auto_promote is false), criteria (markdown), criteria_path, root, path, editable}}],
               skills:[{name, description, path (SKILL.md), folder_name, dir_id, source: claude|agents, shadowed}]}
      - skills = every skill found in the folder dir_id (primary) and the folders ticked as additional, primary first.
        Per folder: .claude/skills when the folder has a .claude folder (then .agents is ignored, even with no
        skills folder), else .agents/skills. shadowed: true = a skill of the same name in an earlier folder wins
      - skill_setting = the agent's skills: "all" | [skill names] (names not in skills are ignored at run time; show
        them greyed) | "cli" (the CLI chat, role pilot: the harness's own skill discovery, no checklist).
        Defaults: Planner "all", every other agent []. Stored per user (<home>/.launchpad/settings.json agent_skills)
      - the six built-ins first (builtin true, root "app", path "app/agents/<folder>/agent.md"), then the agents of the connected folder dir_id
        (builtin false, role null, root = dir_id, path ".claude/agents/<file>.md", purpose from the file's
        `purpose:` field, missing or unknown = other (shown under "Other"); a broken file is listed with its problems in warnings and
        step_worker false). Built-in purposes: Planner + Visualizer planning, Explorer exploring, Builder +
        Orchestrator + CLI building
      - uses = times the agent was started (per user, survives restarts; keyed by agent name)
      - folder agents as Launchpad runs them: exploring / reviewing = read-only (no write, edit or shell tools);
        building and other = the Builder's gated tools and checks; custom_tools = Launchpad's step tools
      - sent again after a save of one of the app's files, after agent_create / agent_remove, and after a save of a
        folder's .claude/agents/*.md (that folder's list)
      - mcp_supported (bool) = the engine this agent runs on can take MCP servers per run (agentlib; claude yes, fake
        and Cursor no: assignments are kept but do nothing; say so on the card); engine_label = that engine's name
        ("Claude", "Cursor", "Fake engine (demo)"). Planner = the planner's harness, CLI = the CLI chat's, others = the
        launch engine
    connection_test {id, installed, version, reachable, usable, detail}  (reply to test_connection; Settings >
                    Connections. Any of version / reachable / usable / detail may be null = not checked; version =
                    the number only, e.g. "2.1.160")
      - one test script per CLI tool (app/connections/<tool>.py, each runnable alone from a terminal); the list of
        tools comes from the server (mcp_library connections), so a new tool needs no page change. Connections is the
        ONE place the page names the real tools ("Claude Code", "Cursor"); everywhere else it still says "CLI"
      - claude_code: installed (claude on PATH, else the copy bundled with the SDK) + version + reachable = one minimal
        request through agentlib (a fraction of a cent; the fake engine in the demo: zero tokens); usable = both
      - cursor: install check only (cursor-agent / agent); reachable null; usable false while agentlib's Cursor engine
        is a stub, with the reason in detail
      - nothing runs until the user clicks Test; a second click while one runs is answered by the running test
    mcp_library {servers:[{name, kind: command|url, config, status: connected|failed|untested|testing, detail,
                 tool_count, tools:[names], tested_at}], assignments: {<agent name>: [server names]},
                 connections:[{id, name}], import_sources:[{id, name}], error?}
      - reply to every MCP message (below); also on connect and whenever a test starts or ends (broadcast)
      - config: kind command {command, args:[..], env:{..}}; kind url {url, headers:{..}, type?: "sse"} (no type =
        streamable HTTP; a URL whose path ends in /sse defaults to sse; an edit without type keeps the stored one).
        Secret values arrive as "********": every env / header value (a value that is only a ${VAR} reference is shown),
        secret-looking --flag=value / --flag value args, URL credentials and secret-looking query values. Send a
        masked value back exactly as received to keep the stored secret; a mask with nothing stored is refused
      - status testing = a test is running (the stored result stays in force for runs until it ends); detail = "N tools"
        when connected, else the error; tool_count null unless connected; tested_at ISO time of the last finished test
      - assignments: agent names as in crew_list `name` (launchpad-builder, launchpad-planner, launchpad-pilot,
        copy-reviewer, ...). No agent has any server by default (absent = none)
      - connections = the CLI tools for Settings > Connections; import_sources = "Import from <name>" buttons
      - error = why the last request was refused (bad name, name taken, unknown server, hidden value not stored, ...);
        absent when it worked. For anything but a save the same text also arrives as system "MCP: ..."
      - stored in <home>/.launchpad/mcp.json (never settings.json, never a project); under --fake a temp sample library
    mcp_imports {source, servers:[{name, kind, summary, scope: local|project|user, exists}]}  (reply to
                list_mcp_imports; summary = the command line or URL, masked, " · " where it came from; exists = a server of
                that name is already in the library (importing it is skipped))
      - claude_code source: each connected folder's local scope (~/.claude.json projects["<folder>"].mcpServers) and
        <folder>/.mcp.json, then user scope (~/.claude.json mcpServers); the first of a name wins (Claude Code's own
        precedence). Only stdio / http / sse entries; ${VAR} references copied as they are (expanded at test / run)
    MCP at run time: right before ANY crew agent starts (planner, Explorer, orchestrator, builders and folder step
      agents, Visualizer, CLI chat; identical rule) it gets its assigned servers whose last finished test passed. Each
      other assigned server is skipped: system {text: "MCP server '<name>' was not given to the <agent>: <reason>. It
      runs without it.", session_id | chat_id} (once per session / chat, agent, server and reason; a step's warning is
      also in its step report's issues). An engine that cannot take MCP servers (fake, Cursor): nothing given, no
      warning. MCP tools are pre-approved (no permission cards, Launchpad's write guard does not see them)
    agent_uses {name, uses}  (whenever a count changes: planner session started, explore, step, run, visual render,
                CLI chat's first turn)
    agent_drafted {ok: true, dir_id, fields: {name, description, purpose, model, tools:[..], instructions},
                   usage: {tokens, cost, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}, role?}
                  | {ok: false, dir_id?, error, role?}   (reply to agent_draft; fields are a suggestion the user edits)
      - usage = the drafting call's own tokens and cost (show them with the draft); role = echoed when the draft was
        for a tally role (define path)
    agent_saved {ok: true, dir_id, name, role?, case_path?} then roles_list (role given or an entry named like the
                agent) and crew_list | {ok: false, dir_id?, error, problems:[..], role?}
      - role given (define path): the role's tally entry is removed (also an entry named like the new agent) and, when
        the role was reviewed this launch, the case is saved beside the agent: case_path = ".claude/agent-cases/
        <name>.md" relative to the folder (outside .claude/agents/, so it is never loaded as an agent)
    agent_removed {ok: true, dir_id, name} then crew_list | {ok: false, dir_id?, name?, error}
    roles_list {threshold: 2, resurface_uses: 5, entries:[{name, base_agent, purpose, skills:[..], folders:[{dir_id,
                name}], uses_total, first_used, last_used, samples:[{text, session_id, step, title, at}], verdict:
                {decision: define|keep|not_yet, reviewer_verdict, at, uses_at, case_file}|null, dismissed, last_review:
                {review_id, verdict, case_file, cost, tokens, at}|null, uses:[{id, at, dir_id, folder, session_id, run,
                step, title, skills, outcome: done|failed|blocked, questions, assumptions, timed_out, sent_back,
                named_agent}] (newest first, at most 20), problems, state, visible, uses_to_list, resurfaced, reviewing,
                review_id}]}
      - undefined roles: the per-user tally (<home>/.launchpad/roles.json, app/tally.py), every entry most recently used
        first. Sent on connect and after every change (a step recorded, a send-back marked, dismiss, merge, a review
        starting or ending, a decision, an agent created for a role)
      - recorded: a plan step with a role that ran on the Builder, or a step naming an agent that does not exist
        (named_agent true, tallied under that name); never a step run by a registered agent. questions = asked by the
        worker; assumptions = logged for the step (timer, autopilot and report ones); timed_out = questions the timer
        answered; sent_back = the session's plan was revised after that run
      - visible = show under "Used but not defined". state: few_uses (fewer than threshold uses; uses_to_list = how
        many more) | dismissed (until used again) | resting (after a keep or not_yet decision: until resurface_uses
        more uses or a new failed / blocked / sent-back use; uses_to_list = uses left) | defining (decision define,
        until the agent is created) | listed (resurfaced true = back after a rest). problems = failed, blocked or
        sent-back uses among those listed. reviewing = a review is running (review_id)
    review_started {review_id, role, model, harness}  (reply to review_start; the reviewer is reading)
    review_progress {review_id, role, phase: reading|asking|finalising, text}  (one line each: what it opens, how many
                question cards wait, finalising with the answers)
    review_case {review_id, role, case}  (the review finished; also replayed on connect: the latest case per role)
      - case = {case_id, review_id, role, date, reviewer: {name, harness, model, label}, uses_total, uses_recorded,
        opened:["U7", ...] (uses whose session records were opened), missing:["U8", ...] (session folders gone),
        sections:[{test: value|logic|history|fixes|independent, title, finding, evidence:[{quote, source}], strength:
        none|weak|moderate|strong}] (always five, in that order), verdict: define|keep|not_yet, reason, history_thin,
        skill_notes ("" unless keep: what the skill should cover), proposal: {name, purpose, description,
        instructions}|null (define only), questions:[{test, question, why, recommended, answer}], usage: {tokens,
        cost, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens}, decision: {decision, at, agent?,
        folder?}|null, case_file (file name in <home>/.launchpad/role-cases/, null when the store is in memory)}
      - section titles: Clear value · Logic beyond the skill · Clear usage history · Mistakes or issues it would fix ·
        Independent view: is a subagent the right fix?
    review_failed {review_id, role, error}  (the review errored; the role stays reviewable)
    review_refused {role, review_id|null, error}  (review_start refused: a review of that role is already running
                   (review_id = the running one), or the role is not in the tally)
    review_decided {role, decision, reviewer_verdict, review_id, case_file} then roles_list  (reply to review_decide;
                   the decision is written into the case file)
    chat_started {chat_id, mode, model, harness, label, option_id, started, cwd, dir_id, additional_dir_ids,
                  from_session_id?} · chat_typing {chat_id, on} · chat_delta {chat_id, text}
      - cwd = the chat's primary folder; additional_dir_ids = the additional folders it got as add_dirs
      - harness / model = the chat's CLI and model; label = "<CLI> · <model>" (e.g. "Claude · Sonnet"); option_id =
        "<harness>:<model>" (a cli_choice option id); started = someone wrote to it (CLI and model fixed)
    chat_model {chat_id, harness, model, label, option_id, started}
      - the chat's CLI and model changed or became fixed: sent when a chat nobody has written to is reloaded with a
        new choice, and at its first message (started true)
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
    planner_choose {option_id, session_id?}  (the picker; session default the current one) -> planner_model and / or
                  planner_choice: an unstarted session takes any available option at once (remembered per user);
                  the session's top model while it runs on its start model = planner_promote (nothing remembered);
                  anything else (a step down, another harness) is remembered for the next new plan. Refused
                  (system "Planner: ..."): unknown or unavailable option, or a model pinned by --model
    cli_choose {option_id}  (the CLI chat's picker) -> cli_choice, plus chat_model for every chat nobody has written to
                  yet (it is reloaded on the new CLI and model at once); a chat in progress keeps its own, the choice
                  is for the next new chat (remembered per user: pilot_harness + pilot_model). Refused (system
                  "CLI: ..."): unknown or unavailable option
    agent_draft {dir_id, text, role?} -> agent_drafted  (one cheap one-shot call: haiku, no tools; nothing saved)
      - role (define path): a tally role; the drafter also gets the role's samples and skills and the latest review
        case of it (proposed name, purpose, description, instructions beyond the skill); text may be empty then.
        The output fields are the same as without it
    agent_create {dir_id, fields: {name, description, purpose: exploring|building|reviewing|other, model?, tools:[..],
                  instructions}, role?} -> agent_saved  (writes <folder>/.claude/agents/<name>.md after the agent-file
                  validation; refused: planning purpose, a built-in name, an existing agent or file, read-only
                  purpose with Write / Edit / Bash; empty tools = the purpose's default set). role = the tally role
                  this agent defines (removed from the tally, case copy saved beside the agent); dir_id = the folder
                  chosen on the Crew tab
    roles_get {} -> roles_list
    role_dismiss {role} -> roles_list  (hidden until the role is used again)
    role_merge {role, into} -> roles_list  (folds role into into: uses, samples, skills, folders; counts add up; role
                  is gone). Refused (system "Roles: ...") for an unknown role or the same name twice
    review_start {role} -> review_started, review_progress ..., queue_item (questions, if any), review_case |
                  review_failed; then roles_list. One review at a time per role (else review_refused). The reviewer:
                  read-only (Read / Grep / Glob, each checked against the paths of its brief), on the planner's chosen
                  CLI with the reviewer_model setting
    review_decide {role, decision: define|keep|not_yet} -> review_decided + roles_list  (the user's decision; it may
                  differ from the reviewer's verdict. keep / not_yet: the role rests (see roles_list); define: the role
                  stays listed as defining; the page then sends agent_draft {dir_id, text: "", role} and, after the
                  user edits the form, agent_create {dir_id, fields, role})
    set_agent_skills {name, skills: "all" | [skill names], dir_id?} -> crew_list (for dir_id, default the current
                  session's folder)  (one agent's skill setting, keyed by agent name; saved per user; new sessions and
                  steps only). Refused (system "Crew: ...") for anything but "all" or a list of names
    agent_remove {dir_id, name} -> agent_removed  (folder agents only; the file is backed up like a save, restorable
                  via list_backups / restore_backup {root: dir_id, path: ".claude/agents/<name>.md"})
    chat_from_plan {session_id} -> chat_started (mode plan, from_session_id) in the session's folder, the plan sent as
                  the first message; the draft stays approvable. Refused (system) if the session has no draft
    test_connection {id} -> connection_test  (id from mcp_library connections: claude_code | cursor)
    get_mcp {} -> mcp_library  (the Settings page sends it when it opens)
    save_mcp_server {server: {name, kind, config}, original_name?} -> mcp_library (untested), then mcp_library
                  (testing), then mcp_library (connected | failed): every save is tested. original_name = edit (a new
                  name = rename, followed into every assignment); refused -> mcp_library with error
    remove_mcp_server {name} -> mcp_library  (also removed from every agent)
    test_mcp_server {name} -> mcp_library (status testing), then mcp_library (the result). A test = start the server,
                  list its tools, stop it (agentlib.mcp_check; zero tokens; 30 s limit). Every server is also re-tested
                  once in the background when the app starts
    list_mcp_imports {source} -> mcp_imports
    import_mcp_servers {source, names:[..]} -> mcp_library, then each imported server is tested (names already in the
                  library or no longer found are skipped: system "MCP import: ...")
    set_agent_mcp {agent, servers:[names]} -> mcp_library  (the whole list for that agent; [] = none; unknown names
                  refused; failing servers may stay assigned (the card warns), the page offers only connected ones)
    set_autopilot {session_id, on: bool}
    set_auto_answers {session_id, on: bool} -> auto_answers (+ auto_answer lines and queue_resolved by "auto" for the
                  plan-step questions already waiting). Builders only. Per session, off by default, separate from
                  Autopilot, state kept on the server
    get_settings {} · set_settings {patch: {<setting>: value, default_dir_id?: dir_id ("Make default" = the primary),
                  additional_dir_ids?: [dir_id] (the whole list of folders ticked as additional)}}

    git_scan {} -> git_repos · git_refresh {repo_id} (re-read status only) · git_fetch {repo_id} (git fetch, then re-read)
    git_commit {repo_id, message, paths:[repo-relative file paths], push?: bool} · git_push {repo_id}  -> git_result
      - the Repos panel (right-hand panel while the Files tab is open). git runs as argument-list subprocesses (never a
        shell) off the event loop, with timeouts, GIT_TERMINAL_PROMPT=0 and literal pathspecs; one operation at a time
        per repo. Never: force push, pull, branch switch, reset, history rewrite. Commits use the user's own git identity
      - commit: message trimmed and required; every path must lie inside the repo AND be one of its changed files
        (else refused, nothing staged); stages exactly those paths (git add -A -- paths) and commits only them
        (git commit -- paths: other staged files stay staged); push true then pushes the current branch to its own
        upstream (git push, never forced); a push that fails after a commit = ok false, committed true
      - git_push alone: nothing to push (not ahead) -> ok true "Nothing to push."; fetch / push on a repo that is not
        linked are refused; git not installed or an unknown repo_id -> ok false with a clear message
    add_directory {path} · remove_directory {dir_id} (refused while busy; never deletes anything) · pick_directory {}
    list_dir {root, path} · read_file {root, path} · save_file {root, path, text, base_version}
    list_backups {root, path} · restore_backup {root, path, backup_id}
      - root = a connected folder's dir_id, or "app" (Launchpad's agent files + promotion criteria); path relative,
        "" = top; resolved paths must stay inside the root (symlinks and .. checked); only .md files are editable;
        files over 1 MB or binary are listed but never sent; restore = a save of the backup (current kept as backup);
        saves keep the file's own line endings (CRLF stays CRLF; new files LF)
      - fake demo: root "app" serves a temporary copy of the agent files and criteria, never the real ones  (before launch and during a run; on also approves the run's open cards)

  Workflows (Features/2026-11-17-workflows.md; back end app/workflows/, format in app/workflows/README.md)
    A workflow = ONE JSON file <connected folder>/workflows/<slug>.json: the single definition (the form writes it; it
    may be edited by hand). Found in the primary folder + the folders ticked as additional (Settings), like skills and
    agents. A straight line of stages, two kinds: agent and review. Nothing else (no branching, loops, schedules)
    UI -> here
    workflows_get {} -> workflows_list
    workflow_save {folder: dir_id, workflow: {name, description?, output_folder, unattended_default?: bool,
                   inputs?: [{name, label?, kind?, required?, default?, options?, help?}], files?: [path strings],
                   stages: [{kind: agent|review, title, agent?, instruction?, files?: [path strings],
                   checklist?: [{text, kind?: tick|answer} | text]}]}, original_id?} -> workflows_list
      - new (no original_id): written to <folder>/workflows/<slug>.json, slug made from the name (lower case a-z 0-9
        and "-"); refused when that file already exists (choose another name)
      - edit (original_id = a workflow id): rewrites that file (the old version is backed up first into
        <home>/.launchpad/backups/, where File Explorer saves go; list_backups {root: its folder, path:
        "workflows/<slug>.json"} lists them; restore_backup only restores .md files, so a JSON backup is restored
        by hand); the slug and
        file name never change on an edit; another folder = written there under the same slug, the old file backed up
        and deleted (refused when the target exists). Allowed while it runs (a run keeps the definition it started with)
      - refused (workflows_list with error; nothing written): no name, no output_folder, no stages, a stage without a
        title or with another kind, an agent stage without agent or instruction, a bad input (name not
        [a-z][a-z0-9_]*, duplicate, unknown kind, choice without options), an attached file that is not .md /
        .markdown, folder not connected / not a primary-or-additional folder, original_id unknown. Missing attached
        files and unknown agents ARE saved: they show as error warnings on the card and block Run
      - files may also be sent as [{path}] objects (as received in workflows_list); extra fields are ignored
    workflow_remove {id} -> workflows_list  (the file is backed up, then deleted; refused while that workflow runs)
    workflow_run {id, inputs: {<input name>: string}, test: bool, unattended: bool}
                 -> workflow_run_state {run}  |  refused: workflow_run_state {run: null, workflow_id: id, error}
      - refused when: unknown id; the workflow has error warnings (error lists them); a run of it is in progress (ONE
        run per workflow at a time; a run waiting at a review counts); a required input empty; a date not YYYY-MM-DD,
        a number not a number, a choice not one of its options, a file input not found; an attached file missing
        (re-checked at the start: every attachment is read then); the output folder cannot be made; a test run whose
        `test` folder was not made by Launchpad (below). Nothing is created or deleted when a run is refused
      - inputs: by input name, strings; a missing one takes its default; unknown names are ignored. Every agent stage
        is given all inputs; they are saved in the run record
      - real run: run folder = <output_path>/<YYYY-MM-DD_HHMM> (created; "_2", "_3", ... when taken)
      - test (true): run folder = <output_path>/test, always the same one. Emptied COMPLETELY at the start of every
        test run, but ONLY when it holds Launchpad's marker file `.launchpad-test-folder` (written when Launchpad made
        the folder). A `test` folder without the marker is never touched: the run is refused with "The folder <path>
        was not created by Launchpad, so it will not be emptied. Rename or remove it, or choose another output
        folder." Every record of a test run is labelled "Test run"
      - unattended (true): the run's AGENT stages get the existing Auto answers behaviour (each question answered at
        once with the agent's own recommendation) and Autopilot (each permission request approved, logged). Review
        stages ALWAYS stop and wait for a person, whatever is set. The page pre-ticks it from unattended_default
    workflow_stop {run_id} -> workflow_run_state  (running or waiting at a review -> status stopped; the running agent
        is stopped and its stage shows failed with error "Stopped"; open question / permission cards are withdrawn).
        Refused (error, unchanged run) when the run is not in progress or unknown (run null then)
    workflow_review {run_id, stage: index, answers: [{ticked?: bool, answer?: string}], name, note?, decision:
                     approve|send_back, back_to?: index} -> workflow_run_state
      - only for the stage the run waits at (run.status awaiting_review, run.current_stage == stage)
      - answers: one per checklist item, same order; tick items use ticked, answer items use answer (a tick item may
        carry an optional answer as a comment)
      - approve: every tick item ticked, every answer item answered (non-empty) and name required; the review record
        is saved and the run goes on with the next stage (or finishes)
      - send_back: name, note and back_to required; back_to = the index of an EARLIER AGENT stage; the checklist may
        be incomplete (what was filled in is recorded). That stage and every stage after it run again (review stages
        between them stop again), each re-run agent stage is given the note and its rejected result; rejected results
        are kept (never overwritten): the re-run writes attempt 2, 3, ... and the old attempt is marked rejected
      - refused (error; the run is unchanged and sent again): not waiting at that stage, an unticked / unanswered
        item on approve, no name, send_back without note or with a bad back_to, an unknown decision
      - name is remembered per user (workflows_list reviewer_name prefills the next sign-off)
    here -> UI
    workflows_list {workflows: [workflow], folders: [{dir_id, name, path, is_primary}], agents: {<dir_id>: [{name,
                    display_name, purpose, builtin}]}, reviewer_name, error?}
      - reply to workflows_get / workflow_save / workflow_remove; also sent on connect, after a run starts or ends,
        and after a change of the connected / additional folders
      - folders = where a workflow can live and be saved: the primary folder, then the folders ticked as additional
        (only folders that exist), in that order; workflows from all of them are listed (primary first, then by name)
      - agents[dir_id] = what an agent stage of a workflow in that folder may name (the Add / Edit form's agent
        list): the Builder (launchpad-builder) and the Explorer (launchpad-astronaut, read-only), then that folder's
        own agents (.claude/agents/*.md) that can take a plan step (purpose exploring | building | reviewing | other;
        broken files left out). Planner, Orchestrator, Visualizer and CLI are not stage agents
      - reviewer_name = the name typed at the last sign-off (per user), "" when none
      - error = why the last save / remove was refused (absent when it worked)
    workflow = {id, slug, name, description, folder, folder_name, path, output_folder, output_path, unattended_default,
                inputs: [input], files: [attached file], stages: [stage], warnings: [warning], can_run,
                running_run_id, last_run_id}
      - id = "<dir_id>/<slug>" (opaque); slug = file name without .json; folder = the dir_id of its connected folder;
        folder_name = that folder's name; path = "workflows/<slug>.json" relative to the folder (read_file shows it)
      - output_folder = as written (relative to the workflow's folder, or absolute; may be outside every connected
        folder, e.g. a shared drive); output_path = the absolute folder it resolves to ("" when output_folder is empty)
      - can_run = no warning of level error. running_run_id = its run in progress (also waiting at a review) or null;
        last_run_id = its latest run this launch or null (that run's workflow_run_state has been sent)
    input = {name, label, kind: text|date|number|file|choice, required, default, options: [strings], help}
      - name: [a-z][a-z0-9_]*, unique; label defaults to the name; options only for choice ([] otherwise); default
        and help "" when not given; required defaults to true. date = YYYY-MM-DD; file = a path (relative to the
        workflow's folder, or absolute) that must exist when Run is pressed
    attached file = {path, resolved, exists, name}
      - path = as written (relative to the workflow's folder, or absolute; .md or .markdown); resolved = absolute path;
        exists = found right now; name = the file name. Links, never copies: read at the start of every run (so a
        corrected page is used next time). Workflow-level files go to every agent stage, a stage's files to that stage
    stage = {index, kind: agent|review, title} + agent stage: {agent, agent_display, agent_purpose, instruction,
            files: [attached file]} + review stage: {checklist: [checklist item]}
      - index = 0-based position; stages run in this order. agent_display / agent_purpose = that agent's display
        name and purpose (unknown agent: the name as written and "other", plus an unknown_agent error warning)
    checklist item = {text, kind: tick|answer}  (tick = must be ticked to approve; answer = needs a written answer).
      An empty checklist = a plain stop and sign-off
    warning = {level: error|warning, code, message, stage: index|null, field: string|null}
      - codes: invalid_file (not readable / not JSON / not an object: the card then shows name = slug, no stages),
        invalid (a field is wrong; message says which), no_output_folder, missing_file (an attached file is not
        there), unknown_agent (not in agents[folder]); level warning: unknown_field (ignored; dropped on the next form
        save). Any error-level warning disables Run
    workflow_run_state {run, error?, workflow_id?}
      - pushed to every client whenever a run changes (started, a stage starts / ends, a review waits / is signed, a
        send-back, finished, stopped); on connect the latest run of every workflow (this launch) is replayed, so a run
        in progress, also one waiting at a review, survives a page reload. Runs live in memory: quitting Launchpad
        ends them (their run folders stay)
      - error = why a request was refused (run null for a refused workflow_run, with workflow_id; else the unchanged run)
    run = {id, workflow_id, workflow_name, test, folder, mission_id, inputs: {name: value}, unattended, autopilot,
           auto_answers, status: running|awaiting_review|done|failed|stopped, current_stage: index|null, started_at,
           finished_at, summary_file, error, cost_usd, stages: [stage run]}
      - folder = absolute path of the run folder; summary_file = absolute path of its run-summary.md (rewritten at
        every change); started_at / finished_at = ISO times (finished_at null while in progress); error = why it
        failed / stopped, else null; autopilot / auto_answers = the two switches now (both = unattended at start)
      - mission_id = the session id its Missions events use ("wf-<run id>"; see Missions below)
    stage run = {index, kind, title, status: waiting|running|done|failed|awaiting_review, agent, agent_display,
                 result_file, result_markdown, attempts: [{attempt, result_file, status, rejected, note}], checklist,
                 review, reviews, error, cost_usd}
      - result_file = the current attempt's result (absolute path) or null; result_markdown = that file's text (what
        the review screen shows; the run folder may be outside every connected folder, so read_file cannot reach it;
        cut at 100 000 characters with a closing line saying so) or null; attempts = every attempt so far, oldest
        first (rejected true = a review sent it back; note = that reviewer's note). Review stages: agent null,
        agent_display "Review", result_file null, result_markdown null, attempts []
      - review stages: checklist = the items; review = the current pass's review record or null; reviews = every
        record of this stage, oldest first (send-backs included). Agent stages: checklist [], review null, reviews []
    review record = {decision: approve|send_back, name, note, at, answers: [{text, kind, ticked, answer}], back_to:
                     index|null, record_file}  (record_file = absolute path of the review's markdown file)
    Run folder (the record a person keeps; may be outside every connected folder; agents may write there):
      NN-<stage-slug>.md (each agent stage's result, NN = index + 1; attempt k >= 2: NN-<stage-slug>-k.md),
      NN-<stage-slug>-review.md (later passes -k), run-summary.md (workflow, test label, inputs, unattended, stages
      with status / attempts / reviews, attachments read, data files, costs), run.json (the run object above),
      questions/ (questions the agents asked, with answers), assumptions.md, plus any data files the agents wrote.
      Launchpad's own bookkeeping (activity.log, operations-manual.md with costs) stays in <workflow's
      folder>/.launchpad/workflow-runs/<run id>/
    Missions: a workflow run also shows as a run in Missions, under session_id = run.mission_id: run_started {name:
      "Workflow: <name>" (+ " (test run)"), steps: one per stage (n = index + 1; review stages agent null,
      agent_display "Review", agent_purpose "reviewing"), run: 1, revision: 0, autopilot, auto_answers, workflow},
      followed at once by autopilot {session_id, on} and auto_answers {session_id, on} (the two switches' state; both
      = unattended at start); step_update per stage change (waiting -> todo, running -> in_progress,
      awaiting_review -> blocked, done, failed); run_finished {..., workflow} at the end (report_path =
      run-summary.md, absolute; markdown = its text; planner_cost_usd 0); agent_usage / activity / queue_item /
      auto_answer / usage scope session carry the same session_id. It sends NO session_started and is not in the
      snapshot's sessions (not a planning session). run_stop {session_id: mission_id} = workflow_stop; set_autopilot /
      set_auto_answers {session_id: mission_id} switch those for the rest of the run (review stages still stop) ->
      autopilot / auto_answers events + workflow_run_state. Replayed on connect after the snapshot (run_started,
      autopilot, auto_answers, then run_finished when finished)
      - workflow = {id, name, run_id, test} (workflow id, its name, the run id, test run or not) on run_started and
        run_finished (and on the review card below) = THE marker of a workflow run: present only for workflow runs,
        absent for a planner's plan. With it the page labels the run and its report card as the workflow (not
        "Orchestrator") and hides planner-only actions (Send to planner); no planner or orchestrator is involved
      - waiting for a review sign-off: the review stage's step (run_started steps / step_update) has status blocked
        plus waiting_for: "review" (absent otherwise), and Incoming gets the "needs you" card: queue_item {id,
        session_id: mission_id, chat_id: null, kind: "review", agent: "Review", agent_id: null, step: n (index + 1),
        title: "Sign-off needed: <stage title>", body (one line: the workflow, the stage, sign off in the Workflows
        view), rec: null, blocking: true, timeout_s: null, expires_at: null, workflow, run_id, stage: index}. It stays
        open (replayed on connect like other open cards) until the review is signed or the run stops: then
        queue_resolved {id, answer: "approve" | "send_back" | null (stopped), by: "user"}. The page shows it as
        "needs you" and opens the review screen for run_id / stage; queue_response cannot sign it (answered with
        system "Sign off this review (approve or send back) in the Workflows view.")
    Form helpers (existing messages, nothing new): list_dir {root: dir_id, path} browses a connected folder for
      attached files, input files and an output folder (paths relative to that folder are what the file wants);
      pick_directory -> directory_picked {path} picks an output folder anywhere (only when settings
      can_pick_directory; the page uses the path as typed text and does NOT send add_directory for it); anything
      else = type the path (absolute paths are fine)
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

from .agents.visualizer import libraries
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
        lib = libraries.LIBRARIES.get(key)
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
        files = libraries.library_files(key, project)
        if not files:
            raise HTTPException(status_code=404)
        if len(files) == 1:
            return FileResponse(files[0], media_type="application/javascript", headers=headers)
        # several files (Bokeh + its plotting API): one response; the page splits it into one script tag per file
        body = libraries.LIB_PART_SEPARATOR.encode().join(f.read_bytes() for f in files)
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

    @app.on_event("startup")
    async def _startup():
        hub.start_background()          # re-test every MCP server in the library (once per launch)

    @app.on_event("shutdown")
    async def _shutdown():
        await hub.close()

    return app
