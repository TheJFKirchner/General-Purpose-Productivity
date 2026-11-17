# Example: PowerPoint deck

Healthcare cost review, six slides, mock data. Shows grouping slides into generators and an executive summary written only from the other slides' verified commentary.

| File | What it is |
| --- | --- |
| `commentary_plan.md` | The plan: what each slide's commentary answers, grouping, review |
| `commentary_shell.json` | The plan for the scripts: six units, three generators (diagnosis slides, pharmacy, executive summary) |
| `cost_review.pptx` | Unfilled deck, one `{{commentary:<unit_id>}}` per slide |
| `data/` | The aggregated tables behind each slide (CSV) |
| `commentary_outputs/` | One output file per run: the shell with commentary written in |
| `commentary_run.md` | Report from the last run, with the Review section (read this first after a run) |
| `cost_review_filled.pptx` | The filled deck |

Rerun from the skill folder (`.claude/skills/commentary`) (live writer calls):

```
python examples/make_examples.py --only=deck_pptx          # reset inputs
S=scripts
python $S/status.py examples/deck_pptx/commentary_shell.json
python $S/generate.py examples/deck_pptx/commentary_shell.json
python $S/fill.py examples/deck_pptx/commentary_shell.json
```
