# Step 6: commentary

Written by the `commentary` skill's writer, in a separate session.

- It sees only each section's `QUESTION`, `NOTES` and summary tables. Never the raw data or this conversation.
- Every number is checked against the tables.

## Before

- [ ] Sections run cleanly; charts are final
- [ ] Each `NOTES` is filled in
- [ ] Each `summary` holds the figures its claim needs

## Run

```
python run.py commentary
```

- One writer call per section, then one for the answer. Each is a paid model call, about one to three minutes; four sections at a time.
- Needs the `commentary` skill and the `claude` command.
- Skill is found automatically in a `.claude/skills/` folder above the analysis or in the home folder. Otherwise: `--skill <path to skills/commentary>`.
- Do not write a commentary plan or shell by hand. `run.py` generates `commentary/commentary_shell.json` from the section files.
- It then rebuilds the report.

| It writes | Where it shows |
| --- | --- |
| A one-sentence finding per section | The section heading |
| Up to three bullets per section | Under the heading |
| The answer (up to three bullets), written last from the sections' commentary | Top of the report |

Output: `commentary/commentary.json`, one item per piece:

| Field | What |
| --- | --- |
| `id` | `C1`, `C2` ... |
| `commentary` | The text |
| `source` | The tables, rows and columns the figures come from; any filter or adjustment |

In the report, each block has a collapsed line with its id and source.

## After

Read the report top to bottom, and `commentary/commentary_run.md`.

| You see | Do |
| --- | --- |
| `[unverified figure]` on a bullet | Figure is not in a summary table. Add it to the table (or remove it from `NOTES`), rerun the section, rerun commentary |
| "Writer says this is missing" in the run report | Add that comparison or figure to the summary table |
| A section shows "failed its checks" | Read the reason in the run report. Figure missing from the table: add it, rerun the section, rerun commentary. Figure is in the table: just rerun commentary |
| "writer timed out" or "writer call failed" | `python run.py commentary` again; only failed pieces are retried |
| Commentary misses the storyline's claim | Sharpen `QUESTION` or `NOTES`, then `python run.py commentary` (changed sections are rewritten) |
| Right facts, wrong wording | Hand edit: `python <commentary skill>/scripts/edit.py commentary/commentary_shell.json <unit> --bullet "..."`, then `python run.py build`. Unit ids are `C1`, `C2` ...; `python run.py status` shows which is which. One `--bullet` per bullet; together they replace all of that unit's bullets |

- Rewritten only: sections whose question, notes or summary data changed, or that failed last time. The answer: whenever any section's commentary is.
- `python run.py report` and `python run.py commentary` as separate commands, not chained, so a STOP in the first is seen.
- Data changed and commentary not rerun: the old commentary is hidden, not shown against new numbers.
- Never report a figure as checked unless the run report says so.
