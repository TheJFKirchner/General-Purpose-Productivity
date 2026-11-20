# Add to the main agent file

- Paste everything below the line into the file your main conversation loads (its agent file or user-level CLAUDE.md). Fill in the two brain paths.
- Holds how the main conversation behaves: recording facts, using `braincite.md`, choosing and running the analysis skills.
- Install places, the project map and where files go: `add-to-claude-md.md`, not here.

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

- Before touching a project, read the `## Map` in its CLAUDE.md. No map: `toolbox` first.
- A file no skill places (one sent over): its map row, else the project layout in CLAUDE.md; still unclear, ask in one line.
- Load the skill before opening anything in a report, dashboard or deck folder; it says what to read.
- Every number in anything handed out traces to code or a named source, including files no skill makes.

### Which skill
| Request | Use |
| --- | --- |
| New project, full rescope, a new kind of output | `toolbox` |
| A question of the data; "write it up"; change or rerun a report; a report table out to Excel | `analysis` |
| "Note that"; before writing any deck, report or summary | `findings` |
| New dashboard, change one, port work into one, new data for it, an offline file from it | `dashboard` |
| Dashboard text across many filters or refreshes | `commentary` |
| A deck, or a change to one | `presentation` |
| The user likes a visual, "save that" | `design-librarian` agent |

### Subagents
- Toolkit work stays in this conversation. A subagent only where the loaded skill names one.

### Living with an existing orchestrator
- A skill's gates (brief, answer, slide list, storyboard, plan, sign-off) belong to the user: held in this conversation, never delegated.
- A delegated builder gets the skill's path, the one reference it needs and a brief. Never the skill's text or this conversation.
- Never split a small edit across subagents: each costs about 60K tokens before it starts; an add is 10 to 20 tool calls in place.
- A delegated worker writes only inside the folder the map names, adds no folders, and shares no file with another worker.
- The orchestrator's own plan, task or decision files never replace the project's plan, map or `findings.md`; results go there.
