# Add to the main agent file

Paste everything below the line into the instruction file your main conversation loads (for example your user-level CLAUDE.md).

---

## Brain: session facts and BrainCite

`brain` = `python "$BRAIN_HOME/scripts/brain.py"`. The wiki root is `$BRAIN_WIKI`.

### Session facts (all session)

- Keep one facts file per session: `$BRAIN_WIKI/personal/raw/session-facts/<YYYY-MM-DD>-<short-name>.md`, first line `# Session facts: <short-name>`.
- As the session goes, append each durable fact as a plain dated bullet: `- YYYY-MM-DD: one fact, one sentence.` No page names, tags or routing.
- You are the only writer of this file. Sub-agents report facts back to you in their reply; you append them.
- Durable = still true and useful next month: how data, tables, systems, clients, contracts or methods behave; decisions and why; traps found.
- Do not record: public or textbook knowledge, to-dos, scratch work, intermediate numbers, notes about the session itself.
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
