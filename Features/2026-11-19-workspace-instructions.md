# Two pages for installing the toolkit into an existing setup

Status: built
Date: 2026-11-19

The toolkit is being merged into a work Claude setup that already has its own orchestration logic. `Toolkit Update/` now has two separate pages to paste from: `add-to-main-agent.md` for how the main conversation behaves, and `add-to-claude-md.md` for standing facts about the workspace. Picking the skills apart to write them exposed places where the skills disagreed with each other; those were fixed.

## Decisions

- **The show-or-tell test.** The owner's rule for both pages: when the relevant skill is loaded for the job, will it show or tell the reader this? If yes, the line stays off the page, or becomes a one-line pointer. Restating a skill is the failure mode. A line earns its place only if it is needed before any skill loads, sits across skills and so is in none, concerns the workspace or machine that no skill owns, or concerns the main conversation's own behaviour.
- **`add-to-main-agent.md`** keeps brain's block unchanged and adds: read the project map first (no map means `toolbox`); where a file goes when no skill places it; a router from request to skill; that work stays in the main conversation unless the loaded skill names a subagent; and five lines for living with an existing orchestrator (the skills' gates belong to the user and are not delegated; a delegated builder gets the skill's path and one reference, not its text; a small edit is never split across subagents; a delegated worker writes only where the map says; the orchestrator's own plan files do not replace the project plan, map or findings).
- **`add-to-claude-md.md`** is one block for a workspace or user-level CLAUDE.md: where the toolkit is installed, software needed before first use, the dashboards folder outside every synced folder, and the project layout as one table with a "never anywhere" line.
- **No project template.** The toolbox writes each project's map and the other skills add their own rows, so nothing for a project's CLAUDE.md passed the test. Rejected: a pasted map template, which would restate the toolbox.
- **Source of each page.** `brain-intake/add-to-main-agent.md` is the source of the bundle's main-agent page and the two stay identical. `add-to-claude-md.md` and the bundle's README are edited in place in `Toolkit Update/`.

## Skill disagreements fixed

- A report's refresh step is `python run.py report` everywhere; the plain form does not build the page.
- Dashboard examples point at `../reports/<name>`.
- The dashboard setup tool, both dashboard skills and the add command agree on chart kinds: bar, line, table, kpi.
- A dashboard screenshot given a bare file name is saved in `Data/.shots/`, which git ignores; screenshots are for looking and are not kept.
- The commentary tables file follows one convention: the default file, and the name the command prints.
- The bundle README lists pyarrow and openpyxl as well as pandas for reports.
- The optional "Design library:" map line is described as optional, for a library kept somewhere unusual.

## Rules added where the skills were silent

- **Deck screenshots** go to the system temp folder, in a subfolder named for the deck, and are not kept.
- **Excel.** The report export writes a real workbook: `python run.py data NAME [TABLE] --out <file>.xlsx`, one sheet per table when no table is named. Excel files go in the project's `exports/`.
- **A dashboard for a project in a synced folder** goes in `<workspace dashboards folder>/<project>/`. The project's map row names that folder, and its sources script reads the project's `inputs/` by absolute path. This is the one stated exception to "relative paths only".
- **The optional slide overflow check** is installed with the presentation skill's scripts, never in a project.

## Open

- **Database credentials.** No mechanism was invented. The skill says to ask how the machine connects and never to write a password, token or connection string into a project, the map or a skill.
- **Git ignore rules for a report's built page and screenshot.** None added.
- The fixes were checked by the builder on scratch copies, not by a cold run of the skills.
