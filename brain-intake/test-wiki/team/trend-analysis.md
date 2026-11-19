---
description: How analytics measures cost trend for client reports and renewal packs.
template: concept
---

# trend-analysis

## Overview

Trend is the year-over-year change in cost per member, and it is the number clients ask about first at renewal. Analytics reports it on PMPM, never on total dollars, so that a group that grew or shrank is not mistaken for one whose costs changed. (src: 2026-02-11-team-method-review)

Trend is always shown for medical and pharmacy separately and combined, because the two move for different reasons and a combined figure alone hides which one is driving the change. (src: 2026-02-11-team-method-review)

## How it fits

Trend is built from [[pmpm]], so every caveat on that page applies here. Large claimants distort it more than any other input: one member in [[high-cost-claimants]] can turn a flat year into a double-digit increase for a small group, which is why trend is reported with and without claimants above the high-cost threshold. (src: 2026-03-04-team-method-review)

## Decisions

| Date | Decision |
|---|---|
| 2026-02-11 | Trend is reported on paid PMPM for client reports and on incurred PMPM for actuarial work. |
| 2026-03-04 | Every trend figure is shown twice: all members, and excluding members above the high-cost threshold. |
| 2026-07-20 | The comparison is the latest 12 months against the 12 months before, not calendar year against calendar year. |

## Traps

The most common mistake is comparing a complete prior period with an incomplete current one. Recent months are missing claims that have not been paid yet, so an unadjusted comparison understates trend; apply completion from [[ibnr]] first or leave the last three months out. (src: 2026-03-04-team-method-review)

A change in the member mix can look like trend. When a group adds a large block of new members partway through the year, compare like with like or say plainly that the populations differ. (src: 2026-07-20-team-method-review)

## Reference

| Term | Meaning |
|---|---|
| Base period | The earlier 12 months in the comparison. |
| Current period | The latest 12 months in the comparison. |
| Normalised trend | Trend after removing members above the high-cost threshold. |

## Notes

Clients often quote a national trend figure from a broker report. Those figures are on a different basis and are not comparable with ours.
