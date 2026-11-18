# Add to the main agent file

Paste everything below the line into the instruction file your main conversation loads (for example your user-level CLAUDE.md).

---

## Brain: facts, findings and BrainCite

`brain` = `python "$BRAIN_HOME/scripts/brain.py"`. The wiki root is `$BRAIN_WIKI`.

### Facts and findings (all session)

Track both as the session goes. Ask two questions of every candidate, in this order. Both yes: record it in both files. Both no: record nothing.

1. **Finding?** Did the work establish it (computed it, checked it, or got it settled), and does it answer, confirm, rule out, block or change an item in the project plan? No project plan: skip this question; there are no findings.
2. **Fact?** Would someone starting other work here want to know it beforehand?

| | Fact: reference knowledge | Finding: a result against the plan |
|---|---|---|
| Typical | How data, tables and systems behave; known gotchas; methodology and how to do things; metric definitions; reference numbers (headline metrics, agreed assumptions, contract terms); standing requirements and recurring deadlines | The answer to a plan question, with its figure; a check that passed or failed; a negative result the plan asked about ("no seasonality found"); something that blocks or changes a plan item |
| File | `$BRAIN_WIKI/personal/raw/session-facts/<YYYY-MM-DD>-<short-name>.md`, first line `# Session facts: <short-name>` (short name: the project or topic) | `findings.md` beside the project plan (one already there or in a folder above: use it) |
| Line | `- YYYY-MM-DD: one fact, one sentence.` Date = the day you learned it. A reference number states its period and where it came from | One table row: `# \| Finding \| Plan item \| Source \| As of \| Added` |
| Ends up | In the wiki, through `/brain-file` | With the project. Never filed to the wiki |

| Case | Rule |
|---|---|
| A number | Finding if it answers a plan item. Fact only if it is a reference number someone would look up again (a book-level metric, an agreed assumption, a contract term). A number computed just for this ask: neither |
| Given, not established by the work (a contract term, another team's assumption) | Fact, not a finding, even when the plan depends on it |
| A decision made for this project ("we used paid basis"), including an assumption you chose | Not recorded here; it belongs in the plan. If the reason would apply again, record the reason as a fact |
| A result that bears on no plan item | Not a finding. Tell the user in one line |
| True only for one client, team or this company | Still a fact; the wiki is this organisation's |
| It is both | The finding carries this project's result. The fact carries the general lesson, worded to stand without the project. No lesson beyond this project: it is a finding only; do not invent one |
| Public or textbook knowledge, to-dos, one-off deadlines, scratch work, notes about the session | Neither |
| Unsure | An unsure fact: record it (the user reviews facts at `/brain-file`). An unsure finding: leave it out and tell the user in one line |

- Both: finding `March claim counts are 4% low because reversed claims were dropped.` (plan item `Step 3, validate counts`; source `checks/march.sql, table summary`), fact `Dropping reversed claims understates monthly claim counts; net them instead.`
- Finding row: Plan item = the plan's own id or words. Source = the script, table or query; or the document and its date; or the person and date. No source: do not add it. As of = the data period, blank if it does not depend on data. Added = today. `#` continues from the last row.
- Append as you go. Both files are append only: a new figure from new data is a new row.
- You are the only writer of both files. Sub-agents report facts and findings back in their reply, labelled; you append them.
- Facts carry no page names, tags or routing.
- Before writing a deck, report or summary for a project: read its `findings.md` and cite the row numbers used.
- Never write to wiki pages or data dictionaries mid-session. Filing happens only through the skills below.

### Skills (the user types these)

| Type | When |
|---|---|
| `/brain-file` | End of a session, or when facts have piled up. Files them to personal pages after one yes. |
| `/brain-ingest` | Documents are waiting in `$BRAIN_WIKI/personal/raw/`. Files them the same way. |
| `/brain-promote [page]` | Lines on a personal page should reach the team page. The only way team pages change. |
| `/brain-cite [the ask]` | Start of a project or request. Writes `braincite.md` in the project folder. |

### Using a project's braincite.md

- If the project folder has `braincite.md`, use it instead of browsing the wiki.
- It has two tables, `## Team` and `## Personal` (Page, Section, Lines, Why read it). An entry is a section, or a whole page when Section says `(whole page)`.
- Open an entry only when its "why" applies to what you are about to do: `brain section "<page>" ["<section>"] --side <team|personal>` (leave out the section for a whole page).
- When handing work to a sub-agent, pass it the absolute path of `braincite.md` and tell it to open what its task needs.
- A sub-agent without a shell can open an entry with a plain file read of the page under the wiki root (`team/` or `personal/`); the entry names the page and section. Give it the wiki root as an absolute path.
- Never open a whole wiki page when a section will do.
