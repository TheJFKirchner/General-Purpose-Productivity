# brain-intake

Four skills that get facts into a markdown wiki and tell a project which wiki pages to read. Facts are recorded during a session and filed later, in a separate step the user starts. Filing is automatic: no questions, and it creates a page when a topic has none. Filing writes personal pages only; team pages change only through the promote skill. Data dictionaries are never touched. Design decisions: [Features/](Features/README.md).

## Skills

| Skill | What it does |
|---|---|
| [brain-cite](skills/brain-cite/SKILL.md) | Takes what the user is working on, has a sub-agent go through the wiki index, and adds the pages or sections worth reading to the project's `braincite.md`, each with a reason |
| [brain-file](skills/brain-file/SKILL.md) | Files every session fact recorded so far, with no questions: one sub-agent decides where each goes, creates a page when a topic has none, and works them all in |
| [brain-ingest](skills/brain-ingest/SKILL.md) | Has a sub-agent pull facts from documents dropped in `personal/raw/`, then files them the same way, with no questions |
| [brain-promote](skills/brain-promote/SKILL.md) | Moves lines the user picks from a personal page to the team page of the same name |

## Sub-agents

| Agent | Model | What it does |
|---|---|---|
| [brain-context-analyst](agents/brain-context-analyst.md) | Haiku | Picks up to 8 pages or sections worth reading for an ask |
| [brain-extractor](agents/brain-extractor.md) | Haiku | Reads documents and returns the durable facts in them |
| [brain-filer](agents/brain-filer.md) | Sonnet | Decides where each fact belongs and works it into that personal page, in the page's own style, creating a page from a template when a topic has none. One per filing, however many pages are touched |
| [brain-promoter](agents/brain-promoter.md) | Sonnet | Adds picked lines to a team page and removes them from the personal page |

## Other files

| Item | What it is |
|---|---|
| [scripts/wiki_index.py](scripts/wiki_index.py) | The only script. Lists every wiki page with its description and section headings, so a sub-agent does not have to open every page to learn what exists. It makes no decisions and changes no page |
| [add-to-main-agent.md](add-to-main-agent.md) | Text to paste into the main agent file. Only what no skill covers: where the wiki and this folder are, how to record facts during a session and tell them from findings, and how to use a `braincite.md` |
| [how-to-build-findings.md](how-to-build-findings.md) | Goes in the new-project standup instructions: how to create and keep a project's `findings.md`. Matches the `findings` skill in this repo |
| [test-wiki/](test-wiki/) | A small sample wiki (team and personal pages from different templates, one data dictionary, waiting facts and documents, a sample project) for trying the skills |

## How the pieces fit

1. During a session the main conversation records facts in the wiki's `personal/raw/session-facts/` folder, one line each, with the page a fact belongs on when that is known.
2. When the user runs `/brain-file`, one sub-agent works every fact into personal pages without asking anything, and the user is told what went where.
3. A fact whose topic has no page gets a new personal page, started from the best-fitting team template. The few facts that cannot be filed (a contradiction the rules do not cover, a full page) are kept in `session-facts/unfiled.md` and tried again next time.
4. Filed facts files and ingested documents move to `personal/raw/processed/`.

## Install

1. Copy the four `skills/` folders to `~/.claude/skills/` and the four `agents/` files to `~/.claude/agents/`.
2. Paste `add-to-main-agent.md` into your main agent file (CLAUDE.md) and fill in its two paths: this folder and the wiki root. The skills read them from there.
3. Check that Python runs: `python scripts/wiki_index.py "<wiki root>"` should print how many pages it listed.
4. Try the skills first with the wiki root set to a copy of `test-wiki/`.

## What you must set up or check when moving this to another computer

Every folder and file name below is an assumption written into the skills, agents or script. None has been checked against a real wiki. If yours differs, either make the folder or link match, or change the name in the files listed.

### You set these yourself

| What | Assumed | Where it is written |
|---|---|---|
| Wiki root | An absolute path you type in | The `Wiki root:` line of the text pasted from `add-to-main-agent.md` |
| This folder | An absolute path you type in | The `Brain folder:` line of the same text |
| Where skills are installed | `~/.claude/skills/brain-cite`, `brain-file`, `brain-ingest`, `brain-promote` | Copy or link the four folders in `skills/` |
| Where agents are installed | `~/.claude/agents/` | Copy or link the four files in `agents/` |
| Project folder | The folder the session is open in; `braincite.md` sits directly in it | `skills/brain-cite`, `brain-file`, `brain-ingest` |

### Must already exist in the wiki

| What | Assumed path under the wiki root | Where it is written |
|---|---|---|
| Team pages | `team/` | `scripts/wiki_index.py` (`SIDES`), all four agents, `add-to-main-agent.md` |
| Personal pages | `personal/` | Same |
| Page templates | `team/templates/`, one `.md` per template | `agents/brain-filer.md`, `agents/brain-promoter.md`, `skills/brain-promote` |
| Rules for personal pages | `personal/rules.md` | `agents/brain-filer.md`, `agents/brain-promoter.md` |
| Rules for team pages | `team/rules.md` | `agents/brain-promoter.md` |
| Allowed tags | `personal/tags.md`, `team/tags.md` | `agents/brain-filer.md`, `agents/brain-promoter.md` |
| Data dictionaries | Any file named `*-dictionary.md` or `*.dictionary.md` | `scripts/wiki_index.py` (`DICTIONARY_PATTERNS`), all four agents |
| Session facts waiting to be filed | `personal/raw/session-facts/` | `add-to-main-agent.md`, `skills/brain-file` |
| Documents waiting to be ingested | Files directly in `personal/raw/` | `skills/brain-ingest` |

### Created automatically the first time they are needed

| What | Path under the wiki root | Where it is written |
|---|---|---|
| The page index | `brain-work/index.md` | `scripts/wiki_index.py`, all four skills |
| Filed session facts | `personal/raw/processed/session-facts/` | `skills/brain-file` |
| Ingested documents | `personal/raw/processed/` | `skills/brain-ingest` |
| Facts that could not be filed | `personal/raw/session-facts/unfiled.md` | `skills/brain-file`, `skills/brain-ingest` |

### Other things assumed

| What | Assumed | Where it is written |
|---|---|---|
| Folders that hold no pages | `templates`, `raw`, `sources`, `brain-work` are skipped by the index, as are `rules.md` and `tags.md` | `scripts/wiki_index.py` (`SKIP_FOLDERS`, `SKIP_FILES`) |
| Page sections | Marked with `##` headings | `scripts/wiki_index.py` |
| Page description | A `description:` line in the page's frontmatter | `scripts/wiki_index.py` |
| Model names | `haiku` and `sonnet` are allowed by your sign-in | The `model:` line of each agent file |
| Python | `python` runs from the shell | The index step of each skill |

## New pages

A new page is never free-form. The filer and the promoter start every new page from a template in the templates folder, keep that template's headings, and write it to the wiki's rules like any other page. The rules are `rules.md` in each side's folder (`personal/rules.md`, `team/rules.md`), confirmed by James on 2026-11-18 as the layout of the real wiki.
