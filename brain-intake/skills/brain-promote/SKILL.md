---
name: brain-promote
description: Move chosen lines from a personal wiki page (a twin) to its team page, creating the team page from a team template when it does not exist yet. The only brain skill that writes team pages. Use when something personal should reach the team.
---

# brain-promote

- `brain` below = `python "$BRAIN_HOME/scripts/brain.py"` (Bash tool). Env vars: `hookup-checklist.md`. Rules: `brain-reference.md` §8, §9, §13, §15.
- Cost: read only script output. Never open wiki pages or packets. The filer returns one line only.
- Team write: team rules and team tags only (the packet names them). Data dictionaries are never read or written.
- Hand the filer absolute paths built from ROOT. Log with absolute `--in-file` paths and `--out-text "<the filer's reply>"`.
- A promoted line must stand alone for team readers: context left behind on the personal page is invisible to them.

## Steps

1. Run `brain root`, `echo "$BRAIN_HOME"`, `date +%F` -> ROOT, HOME, DATE.
2. Sync in: `git -C "ROOT" pull --ff-only`. Not a git repo -> skip sync here and in step 13. Fails -> stop.
3. PAGE = the argument. None: `brain promote --list`, show it, ask "Which page?". `no personal pages ...` -> stop.
4. `brain promote PAGE --show`. Show its output unchanged, flags included (`[first person]`, doubt tags such as `[#verify]`, `[no source]`).
5. First line says `no team page yet`: Glob `ROOT/team/templates/*.md` -> template names.
6. Ask the one question:
   - "Which lines move to the team page (e.g. `12,14-16`)? They leave your page and must read on their own. For each flagged line: give a rephrase, drop it, or say `as is`. [No team page yet: which template: <names>?] `no` stops."
7. `no` -> stop; nothing changed.
8. Each rephrased line: Read only that line of `ROOT/personal/PAGE.md` (offset n, limit 1), Edit it to the user's words (keep its `(src: ...)`). Dropped lines leave the spec.
9. `brain promote PAGE --lines <spec>` plus `--template NAME` when chosen (it creates the team page). Exit 1 -> show the error; stop. Relay every `warn: doubt tag ...` and `stripped personal tags:` line to the user. Note the `packet:` line: `<packet> -> <target> (<status>)`.
10. Launch one `brain-filer` with: packet `ROOT/<packet>`, root ROOT. Then `brain log brain-filer --in-file "ROOT/<packet>" --out-text "<reply>" --note promote`.
11. Filer reply in the §7 format without `limit reached` or `failed`: `brain markfiled --promoted <team name>` (team name = packet file name after `team-`, without `.md`). Relay any `warn:` line from step 9 or the filer's flags to the user.
12. markfiled exit 1 (team-write guard: a team file other than this page changed) -> stop; show its output.
13. Sync out: `git -C "ROOT" add -A personal team && git -C "ROOT" commit -m "brain-promote PAGE DATE" && git -C "ROOT" push`.
14. Tell the user in one line: lines moved, the team page path, and the filer's added / dup / conflict and flags.

## Stop conditions

- Steps 2, 3, 7, 9, 12 as above. A missing env var or `error:` from brain -> show it and stop.
- Filer failed or hit the limit: do not run markfiled or sync. Tell the user the moved lines are kept in `ROOT/<packet>`; retry = rerun `brain-filer` on it, then step 11.
- `promote` refuses while an earlier team packet for the page waits: run the retry above first.
