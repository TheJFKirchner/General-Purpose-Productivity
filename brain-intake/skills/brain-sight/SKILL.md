---
name: brain-sight
description: At the start of a project or a new request, find the wiki pages and sections worth reading and list them, with a reason for each, in the project's brainsight.md (Team and Personal tables). Re-running adds new entries only.
---

# brain-sight

- Purpose: take the ask (the request, or the new information being looked for) and pass it as context to the analysts, who list what to read for it.
- `brain` below = `python "$BRAIN_HOME/scripts/brain.py"` (Bash tool). Env vars: `hookup-checklist.md`. Rules: `brain-reference.md` §11, §12.
- Cost: read only script output. Never open wiki pages, the section index files or the rows files. Analysts reply with one path.
- Writes only the project's brainsight.md. Data dictionaries are never read or written.
- Hand analysts absolute paths built from ROOT. Log with absolute `--in-file` paths and `--out-text "<the analyst's reply>"`. Counts come from `sight-add` output only.

## Steps

1. Run `brain root`, `echo "$BRAIN_HOME"` -> ROOT, HOME. PROJECT = the folder this session is open in (absolute). SIGHT = `PROJECT/brainsight.md`. PREVIEW = `ROOT/brain-work/brainsight-preview.md`.
2. ASK = the argument. None: ask "What is the ask, in one or two lines?". TITLE = a short name from ASK.
3. `brain sections --side team --out brain-work/sections-team.txt` and `brain sections --side personal --out brain-work/sections-personal.txt`.
4. SIGHT exists (re-run): `brain candidates --sight "SIGHT" --out brain-work/sight-existing.txt`; EXISTING = `ROOT/brain-work/sight-existing.txt`. Else EXISTING = `none`.
5. Launch two `brain-context-analyst` in parallel, one per SIDE (`team`, `personal`), each with: ask ASK, side SIDE, root ROOT, index `ROOT/brain-work/sections-SIDE.txt`, existing EXISTING, rows_out `ROOT/brain-work/sight-rows-SIDE.json`.
6. Per analyst: `brain log brain-context-analyst --in-file "ROOT/brain-work/sections-SIDE.txt" --in-chars <ASK length> --out-text "<reply>" --note SIDE`.
7. Preview: SIGHT exists -> `cp "SIGHT" "PREVIEW"`; else `rm -f "PREVIEW"`.
8. Per side: `brain sight-add --sight "PREVIEW" --rows "ROOT/brain-work/sight-rows-SIDE.json" --title "TITLE"`. Keep its `table SIDE:` line and any `rejected:` and `replaced:` lines.
9. Nothing added on either side -> stop: "No new entries found; refine the ask and rerun."
10. Ask the one question, showing the `rejected:` and `replaced:` lines:
    - "This run adds <n> team and <n> personal entries (<r> rejected). Write them to SIGHT? `yes` / `no`."
11. `no` -> stop; SIGHT is unchanged.
12. `cp "PREVIEW" "SIGHT"`.
13. Tell the main conversation, in these words:
    - "Open an entry in SIGHT only when its 'why' applies to what you are about to do: `brain section "<page>" ["<section>"] --side <team|personal>`."
    - "When handing work to a sub-agent, pass it the path SIGHT and tell it to open what its task needs."

## Stop conditions

- Steps 9 and 11 as above. A missing env var or `error:` from brain -> show it and stop.
- `sight-add` exits 1 for a side (every row rejected): show its `rejected:` lines; carry on with the other side.
