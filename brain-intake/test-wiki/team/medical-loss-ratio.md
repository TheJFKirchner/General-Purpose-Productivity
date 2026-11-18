---
description: Share of premium spent on claims and quality improvement; regulated for fully insured business.
template: metric
---

# medical-loss-ratio

## Overview

- Medical loss ratio (MLR) is the share of premium spent on medical claims and quality improvement. #metric
- Regulated for fully insured plans; reported internally for self-funded plans using premium equivalents. #regulatory
- Finance and actuarial own the official filing; analytics builds the monthly view.

## Decisions

- 2026-03-18: The monthly view uses paid claims plus an IBNR estimate from actuarial. #actuarial
- 2026-05-09: Self-funded MLR uses premium equivalent rates from the renewal file.

## Definition

- MLR = (incurred claims + quality improvement spend) / (premium - taxes and fees). #definition

## Calculation

- Incurred claims = paid claims from [[claims-header]] plus the [[ibnr]] estimate for the period. #formula
- Premium comes from the finance premium table, by month and group.
- Quality improvement spend is a fixed monthly amount supplied by finance.

## Traps

- Using paid claims without IBNR understates MLR for recent months. #trap
- Stop-loss reimbursements are not deducted from claims in the regulatory MLR. #trap
- Premium refunds and rebates belong in a separate line; do not net them from premium. #trap

## Reference

- Regulatory minimums: 80% for small group and individual, 85% for large group. #regulatory
- The official filing uses a three-year average; the monthly view does not.

## Notes

- Questions about the official filing go to finance, not analytics.
