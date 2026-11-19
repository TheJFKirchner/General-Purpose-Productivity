# Toolkit Update bundle

Status: built
Date: 2026-11-19

`Toolkit Update/` is one folder that can be carried to another workspace and installed in one go: the seven analysis toolbox skills, brain's four skills, the six subagents they use, the design library, brain's index script, and one page of lines to paste into the main agent file. It is a copy; the working copies stay where they were.

## Decisions

- **Copy, not move.** The skills only load in sessions on this repo while they sit in `.claude/skills`. Moving them would stop that. Cost accepted: two copies, so the bundle must be refreshed after an edit. The refresh commands are in the bundle's README. Rejected: moving the skills into the bundle.
- **The inner folder is `claude`, not `.claude`.** A `.claude` folder inside the repo would make sessions here load a second copy of every skill. Installing means copying `claude/skills` and `claude/agents` into a `.claude` folder (the workspace's or the user-level one).
- **Layout keeps the design library findable.** The presentation skill looks for the library three folders up from itself, so `design-library/` sits beside `claude/` in the bundle and beside `.claude/` after install. A "Design library:" line in a project's map overrides this.
- **One page for the main agent.** `add-to-main-agent.md` holds brain's block and a new analysis toolbox block. The analysis block carries only what no single skill says alone: the project map, the two fixed rules, the five words, which skill for which job, the read-little rule with the inventory and add commands, when to launch `commentary-generator` and `design-librarian`, and when to tell the user before proceeding. `brain-intake/add-to-main-agent.md` is the source and the bundle copy is identical.
- **One set of findings rules.** Brain's `how-to-build-findings.md` held an older version that disagreed with the findings skill. It is now a short pointer to the skill, and brain's page says to record findings as the findings skill says.
- **Left out of the bundle:** brain's test wiki, decision records and README; the analysis skill's test-data helper; the design library's `denylist.json`, which is also ignored by git.

## Checked

- Every copied file is byte-identical to its source.
- Installed into a scratch workspace, the presentation skill found the design library there, and the report scaffold, the dashboard setup tool and brain's index script ran.
- No machine paths, company names, environment variables or raw agent SDK imports.

## Open

- The refresh is a manual step. A script or a pre-commit check would stop the bundle falling behind.
