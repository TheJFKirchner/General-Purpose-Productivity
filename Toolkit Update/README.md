# Toolkit Update

The analysis toolbox and brain in one folder, ready to add to a Claude Code workspace.

- The skills, agents and brain files here are copies; their working copies live elsewhere in this repo (see "Keeping this folder current").
- `design-library\` and `add-to-claude-md.md` are not copies: they live only here and are edited here.
- `claude\` has no dot on purpose: sessions on this repo do not load every skill twice.

## What is in it

| Item | What it does |
| --- | --- |
| `claude\skills\toolbox` | Starts a project: a short talk, the map in `CLAUDE.md`, a plan |
| `claude\skills\analysis` | Explores data in the conversation; a short HTML report when asked, its sections added from the design library |
| `claude\skills\findings` | Keeps `findings.md`: cited results against the plan |
| `claude\skills\commentary` | Dashboard text across many filters or refreshes |
| `claude\skills\dashboard` | Starts a dashboard or changes one: sections added from the design library, then edited |
| `claude\skills\presentation` | Builds a reveal.js deck; slides and charts added from the design library |
| `claude\skills\brain-cite` | Lists the wiki pages worth reading for an ask, in `braincite.md` |
| `claude\skills\brain-file` | Files recorded session facts into personal wiki pages |
| `claude\skills\brain-ingest` | Pulls facts from documents in the wiki's `personal\raw\` and files them |
| `claude\skills\brain-promote` | Moves picked lines from a personal page to the team page |
| `claude\agents\commentary-generator.md` | Writes `commentary.json` for the commentary skill |
| `claude\agents\design-librarian.md` | Saves visuals the user likes into the design library |
| `claude\agents\brain-*.md` (4) | Do the reading and writing for the brain skills |
| `design-library\` | Shared slides, charts, tables, hero cards, animations, layout pieces and themes; `index.html` shows them all |
| `brain\scripts\wiki_index.py` | Lists every wiki page for the brain agents |
| `add-to-main-agent.md` | Paste into the main agent file: how the main conversation records facts, picks a skill and works beside an existing orchestrator |
| `add-to-claude-md.md` | Paste into the workspace or user-level CLAUDE.md: install places, software, synced folders, project layout |

## Install

1. Copy the contents of `claude\skills\` into your `.claude` folder's `skills\` (the workspace's, or the user-level one), and `claude\agents\` into its `agents\`.
2. Put `design-library\` beside whichever `.claude` folder you used (same parent folder), or put its path on a "Design library:" line in a project's map. The skills look at the map line first, then beside `.claude`.
3. Put `brain\` anywhere that stays put (beside `.claude\` is fine).
4. Paste everything below the line in `add-to-main-agent.md` into the main agent file. Fill its two paths: the `brain\` folder and the wiki root.
5. Paste everything below the line in `add-to-claude-md.md` into the workspace or user-level CLAUDE.md. Fill the `.claude` folder and a dashboards folder outside OneDrive. Nothing goes into project CLAUDE.md files; the toolbox writes their maps.
6. Build the brain index: `python "<brain folder>\scripts\wiki_index.py" "<wiki root>"`. It prints how many pages it listed.

The wiki must already have:

| Path in the wiki | Holds |
| --- | --- |
| `team\`, `personal\` | Pages |
| `team\templates\` | One `.md` per page template |
| `team\rules.md`, `personal\rules.md` | Page rules |
| `team\tags.md`, `personal\tags.md` | Allowed tags |
| `personal\raw\session-facts\` | Facts waiting to be filed |

## What each skill needs

| Skill | Needs |
| --- | --- |
| analysis | Python with pandas; pyarrow for kept or `.parquet` sources; openpyxl for `.xlsx` sources and Excel exports; Edge or Chrome for screenshots |
| dashboard | Node.js; Python 3.10+ with fastapi, uvicorn, duckdb, pyarrow, pandas; Edge or Chrome for screenshots |
| presentation | Node.js; Edge or Chrome for screenshots |
| design-library | Node.js to save items or rebuild the index |
| brain skills | Python |
| Reports, decks, library items | Internet when opened: the chart library loads from a CDN |
| Agents | Sign-in that allows the `sonnet` and `haiku` models |

## First use

1. "New project": toolbox asks a few questions, writes the map and plan.
2. Ask a question of the data: analysis explores in the conversation.
3. "Write it up": analysis builds a report.
4. "Add that to the findings": findings records it with its source.
5. "Save that chart": design-librarian copies it into the design library.

## Keeping this folder current

- Never edit the copies here. Edit the working copies, then refresh this folder.
- The exceptions: edit the design library in place in `design-library\`, then rebuild its index there with `node build-index.js`; edit `add-to-claude-md.md` in place.

| Working copy (in this repo) | Copied to |
| --- | --- |
| `.claude\skills\` toolbox, analysis, findings, commentary, dashboard, presentation | `claude\skills\` |
| `brain-intake\skills\` (4) | `claude\skills\` |
| `.claude\agents\commentary-generator.md`, `design-librarian.md` | `claude\agents\` |
| `brain-intake\agents\` (4) | `claude\agents\` |
| `brain-intake\scripts\wiki_index.py` | `brain\scripts\` |
| `brain-intake\add-to-main-agent.md` | `add-to-main-agent.md` |

Refresh, in PowerShell from the repo root (robocopy exit codes below 8 mean success):

```powershell
$T = "Toolkit Update"
$X = @("node_modules", "__pycache__", ".pytest_cache", "tests", "shots", "dist", "build")
$Q = @("/NFL", "/NDL", "/NJH", "/NJS")
foreach ($s in "toolbox", "analysis", "findings", "commentary", "dashboard", "presentation") {
  robocopy ".claude\skills\$s" "$T\claude\skills\$s" /MIR /XD $X $Q }
foreach ($s in "brain-cite", "brain-file", "brain-ingest", "brain-promote") {
  robocopy "brain-intake\skills\$s" "$T\claude\skills\$s" /MIR /XD $X $Q }
robocopy ".claude\agents" "$T\claude\agents" commentary-generator.md design-librarian.md $Q
robocopy "brain-intake\agents" "$T\claude\agents" *.md $Q
robocopy "brain-intake\scripts" "$T\brain\scripts" wiki_index.py $Q
Copy-Item "brain-intake\add-to-main-agent.md" "$T\add-to-main-agent.md"
```

- Left out on purpose: `node_modules`, `__pycache__`, `.pytest_cache`, test helpers (`tests`), screenshots (`shots`), build output (`dist`, `build`). The library's `denylist.json` (local hashes of project words) is git-ignored.
- A new skill or agent: add it to the commands and the tables above.
