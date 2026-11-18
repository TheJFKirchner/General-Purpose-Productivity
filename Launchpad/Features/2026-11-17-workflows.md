# Workflows

Status: built
Date: 2026-11-17

A Workflows view where a user registers any report or study they run more than once, so nobody has to ask an agent to go and find the study and its plan again. A workflow is a JSON file describing a straight line of stages. Each stage is either an agent doing one job, with markdown files attached for context, or a human review stop with a checklist and sign-off. The card shows the stages left to right with live status. Runs save everything a person would want as a record into a folder the user chooses, and a test run reuses one folder that is cleared each time. Approved but not started: it is built after request 27 (Settings, connections and MCP) is accepted and after request 29 (sidebar).

Feature branch: `feature/workflows`, created from `feature/sidebar-navigation` (request 29), which itself sits on `feature/settings-connections-mcp` (request 27). Merge in that order.

## What was built, and where it differs from the plan

- Built as planned: the JSON format with checking and discovery (`app/workflows/format.py`), the runner (`runner.py`), run records (`records.py`), the manager and messages (`manager.py`), an example workflow and format notes (`app/workflows/`), and the Workflows view with wide cards, stage track, Run box, review screen and Add / Edit form (`frontend/src/views/Workflows/`).
- **Stage agents are narrower than assumption 4.** A stage may name the Builder, the Explorer or one of the folder's own agents. Planner, Orchestrator, Visualizer and CLI are not offered, because they are built around their own screens. Raised with the user.
- **Choices the back-end builder made, raised with the user:** a failed agent stage fails the whole run (no retry outside a review's send-back); attached files are read once at the start of a run, so stages re-run after a send-back use the same reading; send-back does not require the checklist to be complete, approve does; stopping at a review puts that review back to waiting; send-back targets earlier agent stages only.
- **Runs live in memory.** A page reload keeps a run, including one waiting at a review; quitting Launchpad ends it, though its folder and files stay. Each run already writes `run.json`, so resuming unfinished runs at start is a contained follow-up (a run waiting at a review resumes exactly; one caught mid agent stage restarts that stage).
- **Added beyond the plan:** a waiting review raises a card in Incoming and marks the run as needing the user in Missions and the run row; workflow runs are labelled with the workflow's name there and planner-only actions are hidden; a `test` folder that is a link is refused as well as one without Launchpad's marker.
- **Attached files are typed as paths;** only the output folder has a Browse button.
- Checked: fake-engine tests (including a real load and run of Explorer, folder-agent and Builder stages, the demo's sample workflow run to its review, and Unattended auto-answering a stage question), front-end tests and build, and one UI review of the running demo covering this request and the sidebar, followed by one fix round (Explorer stages failing to load, Unattended shown as off, a waiting review invisible outside Workflows, the stage track cut off, planner labels on workflow runs, a stale review message, the example hidden in the demo).
- Not checked: nothing has been run on a real agent; the fix-round changes were not looked at again in the running app (the stage track fitting at the default size is an estimate); removing a workflow, rejected results shown after a send-back and a run surviving a reload were not seen in the app, only in tests; the Workflows screens at narrow widths.

## Principle agreed first

Launchpad provides the mechanism (a way to define, run and watch a workflow) and has no opinion about the content. Every workflow is somebody's own. The user had been torn between making things anyone can use any way and making something specific, and did not want anything authoritative; "everyone will want their own workflow" was taken as the reason to build the feature, not a reason against it. The same principle covers extras: an email-style summary of a run is not a Launchpad feature, the user makes an agent that writes one and adds it as the last stage.

## Assumptions (shown to the user, uncorrected)

1. Workflows is a new view. Each workflow is a wide card (more horizontal than a Crew box) showing its name, description, its stages left to right, and Run with a Test run tick box.
2. Each workflow is one JSON file in a `workflows` folder at the top of a connected folder, found the same way skills and agents are. Launchpad ships one small example and no others.
3. A workflow is a straight line of stages of two kinds: agent stage and review stage. The picture is drawn from the file.
4. An agent stage names any agent from Crew, built-in or the user's own, and that agent runs under its usual rules and model.
5. Attached markdown files are links, read at the start of each run. Workflow-level files go to every agent stage, stage-level files to that stage. A missing file blocks the run with a warning on the card.
6. Each agent stage writes one result file; later stages and reviews are given all earlier result files.
7. Each run gets a dated subfolder in the workflow's output folder holding result files, data files, review records and a run summary. Agents may write there even when it is outside the connected folder. Only Launchpad's internal bookkeeping (activity log, costs) stays in its hidden folder.
8. A review stage shows the results so far and the author's checklist, needs every item ticked or answered, and records a sign-off with a typed name (remembered for next time) and an optional note. An empty checklist makes it a plain stop and sign-off.
9. A reviewer can send work back to a chosen stage with a note; that stage and all later ones run again, and the rejected results are kept, not overwritten.
10. A test run behaves the same as a real run, review stops included, and its records are labelled as a test.
11. One run of a given workflow at a time. A running workflow also appears in Missions like any other run.
12. Out of scope for the first version: branching, loops and conditions, a drag-and-drop canvas, triggers and running on a schedule, and having the planner draft a workflow.
13. A workflow can define named inputs (for example a valuation date or a data file), filled in at Run, passed to every stage and saved in the run record.
14. Run has an "Unattended" option, off by default with a per-workflow default, which answers agents' questions with their own recommendation and approves their permission requests (the existing Auto answers and Autopilot behaviour). Review stages always stop.
15. Launchpad only empties a `test` folder it created and marked itself; a `test` folder it did not create is refused with a message, never cleared.

## Decisions from the interview

- **JSON definition.** The user wanted a structured object definition and chose JSON over markdown.
- **Straight line, drawn not edited (Q1).** The user's reference point was an n8n style but explicitly not a recreation of it. What makes that kind of tool large is the canvas editor, branching, triggers and integrations; none is needed for the picture and the review points. Branching can be added to the file format later without redoing the picture.
- **Two kinds of stage, no plan stage (Q4).** The first proposal was a workflow as one saved plan; the second was three stage kinds (plan, brief, review). The user did not want attaching a plan to be required, and asked for markdown files attachable to the whole workflow and to individual stages. That made a plan just another attachment, so the plan kind was dropped. Accepted cost: a stage is one agent doing one job and cannot itself be a multi-step orchestrated plan; splitting work into steps is what the workflow is for. It also avoids building a way to run old plan files (today a plan can only run in the session whose planner wrote it).
- **Hand-off by result files (Q5).** Simple, makes a closing summary agent work with no special feature, and gives a review something concrete to show. Named inputs and outputs per stage were rejected as more than a first version needs.
- **Attachments are links (Q6).** A corrected methodology page is used by the next run automatically; no second copy. Refusing to start on a missing file is safer than running a study without a page it was meant to follow.
- **Output folder chosen by the user (Q7).** The user did not want a team's study records saved in a hidden `.launchpad` folder: several people work on a study and need a real record of the files that went into it, in a folder they already use (a shared drive or a repo).
- **Review stage is a fixed gate; AI help is a separate stage (Q8).** The user asked whether review should be a dedicated agent that is given questions that must be answered, or a plain stop and sign-off. Decision: neither alone. Agent-written questions vary run to run and let the agent decide what matters, so they must not be the gate; for actuarial studies the checks before sign-off are set by the method's owners and are the same every time. Launchpad provides the checklist, sign-off and saved record. If the user wants AI preparation, they place an ordinary agent stage before the review that writes a memo (what it verified, what looks off, questions for the reviewer). The user called human review the most important part and a natural breaking point.
- **Send back to a chosen stage (Q9).** A review that can only approve is not a review; choosing the stage avoids re-running a whole study for a problem in its last section.
- **Test run (user's addition).** The user was tired of testing leaving hundreds of dated folders. Real runs get dated folders; test runs share one `test` folder inside the output folder that is completely cleared at the start of each test run.
- **Run-time inputs (Q10)** and **Unattended (Q11)** as in assumptions 13 and 14.
- **Registering by form (Q3).** An Add workflow form writes the JSON; the file stays the single definition and can be edited directly.
- **Build order (Q12).** After the sidebar (request 29).

## Later ideas (not in this build)

- A test run lists every permission the agents asked for, so they can be sorted out before the workflow is run unattended. Raised by the user, who said it is not important now.
- The planner drafting a workflow from a description.
- Analytic spaces (request 28, parked): a workflow with a methodology's pages attached is a general form of the same idea, and may be where spaces come back.

## Facts about today's code that the build rests on

- A plan is `<folder>/.launchpad/<session-id>/plan.md`; a run starts only from a draft the in-session planner wrote. The workflow runner is a new path, not a reuse of plan approval.
- Nothing pauses between steps today and nothing chains runs; review stops and stage sequencing are new.
- Step workers already receive the paths of earlier step reports; there is no structured hand-off.
- Folder agents come from `<folder>/.claude/agents/*.md` (`app/agents/crew.py`) and skills from `app/skills.py`, over the primary folder plus ticked additional folders. Workflow discovery follows the same folders.
- Autopilot and Auto answers already exist per session and are what Unattended reuses.

## Shared interface (websocket)

| Sent by the page | Reply |
|---|---|
| `workflows_get` | `workflows_list {workflows}` |
| `workflow_save {folder, workflow, original_id?}` | `workflows_list` |
| `workflow_remove {id}` | `workflows_list` |
| `workflow_run {id, inputs, test, unattended}` | `workflow_run_state {run}` |
| `workflow_stop {run_id}` | `workflow_run_state` |
| `workflow_review {run_id, stage, answers, name, note, decision, back_to?}` | `workflow_run_state` |

- A workflow: `id`, `name`, `description`, `folder`, `output_folder`, `inputs`, `files`, `stages`, `unattended_default`, `warnings`.
- A stage: `kind` (`agent` or `review`), `title`; an agent stage adds `agent`, `instruction`, `files`; a review stage adds `checklist`.
- A run: `id`, `workflow_id`, `test`, `folder`, `inputs`, `status`, and per stage a `status` (waiting, running, done, failed, awaiting review), its result file and, for reviews, the checklist and the saved record.
- `decision` is `approve` or `send_back`; `back_to` names the stage to return to.
- `workflow_run_state` is also pushed whenever a run changes, and replayed on reconnect.
- The header of `app/server.py` is the authoritative contract and `frontend/src/contract.ts` mirrors it. Request 27 showed that a table at this level leaves gaps (where lists ride, exact config shapes, how errors are reported): the back-end builder writes the full contract into the `app/server.py` header first and the front-end builder builds to that.

Filled in by the back-end builder (full detail in the `app/server.py` header, "Workflows" block):

- `workflows_list {workflows, folders, agents, reviewer_name, error?}`: `folders` = where a workflow can be saved (primary, then ticked additional folders); `agents[dir_id]` = the agents a stage may name in that folder (Builder, Explorer, the folder's step-worker agents; Planner, Orchestrator, Visualizer and CLI are not stage agents); `reviewer_name` = the last sign-off name (per user); `error` = why a save or remove was refused. Also sent on connect.
- A workflow adds `slug`, `folder_name`, `path`, `output_path`, `can_run`, `running_run_id`, `last_run_id`; `id` = `"<dir_id>/<slug>"`, `folder` = a dir_id. An input = `{name, label, kind: text|date|number|file|choice, required, default, options, help}`. An attached file = `{path, resolved, exists, name}`. A stage adds `index` (0-based); agent stages add `agent_display`, `agent_purpose`; a checklist item = `{text, kind: tick|answer}`. A warning = `{level: error|warning, code, message, stage, field}`; any error disables Run.
- `workflow_run_state {run, error?, workflow_id?}`: a refused run = `run: null` + `error`; other refusals resend the unchanged run with `error`. A run adds `workflow_name`, `mission_id`, `unattended`, `autopilot`, `auto_answers`, `current_stage`, `started_at`, `finished_at`, `summary_file`, `error`, `cost_usd`; status `running|awaiting_review|done|failed|stopped`. A stage run = `{index, kind, title, status: waiting|running|done|failed|awaiting_review, agent, agent_display, result_file, result_markdown, attempts, checklist, review, reviews, error, cost_usd}` (`result_markdown` = the current result's text for the review screen, since the run folder may be outside every connected folder); a review record = `{decision, name, note, at, answers, back_to, record_file}`.
- `workflow_review` `stage` and `back_to` are 0-based stage indexes; `answers` = one `{ticked?, answer?}` per checklist item. Approve needs every item and a name; send-back needs a name, a note and an earlier agent stage.
- Missions: a run also appears as a Missions run under `session_id = run.mission_id` (`"wf-<run id>"`) through the existing run events; `run_stop`, `set_autopilot` and `set_auto_answers` on that id work for the workflow run. `run_started` and `run_finished` carry `workflow {id, name, run_id, test}` (the marker of a workflow run: label it as the workflow, hide Send to planner); `run_started` also carries `auto_answers` and is followed by `autopilot` / `auto_answers` events. A run waiting at a review marks the step `waiting_for: "review"` and posts a `queue_item` of kind `review` (the "needs you" card, with `workflow`, `run_id`, `stage`), resolved when the review is signed or the run stops.
- Form helpers reuse `list_dir` (browse a connected folder) and `pick_directory` (an output folder anywhere); no new messages.

## Tasks

### Task A: back end

- **Goal:** the workflow file format with checking and discovery, and the runner: stages in order, attachments, hand-off of result files, output folders, test runs, inputs, unattended mode, review stops with sign-off records, and send-back.
- **Builder:** factory-builder, Opus (agent wiring).
- **Owns:** `app/`, `tests/`, Launchpad docs (CLAUDE.md, `app/README.md`, `docs/architecture.md`), the example workflow.
- **Read first:** `app/server.py` header, `app/hub.py`, `app/agents/orchestrator/run.py`, `app/agents/builder/`, `app/agents/crew.py`, `app/skills.py`, `app/sessionfiles.py`, `../agentlib/README.md`.
- **Done when:** a workflow file with a mistake is reported clearly on its card and cannot run; a run produces the dated folder with result files, review records and a summary; inputs reach every stage and appear in the run record; a test run clears and reuses the `test` folder and refuses one it did not create; a missing attachment blocks the run; Unattended never skips a review; send-back re-runs from the chosen stage and keeps the rejected results; a run in progress survives a page reload; `--fake` shows a believable workflow and run; `python -m pytest` passes on the fake engine.
- **Runs with:** Task B, in parallel, once the contract is in the `app/server.py` header.

### Task B: front end

- **Goal:** the Workflows view: wide cards with the stage picture and live status, the Add and Edit form, the Run box with inputs, Test run and Unattended, and the review screen with checklist, sign-off and send-back.
- **Builder:** factory-builder, Sonnet, UI.
- **Owns:** `frontend/`.
- **Read first:** `frontend/README.md`, `frontend/src/views/Crew/`, `frontend/src/views/Missions/`, `contract.ts`, the sidebar from request 29.
- **Done when:** the view is in the sidebar; a workflow can be added, edited and removed from the form; the picture shows each stage as waiting, running, done, failed or awaiting review; warnings (bad file, missing attachment) show on the card and disable Run; a review cannot be signed off with unanswered items; send-back asks for a stage and a note; a sensible empty state; demo data covers every screen; `npx vitest run` passes and `npm run build` succeeds.
- **Runs with:** Task A, in parallel.
