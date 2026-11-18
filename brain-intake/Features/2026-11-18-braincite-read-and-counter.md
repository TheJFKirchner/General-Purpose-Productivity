# BrainCite: chained reads and a read counter

Status: built

Built 2026-11-18 as specified. Additions: `read --report` (what was read, total lines, entries never read), `read --all`, `read --no-count`, and the old `section` command was removed because `read` covers it. One end-to-end run with parallel sub-agents reconciled every count.
Date: 2026-11-18

BrainSight is renamed BrainCite, because the file is the citation list of what a session drew on. One `read` command opens any number of listed pages and sections in a single call, and every read adds 1 to that entry's `Reads` count in the BrainCite file, so the file shows what actually went into the session.

## Decisions

- **Name.** BrainSight becomes BrainCite everywhere: skill `brain-cite`, file `braincite.md`, script commands and options (`cite-add`, `--cite`). The sub-agent keeps the name `brain-context-analyst`.
- **Entry ids.** Each entry has a stable id: `T1`, `T2`... in the Team table, `P1`, `P2`... in the Personal table. Ids are never reused.
- **One read command.** `brain read` takes any mix of ids and direct targets (`"page > Section"` or a page name) in one call and prints them in order, each under a one-line header. This replaces opening sections one at a time.
- **Counter.** The tables gain a `Reads` column. Each page or section read adds 1 to its entry. Sub-agents use the same command, so their reads count.
- **Unlisted reads are recorded.** Reading something the analyst did not list adds it as a new entry marked "read directly" with a count of 1. A row left at 0 was suggested but never opened.
- **Table columns.** `#`, Page, Section, Lines, Reads, Why read it.

## Assumptions

1. The counter is a plain count per entry, not a log of who read it or when.
2. Reads by parallel sub-agents must not lose counts; the script updates the file safely.
3. A dictionary file can never be read through this command.
4. Intake routing still reads the BrainCite file's entries; counts play no part in routing.

## Tasks

1. Script, reference, sample file and tests: rename, ids, `read`, counter. Builder: factory-builder (slice 1 owner).
2. Skills, analyst, extractor wording, hand-off files, README: rename and use `read`. Builder: factory-builder (slice 2 owner). Runs after task 1.
3. One end-to-end run of `brain-cite` followed by chained reads, on a copy of the test wiki.
