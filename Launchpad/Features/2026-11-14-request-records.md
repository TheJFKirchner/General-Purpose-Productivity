# Request records: one file per request

Status: built
Date: 2026-11-14

Stops keeping one large combined decisions file. Every conversation or feature request is now saved as its own markdown file in `Features/`, and `Features/README.md` is the short list of all of them: an id, the request's name linked to its file, and two sentences describing it. The old combined file was split retroactively into one file per request; a decision that only summarised an existing feature spec was added to that spec under `## Decisions`.

The user asked for this directly; no interview.

## Decisions

- One home for request records: `Features/`. One file per conversation / feature request: `Features/<YYYY-MM-DD>-<short-slug>.md`
- Each file starts with `# <Name>`, then a `Status:` line (`decided` for decision-only conversations, `built`, `approved`, `abandoned`), a `Date:` line, a one-paragraph summary, then the full detail
- `Features/README.md` = the list of all requests, oldest first: one intro line, a line stating that newer requests override older ones where they conflict, and a table with exactly the columns `#`, `Request`, `Summary`
  - `#` counts from 1 in date order; `Request` = the name linked to its file; `Summary` = exactly two plain sentences for someone who has not read the file; nothing else in the table
- Newer requests override older ones where they conflict; a request file that a newer one changes gets a "Later changed by: <link>" line
- Before planning: read the list, then open only the request files that bear on the task
- History: until 2026-11-14 all decisions lived in one combined, dated file, docs/decisions.md (305 lines, about 33 sections). It was split verbatim into the request files listed in `Features/README.md` (rows 1 to 22) and then removed; the three sections that only summarised an existing spec went into that spec's `## Decisions` section
- Not the same thing: the per-session runtime file `<folder>/.launchpad/<session-id>/decisions.md` (visual picks) is unchanged
