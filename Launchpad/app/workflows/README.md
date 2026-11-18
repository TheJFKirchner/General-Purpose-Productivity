# app/workflows/

Workflows: a recurring report or study as a straight line of stages, run and watched from the Workflows view.
Request: `Features/2026-11-17-workflows.md`. Websocket contract: `app/server.py` header, "Workflows" block.

| File | What it does |
|---|---|
| `format.py` | The file format: checking (warnings), discovery, the page's `workflow` object, the JSON the form writes, which agents a stage may name |
| `runner.py` | One run: stages in order, agent stages on their Crew agent (agentlib, Builder rules via `StepContext`), review stops, send-back, test folder, run folder records |
| `records.py` | Markdown written into the run folder: result files, review records, `run-summary.md` |
| `manager.py` | The hub's side: `workflows_*` / `workflow_*` messages, one run per workflow, Missions switches, reconnect replay |
| `example-workflow.json` | The one shipped example (reference; the `--fake` demo copies it into "Demo shop") |

## The file
- One JSON file per workflow: `<connected folder>/workflows/<slug>.json`, found in the primary folder and the folders ticked as additional
- The file is the only definition. The Add / Edit form writes it; editing it by hand is fine. A file with a mistake shows as a card with warnings and cannot run
- Paths (attached files, output folder, file inputs): relative to the workflow's connected folder, or absolute

| Field | Meaning |
|---|---|
| `format` | `1` (written by the form) |
| `name` | Required |
| `description` | Optional |
| `output_folder` | Required. Each real run gets a dated subfolder here (`YYYY-MM-DD_HHMM`); test runs reuse `test` |
| `unattended_default` | `true` / `false`: whether Run's Unattended box starts ticked |
| `inputs` | `[{name, label, kind: text\|date\|number\|file\|choice, required, default, options, help}]`; `name` = `[a-z][a-z0-9_]*` |
| `files` | Markdown files (`.md`, `.markdown`) every agent stage gets; read at the start of each run; a missing one blocks the run |
| `stages` | At least one, in order. Agent: `{kind: "agent", title, agent, instruction, files}`. Review: `{kind: "review", title, checklist: [{text, kind: tick\|answer}]}` |

- `agent` = the Builder (`launchpad-builder`), the Explorer (`launchpad-astronaut`, read-only) or one of the folder's own agents that can take a plan step. It runs under its usual rules, model, guards and skills
- A checklist item given as a plain string is a `tick` item. An empty checklist = a plain stop and sign-off

## A run
- Each agent stage gets the instruction, all inputs, the workflow and stage attachments, every earlier stage's result, and any reviewer's send-back note; it finishes with `submit_report {result, status, issues, assumptions, files}` and code writes `NN-<stage>.md`
- Agents may write data files into the run folder without a card, even outside the connected folder; anything else follows the Builder's rules
- Review stages always stop (Unattended only covers agent questions and permission requests). Approve needs every item ticked or answered and a name; send-back needs a name, a note and an earlier agent stage, which runs again with everything after it. Rejected results are kept (`-2`, `-3`, ...)
- Test runs: `<output>/test`, emptied completely at the start of each test run, only when it holds Launchpad's marker `.launchpad-test-folder`; a `test` folder without it is refused and never touched
- Run folder: results, review records, `run-summary.md`, `run.json`, `questions/`, `assumptions.md`, data files. Launchpad's bookkeeping (activity log, costs): `<folder>/.launchpad/workflow-runs/<run id>/`
- A run also appears in Missions under session id `wf-<run id>`. Runs live in memory: a page reload keeps them, quitting Launchpad ends them
