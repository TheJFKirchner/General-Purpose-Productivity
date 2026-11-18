# brain-intake

Gets facts into a markdown wiki cheaply, and tells a project which wiki sections to read, counting each read. Facts from sessions and documents are filed to personal pages by typed skills over small-model sub-agents and one script; team pages change only through a separate promote step. Data dictionaries are never touched. Nothing runs by itself and nothing is filed without one yes. Design decisions: [Features/](Features/README.md).

## Skills

| Skill | What it does |
|---|---|
| [brain-file](skills/brain-file/SKILL.md) | Files the session facts to personal pages, routing against the project's `braincite.md` first |
| [brain-ingest](skills/brain-ingest/SKILL.md) | Turns documents in `personal/raw/` into source records, then files them the same way |
| [brain-promote](skills/brain-promote/SKILL.md) | Moves chosen lines from a personal twin to the team page (new team pages come from a team template) |
| [brain-cite](skills/brain-cite/SKILL.md) | At the start of a project or request, writes `braincite.md`: two tables (Team, Personal) of pages or sections to read, each with an id, when to read it, and a Reads count kept by `brain read` |

## Sub-agents

| Agent | What it does |
|---|---|
| [brain-extractor](agents/brain-extractor.md) | Writes one pending source record per input, routing facts to page names; never opens wiki pages |
| [brain-filer](agents/brain-filer.md) | Merges one packet of bullets into one page under that side's rules and tags |
| [brain-context-analyst](agents/brain-context-analyst.md) | Picks up to 8 pages or sections on one side worth reading for the ask, most important first, and writes BrainCite rows |

## Scripts and files

| Item | What it is |
|---|---|
| [scripts/brain.py](scripts/brain.py) | Every step that needs no judgement: page list, summary, approve, collect, markfiled, log, promote, sections, BrainCite entries, and `read` (one call opens many entries and counts each read). Standard library only |
| [scripts/test_brain.py](scripts/test_brain.py) | Tests for brain.py against the test wiki |
| [brain-reference.md](brain-reference.md) | The one reference: record, packet and BrainCite formats, merge and tag rules, every command |
| [add-to-main-agent.md](add-to-main-agent.md) | Text to paste into the main agent file: how to keep session facts and how to read `braincite.md` entries with `brain read` |
| [hookup-checklist.md](hookup-checklist.md) | Every assumed name and setting, as an install test, with a 7-step smoke test including the read counter and the team-write guard |
| [test-wiki/](test-wiki/) | Small sample wiki (personal, team, templates, one dictionary, a sample project) for trying everything |

## Install

1. Set `BRAIN_HOME` (this folder) and `BRAIN_WIKI` (the wiki root), for example in `~/.claude/settings.json` under `"env"`.
2. Copy the four `skills/` folders to `~/.claude/skills/` and the three `agents/` files to `~/.claude/agents/`.
3. Paste `add-to-main-agent.md` into your main agent file.
4. Walk `hookup-checklist.md`, ending with its smoke test.
5. Try it first with `BRAIN_WIKI` pointing at a copy of `test-wiki/`.
