---
name: brain-ingest
description: Pull the durable facts out of documents waiting in the wiki's personal raw folder and file them into personal wiki pages, with no questions asked. Run only when the user asks, after documents have been dropped in raw/.
---

# brain-ingest

Turns documents dropped in the wiki's `personal/raw/` folder into facts and files them, the same way session facts are filed. It runs start to finish without asking the user anything.

1. **Find the documents.** List the files directly in `personal/raw/` (not its subfolders). None: say "No documents in raw/" and stop. Do not read them yourself.
2. **Hand them to one `brain-extractor` sub-agent.** Give it the document paths. It returns the durable facts, under the name of the document each came from. More than 5 documents: groups of 5, one extractor per group, all at once.
3. **Build the index.** Run `python "<brain folder>/scripts/wiki_index.py" "<wiki root>"`. It writes `brain-work/index.md` in the wiki: every page with its description and section headings. Do not read the index yourself.
4. **Hand the facts to one `brain-filer` sub-agent.** Give it the facts as the extractor returned them, each under its document name, with the wiki root, the index path, and the path of the project's `braincite.md` if there is one. It decides where each fact goes, creates a page when a topic has none, and works every fact in. No facts returned: skip to step 5.
5. **Tidy the raw folder.** Only once the filer has reported; if it did not finish, leave everything where it is and tell the user.
   - Move the documents to `personal/raw/processed/` (`mkdir -p` the folder, then `mv`).
   - Add each fact the filer reported as `not filed` to `personal/raw/session-facts/unfiled.md`, one per line, ending `(from: <document name>)`. The next brain-file tries them again.
6. **Tell the user** what happened, briefly: new pages created first, then how many facts went onto which pages, then any fact not filed and why.

Do not open or change wiki pages yourself; the filer does all of it.
