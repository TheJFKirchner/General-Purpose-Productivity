# Plain-language skills, one filer, no brain.py

Requested 2026-11-18. Overrides requests 1 and 2 wherever they describe `brain.py`, source records, packets, repo sync or one sub-agent per page.

## Why

The skills had become lists of script commands that James could not read or trust. Filing also stood up one sub-agent per page, and standing up a sub-agent costs more than reading several pages.

## Decisions

| Decision | Detail |
|---|---|
| Skills are plain language | Each skill is 5 to 7 steps saying what happens. A script or shell command needs a stated reason to be there. |
| One script | `scripts/wiki_index.py` lists pages, descriptions and section headings. It makes no decisions. `brain.py`, its tests and its reference file are deleted. |
| Shell commands | Only `mkdir -p` and `mv`, to move filed inputs to `personal/raw/processed/`, so a later run knows what is done. |
| No git, no environment variables | The skills never pull, commit or push. The wiki root and this folder are given in CLAUDE.md. |
| Facts are recorded, then filed separately | The main conversation records facts silently during a session, in the wiki's `personal/raw/session-facts/`. Filing happens only when the user runs `/brain-file`; it is never started or suggested. |
| Page noted at record time | A fact ends with `(page: name)` when that page is in the project's `braincite.md` or was opened this session. Never guessed. |
| Filing is automatic | `/brain-file` and `/brain-ingest` ask nothing. The filer decides where every fact goes and the user is told afterwards. (An earlier version of this request had the user confirm each fact; James found that too manual.) |
| One Sonnet filer per filing | It opens the noted pages, finds a page from the index for the rest, and works every fact in. No Haiku scan first; add one only if un-noted facts turn out to be many. |
| Sections are fixed | A page's headings come from its template. The filer never adds, renames or reorders one; a fact with no exact section goes in the page's most general one. |
| Conventions come from the wiki | Citing, tagging and format are taken from the wiki's `rules.md` and `tags.md` and from the style already in the section. Nothing about them is written into the agents. |
| New pages | When no page covers a fact's topic, the filer creates a personal page from the best-fitting team template: one page per topic, not per fact. |
| Unfiled facts | Only a contradiction the rules do not cover, or a full page. They go to `session-facts/unfiled.md` and are tried again next run. |
| Large filings | Over 30 facts, the facts are split into groups by noted page and filed by one filer per group, one after another. |
| Personal page for a team topic | Created automatically when a fact belongs to a team page's topic and no personal page of that name exists. |
| Personal pages only | Filing never changes a team page. Only brain-promote does. |
| Ingest | A Haiku extractor reads the documents and returns facts; the same filer files them. |
| Dropped | The cost log, source records, packets, the pending/approved/filed tracking, the team-write guard script, and brain-cite's preview and yes/no question. |

## Tested 2026-11-18

Each sub-agent was run from its agent file against copies of `test-wiki/`, with the main conversation's steps done by hand. Team pages and the data dictionary were unchanged after every filing run.
