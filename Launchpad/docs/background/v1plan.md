# Mission Control: Launchpad V1 Design

Status: design interview complete for V1 (except Cursor research). Pre-build review applied (D53–D66). Last updated: 2026-11-04 (session 4).
V1 focus: **the planner only**. V1 runs on James's own Claude subscription; no gateway, no team install yet.
Supersedes: `planning-buddy-interview.md` and the "Planning Buddy V1 — Working Interview" doc.

This file is self-contained. It is meant to be handed to a fresh session (e.g. Claude Code) with no access to the conversations that produced it.

## Names
- **Mission Control**: the app (part of James's wider work folder/project **Cosmo**, "Claude/Cursor shared memory orchestration").
- **Launchpad**: the planner screen inside Mission Control.
- Everything else keeps plain names: plans, briefs, interview notes, runs, reader, workers. No further renaming.

---

## 1. Why this exists
- Current workflow: one Claude Code session, a few sub-agents gather context and SQL, all real work happens in that session. Analysis gets complicated, context bloats, every turn re-reads the whole history, token cost snowballs.
- Forcing Claude Code to follow a strict flow (planner, workers, checks) means fighting its defaults. Messy.
- Direction: our own harness. Our code decides step order and what each step sees. Claude Code / Cursor are where workflows get *built* and where Launchpad is *launched from*; repeatable work *runs* in Mission Control.
- Plan Pal (an earlier headless-Claude Opus interviewer) was **V0**. This is **V1**, built on the lessons, not the code (see D50).

## 2. Core concepts
- An agent is tools plus steps.
- **Graph engineering**: designing the flowchart deliberately. Checklist = linear. Graph adds branches (if X go here) and loops (send back for rework until pass or retry limit).
- **Context graph**: knowledge as connected pieces (table → related tables → gotchas), so each step pulls only what it needs.
- Not every step needs a model. Mechanical checks are plain Python. Different steps can use different models.
- Each step starts fresh and receives only a small output (summary, table, file path), never the full history.
- **Prompt caching**: the provider remembers the start of a prompt; only text up to the first change is cheap. Stable content first, changing content last. Each agent has its own cache lane; switching agents breaks nothing. Hand-offs pass short summaries.
- **Skills vs knowledge**: skills are procedures (actuarial memo, HTML report); knowledge is facts (how to query table X) and belongs in a knowledge wiki, not a skill library.

## 3. Full architecture vision (mostly out of scope for V1)
- **Router** (later): cheap model, runs once per new task. Lanes map to the three planning tiers (D30):
  - tiny/cosmetic → worker or general agent, no planning
  - one piece of an existing project → Launchpad in **brief** mode
  - big or brand new → Launchpad in **project plan** mode
  - Plain code first checks whether the project already has a project plan; if it does, anything non-trivial is probably a brief.
  - In V1 the launch skill plays the router's role; later the router takes over the same decision with no planner changes.
- **General agent** (later): Claude Code-like default agent. Has an `escalate_to_planner(summary, files, reason)` tool; code ends that session and starts Launchpad with the note.
- **Orchestrator** (later): backstage, mostly plain code, cheap model for judgement calls. Reads the plan header, runs one step at a time, briefs workers with a cut of their own step (workers never load the whole plan), reads short reports, ticks the plan. Prompt rebuilt fresh each turn with the plan at the end, so plan changes are cheap. Small clarifications go into a decisions note, no replan.
- **Workers** (later): disposable specialists, fresh context, save outputs to disk, return status `done` / `blocked` (with question) / `needs_replan`. Code routes on status. A skill basically defines a worker type. Long term users can create custom workers on either engine.
- **Replanning** (later; V1 files must support it): worker flags `needs_replan` → orchestrator pauses, marks step blocked → Launchpad starts with plan + interview notes + worker note → presents options, **user decides** → only unfinished steps rewritten → orchestrator resumes. Needs a notification (Teams later).
- **Domain expertise for readers**: code for mechanical checks (e.g. Excel hard-coded values), written checklists for judgement, planner questions as the safety net.
- **Workspace rules**: deliverables live in the project; shared skills and wikis are read-only to agents; reusable learnings are *proposed* as wiki edits for a human to approve; claims data never lands in Git.

## 4. V1 scope
**In**: Launchpad, an interactive planning session launched from Claude Code in its own window, producing a plan (or brief) plus interview notes. Built as **the first screen of the single Mission Control app**, not a separate planner app.

**Out**: router, general agent, escalation, orchestrator, workers, replan execution, Teams, real-data access, Cursor engine adapter (pending research), visual board (later version), Excel scanner, generating the wiki related-pages file, full transcript resume.

---

## 5. Decisions

### Launch and hand-back
- **D1** A Python script. For V1 testing it is triggered by a **user-invoked skill** in Claude Code. The skill is only the trigger; planning happens in the pop-up.
- **D2** Claude Code passes a **short summary of the discussion** as the starting request.
- **D3** Claude Code keeps working while the window is open. On finish it receives **the plan file path plus a two-to-three-line summary**. It never holds the interview transcript.

### Window and app shell
- **D4** Local web page served by the script, shown in a **pywebview** window. Windows and Mac.
- **D5** Clean UI. One app shell with a sidebar: **Launchpad** works in V1; Runs, Workers etc. visible but greyed out.
- **D6** Layout: **chat plus a live panel** showing what's decided and what's open, as a grouped list by topic (decided ticked, open highlighted). Tree view could come later.
- **D7** Panel is **display-only**. Decisions are changed by telling the planner in chat.
- **D8** Visible **token/cost counter**, plus a **warning when the conversation gets long** that offers a fresh restart from the notes. Threshold is a setting; default picked after seeing typical interview lengths.
- **D9** Closing the window mid-interview **asks for confirmation first**; state is already saved so the session can be picked back up (via D41).
- **D10** Leave room in V1 layout for a future visual board, and let question cards reference a preview (see section 7).

### Security
- **D11** Web server and websocket listen on **localhost only**.
- **D12** Random **one-time access code** in the URL; websocket checks it before accepting a connection.
- **D13** Websocket **rejects connections from any other web page** (origin check).
- **D14** No external scripts, fonts or CDNs; everything bundled. Only outbound call is the Agent SDK's call to Anthropic.
- **D15** Full chat transcripts are kept in runs for the retention period (7 days default). James is comfortable with this.

### Gateway, models and cost
- **D16** **V1 auth = the user's existing Claude subscription** (the Agent SDK uses the local Claude Code login). No base URL, no API token, nothing to configure. The company LiteLLM gateway is a later option. **Deployment model:** nothing is hosted. Each person clones the repo and runs Mission Control locally on their own computer, with their own Claude Code login, the same way they already use Claude Code. Auth stays a single setting in case that ever needs to change. Model per role is a setting (Opus for Launchpad, Haiku for the reader by default).
- **D17** Cost counter is a **simple local approximation**: each reply's token counts (new input, output, cache reads, cache writes) × a price table in settings. On a subscription the cost is notional (list-price equivalent); tokens are the real signal. **Never query any service for spend.**

### Engines and the agent library
- **D18** Launcher and engine are **fully independent**: launch from Claude Code or Cursor; engine (Claude or Cursor) is a swappable option inside the app.
- **D19** Long term: a settings menu to choose the engine **per role** (orchestrator, planner, reader, workers) and create custom workers.
- **D20** A small **separate agent library**, shipped alongside the app. An agent is defined with plain fields: `name`, `engine` (claude | cursor), `model`, `instructions`, `tools`. Goal: easy to read for non-coders. Start small: start session, send message, stream reply, use tools, count tokens. Includes a **fake engine** for testing (D44).
- **D21** Library and app live in **one repo, separate folders**. May split later.
- **D22** Planner tools are built as **one MCP server** (the standard tool plug-in format both engines support).
- **D23** V1 uses **Claude (Agent SDK) as the engine**. Cursor adapter comes second, **pending the research in section 9**, which may change the approach.

### Planner tools
- **D24** Launchpad gets **none of the built-in tools** (no Bash, Edit, Write, general sub-agent). Only four custom tools with one-line descriptions:
  1. `ask_user`: posts a round of questions as a card in the chat and **returns immediately** (no blocking). Card answers arrive as the user's next message.
  2. `explore`: starts the Haiku reader in the background with a brief.
  3. `save_note`: records a decision and its reason (updates the scoreboard, which writes the interview notes).
  4. `write_plan`: saves the plan/brief, only after user approval; can only write to the plans folder.
- **D25** No separate knowledge-lookup tool; the reader covers wiki scanning.

### Reader (Haiku)
- **D26** Reuse James's existing lightweight Haiku reader. The app starts it as **its own separate background session through the library** (not the SDK's built-in sub-agent feature), so it works with either engine.
- **D27** Interview **keeps going** while the reader works. When it finishes, its summary **waits quietly** and is added with the user's next message; the panel shows a small "research done" note. No interruptions. **Exception:** if no round is open (the planner is waiting only on research), the summary is delivered right away as a new turn, so the session doesn't stall.
- **D28** Summary capped around **300 words**, as **short bullet answers to the questions it was asked, no full sentences**. Full report saved in the run folder.
- **D29** If the reader fails or times out, the panel shows "research failed" and the planner is told with the next message, so it can ask the user or retry.
- **D30a** **No real data in V1** (no Databricks). A separate data sub-agent may come later.
- **D30b** Reader scope: **current working directory by default, plus any number of extra folders** listed in settings (e.g. a team wiki outside the project).
- **D30c** James's per-project **wiki related-pages file** (summary of related wiki pages with links) is loaded **at launch** into the planner's opening context. Generating it when missing is deferred.
- **D30d** No special scanners (e.g. Excel hard-coded value checker) in V1.

### Planning tiers
- **D30** Three tiers:
  - **Project plan**: the big picture (what a weekly trend package shows, cuts, audience). Changes rarely.
  - **Brief**: a smaller planning session for one piece (adding a tab, settling the HTML structure). Saved next to the project plan, links to it, starts with the project plan as background so it doesn't re-ask basics. If it changes something big, it ends with a short **"changes to the project plan"** list the user approves; it never silently rewrites the plan.
  - **Tiny/cosmetic** (a colour, a label): just chat, nothing recorded.
  - Rule of thumb: changes what the project does or decides → brief; cosmetic → chat.
  - The planner can switch tiers itself, with confirmation, if a "small" brief turns out big.

### Interview style
- **D31** **Rounds**, modelled on Matt Pocock's grill-me/grilling skill (github.com/mattpocock/skills). Goal: **shared understanding**. Start basic; each round is worked out fresh from previous answers. A round only holds questions that don't depend on each other.
- **D32** Up to **five questions per round**. Each comes with the planner's **recommended answer and a one-line reason**.
- **D33** **Skipped questions stay open** and are asked again later; never auto-accepted.
- **D34** Chat stays usable while a round is open: the user can ask the planner something back instead of answering.
- **D35** **Pushback** on methodology and important steps (ask why, flag risks). **No pushback** on taste: design, UI, colours. Guards against the "agreed, agreed, agreed" failure mode.
- **D36** The planner **never decides on its own**, including in replans. It presents options and trade-offs; the user chooses.
- **D37** **Done** = shared understanding, checked against the playbook's done checklist (default: goal, audience, inputs, outputs, done criteria per step, sign-off points). User can say "draft now" anytime.

### Playbooks (modes)
- **D38** Each playbook is a small file: **name + two-line description** at the top, then **interview questions / done checklist** and a **final plan format**. If a playbook has no format, the planner makes its own.
- **D39** A **default playbook** is always selected when nothing else fits. Its plan format: goal and audience; background; steps with done criteria; checks and sign-off points; open risks; files and wiki pages relied on.
- **D40** Presets planned: analysis, machine learning, presentations. Teams can write their own. The planner sees only names and descriptions, **suggests one from the first message**, user confirms or picks another. Chosen playbook goes into the planner's fixed instructions. **Switching mid-interview** only as a last resort, with confirmation; decisions carry over.

### Resuming
- **D41** **No resuming by default**; every launch starts fresh. If the user explicitly asks, the window lists recent sessions (within retention) and resume means a **fresh session that catches up from the scoreboard and interview notes**. Full transcript resume deferred.

### Files and folders
- **D42** Every project gets a `plans/` folder (committed with the project). Per plan or brief, two kept files:
  - **Plan / brief**: what to do. Read by the orchestrator and (via briefs cut from it) workers. Markdown with a **header data block**: name, draft/approved status, date, link to interview notes, (for briefs) link to the project plan, plus one line per step (number, title, skill, depends on, status). Readable detail below, in the playbook's format.
  - **Interview notes**: why. Each decision, reason, options turned down. Read **only by the planner**, mainly for replans, briefs and resuming. Written from the scoreboard as decisions are made.
- **D43** A third file, the **scoreboard**, lives in the run folder: the session's live state (topics, each decided or open, plus research status). The live panel draws from it, so markdown stays clean.
- **D44a** Scratch goes in **`~/.mission-control/runs/`** (home folder, outside every project and Git), one folder per session: reader reports, transcript, session ID, scoreboard, receipt (tokens, approximate cost, where the plan was saved). Later also worker reports and intermediate data.
- **D44b** **Retention**: run folders older than the setting (**default 7 days**) are deleted when Launchpad starts. No scheduled task.

### Settings
- **D45** One **per-user settings file in the user's home folder**, outside any project, always persisted. No per-project overrides. Holds: extra reader folders, retention days, long-conversation warning threshold, model per role, engine per role (later), token price table.

### Code architecture
- **D46** **One Python process** runs the web server, agents and file writing.
- **D47** Window ↔ Python over a **websocket** (live two-way connection) for chat messages, panel updates, research status and token counter. Secured per D11–D13.
- **D48** **Prompt order** for caching: core rules → tool descriptions → playbook file → wiki related-pages file → live conversation last.
- **D49** Before saving, **plain Python validates the plan header**; if anything's missing or wrong, the planner is told to fix it and try again.
- **D50a** **Model call failure**: exactly **one automatic retry**, then a clear message in chat with a retry button. Nothing lost. The SDK/CLI has its own internal retries; turn those down so the user isn't left waiting silently.
- **D50b** **Testing**: the library's **fake engine** returns scripted replies so the window, panel, files and validation can be tested without spending tokens; plus a few real end-to-end runs by hand.

### Relationship to existing work
- **D50** Plan Pal = V0. Don't base the build on its code. Before building, run a **one-off extraction**: a reader gets this file and returns a short list of Plan Pal scripts or script sections worth reusing, and why.
- **D51** The phone-based **PRD interview skill stays separate**.
- **D52** James may also have another bare-bones build of something similar; treat it the same way, as reference only.
- Plan Pal lives at `Misc Claude/Planning Chatbot/interviewer_sdk/`. Extraction output: `planpal-extraction.md` next to this file. Read Plan Pal only through sub-agents.

### Pre-build review (session 4)
**Setup**
- **D53** James builds and tests V1 first, but it is **designed for other people from day one** (see D67–D70). Teammates install later by cloning from Git (not set up yet). Code lives **outside OneDrive** (OneDrive sync fights virtual environments and the `runs/` churn).

**Launch and hand-back mechanics** (detail for D2/D3)
- **D54** The skill writes the starting summary to a temp file (avoids Windows command-line length and quoting limits) and runs `launch.py --summary-file <path> --cwd <project>` as a **background** command. On exit the script prints **one JSON line**: `{status: approved | draft | cancelled, plan_path, summary}`. Claude Code's background-task notice delivers it. A cancelled session still returns the run folder path. The window is a child of the Claude Code session; closing Claude Code may close it, which is accepted for V1.

**Panel and tools**
- **D55** **Open items are seeded and tracked by code**, not only by `save_note`: at start the panel is filled from the playbook's done checklist (one open item each); every `ask_user` question registers itself as an open item under a topic; `save_note` takes an optional item ID so it can close an open item or **supersede** an earlier decision (old one kept in interview notes as "replaced"). Code can then tell when every checklist item is decided (feeds D37).
- **D56** `ask_user` card answers: per question, **free text**, a one-click **"accept recommended"**, and **Skip**. Ending the turn is **enforced by an SDK hook** after `ask_user` (Plan Pal showed Opus otherwise makes another call and keeps going); the tool result and prompt also say so.
- **D57** **Approval is enforced in code** (refines D24): `write_plan` may always save with `status: draft`; the window shows the draft in a **review view** with an **Approve** button; only that button flips the header to `approved`. Edits go back through chat.
- **D58** Tools are served from the SDK's **in-process MCP server** for V1 (keeps D46's one process). Tool logic is engine-neutral; a stdio wrapper is added when the Cursor adapter lands.

**Files** (detail for D42)
- **D59** Header = **YAML front matter**. Fields: `name`, `type` (plan | brief), `status` (draft | approved), `date`, `notes` (path), `project_plan` (briefs only), `steps` (list of `{n, title, skill, depends_on, status}`). Step status: `todo | in_progress | blocked | done`. `skill` is free text in V1 (no worker list yet).
- **D60** Naming: `plans/<slug>.md` + `plans/<slug>.notes.md`; briefs in `plans/<project-slug>/briefs/<brief-slug>.md` (+ `.notes.md`). Brief mode: if the project has more than one project plan, the window asks which.
- **D61** Interview notes are written to the **run folder** until the first `write_plan` names the plan, then copied to `plans/` and kept in sync. Abandoned sessions leave nothing in the committed folder.

**Reader safety**
- **D62** Reader folder limits are **enforced in code** (a per-tool permission check that allows only the working directory and extra folders), not just in the prompt. A settings **deny list** blocks data files and folders by default (`*.csv, *.parquet, *.xlsx, *.xls, *.sas7bdat, data/`). At most **2 readers at once**, **5-minute timeout** (both settings).

**Engine isolation**
- **D63** Launchpad and the reader load **no filesystem settings** (no project `CLAUDE.md`, skills or `settings.json`), have built-in tools **fully disabled** (not just missing from an allow list), use **`strict_mcp_config`** (otherwise the user's claude.ai connectors get attached), and use a custom system prompt.
- **D63a** Windows gotchas from Plan Pal: the SDK passes the system prompt on the command line (about a 32K-character limit), so a large playbook plus wiki file may need to go in the first message instead; the SDK's `total_cost_usd` is a running total for the conversation, so per-turn cost is the difference; cache writes on the subscription were 1-hour (2× input price), so the price table needs that rate. Tool definitions always come before the system prompt, so D48's order applies from the system prompt onward.

**Restarts**
- **D64** One mechanism, **"fresh session that catches up from scoreboard + interview notes"**, serves the long-conversation restart (D8), playbook switch (D40), tier switch (D30) and resume (D41). Anything that changes the fixed instructions goes through it.

**UI**
- **D65** Keep the **websocket** (not pywebview's direct JS bridge) so the UI can be tested in a normal browser with the fake engine. pywebview owns the main thread; server and agents run on a background asyncio thread.
**Built for other people to use and customise**
- **D67** **Anything a team might want to change is an editable markdown file, not code.** That covers agent instructions (planner, reader, later workers), the core interview rules, playbooks, plan formats, done checklists, and the tool descriptions the model sees. Code holds only mechanics.
- **D68** **Agent definitions are markdown files**: YAML front matter for `name`, `engine`, `model`, `tools`, with the instructions as the body. Non-coders can read and edit them (supersedes the "plain fields" wording in D20).
- **D69** **Override layers**, first match wins: **personal folder** (`~/.mission-control/custom/`) → **team folder** (any path set in the settings file, e.g. a shared repo or wiki folder) → **bundled defaults** in the app. Files are matched by the same relative path (e.g. `agents/planner.md`, `playbooks/analysis.md`), so a team overrides one file by copying it and editing. Bundled defaults are never edited in place, so app updates don't clobber team changes.
- **D70** The app shows **which layer each file came from** (in the run receipt and, later, a settings screen), so "why is it behaving like this?" is answerable. A broken override (e.g. bad front matter) falls back to the next layer with a visible warning, never a crash.
- **D66** Model output in chat is rendered as markdown and **sanitized** (bundled DOMPurify); links open in the system browser, never inside the window.

---

## 6. Suggested package layout (starting point, not yet confirmed in detail)
```
mission-control/
  agentlib/            # the small agent library
    engines/
      claude.py        # Agent SDK adapter
      cursor.py        # CLI/ACP adapter (after research)
      fake.py          # scripted replies for testing
    agent.py           # simple agent definition: name, engine, model, instructions, tools
    usage.py           # token counting + cost approximation
  app/
    core/              # session manager, event stream (websocket), settings, runs manager, retention cleanup
    tools/             # MCP server: ask_user, explore, save_note, write_plan
    launchpad/         # planner prompts, scoreboard, plan/notes writers, header validator
    playbooks/         # default + presets (analysis, ML, presentations)
    ui/                # bundled web page (chat, live panel, sidebar, cards)
  launch.py            # entry point called by the Claude Code skill
```

## 7. Later version: visual board
- A board beside the chat showing on-the-fly previews of options (chart types, colour palettes) with **made-up data**, for any domain. **No ready-made templates.**
- The planner never writes code. It writes a short brief ("three chart options for monthly claims trend, two palettes") to a **very cheap visual agent** (Haiku) running in the background in its own session.
- The visual agent gets **no tools**, returns one self-contained web snippet (size-capped), which the app saves; the planner receives only the file location.
- Previews render in a **locked-down frame**: no internet, no access to the rest of the app. Charting libraries bundled.
- A **"try again"** button for broken previews. A chosen option is recorded as a normal decision.
- V1 prep only: room in the layout, and question cards that can reference a preview.

## 8. Still open
- Cursor engine details: see section 9 research; may change D22–D23.
- Default long-conversation warning threshold: placeholder **60% of the model's context window**; tune after real use.
- Token price table values: start from Plan Pal's `config/pricing.json` (list prices, 1-hour cache writes).
- Exact contents of the presets (analysis, ML, presentations).
- Location and name of the wiki related-pages file (D30c), and whether the "existing Haiku reader" (D26) is Plan Pal's reader: confirm from `planpal-extraction.md`.

---

## 9. Research brief: Cursor vs Claude Agent SDK
**Copy this section into a fresh research session.**

You are researching, from the most current official documentation, whether Cursor's command-line agent can do everything the Claude Agent SDK (Python) can do for a specific app. Use official sources first (cursor.com/docs, Cursor changelog and staff forum posts, docs.claude.com / Anthropic Agent SDK docs, the claude-agent-sdk GitHub repo). Note the date and version of every source. Where docs are silent, say "not documented" and suggest a quick experiment.

**Context.** A local Python desktop app (pywebview window) runs an interactive planning agent, and later an orchestrator with worker agents. Launcher and engine are independent: the app can be launched from Claude Code or Cursor, and each agent role can run on Claude (Agent SDK) or Cursor (CLI). A small wrapper library defines an agent as: name, engine, model, instructions, tools. Company access to Claude is through a LiteLLM gateway; enterprise licences for Claude Code and Cursor. Everything runs locally; claims data must not leave approved channels.

**Initial findings to confirm** (quick search, 2026-11-04): Cursor CLI has print mode (`-p`), `json` and `stream-json` output (newline-delimited events), session IDs in results, MCP support via `mcp.json` shared with the editor, rules from `.cursor/rules`, `AGENTS.md`, `CLAUDE.md`, and an ACP server mode (`agent acp`, JSON-RPC over stdio) for custom clients.

**For BOTH Cursor CLI and Claude Agent SDK, give a verdict (Yes / Partly / No / Not documented), evidence and a source link:**
1. **Programmatic control**: official library, or CLI only? What ACP offers: spec, messages, stability, client examples.
2. **Non-interactive runs and streaming**: exact flags; full list of stream event types; can partial text stream live to a UI?
3. **Multi-turn sessions**: one open session with several messages, or one process per call? Session IDs, resume, where history is stored and for how long.
4. **Instructions**: set directly per call, or only via rules files? Can project rules / `AGENTS.md` / `CLAUDE.md` be turned off?
5. **Restricting tools**: disable all built-in tools and allow only custom ones? Allow/deny lists, read-only mode, approval prompts in print mode.
6. **Custom tools via MCP**: specify MCP servers per run (flag or config path) rather than global `mcp.json`? Local stdio servers in print mode? Limits on tools or schemas?
7. **Sub-agents**: supported? If not, can several CLI processes run in parallel safely?
8. **Model choice**: per-run model selection; enterprise models; Anthropic models; can it point at a company gateway like LiteLLM or does it always route through Cursor's servers?
9. **Token usage**: input, output and cached tokens per run reported? Any other way to get usage?
10. **Prompt caching**: documented behaviour; can instruction order be controlled for a stable cached prefix?
11. **Sandbox and security**: defaults (network, files), where prompts and code go, enterprise privacy mode, retention, anything blocking local use on sensitive data.
12. **Working directory and file access**: how it's set; can reads be limited to the working directory plus a list of extra folders?
13. **Errors**: how failures, timeouts and rate limits appear in print mode and `stream-json`.
14. **Authentication in scripts**: API key vs login token; enterprise considerations.
15. **Windows and Mac**: platform differences, especially Windows.

**Then provide:**
- A side-by-side table: capability × Agent SDK × Cursor CLI (verdict + one-line note).
- Top 3 risks of using Cursor as an engine here, each with a workaround.
- A recommendation: CLI print mode vs ACP for the Cursor adapter, with reasons.
- Whether the library's interface (start session, send message, stream reply, use tools, count tokens) can be fully supported by both engines, and which parts are engine-specific.
- Quick experiments (commands) to confirm anything undocumented.

Keep it factual and sourced; flag anything recent, beta or experimental.

---

## 10. Build order (suggested)
1. Plan Pal extraction run (D50): output in `planpal-extraction.md`.
2. `agentlib` with Claude + fake engines and token/cost counting.
3. App core: one process, localhost server + websocket with security checks, settings file, runs folder + retention cleanup.
4. UI shell: sidebar (Launchpad live, others greyed), chat, question cards, live panel, token counter.
5. MCP tool server: `ask_user`, `explore`, `save_note`, `write_plan`.
6. Launchpad: prompt assembly, default playbook, rounds/pushback rules, scoreboard → interview notes, header validation, brief mode linked to project plans.
7. Reader integration: background session, 300-word bullet summary, quiet pickup, failure handling.
8. Launch skill for Claude Code: passes summary, receives path + short summary.
9. Resume-from-notes, long-conversation warning, close confirmation.
10. Preset playbooks; then the Cursor adapter once research is back.

---

## 11. Revisions after first hands-on test (session 5, 2026-11-04)
- **D40 revised**: there is no playbook chooser up front. The planner sees only a catalogue of playbook names and descriptions. From the first description it **guesses the playbook and asks it as a normal round-1 question**, with its recommendation and reason. After the user confirms, it calls a new tool, **`use_playbook`**, whose result carries the playbook text into the conversation, so there's no restart and the cached prompt stays stable. It can be called again to switch later.
- **D24 revised**: the planner has five tools (adds `use_playbook`).
- **D38/D55 revised**: playbooks are **optional structure** ("what tends to matter for this kind of request", a short done check and a plan format), **never a form to fill in**. The panel is not seeded with checklist items; topics appear as the conversation raises them. The interview style follows Plan Pal's (see `docs/planpal-interview-style.md` in the repo).
- **D71 Dugout**: a sidebar section where users see **every agent and the exact prompt it gets**: the assembled system prompt with each part labelled by source file and layer, the exact tool descriptions and schemas, built-in tools on or off, and the exact message sent on each turn or research job. It updates live. This is what "transparency" means here.
- **D72 Visual style**: the UI follows Plan Pal's look, especially its question cards. Flat and calm, with no gradients.
- Code lives in `C:\Users\JFKir\dev\mission-control` (not under git yet). The agent map is at `docs/agent-map.html`.

## 12. Revisions after second hands-on test (session 5)
- **D73 Typed answers**: card answers must be typed. Recommendations and "ideas" are shown as hints only, with no one-click accept and no clickable options. Skip still leaves a question open.
- **D74 Pushback with justification** (strengthens D35): each typed answer reaches the planner with its own recommendation alongside. If an answer is surprising or goes against the recommendation, an earlier decision or a research fact, and it concerns method or important steps, the planner asks "why" in the next round and records the decision only once it's justified. Answers no longer mark decisions in code; the planner's `save_note` does.
- **D75 Two distinct outputs** (refines D30, D42, D59):
  - **Project plan**: high level, the source of truth for project goals, audience, scope, success, constraints, principles, phases or milestones, risks and key decisions. **No YAML front matter** and no worker steps. Code keeps a single italic status line under the title.
  - **Brief**: a focused plan for one portion of the project, **structured with the YAML header and steps** for future workers. It links to the project plan and ends with "Changes to the project plan". Saved to `plans/<project>/briefs/`.
  - **Playbooks apply to project plans only**, and each one's plan format lists the project plan headings. Briefs use one fixed format.
- **D76 Tier decided in the interview** (replaces the launch-time choice): at start, code scans the project's `plans/` folder for existing project plans. If there are none, the session is a project plan. If there are some, round 1 asks, for example, "Is this a brief under *Weekly claims trend pack*, or a new project plan?", with a recommendation. A `set_mode` tool then loads the mode's instructions and template, plus the project plan as background for a brief, into the conversation, with no restart. The tier shapes the interview: **broad** questions for a project plan, **technical/specific** ones for a brief. It can switch, with the user's OK, until the first draft is saved. `/launchpad` just opens the window.
