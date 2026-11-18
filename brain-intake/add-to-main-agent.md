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

- If the project folder has `braincite.md`, use it instead of browsing the wiki. It has two tables, `## Team` and `## Personal`; each entry has an id (`T1`, `P2`), a page, a section or `(whole page)`, a Reads count and a "why".
- Open an entry only when its "why" applies to what you are about to do.
- Read everything you need in ONE call: `brain read --cite "<absolute path>/braincite.md" T1 T3 P2` (ids and direct targets such as `"page > Section"` can be mixed).
- Always read wiki pages through `brain read`, never with a plain file read: every read is counted in the Reads column, and reading something not listed adds it as an entry.
- When handing work to a sub-agent, pass it the absolute path of `braincite.md` and the full command with both paths written out (a sub-agent may not have `BRAIN_HOME` or `BRAIN_WIKI` set): `python "<brain-intake folder>/scripts/brain.py" --wiki "<wiki root>" read --cite "<absolute path>/braincite.md" <ids>`, so its reads are counted too.
- At the end of the session, `brain read --cite "<absolute path>/braincite.md" --report` shows what was read.
