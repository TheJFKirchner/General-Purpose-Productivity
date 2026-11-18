---
name: brain-ingest
description: Turn documents waiting in the wiki's personal raw folder into source records, then file them to personal pages after one yes. Use when documents have been dropped in raw/.
---

# brain-ingest

- `brain` below = `python "$BRAIN_HOME/scripts/brain.py"` (Bash tool). Env vars: `hookup-checklist.md`. Rules: `brain-reference.md` §4, §13, §14, §15.
- Cost: read only script output. Never open the documents, records, wiki pages, the page list or packets. Sub-agents return paths and flags only.
- Writes personal pages only. Data dictionaries are never read or written.
- Hand sub-agents absolute paths built from ROOT. Log every call with absolute `--in-file` paths and `--out-text "<the sub-agent's reply>"`. Take counts from script output.

## Steps

1. Run `brain root`, `echo "$BRAIN_HOME"`, `whoami`, `date +%F` -> ROOT, HOME, USER, DATE.
2. Sync in: `git -C "ROOT" pull --ff-only`. Not a git repo -> skip sync here and in step 19. Fails -> stop.
3. SIGHT = the argument (absolute path), else `<project folder>/brainsight.md` (absolute; the folder this session is open in) if it exists, else none.
4. `brain summary --status approved`. Output other than `no approved records ...` -> stop; follow `brain-reference.md` §14.
5. Glob `ROOT/personal/raw/*` (top-level files only; names only). `brain summary`: records headed `[ingest, pending]` = OLD; drop documents OLD already names. Nothing left and no OLD -> stop: "No documents in raw/."
6. `brain pagelist`. SIGHT set: `brain candidates --sight "SIGHT" --out brain-work/candidates.txt`; exit 3 -> SIGHT = none.
7. Documents left (else step 9): batches of up to 5; one `brain-extractor` per batch, all in parallel, each with: inputs = the batch, origin `ingest`, root ROOT, date DATE, user USER, page_list `ROOT/brain-work/page-list.md`, candidates `ROOT/brain-work/candidates.txt` or `none`, sources `ROOT/personal/sources`, reference `HOME/brain-reference.md`.
8. Per batch: `brain log brain-extractor --in-file <each document> --in-file "ROOT/brain-work/page-list.md" --out-text "<reply>" --note ingest`.
9. RECS = OLD plus the record names (file stems) from the extractors' `record:` lines. `brain summary RECS...`. Show its output (counts only) unchanged, then ask the one question:
   - "Reply `yes` to file and sync. `skip <record>` leaves it pending. Name any `New page:` to create (`EXISTS` needs a new name; `NEAR` needs `allow near`). `no` stops."
10. `no` -> stop; records stay pending, documents stay in raw/.
11. `brain approve <each record in RECS not skipped>`. Never `--all`.
12. `brain collect <same records>` plus `--new-page NAME` per approved new page, plus `--allow-near` if allowed. Exit 1 -> show the error; stop.
13. One `brain-filer` per `packet:` line, all in parallel, each with: packet `ROOT/<packet>`, root ROOT.
14. Per filer: `brain log brain-filer --in-file "ROOT/<packet>" --out-text "<reply>" --note <page>`.
15. FAILED = pages whose filer reply flags `limit reached` or `failed`, or is not one line in the §7 format.
16. `brain markfiled` plus `--failed <page>` per FAILED page. Documents move to `personal/raw/processed/`.
17. markfiled exit 1 (team-write guard) -> stop; show its output; nothing is filed (§14 step 6).
18. Tell the user in one line: totals added / dup / conflict across filers, the markfiled totals line, and every page with a conflict or in FAILED (its packet is kept; retry per §14).
19. Sync out: `git -C "ROOT" add -A personal && git -C "ROOT" commit -m "brain-ingest DATE" && git -C "ROOT" push`.

## Stop conditions

- Steps 2, 4, 5, 10, 12, 17 as above. A missing env var or `error:` from brain -> show it and stop.
- Never rerun `collect` to retry a failed page (§14).
- Never open a document to summarise it for the user; the summary output is all they get. They may open a record themselves.
