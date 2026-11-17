# Commentary plan: q3_cost_review

## Deliverable
Six-slide healthcare cost review deck (`cost_review.pptx`) for finance leadership, with an executive summary slide for the executive committee.

## Data and refresh
- Tables: diagnosis cost by month, by category and by care setting, top conditions, pharmacy spend by drug class (`data/`)
- Refresh: none. One edition, built once.
- Snapshot column: none
- History: not needed; the next edition gets its own folder

## Filters
| Filter | Commentary changes with it? | Values / count |
| --- | --- | --- |
| None (a static deck) | | |

## Output files
One per run: `commentary_<time>.json`. 6 commentary entries.

## When it runs
Once, in a session, after the slides are built.

## Commentary units
| Unit | Where | Question it answers | Tables | Length | Group |
| --- | --- | --- | --- | --- | --- |
| `exec_summary` | Slide 1 | The three things the committee must know about October cost | none (reads the other slides' commentary) | 3 bullets, 22 words | 3 |
| `dx_trend` | Slide 2 | How October diagnosis cost and PMPM moved versus September and the 12-month trend | `dx_by_month` | 3 bullets, 25 words | 1 |
| `dx_category` | Slide 3 | Which diagnosis categories drove the month-over-month change | `dx_by_category` | 3 bullets, 25 words | 1 |
| `dx_setting` | Slide 4 | Whether the increase is price or volume, by care setting | `dx_by_setting` | 3 bullets, 25 words | 1 |
| `dx_conditions` | Slide 5 | Which top conditions had the largest change in cost per patient | `top_conditions` | 2 bullets, 25 words | 1 |
| `rx_mix` | Slide 6 | What drove the change in pharmacy spend, by drug class | `rx_by_class` | 3 bullets, 25 words | 2 |

## Groups
| Group | Audience | Units | Notes |
| --- | --- | --- | --- |
| 1 | Finance leadership | Diagnosis slides 2–5 | Written together so they read as a set. Tone sample `exec_tone.txt` |
| 2 | Finance leadership | `rx_mix` | |
| 3 | Executive committee | `exec_summary` | Summary: written last, only from groups 1 and 2's checked commentary |

## Review and rules
- Review: the analyst reviews the Review section of `commentary_run.md` before filling the deck.
- Unverified numbers: flagged for the analyst; dropped at fill if not resolved.
- Regenerate when: the analyst asks (`--override`).

## Open questions
- None.
