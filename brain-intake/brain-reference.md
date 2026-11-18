# Brain reference

The one shared reference for the brain skills and agents. Skills and agents point here instead of repeating it. Script: `scripts/brain.py` (run `python scripts/brain.py --help`).

## 1. Names (defaults; all set in the CONFIG block of brain.py or `<wiki>/brain-config.json`)

| Thing | Default (relative to wiki root) |
|---|---|
| Personal pages | `personal/` |
| Team pages | `team/` |
| Rules files | `personal/rules.md`, `team/rules.md` |
| Tags files | `personal/tags.md`, `team/tags.md` |
| Team templates | `team/templates/` (one `.md` per template; name = file stem) |
| Data dictionaries | any file matching `*-dictionary.md` or `*.dictionary.md` |
| Raw documents | `personal/raw/` (top level only) |
| Session facts | `personal/raw/session-facts/` |
| Processed inputs | `personal/raw/processed/` (subfolders mirror `raw/`) |
| Source records | `personal/sources/` |
| Work files | `brain-work/`: `page-list.md`, `packets/`, `collected.md`, `brain-log.md`, `team-guard*.json` |
| Page line limit | 150 |
| Section index level | `##` |
| Dictionaries in section index | no |
| Doubt tags | `#verify`, `#hunch` (`doubt_tags`) |
| BrainCite file | `braincite.md` in the project folder (lock file `braincite.md.lock` while updating) |

- Page name = file name without `.md`. Names are unique per side.
- Skipped everywhere: rules, tags, templates, sources, raw, the work folder `brain-work/` (and any folder named `brain-work`), folders named `skills`, `agents`, `sql`, non-`.md` files, dictionaries.
- Paths printed by brain.py are relative to the wiki root. `brain.py root` prints the absolute root, for handing full paths to agents. Never write an absolute path into any wiki file.
- Every command creates the `brain-work/` folders it writes to. To save output, use `--out FILE` (`summary`, `sections`, `candidates`), not a shell redirect.

## 2. Hard rules

- Intake (session, ingest) writes personal pages only. Team pages change only through promotion.
- Team-write guard: `collect` fingerprints every team file and every dictionary; `markfiled` refuses to file anything if one changed (exit 1, changed files named). `promote` does the same for its run, exempting only its own team page.
- Data dictionaries: never read, never written, never targeted. brain.py refuses them (`REFUSED:` message, exit 1).
- Only the main conversation appends to session facts files.
- Agents read only the paths they are handed. No browsing or search.

## 3. Session facts file

- Path: `personal/raw/session-facts/<YYYY-MM-DD>-<short-name>.md`. One file per session.
- Plain dated bullets. No page names, no routing, no tags.

```markdown
# Session facts: <short-name>

- 2026-11-18: One durable fact, one sentence.
```

## 4. Source record

- Path: `personal/sources/<YYYY-MM-DD>-<origin>-<short-name>.md`. One record per input file. Never deleted.
- Record name = file stem; it is the citation id.

```markdown
---
origin: session | ingest | notes
origin_name: <session name, document file name, or notes batch date>
user: <username>
date: 2026-11-18
status: pending | approved | filed
input: personal/raw/session-facts/2026-11-18-stop-loss-rebuild.md
---

Summary: two or three sentences.

## [[existing-page-name]] > Section heading
- One durable fact.

## [[existing-page-name]]
- One durable fact, no section chosen.

## New page: proposed-name
- One durable fact.

## Unplaced
- Durable, but fits no page.

## Warnings
- Something the reviewer should know (unreadable part, unsure routing).
```

| Part | Rule |
|---|---|
| `input:` | Path of the input file, relative to wiki root. `markfiled` moves it and rewrites this line. |
| `status:` | Extractor writes `pending`. `approve` sets `approved`. `markfiled` sets `filed`. |
| `## [[name]]` | `name` exactly as in the page list (team or personal). A team name with no twin is fine: collect creates the twin. |
| `> Section heading` | Optional. Exact heading text from a BrainCite entry or `sections`. Unknown heading = filed at page level with a warning. |
| `## New page: name` | Personal page proposal. Filed only when the user approves the name. Name must not clash (summary flags `EXISTS` / `NEAR`). |
| `## Unplaced` | Kept in the record only. Never filed. |
| `## Warnings` | Shown by `summary`. Never filed. |
| Any other `##` heading | Error in `collect`. |
| Bullets | One line each, `- ` at column 0. Indented lines join the bullet above. |
| Struck bullet | `- [struck] text` (set by `approve --strike`). Skipped by collect. |

Extractor rules:

1. Routing order: BrainCite entries (`brain.py candidates --cite <file>`) first: a section entry as `## [[page]] > Section`, a whole-page entry as `## [[page]]`; then the page list `brain-work/page-list.md`; then `New page:`; else `Unplaced`.
2. One fact per bullet. Skip facts that are not durable.
3. Every bullet stands alone: its effective date and the context needed to understand it are inside the bullet.
4. Merge bullets that restate one mechanism into one bullet.
5. A time-limited fact carries its date (or date range).
6. A rule that applies generally goes to the topic page, not to a single project's page.

## 5. Page list (`brain-work/page-list.md`, written by `pagelist` and `markfiled`)

| Name | Side | Path | Description | Twin of |
|---|---|---|---|---|
| stop-loss | personal | personal/stop-loss.md | My additions ... | stop-loss |

- Description = frontmatter `description:` (whitespace trimmed), else first prose line (max 140 chars).
- A name on both sides = team page plus personal twin. Filing always goes to the personal page.

## 6. Packet

One file per target page: `brain-work/packets/personal-<name>.md` (from `collect`) or `brain-work/packets/team-<name>.md` (from `promote`). One filer per packet; packets for different pages can run in parallel.

Frontmatter (all packets):

| Key | Meaning |
|---|---|
| `packet` | `personal` or `team` |
| `mode` | personal only. `page` = read and edit the whole page. `sections` = edit only the listed sections |
| `target` | Page to edit. Always exists when the filer starts |
| `target_status` | `existing`, `twin-created` (empty twin just made), `new-page` (personal page with only a title, just made), `created-from-template` (team page just made from the template: headings only, `description: TODO ...`) |
| `team_page_readonly` | Team page for a twin: read, never edit. `none` otherwise |
| `rules` | Rules file for this side |
| `tags` | Allowed tags files: personal write = `personal/tags.md, team/tags.md`; team write = `team/tags.md` |
| `template` | Template the new team page was made from, else `none` |
| `records` | Source records the bullets came from (`none` for promotion) |
| `promoted_from` | team packets: the personal page the lines left |
| `page_line_limit` | 150 |
| `page_lines` | personal packets: current length of the target |

Body:

| Block | Mode | Content |
|---|---|---|
| Cite line | team | `Cite each bullet exactly as given: keep its (src: ...) unchanged; add no other citation.` |
| `## Bullets` | page, team | Bullets, each ending `(src: <record name>)`; promoted lines with no record end `(src: promoted YYYY-MM-DD)` |
| `### Section hint: X` | page | Bullets the extractor aimed at section X; put them there if it fits |
| `### From twin section: X` | team | Lines that sat under heading X on the twin; merge into the matching team section |
| `## Section: X` | sections | `section_lines: a-b` (1-based line range of heading X on the target, or `none` = add the heading), `### Bullets`, `### Current section text` (a copy), `### Team section (read-only, path lines a-b)` or a pointer to the team page |
| `## Warnings` | any | Fallbacks, line-limit risk, tags or links the filer must drop |
| `## Valid wikilink names` | any | Comma list. Personal write: all page names. Team write: team names only |

## 7. Filer merge rules

1. Read the packet, the rules file and the tags file(s). Read `target` (mode `page`) or only each `section_lines` range (mode `sections`; re-find the heading by text if lines moved).
2. Merge each bullet into the right existing section. Never append to the bottom. Keep the page's existing headings and order.
3. Skip a bullet the page already says. On a twin, add only the part the team text (team page or team section) does not already say.
4. A bullet that contradicts or supersedes text on the target or in the read-only team text goes under `## Conflicts`, with both versions, both sources, and the team line it affects. Never overwrite.
5. Keep `(src: ...)` on every added bullet exactly as the packet gives it.
6. Wikilink only to names in `## Valid wikilink names`. Unlink anything else. Never cite or link a personal path on a team page.
7. Use only tags from the packet's tags file(s), and tag an added bullet only when an allowed tag clearly fits. Drop any other tag.
8. `sections` mode: edit only inside the listed sections; edit the lowest section first so earlier line numbers stay valid. Missing heading: add it where the team page or template order puts it.
9. New personal page (`new-page`): may stay a single `# title` plus bullets, or use headings from the closest team template; fill `description:`.
10. New team page (`created-from-template`): already has the template's headings. Replace `description: TODO ...` with one line; fill sections; leave unused headings empty.
11. If the page would pass 150 lines: stop, write nothing more, report.
12. Return exactly one line: `page | added N | dup K | conflict M | sections: A, B | flags` (flags: comma list, or `-`; e.g. `limit reached`, `dropped tag #x`, `unlinked [[y]]`).

## 8. Tags

| Write to | Allowed tags |
|---|---|
| Personal page | `personal/tags.md` + `team/tags.md` |
| Team page | `team/tags.md` only |

- Tag syntax: `#tag` inline at the end of a bullet, before `(src: ...)`. Tags files list `- #tag: meaning`.
- Personal-only tags = in `personal/tags.md` and not in `team/tags.md`. `promote` strips them; other non-team tags appear in the packet's Warnings for the filer to drop.
- Doubt tags (`doubt_tags`, default `#verify`, `#hunch`): `promote --show` flags them; stripping one prints `warn: doubt tag #x stripped from L<n> ...` so the skill can warn the user.

## 9. Twins and new pages

- A personal twin has frontmatter `twin_of: <team page name>` and the same name as the team page.
- It holds only what the team page does not say. What remains on a twin = not yet promoted.
- Twin link line, right under `# name`: `Team page: [name](../team/name.md)` (relative path).
- `collect` creates a missing twin without asking: frontmatter `twin_of` and `description`, `# name`, the twin link line. No facts.
- A new personal page needs the user's yes (`collect --new-page NAME`) and may start with a single heading (`# name`); it has no template.
- A new team page always comes from a team template: `promote --template NAME` creates it.
- Promotion moves lines (removes them from the twin) and drops any heading left empty. Promoting a personal-only page needs `--template`; it sets `twin_of` and adds the twin link line.
- Links are one-way: personal may link to team; team never links to personal.
- Readers: team page first, then the twin.

## 10. Page limit

- 150 lines per page (`page_line_limit`). `pagelist` warns at the limit; `collect` warns when bullets may pass it; the filer stops at it.

## 11. Section index (`brain.py sections --side personal|team|both [--out FILE]`)

```
side: team
[[stop-loss]] team/stop-loss.md | 49 lines | <description> | twin: personal/stop-loss.md
  Overview | 8 | 6
  Traps | 28 | 8
```

- Page line: name, path, the page's total line count, description, then `twin of X` (personal) or `twin: <path>` (team).
- Section line: `heading | start | lines`. start = 1-based line of the heading; lines = heading through the section's last non-blank line. Read a section with offset = start, limit = lines; no command needed.
- To open a section or page, use `brain.py read` (section 12): `read --cite FILE "page > Section" --side team`, or `read --no-count ...` for a peek that needs no BrainCite file. (`section` was removed; `read` replaces it.)

## 12. BrainCite file (`<project>/braincite.md`)

The citation list of what a session drew on: the pages and sections worth reading, and how often each was read.

```markdown
# BrainCite: <project>

<!-- braincite-next: T3 P2 -->

## Team

| # | Page | Section | Lines | Reads | Why read it |
|---|---|---|---|---|---|
| T1 | [[stop-loss]] | Traps | 8 | 2 | Read before writing the reimbursement calculation. |
| T2 | [[claims-header]] | Traps | 7 | 0 | Read before writing the paid-claims query. |

## Personal

| # | Page | Section | Lines | Reads | Why read it |
|---|---|---|---|---|---|
| P1 | [[q4-renewal-analysis]] | (whole page) | 40 | 1 | Read before planning; it sets this pack's scope and deadline. |
```

| Rule | Detail |
|---|---|
| Two tables | `## Team` then `## Personal`. Both always present; an empty one shows `None.` |
| Columns | `#`, Page, Section, Lines, Reads, Why read it. The `##` heading is the side |
| Ids | `T1, T2...` (Team), `P1, P2...` (Personal). Stable, never reused; the `braincite-next` comment holds the next ids. Do not edit it |
| Entry | A section, or a whole page: Section cell `(whole page)` |
| Lines | Lines a `read` prints: heading to the section's last non-blank line, or the page body without frontmatter. Set by the script |
| Reads | Times the entry was opened with `read`. 0 = suggested but never opened |
| Page or section | List the whole page when most of it bears on the request or it is short (40 lines or fewer); otherwise list only the sections that matter |
| Why read it | Name the decision or step in the request that the entry helps with. Never list fields, checks, terms or facts from it; never copy page content |
| Order | Rows keep the order they arrive in (most important first); new rows are appended |
| Twins | A twin's entry sits under Personal with the same page name as its team entry |
| Updates | Only via `brain.py cite-add` and `brain.py read`. An older file (no `#` or Reads column) is upgraded in place the first time either touches it |

Analyst rows file for `cite-add` (JSON list, or TSV with a header):

```json
[{"page": "stop-loss", "section": "Traps", "side": "team", "why": "..."},
 {"page": "q4-renewal-analysis", "side": "personal", "why": "..."}]
```

- `page`, `side` (`team` or `personal`) and `why` are required. `section` is optional: missing, empty or `(whole page)` = whole page.
- Each row is checked against the wiki (page exists once on that side; heading exists once). An invalid row is rejected with a one-line reason; the rest still go in.
- New entries get the next id and Reads 0. Existing entries keep their Reads.
- Already there: same page + side + section, or that page already has a whole-page entry on that side (`(covered by whole page)`).
- A whole-page row for a page that has section entries replaces them at the first one's place, with a new id and the sum of their Reads: `replaced: T1 Traps, T2 Decisions by T4 pmpm > (whole page) (team)`.
- Output gives exact counts; report these, not the analyst's own count:

```
table team: added N, already there N, rejected N
table personal: added N, already there N, rejected N
total: N added, N already there, N rejected -> braincite.md
```

### Reading: `brain.py read`

- `read [--cite FILE] T1 P2 "page > Section" page ...`: prints each target in the order given and nothing else:

```
=== T1 team stop-loss > Traps (8 lines) ===
<section text exactly as on the page>
=== P1 personal q4-renewal-analysis (40 lines) ===
<page body without frontmatter>
```

- Target: an id (case-insensitive), or a direct target `"page > Section"` or `page` (whole page). `--side team|personal` sets the side of direct targets; a page on both sides without `--side` is a bad target.
- `--all` reads every entry; with `--side`, only that table.
- Counting: each read adds 1 to the entry's Reads (twice in one call = 2). A direct target matching an entry counts against it. A direct target with no entry becomes a new entry, why `Read directly (not listed by the analyst).`, Reads 1. A section of a page that has a whole-page entry gets its own entry.
- Bad targets (unknown id, page or heading; page on both sides; dictionary) print one `error: <target>: <reason>` line each to stderr; the good ones are still read; exit 1 at the end. Dictionaries are always refused.
- Parallel calls are safe: the file is updated under a lock file (`<file>.lock`) and written atomically.
- `--no-count`: peek; the file is not changed. With only direct targets it needs no BrainCite file (header id `-`).
- No `--cite`: `braincite.md` in the current folder; if missing, exit 3 asking for `--cite`.
- `read --cite FILE --report`: one line per entry with Reads > 0 (`T1 | stop-loss > Traps | team | 8 lines | 2 reads`), then `read: N entries, N lines in total (lines x reads)` and `never read: N of N entries`.

## 13. brain.py commands

| Command | Does | Main output |
|---|---|---|
| `pagelist [--print]` | Write `brain-work/page-list.md` | `page list: <path> (N personal, N team; N dictionaries excluded)`, `warn:` lines |
| `summary [RECORD...] [--status pending\|approved\|filed\|all] [--full] [--out FILE]` | Show records for approval | Session: `L<n> <bullet>` per bullet. Ingest/notes: `pages:`, `new pages:`, `unplaced:` counts. Flags: `(new twin)`, `UNKNOWN PAGE`, `REFUSED: dictionary`, `(no such section; page level)`, `EXISTS`, `NEAR` |
| `approve [RECORD...] [--all] [--strike RECORD:LINE ...]` | Strike bullets, then approve | `struck:`, `approved:` lines |
| `collect [RECORD...] [--new-page NAME ...] [--allow-near]` | Validate approved records, make twins, write packets, write `collected.md` and the team guard | `twin created:`, `new page created:`, `packet: <packet> -> <target> (...)`, `warn:`, `note:` |
| `markfiled [RECORD...] [--failed PAGE ...] [--promoted NAME ...]` | Check the team guard, file collected records, move inputs, drop done packets, regenerate page list, log | `filed:`, `moved:`, `held (failed page X):`, `packet removed:`; guard failure: `error:` lines naming files, exit 1 |
| `log AGENT [--event E] [--in-chars N] [--in-file PATH ...] [--out-chars N] [--out-text TEXT] [--note T]` | Log one agent call's size | `logged: <event> <agent> in=N out=N`; missing `--in-file` = `warn:` line, not counted |
| `promote --list` | Personal pages with promotable lines | `name \| twin of X \| N lines` |
| `promote PAGE --show` | Promotable lines with flags | `L<n> [first person] [#verify] [no source] <line>` (flags only when they apply) |
| `promote PAGE (--lines 12,14-16 \| --text "line" ...) [--template NAME]` | Move lines into a team packet; create the team page from the template if missing | `team page created from template:`, `twin_of set:`, `removed N line(s)`, `empty headings dropped:`, `stripped personal tags:`, `warn: doubt tag ...`, `packet:` |
| `sections [--side personal\|team\|both] [--out FILE]` | Section index | see section 11 |
| `candidates [--cite FILE] [--side team\|personal] [--out FILE]` | BrainCite entries for the extractor | `id \| page \| section-or-(whole page) \| side \| N reads \| why`, `(page missing)` flag |
| `cite-add [--cite FILE] --rows FILE [--title T]` | Merge analyst rows into the Team and Personal tables | `added: <id> ...`, `already there:`, `replaced:`, `rejected:`, per-table counts, total |
| `read [--cite FILE] TARGET ... [--side team\|personal] [--no-count]` / `read --all [--side ..]` / `read --report` | Print entries or pages/sections in order and count the reads | `=== <id> <side> <page> > <Section> (N lines) ===` then the body; `error:` lines on stderr for bad targets |
| `root` | Absolute wiki root | one path |

- Global options (before or after the command): `--wiki PATH`, `--config PATH`. Default root: `$BRAIN_WIKI`, CONFIG `wiki_root`, then the current folder.
- `--out FILE`: relative to the wiki root (or absolute); folders are created; prints `wrote <file> (N lines)`.
- `log --in-file PATH`: used as given if absolute, else tried against the current folder, then the wiki root.
- Exit codes: 0 ok; 1 invalid or refused (stderr says what to fix; nothing written); 2 bad arguments or config; 3 not found.
- `collect` writes nothing unless every heading in every approved record is valid.
- `markfiled` with no records files exactly the records the last successful `collect` handled. Run it only after every filer has returned.
- `promote` refuses while an earlier `team-<name>.md` packet is waiting; clear it with `markfiled --promoted <name>` after its filer runs.

## 14. Retry after a failed filer (brain-file and brain-ingest)

1. Run `markfiled --failed PAGE` (repeatable; PAGE = the name in `personal-<PAGE>.md`). Records with any bullet for a failed page stay `approved`, keep their input in `raw/`, and stay in `collected.md`; the failed page's packet is kept; everything else is filed and its packets removed.
2. Fix the cause (e.g. split a page at the 150-line limit).
3. Rerun the filer on the kept packet. Do not rerun `collect` for this: it would rebuild packets for pages already filed.
4. If you must rerun `collect` (packet lost or records edited), pass `--new-page NAME` again for every approved new page in the held records, or those sections are skipped.
5. Run plain `markfiled`. It files the held records and removes the packet.
6. A team-guard failure is not a retry case: restore the named team or dictionary files first, then rerun `markfiled`.

## 15. Flows (which command when)

| Flow | Steps |
|---|---|
| brain-file | `pagelist` -> `candidates --cite` (if a BrainCite file exists) -> extractor on session facts files -> `summary` -> user strikes / says yes -> `approve --all` -> `collect` -> one filer per packet (parallel) -> `log` per call -> `markfiled` (failed filer: section 14) |
| brain-ingest | same, extractor input = batch of `personal/raw/*` documents; `summary` shows counts only |
| brain-promote | `promote --list` -> `promote PAGE --show` (show the flags to the user) -> user picks -> `promote PAGE --lines ...` (`--template` if no team page) -> warn on any `warn: doubt tag` -> one filer -> `markfiled --promoted NAME` |
| brain-cite | `sections --side team` and `--side personal` (`--out`) -> one analyst per side (parallel) -> analysts write rows files (page or section entries) -> `cite-add` -> report its per-table counts |
| Using the entries | main conversation and sub-agents open entries with `read --cite FILE T1 P2 ...` (one call for many); end of session: `read --cite FILE --report` |
