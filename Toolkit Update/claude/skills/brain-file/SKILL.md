---
name: brain-file
description: File the session facts recorded so far into personal wiki pages, with no questions asked. Run only when the user asks, usually at the end of a session or when facts have piled up.
---

# brain-file

Facts are recorded as sessions go. This is the separate step that puts them into the wiki. It runs start to finish without asking the user anything.

1. **Find the facts.** List the files in the wiki's `personal/raw/session-facts/` folder, including `unfiled.md` (facts left over from last time). None: say "No session facts to file" and stop. Do not read them yourself.
2. **Build the index.** Run `python "<brain folder>/scripts/wiki_index.py" "<wiki root>"`. It writes `brain-work/index.md` in the wiki: every page with its description and section headings. Do not read the index yourself.
3. **Hand everything to one `brain-filer` sub-agent.** Give it the paths of the facts files, the wiki root, the index path, and the path of the project's `braincite.md` if there is one. It reads the facts and the pages, decides where each fact goes, creates a page when a topic has none, and works every fact in.
   - More than 30 facts across the files: read the files and split the facts into groups. Facts noted for the same page stay together; all facts with no page noted go in one group. One filer per group, one after another, each given its facts word for word with the facts file each came from.
4. **Tidy the facts folder.** Only once the filer has reported; if it did not finish, leave everything where it is and tell the user.
   - Move each facts file except `unfiled.md` to `personal/raw/processed/session-facts/` (`mkdir -p` the folder, then `mv`).
   - Rewrite `unfiled.md` to hold only the facts the filer reported as `not filed`, one per line, each ending `(from: <facts file it was recorded in>)`. None: remove `unfiled.md`.
5. **Tell the user** what happened, briefly: new pages created first, then how many facts went onto which pages, then any fact not filed and why. Those are tried again next time.

Do not open or change wiki pages yourself; the filer does all of it.
