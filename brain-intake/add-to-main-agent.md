# Add to the main agent file

- Paste everything below the line into the file your main conversation loads (e.g. user-level CLAUDE.md). Fill in the two paths.
- Holds only what no skill covers: recording facts, fact vs finding, using `braincite.md`, and what every analysis skill assumes.
- Not here: filing facts (brain skills); writing a finding (the `findings` skill); building anything (the skill for it).

---

## Brain: facts and BrainCite

- Brain folder: `<absolute path of the brain folder, the one holding scripts/wiki_index.py>`
- Wiki root: `<absolute path of the folder holding personal/ and team/>`

### Recording facts (all session)

Two questions for anything learned, in this order. Both yes: record in both places. Both no: record nothing.

1. **Finding?** The work established it (computed, checked or settled) and it bears on a project plan item.
   - Yes: record it as the `findings` skill says.
   - No plan linked in the project's CLAUDE.md: no findings.
2. **Fact?** Someone starting other work here would want to know it beforehand.
   - Yes: record it as below.

Fact = reference knowledge:

- How data, tables and systems behave
- Known gotchas
- Methods
- Metric definitions
- Reference numbers: headline metrics, agreed assumptions, contract terms
- Standing requirements, recurring deadlines

How to record:

- **File:** in the wiki, `personal/raw/session-facts/<YYYY-MM-DD>-<short-name>.md`
  - One file per session
  - Short name = the project or topic
  - First line: `# Session facts: <short-name>`
- **Line:** `- YYYY-MM-DD: one fact, one sentence. (page: <page name>)`
  - Date = the day you learned it
- **Page note:** add `(page: <page name>)` when the fact would have been useful on a wiki page you worked from
  - Only a page in the project's `braincite.md`, or one you opened this session
  - Never guess a name
  - No obvious page: leave it off
- **Wording:** filed as written; nobody reviews it first
  - Must stand alone: say what it is about
  - Reference number: give its period and where it came from
  - No tags

| Case | Rule |
|---|---|
| A number | Fact only if a reference number someone would look up again (book-level metric, agreed assumption, contract term). Computed just for this ask: not a fact |
| Given, not established by the work | Fact when it outlives the project (contract term, another team's assumption, last year's result), even when the plan depends on it |
| A working choice for this project (basis, filter, threshold, assumption) | Not a fact; belongs in the plan. Reason would apply again: record the reason. The organisation's standing definition or threshold: a fact |
| True only for one client, team or this company | Still a fact |
| Both a finding and a fact | Finding = this project's result. Fact = the general lesson, worded to stand without the project. No lesson beyond this project: finding only |
| Public or textbook knowledge, to-dos, one-off deadlines, scratch work, notes about the session | Not a fact |
| Unsure it is true | Record it; say in the fact that it is unconfirmed |

- Append as you go; never interrupt the user. Append only.
- Only you write the file. Sub-agents report facts in their reply; you append them.
- Never write to wiki pages or data dictionaries yourself.
- Facts reach the wiki only when the user runs the filing skill. Never start it or suggest it.

### Using a project's braincite.md

- Project folder has `braincite.md`: use it instead of browsing the wiki.
- Two tables, `## Team` and `## Personal`. Columns: Page, Section, Why read it.
- Open an entry only when its "why" applies to what you are about to do.
  - Page file: `team/<page>.md` or `personal/<page>.md` in the wiki
  - Read only the named section; the whole page only when the entry says so
- Handing work to a sub-agent: give it the absolute paths of `braincite.md` and the wiki root; tell it to open what its task needs.

## Analysis toolbox

- **Map:** `## Map` in the project's CLAUDE.md. Read it before touching a project.
  - A "Project plan" line, then a two-column table: `Folder or file | Holds`.
  - Lists only what exists. Relative paths only, never one person's computer.
  - Each skill adds its own row. A row for anything run again ends with `Refresh: <one command or step>`.
- **Two fixed rules:** a new project starts with a short talk and a map (the `toolbox` skill). Every number in a deliverable traces to code or a named source.
- **Settings:** no environment variables; settings live in config files.

### Words
- Pipeline: fetch and prep data into tables. Answers nothing.
- Analytic: one Python function, one question; returns tables and metrics, plus its question and notes.
- Section: one visual block in a report, dashboard or deck that shows an analytic.
- Finding: a result against the project plan, with its source. Recorded as the `findings` skill says.
- Commentary: generated text for a dashboard that needs it across many filters or refreshes.

### Which skill
- `toolbox`: a new project or a full rescope.
- `analysis`: explore data (the default), or a short HTML report when asked. Exploring needs no skill structure and saves nothing.
- `findings`: record a result against the plan; read before writing a deck, report or summary.
- `commentary`: dashboard text across many filters or refreshes. Not for reports or decks.
- `dashboard-new`: a new dashboard, or port existing work into one.
- `dashboard-work`: change an existing dashboard.
- `presentation`: a deck from existing work.

### A normal edit
- Read the skill, at most one short page, and the inventory. Nothing else.
- Inventory: `python run.py list` (report), `npm run status` (dashboard), `slides.js <deck>` (deck).
- Add: `python run.py add-section`, `npm run new-section`, `add-slide.js`.
- Never read copied framework files: a report's `run.py` and `page.html`, a dashboard's app and tools, a deck's engine and stylesheet, library slide files.

### Subagents and stops
- Small jobs stay in this conversation. Launch a subagent only where a skill says so:
  - `commentary-generator`: once, for dashboard commentary. Never for reports or decks; their bullets come from findings.
  - `design-librarian`: when the user likes a visual or says save it.
- Tell the user, do not silently proceed, when a request repeats a chart that exists, a refresh changes a headline answer, or data contradicts a recorded statement.
