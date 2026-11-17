# Example: dashboard commentary, no dashboard

Claims cost dashboard commentary that varies by month and line of business. No dashboard is built: `demo_calls.py` makes every call a real one would.

| File | What it is |
| --- | --- |
| `commentary_plan.md` | The plan: monthly refresh, `paid_month` snapshots, line of business as the one commentary filter |
| `commentary_shell.json` | The plan for the scripts: three units; generator 1 varies by month, generator 2 by month and line of business |
| `commentary_outputs/` | The saved commentary: one file per run, per snapshot (below) |
| `run_commentary.py` | The stamped no-argument run (what a scheduler would run after each refresh) |
| `demo_calls.py` | Runs the whole life cycle: read shell, setup, Sep and Oct refreshes, rerun, override, hand edit, run-time lookups |
| `demo_output.txt` | Output of the last demo run (recorded before the switch to output files; rerun the demo to refresh it) |
| `snapshots/2026-09`, `snapshots/2026-10` | Two data refreshes; the demo copies each into `data/` in turn |

`commentary_outputs/` after the demo:

| File | Saved by |
| --- | --- |
| `commentary_2026-09_20261110-141003.json` | September refresh |
| `commentary_2026-10_20261110-141024.json` | October refresh |
| `commentary_2026-10_20261110-141045.json` | `--override lob_trend` |
| `commentary_2026-10_20261110-141046.json` | hand edit of `overview` (newest October file: the one shown) |

The rerun with unchanged data saved nothing.

Rerun from the skill folder (`.claude/skills/commentary`) (live writer calls, about $0.25):

```
python examples/make_examples.py --only=dashboard_programmatic
python examples/dashboard_programmatic/demo_calls.py
```

Look commentary up yourself:

```python
import sys; sys.path.insert(0, "scripts")
from runtime import CommentaryRuntime
rt = CommentaryRuntime.from_outputs("examples/dashboard_programmatic/commentary_shell.json")
rt.lookup("lob_trend", {"paid_month": "2026-10", "line_of_business": "Medicare"})
```
