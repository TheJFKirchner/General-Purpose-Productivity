# Example: HTML report

Support operations monthly report, mock data in Parquet and CSV. Shows a paragraph-style unit (backlog) and targets kept in a table (`sla_targets.csv`) so commentary about them can be number-checked.

| File | What it is |
| --- | --- |
| `commentary_plan.md` | The plan: four sections, two groups, review |
| `commentary_shell.json` | The plan for the scripts |
| `support_report.html` | Unfilled report, one placeholder per section |
| `data/` | Weekly tickets (Parquet), channels (Parquet), backlog and SLA targets (CSV) |
| `commentary_outputs/` | One output file per run: the shell with commentary written in |
| `commentary_run.md` | Report from the last run |
| `support_report_filled.html` | The filled report |

Rerun from the skill folder (`.claude/skills/commentary`) (live writer calls):

```
python examples/make_examples.py --only=report_html
S=scripts
python $S/generate.py examples/report_html/commentary_shell.json
python $S/fill.py examples/report_html/commentary_shell.json
```
