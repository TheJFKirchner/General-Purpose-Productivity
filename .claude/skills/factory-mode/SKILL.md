---
name: factory-mode
description: Plan-then-orchestrate workflow for changing one of James's homemade software projects. Interview the user with the grilling skill, show a short plan, then orchestrate factory-builder subagents and report back. Use when the user says "factory mode", or starts planning a new feature or meaningful change to a project under the Misc Claude folder. Do not use for small fixes (a typo, a one-file tweak, a bug with an obvious fix) or when the user says to do it "live" or "just do it".
---

# Factory mode

In factory mode this conversation is a planning and orchestration session. You interview the user until the change is fully understood, agree a short plan, then hand the building to subagents and keep your own context clean. You do not write feature code and you do not read the code that gets written. The point is that the user talks to one orchestrator who holds the design, while the detail lives in the subagents.

Skip factory mode for small fixes, or when the user says "live" or "just do it". If you are unsure whether a request is small, ask in one line.

## The agents

| Agent | Model | Use for |
|---|---|---|
| `factory-reader` | Sonnet by default; pass `model: haiku` for quick scans such as "which files mention X" | Read-only answers about how the project works today, and pass/fail checks of built work |
| `factory-builder` | Opus by default; pass `model: sonnet` for straightforward UI or plain code. Anything involving agent design stays Opus | Building one slice of the plan |
| `factory-ui-reviewer` | Opus | One look at the running UI after the build |
| `security-review` | Opus | One look at the git differences before committing, for exposed keys, personal details and hard-coded machine paths |
| `git-shipper` | Sonnet | The git and GitHub mechanics (feature branches, commit, merge, push, remotes), so git output stays out of this conversation |

"Agent design" means designing AI behaviour inside the software: prompts, system instructions, skills, tool definitions, agent loops.

The model in an agent's definition is only its default; set `model` when you launch it to override.

## Request records

Each project keeps a `Features/` folder: one file per request, and one short list of all of them. Decisions are never recorded in a combined file (no `decisions.md`, no running log). If a project still has one, leave it as it is and put new material in a request file and the list.

- **Request file**: `Features/<YYYY-MM-DD>-<short-slug>.md`. It starts with `# <Name>`, then a `Status:` line (`decided` for a conversation that only settled decisions, `approved`, `built` or `abandoned`), a `Date:` line, and a one-paragraph summary. Then the full detail: for a factory-mode feature, the assumptions list, the decisions reached in the interview (with the reasoning that mattered and the alternatives rejected), and the task blocks. Write it so that a fresh session could pick the work up from this file alone. Nothing private goes in it: no keys, personal details or machine paths.
- **The list**: `Features/README.md`, every request, oldest first. If it does not exist, create it with a one-line introduction, a line saying that newer requests override older ones where they conflict, and a table with exactly the columns `#`, `Request`, `Summary`. Each request gets one row at the bottom:
  - `#`: the next number after the last row, starting at 1.
  - `Request`: the request's name, linked to its file.
  - `Summary`: exactly two plain sentences, written for someone who has not read the file, on what was actually decided or built.

  No other columns.

Requests handled outside factory mode follow the same convention in a project that has a `Features/` folder: a conversation that settles a real decision (not a typo fix) gets its own request file with `Status: decided` and a row in the list.

## 1. Interview

1. Work out which project the change is for. Each subfolder of Misc Claude is an independent project; work inside that project's folder and check it for a README or CLAUDE.md.
2. If the project has a `Features/README.md`, read that list of past requests and open only the request files that bear on this change, so you build on what was decided before (see "Request records" below).
3. Send a `factory-reader` to learn what exists today that bears on the request, so your first questions are informed.
4. Invoke the grilling skill (`grilling` in this repo, or `anthropic-skills:grilling` where that is installed) and follow it fully. The two skills divide the interview between them: the grilling skill is how you interview (the back-and-forth, how questions are asked, when the interview is done), and factory mode is what you interview on. The agenda is set out under "What the interview must cover" below; run that agenda through the grilling skill's method.
5. Facts are your job, not the user's. When a question depends on how the code works today, send a `factory-reader` with one pointed question instead of asking the user or reading the code yourself.
6. Choosing a library is a design decision. Research it during the interview (use a web-reading subagent), settle it with the user, and carry the links into the plan.

### Assume the obvious, ask about the rest

The user's time in the interview goes on design and purpose, not on confirming details. Before you ask anything, sort every open point into one of two kinds:

- **Assumption**: you are about 95% sure what the user would say, because the answer follows from the request, from how the project already works, or from ordinary good practice. Do not ask these. Write them down.
- **Question**: the answer changes what gets built or how, and you could not confidently guess it. These are what the interview is for: what the feature is for, which of several real designs to take, trade-offs, scope, and anything where the user's taste decides.

Show the assumptions as one numbered list, one line each, once the `factory-reader` has reported and before your first question. Ask the user to correct any by number; anything they do not correct stands. As more come up, add them in batches at natural pauses, not one at a time. Carry the final list into the plan so the builders build to it.

This overrides the grilling skill where the two disagree: an assumption the user has seen and not corrected counts as a resolved branch, and is never asked as a question.

If the user answers a plain "yes" several times in a row, you are asking assumptions. Move the rest of that kind to the list and go up a level.

### What the interview must cover

You are a design partner in this interview, not a note-taker. The user wants the feature built the right way, which is not always the way they first describe it. These four areas are the agenda. Each one is a branch the grilling has to work through before the interview can end:

- **Exactly what the user wants.** Pin down the functionality until you could describe every screen, input, output and edge case without guessing, using the assumptions list for the obvious details and questions for the rest. Ask what is out of scope. A vague answer to a real question gets a follow-up question, not a silent assumption.
- **Alternatives and additions.** Propose other ways to get the same result, especially simpler ones, and say which you would choose. Suggest additional functionality that would make the feature cleaner or more complete: the missing empty state, the undo, the setting that removes a hard-coded choice. Offer these as recommendations the user can decline.
- **Problems with what has been proposed.** Look for what will go wrong: conflicts with how the project works today, awkward edge cases, data that will not be there, performance, things that will be painful to maintain. Raise each one with a suggested way round it.
- **How to build it properly.** Settle the technical shape with the user: where the feature lives in the existing code, the data it needs, the libraries, and how the work divides. Use `factory-reader` to ground this in what the code does today.

You do not need to agree with the user. When you think an idea is weak, over-complicated, or solving the wrong problem, say so plainly, give your reasoning and what you would do instead. Then accept their decision; it is their software. Do not soften a real concern into a passing remark, and do not reopen a point once they have decided it.

The interview ends when all four areas are covered and the user confirms you have a shared understanding.

## 2. Plan

Show the plan in chat first; it is saved as a spec file only once approved (see "After approval"). Aim for about one screen: the plan is read by the user, and builders get high-level briefs, not step-by-step instructions.

Start with the final assumptions list from the interview, so the user sees once more what was taken as given. Then one short block per task:

- **Goal**: what this slice delivers, in a sentence or two.
- **Builder and model**: for example "factory-builder, Sonnet, UI".
- **Files or area owned**: what this builder may touch.
- **Relevant files and links**: existing code to read, library docs, anything settled in the interview.
- **Done criteria**: specific, checkable statements of what must be true.
- **Runs with**: in parallel with which tasks, or after which.

How to split the work:

- Separate UI from code where they live in different files. Batch them into one builder when they are closely tied; UI and agent-design work can go together.
- Builders run in parallel only when their file sets do not overlap. If two tasks would touch the same file, merge them into one builder or run them in sequence.
- Where two builders meet (a function signature, a data shape, a route), state that shared interface in the plan so both build to it.

Dispatch nothing until the user explicitly approves the plan.

### After approval: spec file and feature branch

Do these two things before launching any builder.

1. **Feature branch.** If the project folder is a git repo, have `git-shipper` create and switch to a branch named `feature/<short-slug>` from the main branch. The feature is built on this branch so the main branch keeps working until the user accepts the result. If `git-shipper` reports uncommitted changes or that the repo is not on its main branch, take that to the user before going further. If the folder is not a git repo, skip the branch and say so.
2. **Spec file.** The spec file is this request's file, in the format under "Request records": `Features/<YYYY-MM-DD>-<short-slug>.md` in the project, creating the `Features/` folder if it is not there. Every feature built in factory mode gets one. Set `Status:` to `approved`. It must capture the conversation, not just the plan: the summary of what the feature is for, the assumptions list, the decisions reached in the interview with the reasoning that mattered and the alternatives rejected, and the task blocks. At the same time, add the request's row to `Features/README.md`, with a two-sentence summary of what was agreed. The list covers every request, so the row goes in now, not after the build.

The spec is the record of what was agreed. If the scope changes during the build, update the spec to match.

## 3. Build

Launch the builders, parallel ones in a single message. Each brief is that task's block from the plan plus the project folder path and any shared interface. Keep briefs high level: goal, pointers, done criteria. Do not write the implementation into the brief.

Builders return only what they built, issues, and recommendations. If a builder returns code or long text, do not ask for more; work from the summary.

## 4. Check

Check the build without reading it:

- The builders' reports, against the done criteria.
- The list of changed files (for example `git status` or `git diff --stat`), to confirm each builder stayed in its slice.
- The project's tests, build, or the app itself, where it has them.

Never read through the code that was written; that defeats the purpose of delegating it. If something needs a closer look, send a `factory-reader` to check that slice against its done criteria and return pass or fail.

## 5. UI review

If the change touched UI and the app can be launched, run `factory-ui-reviewer` once. It may run only once per user request, so that the build cannot loop. If there is no UI change or the app cannot be launched, skip it and say so in the summary.

It looks through the built-in browser pane when it can, and falls back to a headless screenshot script. If it reports it could not see the app at all, take the one look yourself with the browser tools, under the same once-only rule.

## 6. Fix round

At most one automatic fix round per request. Collect the clear defects from your check and from the UI reviewer, and send each back to the builder that owns that slice (continue the same builder where possible so it keeps its context).

These go to the user instead of into the fix round:

- The reviewer's suggestions (matters of taste). List them and let the user pick.
- Anything that would change the agreed scope.
- Anything still failing after the fix round.

Do not re-run the UI reviewer after the fixes unless the user asks in a new message.

## 7. Finish

Give the user one consolidated summary: what was built, what was checked and how, what is unresolved, the reviewer's suggestions, and the builders' recommendations worth their attention. Mention any `docs/research/` notes the builders wrote. Name the feature branch the work is on and the spec file, and tell the user that the main branch is unchanged until they say to merge.

### Record the feature

Once the build and fix round are finished, and before the commit below:

1. Set the spec's `Status:` line to `built`, and update the spec wherever what was built differs from what was planned.
2. In the list, `Features/README.md`, revise the request's `Summary` so its two sentences describe what was actually built, for the person using the software. Keep the columns `#`, `Request`, `Summary` as they are.

A feature abandoned before the build finished keeps its spec file and its row: set `Status:` to `abandoned` and revise the summary to say it was abandoned and why.

### Security review before committing

If the project folder is a git repo, run `security-review` on it once the build and fix round are finished, and include its verdict in the summary. If the folder is not a git repo, skip this step and say so.

- **CLEAR** or **WARN**: carry on. List the warnings in the summary for the user to decide on.
- **BLOCK**: do not commit or push. Send each finding to the builder that owns that slice, then run `security-review` once more. If it still blocks, stop and take it to the user.

If anything changes after the review has run, run it again before the next commit.

### Committing, merging and pushing

Do not run git commands yourself; hand the mechanics to `git-shipper` with the project folder, exactly what to do, what the user approved, and the commit attribution line. Decisions stay with you and the user: which repo, which branch, and what to do when `git-shipper` stops and reports a problem.

- **Commit on the feature branch: no need to ask.** Once the security review has not blocked, have `git-shipper` commit the work, including the spec file and `Features/README.md`, on the feature branch. Do not push. A commit here is local and leaves the main branch untouched, so it does not need the user's go-ahead. Later changes to the same feature (fixes the user asks for after trying it) are committed to the same branch the same way.
- **Merge into the main branch: only when the user says so.** Have `git-shipper` merge the feature branch into the main branch as its own merge commit, so the feature stays visible as one unit in the history, then delete the merged feature branch.
- **Push: only when the user says so.** A go-ahead to merge is not a go-ahead to push.
- **If the user rejects the feature**, have `git-shipper` switch back to the main branch and leave the feature branch in place. Deleting unmerged work is the user's call.

Work done outside factory mode (small fixes, "live" changes) does not get a feature branch and keeps the ordinary rule: no commit until the user asks.
