---
description: Incurred but not reported claims; the estimate of claims that have happened but are not yet paid.
template: concept
---

# ibnr

## Overview

- IBNR is the estimated cost of claims already incurred but not yet paid. #definition
- Set by the actuarial team each month; analytics uses it, never computes it for official numbers. #actuarial
- Needed for any incurred-basis view of recent months.

## How it fits

- Completes incurred [[pmpm]] and the [[medical-loss-ratio]] for recent months.
- Built from lag triangles on [[claims-header]] paid date versus service date.
- Does not cover open [[stop-loss]] reimbursements.

## Decisions

- 2026-01-25: Analytics uses actuarial completion factors as delivered; no local adjustment. #actuarial
- 2026-06-30: Completion factors are refreshed on the fifth business day of each month.

## Traps

- Completion factors for the latest month are very large; do not show that month incurred without a caveat. #trap
- A claims backlog at the platform makes recent months look low; check the paid-lag report first. #trap
- Factors are by line of business; applying the commercial factor to Medicare business is wrong. #trap

## Reference

- Completion factor: share of eventual incurred cost already paid after n months of lag. #definition
- Completed incurred = paid to date / completion factor. #formula
- Lag triangle: incurred month by paid month matrix of paid amounts.

## Notes

- The actuarial team publishes factors in their shared folder; analytics loads them into a lookup table.
