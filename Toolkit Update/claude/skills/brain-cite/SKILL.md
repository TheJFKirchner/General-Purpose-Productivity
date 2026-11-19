---
name: brain-cite
description: At the start of a project or a new request, find the wiki pages and sections worth reading for it and list them, each with a reason, in the project's braincite.md. Re-running adds new entries only.
---

# brain-cite

Lists, in the project's `braincite.md`, the wiki pages worth reading for what the user is working on.

1. **Get the ask.** Write a few sentences: what the user is working on, what they are trying to do or find out, and the data, clients or methods involved. Take it from the conversation and the argument. If you cannot write it from those, ask the user. A title is not an ask.
2. **Build the index.** Run `python "<brain folder>/scripts/wiki_index.py" "<wiki root>"`. It writes `brain-work/index.md` in the wiki: every page with its description and section headings. Do not read the index yourself.
3. **Hand it to one `brain-context-analyst` sub-agent.** Give it the ask in full, the wiki root, the index path, and the path of the project's `braincite.md` if there is one, so it skips what is already listed. It returns the entries to add, each with a why.
4. **Add the entries to `braincite.md`** in the project folder (the folder this session is open in), under `## Team` or `## Personal`, as returned. Never remove or reword an entry that is already there. No file yet: create it in the layout below.
5. **Tell the user** what was added, one line per entry. Nothing returned: say so and suggest a fuller ask.

Do not open wiki pages yourself; the sub-agent does the reading.

## Layout of braincite.md

```markdown
# BrainCite: <the project or ask, in a few words>

## Team

| Page | Section | Why read it |
|---|---|---|
| [[stop-loss]] | Traps | Read before writing the reimbursement calculation. |

## Personal

| Page | Section | Why read it |
|---|---|---|
| [[q4-renewal-analysis]] | (whole page) | Read before planning; it sets this pack's scope and deadline. |
```

A side with no entries shows `None.` in place of its table.
