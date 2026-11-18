---
description: Count of members enrolled in each month; the denominator for per-member metrics.
template: metric
---

# member-months

## Overview

- One member month is one member enrolled for a calendar month. #metric
- The denominator for [[pmpm]] and other per-member rates.
- Built from the member eligibility table each night.

## Decisions

- 2026-02-14: A member counts for a month if enrolled on the 15th of that month. #definition
- 2026-07-30: Dependents count as separate members; subscribers are not weighted.

## Definition

- Member months for a period = number of (member, month) pairs where the member was enrolled on the 15th. #definition

## Calculation

- Expand each eligibility span into months; keep months where the span covers the 15th. #formula
- Sum by group, product and month as needed.

## Traps

- Counting a member for any day of the month overstates member months by 1 to 2 percent. #trap
- Retroactive terminations remove past member months; reports run before the retro change will not match. #trap
- Overlapping eligibility spans for one member must be merged before counting. #trap

## Reference

- Retro terminations are allowed up to 60 days back under most client contracts. #regulatory
- Average membership = member months / number of months.

## Notes

- Eligibility arrives from the enrollment platform each night; weekend files are smaller.
- Some clients send eligibility by file only once a month; their counts change in steps.
