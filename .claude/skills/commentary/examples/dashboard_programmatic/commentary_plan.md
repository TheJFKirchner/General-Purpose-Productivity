# Commentary plan: dx_cost_dashboard

## Deliverable
Claims cost dashboard for finance. Two tabs: an overview header for finance leadership, and a line-of-business tab for the line-of-business finance leads. In this example there is no dashboard UI; `demo_calls.py` makes the calls a real dashboard would.

## Data and refresh
- Tables: `claims_total` (members, allowed cost, PMPM by month), `claims_by_lob` (the same by line of business), `category_by_lob` (allowed cost by diagnosis category, line of business and month)
- Refresh: monthly, after claims close (simulated by `snapshots/2026-09` and `snapshots/2026-10`)
- Snapshot column: `paid_month` (rule: latest value)
- History: older months stay viewable on the dashboard, so each month keeps its own commentary

## Filters
| Filter | Commentary changes with it? | Values / count |
| --- | --- | --- |
| Paid month | Yes (it is the snapshot) | one per refresh |
| Line of business | Yes, on the line-of-business tab | Commercial, Medicaid, Medicare (3) |
| Region, product | No: the commentary ignores them, and the dashboard says so | |

## Output files
One per snapshot (`commentary_2026-09_<time>.json`, `commentary_2026-10_<time>.json`, ...). Line of business lives inside each file. 7 commentary entries per snapshot: overview × 1, plus 2 units × 3 lines of business.

## When it runs
After each monthly refresh, on the analyst's machine: `python run_commentary.py`. Never when the dashboard is viewed.

## Commentary units
| Unit | Where | Question it answers | Tables | Length | Group |
| --- | --- | --- | --- | --- | --- |
| `overview` | Overview tab, header | How total allowed cost and PMPM moved this month versus last month, and the trend since November | `claims_total` | 3 bullets, 25 words | 1 |
| `lob_trend` | Line-of-business tab, trend | How this line of business's PMPM and membership moved versus last month | `claims_by_lob` | 2 bullets, 25 words | 2 |
| `lob_categories` | Line-of-business tab, categories | Which diagnosis categories changed most this month for this line of business | `category_by_lob` | 2 bullets, 25 words | 2 |

## Groups
| Group | Audience | Units | Notes |
| --- | --- | --- | --- |
| 1 | Finance leadership | `overview` | Varies by month. Sees last month's commentary. Tone sample `exec_tone.txt` |
| 2 | Line-of-business finance leads | `lob_trend`, `lob_categories` | Varies by month and line of business. Sees last month's commentary |

## Review and rules
- Review: the analyst reads `commentary_run.md` after each refresh and hand-edits if needed.
- Unverified numbers: hidden on the dashboard.
- Regenerate when: the analyst asks (`--override`). Restated data only raises a warning.

## Open questions
- None.
