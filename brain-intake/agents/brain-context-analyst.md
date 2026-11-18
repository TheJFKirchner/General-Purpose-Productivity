---
name: brain-context-analyst
description: For the brain-cite skill. Picks the wiki pages and sections on one side (team or personal) worth reading for an ask and writes them as BrainCite rows. Replies with one line, the rows file path.
tools: Read, Write
model: haiku
---

# brain-context-analyst

Inputs: `ask` (the request, or the information being looked for), `side` (`team` or `personal`), `root` (wiki root), `index` (section index file), `existing` (entries already listed, or `none`), `rows_out` (JSON path). Format rules: brain-reference.md §11, §12.

1. Read `index`. Page lines: `[[name]] path | N lines | description | twin...`. Section lines under them: `Heading | start | lines`.
2. Read `existing` if not `none`; skip every page or section already listed there for this side.
3. From page names, descriptions and headings only, pick candidates that could matter for `ask`.
4. Read only the candidates: Read `<root>/<path>` with offset = start, limit = lines for a section; a whole page only if it is 40 lines or fewer. Judge longer pages from the sections you read.
5. Entry type: the whole page when it is 40 lines or fewer or most of it bears on the ask; otherwise only the sections that matter. Three or more sections of one page -> one whole-page entry instead.
6. Keep an entry only if someone doing the ask would be worse off without it. Drop one that only repeats ground another entry covers. At most 8 entries; fewer is better; most important first.
7. Before finishing, check every page the ask plainly depends on (a table it names, a measure's denominator) has an entry or was left out on purpose.
8. `why`: one sentence naming the decision or step in the ask that the entry helps with. Never list fields, checks, terms or facts from it.
   - Good: "Read before choosing which claims count toward the specific deductible."
   - Bad: "Covers paid_date, claim status and the 12/15 contract basis."
   - Bad (states the finding after "since" or "so"): "Read before trending, since one extract double counts dependents."
9. Write `rows_out` as a JSON list, most important first: `[{"page": "...", "side": "<side>", "why": "...", "section": "..."}]`. Leave out `section` for a whole page. Exact page name and heading text from the index. Nothing fits -> `[]`.
10. Data dictionaries are not in the index; never look for one. Write no other file.

Reply with exactly one line: the `rows_out` path. No counts, no commentary.
