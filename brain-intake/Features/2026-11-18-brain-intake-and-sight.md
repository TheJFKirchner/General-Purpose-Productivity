# Brain intake and section-level BrainSight

Status: built

Built 2026-11-18 with one test-and-fix loop. Differences from the plan below: the script has extra commands (`candidates`, `sight-add`, `log`, `root`); work files live in `brain-work/` at the wiki root; `markfiled` refuses to file if any team page or dictionary changed during intake; `promote` creates a new team page from its template and flags first-person, doubt-tagged and unsourced lines; the BrainSight file is two tables (Team, Personal) of section or whole-page entries, with no planning/work split (see section 8). Known weaknesses after testing: some "why read it" cells still give away the finding; a filer folded one of three conflicts into another entry; nothing has been run on a real wiki or on macOS.
Date: 2026-11-18

Rebuilds how facts enter the wiki and how a project finds what to read. Intake becomes three typed skills (file, ingest, promote) over small-model sub-agents and one script, writing only to personal pages; BrainSight points at sections with a reason to read each, instead of whole pages. Built in a standalone `brain-intake/` folder for now, to be moved into the `General-Purpose-Productivity` repo once James says so.

Alternatives rejected: filing straight to team pages on approval (replaced by personal twins plus a separate promote step); routing session facts in the main conversation (given to the small-model extractor to keep the page list out of the main context); a pending view in the wiki app (approval is in chat for now).

## 1. What we are building

A way to get facts into the wiki that is cheap, manual but easy, and never lets an automated step touch a team page or a data dictionary.

- 3 skills, 2 sub-agents, 1 script file, 1 reference file.
- 2 hand-off files for the work install: `add-to-main-agent.md` and `hookup-checklist.md`.

## 2. Fixed rules

| Rule | Detail |
|---|---|
| No hooks | Nothing fires by itself. Every step is a skill James types, or a standing instruction in his main agent file. |
| Orchestrator owns session facts | Only the main conversation appends to the session facts file. Sub-agents report back to it. |
| Intake writes personal only | Sessions, ingest and (later) notes file to personal pages. Team pages change only through `brain-promote`. |
| Data dictionaries are off limits | Dictionary files are excluded from the page list on both sides. No skill, agent or script here reads or writes them. Adding tables is a separate work stream. |
| Table facts are allowed | A fact about a table goes to the table's main markdown page (personal twin first, team by promotion). |
| Rules and tags | Personal write: personal rules, personal tags plus team tags. Team write: team rules, team tags only. |
| Templates | Team pages can only be created from the team templates list. Personal pages have no template list. |
| Cost | Cheapest model that does the job. Scripts wherever no judgement is needed. |
| Size | Each skill at most 60 lines, each agent at most 40. Lists and tables, no prose. Detail lives in the one reference file. |

## 3. Mirror pages

- A personal page can be the **twin** of a team page: same name, frontmatter `twin_of: <team page name>`.
- The twin holds only what the user knows that the team page does not say.
- Filing to a team page name with no twin: the script creates the twin without asking.
- A brand-new personal page with no team counterpart: needs a yes first.
- Promotion **moves** chosen lines from the twin to the team page, so what is left on a twin is always what has not been promoted.
- Readers wanting the full picture read the team page and then the twin.
- Linking stays one-way: personal links to team, never the reverse.

## 4. Pieces

### Skills (James types these)

| Skill | When | Steps |
|---|---|---|
| `brain-file` | End of a session, or whenever session facts have piled up | Page list, extractor on the session facts files, show summary, yes, file to personal pages, mark filed |
| `brain-ingest` | Documents are waiting in `raw/` | Same as `brain-file`, but the extractor's input is the batch of raw documents; raw files move to processed at the end |
| `brain-promote` | James decides something should reach the team | Pick a twin, pick lines, move them, filer merges into the team page |

`brain-ingest` ends by filing, so the two are never both needed for the same material.

### Sub-agents

| Agent | Model | Receives | Does | Returns |
|---|---|---|---|---|
| `brain-extractor` | Smallest (Haiku) | Input file paths, the page list | Writes one source record per input: bullets under exact page names | Record paths and warnings |
| `brain-filer` | Smallest (Haiku) | One packet: target page, bullets, rules file, tags file(s), team page read-only (personal writes), template (new team page) | Merges bullets into the page | Page path, lines added, flags |

- Neither agent has wiki browsing or search tools. Each reads only the paths it is handed.
- The session facts file is just another extractor input, so the main conversation never loads the page list.
- Move the extractor up one model only if testing shows it routes badly. Do not set one blanket model.

### Script: `brain.py` (Python standard library, no model)

| Command | Does |
|---|---|
| `pagelist` | Walks `personal/` and `team/`, writes name, scope, path, one-line description, twin link. Skips sources, raw, dictionaries, SQL, skills, agents, rules, tags, templates. |
| `summary` | Prints pending records compactly: page, bullet count, new pages, warnings. Session records print their bullets in full. |
| `approve` | Sets pending records to approved. |
| `collect` | Validates headings against the page list, creates missing twins, writes one packet per page with the right rules and tags paths. Bad headings fail loudly. |
| `markfiled` | Sets records to filed, regenerates the page list, logs input and output size per agent call. |
| `promote` | Removes the chosen lines from the twin and writes a team packet. |

### Reference: `brain-reference.md`

Source record format, filer merge rules, tag rules, the 150-line page limit. Skills and agents point at it instead of repeating it.

## 5. Flows

### Session facts

1. All session: the orchestrator appends dated plain bullets to `personal/raw/session-facts/<date>-<short name>.md`. No routing, no page names. (Text for this is `add-to-main-agent.md`.)
2. James types `brain-file`.
3. `pagelist`, then one `brain-extractor` turns the facts files into source records with status `pending`.
4. `summary` shows the bullets by page. James can strike a line or say yes.
5. `approve`, `collect`, then one `brain-filer` per page, in parallel.
6. `markfiled`. Facts files move to processed.

### Manual ingest

1. James drops documents in `personal/raw/` and types `brain-ingest`.
2. Repo sync. `pagelist`. Documents are grouped into batches, one `brain-extractor` per batch.
3. `summary` shows counts, warnings and proposed new pages. The main conversation does not read the documents or the record bodies.
4. Yes, then steps 5 and 6 above. Repo sync.

### Promotion

1. James types `brain-promote` with a page name, or picks from the list of twins that have content.
2. The main conversation shows the twin's lines. James picks.
3. `promote` removes those lines from the twin and writes the team packet (team rules, team tags only, personal-only tags stripped).
4. No team page yet: James picks a template from the team list and says yes.
5. One `brain-filer` merges into the team page. Repo sync.

## 6. Source record

Stored in `personal/sources/`. Never deleted; a filed record is the citation target.

```markdown
---
origin: session | ingest | notes
origin_name: <session name, document name, or notes batch date>
user: <username>
date: 2026-11-18
status: pending | approved | filed
---

Summary: two or three sentences.

## [[existing-page-name]]
- One durable fact.

## New page: proposed-name
- One durable fact.

## Unplaced
- Durable, but fits no page.
```

## 7. Filer rules (short form)

- Merge into the right section; never append to the bottom.
- Skip what the page already says. On a personal twin, also skip what the team page says.
- A contradiction goes under "Conflicts" with both versions; never overwrite.
- Cite the source record. Wikilink only to names in the page list.
- Use only allowed tags for that side.
- At 150 lines, stop and report.

## 8. BrainSight (finding what to read)

Run at the start of a project. It replaces the page-level BrainSight: it points at **sections**, and says why to read each one. It never copies page content.

| Piece | Kind | Does |
|---|---|---|
| `brain.py sections` | Script | Section index for one side: page, heading, line count. Dictionaries excluded. |
| `brain.py section "<page>" "<heading>"` | Script | Prints one section only, found by heading so edits to the page do not break it. |
| `brain-context-analyst` | Sub-agent, smallest model | One per side (personal, team). Gets the project description and that side's section index. Picks candidate sections from headings and descriptions, reads only those, returns rows. |
| `brain-sight` | Skill | Asks what the project is, launches the two analysts in parallel, writes or appends to the BrainSight file. |

BrainSight file (`brainsight.md` in the project folder), a running list. Re-running adds new rows and skips rows already there.

```markdown
| Page | Section | Side | Lines | Why read it |
|---|---|---|---|---|
| [[stop-loss]] | Traps | team | 18 | Lists the mistakes people make applying the attachment point; read before writing any stop-loss logic. |
| [[stop-loss]] | Reference | team | 40 | Definitions and formulas; read only when you need an exact term. |
| [[stop-loss]] | Notes | personal | 6 | Your own unpromoted findings on lasering. |
```

- "Why read it" says when the section is worth opening, not what it says.
- The orchestrator opens a section with `brain.py section`, never a whole page.
- A team page and its personal twin are listed next to each other.
- For this to work, pages need consistent section headings. The filer keeps the sections a page already has, and team templates define them for new pages.

### BrainSight file as built (decided 2026-11-18, overrides the rest of this section)

James dropped the planning/work split after testing: the small-model analysts guessed the groups badly and invented task labels that did not match, and the "why read it" text already says when an entry matters.

- Two tables only: `## Team` and `## Personal`. Columns: Page, Section, Lines, Why read it. No Side, Use or Topic.
- An entry is a section or a whole page (`(whole page)` in the Section cell). Whole page when it is 40 lines or fewer or most of it bears on the ask; three or more sections of one page become one whole-page entry.
- The `brain-sight` skill takes the ask and passes it as context to two `brain-context-analyst` sub-agents (team, personal). `sight-add` validates and merges their rows.
- The main conversation opens an entry only when its "why" applies; a working sub-agent is handed the BrainSight file path.

### Two groups in the BrainSight file (added 2026-11-18, then dropped; kept for the record)

| Group | Who reads it | Typical sections |
|---|---|---|
| `## For planning` | The main conversation, while planning | Overview, purpose, scope, decisions, how things fit together |
| `## For the work` | The sub-agent doing the work; the main conversation passes the rows on and does not read them | Traps in the data, reference detail, definitions, field-level notes |

- Each analyst row carries `use: plan` or `use: work`. Standard headings have a default (set in the script's config); the analyst may override it for a given project.
- Each group is split again into `### Team` and `### Personal`, so the file has four tables and no Side column. A twin appears under Personal with the same page name as its team page.
- `brain.py sight-add` merges rows into the right table and skips rows already there.

### BrainSight is the routing map for intake (added 2026-11-18)

New facts must not cause the wiki to be re-read.

- When a project has a BrainSight file, the extractor routes session facts against its rows first (`brain.py candidates`). Only bullets that fit none of them fall back to the page list (names and one-line descriptions).
- A record heading can name a section: `## [[page]] > Section`. The filer then gets that one section, not the page.
- Documents ingested with no project BrainSight route from the page list alone.
- Guards, all script checks: every heading is validated against the full page list; a proposed new page is compared with existing names and near matches are flagged before James is asked; the filer still skips what its section already says.
- Known limit: a fact is only de-duplicated against the section it is filed to, not the whole wiki. Accepted, to keep cost down.

## 9. Build order

Each step has a check. Test wiki: a copy of `Sample Wikis` with a team tags file, a templates folder and one dictionary file added.

| # | Build | Check |
|---|---|---|
| 1 | Test wiki, `brain-reference.md`, `brain.py pagelist` | Page list is right; the dictionary file is absent from it |
| 2 | `summary`, `approve`, `collect`, `markfiled` | Two hand-written records touching one page give one packet; a missing twin is created; a bad heading fails |
| 3 | `brain-filer` | The packet from step 2 edits the page once, cited, no duplicates, tags allowed |
| 4 | `brain-extractor` | A sample facts file and two sample documents become valid records |
| 5 | `brain-file`, `brain-ingest`, `add-to-main-agent.md` | One subagent runs each skill end to end; a second reviews the output; fix from both |
| 6 | `promote`, `brain-promote` | Chosen lines leave the twin and appear on the team page with team tags only |
| 7 | `sections`, `section`, `brain-context-analyst`, `brain-sight` | For a sample project, the BrainSight file lists sections with reasons, no page content, and no dictionary |
| 8 | Test loop | One subagent runs each skill end to end on the test wiki; separate subagents review; one round of fixes |
| 9 | `hookup-checklist.md` | Lists every assumed name: wiki roots, rules files, tags files, templates folder, dictionary pattern, raw and sources folders, sync command, model names |

## 10. Later, not in this build

- Notes: the wiki app distills changed note blocks into a pending record (old plan, section 8). It then uses the same filing.
- A pending view in the wiki app. Approval is in chat for now.
- Removing topic pages, the old review stage and `promotion-queue.md`. Only after this flow has run on real inputs.
- A script-only path for pages receiving one or two bullets, if the logged sizes show the filer is the main cost.

## 11. Open

- **Where the build lives.** `General-Purpose-Productivity/brain-intake/`, so it syncs to work. Taken as the default when James said to build; move it if he prefers elsewhere.
- **Dictionaries in BrainSight.** Excluded from the section index for now, like everywhere else. One setting in `brain.py` if James wants BrainSight to be able to point at them (read-only).
- **Existing brain skills and agents.** If older ones exist at work, the hookup checklist will name which to retire.
