# Commentary plan: support_ops_oct

## Deliverable
Monthly support operations report (`support_report.html`) for the head of customer support and their team leads. Four sections get commentary.

## Data and refresh
- Tables: tickets by week and by channel (Parquet), backlog by team and SLA targets (CSV), in `data/`
- Refresh: monthly; each month is a new edition of the report in its own folder
- Snapshot column: none within an edition
- History: last month's edition stays as it was

## Filters
| Filter | Commentary changes with it? | Values / count |
| --- | --- | --- |
| None (a static report) | | |

## Output files
One per run: `commentary_<time>.json`. 4 commentary entries.

## When it runs
Once per edition, in a session, after the month's data is in `data/`.

## Commentary units
| Unit | Where | Question it answers | Tables | Length | Group |
| --- | --- | --- | --- | --- | --- |
| `volume` | Volume and response times | How ticket volume, first response time and CSAT moved over the last weeks, and when the change started | `tickets_by_week` | 3 bullets, 28 words | 1 |
| `channels` | Channels | Which channels absorbed the extra volume and how their CSAT compares | `by_channel` | 2 bullets, 28 words | 1 |
| `backlog` | Backlog by team | Which teams' backlogs grew most in four weeks and how old their oldest tickets are | `backlog_by_team` | 1 paragraph, 70 words | 2 |
| `sla` | SLA position | Whether median first response time and CSAT are inside their targets, by how much, and for how many weeks they have been outside | `tickets_by_week`, `sla_targets` | 2 bullets, 25 words | 2 |

## Groups
| Group | Audience | Units | Notes |
| --- | --- | --- | --- |
| 1 | Head of support and team leads | `volume`, `channels` | |
| 2 | Head of support | `backlog`, `sla` | SLA targets are kept in a table so commentary about them can be checked |

## Review and rules
- Review: the head of support reads the filled report before it goes out.
- Unverified numbers: flagged; edited or dropped before filling.
- Regenerate when: asked (`--override`). Next edition: copy this plan and the shell, and point `prior_file` at this edition's `commentary_outputs` if sections should refer back.

## Open questions
- None.
