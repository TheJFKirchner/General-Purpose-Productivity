---
description: Per member per month cost; the headline cost metric in every client report.
template: metric
---

# pmpm

## Overview

- PMPM is total plan cost divided by member months for the same period. #metric
- It is the headline number on every client cost report and the renewal deck. #reporting
- Used to compare cost across groups of different size and across periods.

## Decisions

- 2026-01-10: Client reports use paid PMPM; actuarial reports use incurred PMPM with completion. #actuarial
- 2026-04-22: Medical and pharmacy PMPM are shown separately and combined.
- 2026-08-05: Capitation payments are included in medical PMPM.

## Definition

- PMPM = plan paid amount / member months, for one period and one population. #definition
- Paid basis by default; incurred basis must be labelled "incurred PMPM".

## Calculation

- Numerator: sum of paid amount from [[claims-header]], latest version only, for the period. #formula
- Denominator: [[member-months]] for the same population and months. #formula
- Pharmacy numerator comes from the pharmacy claims table, net of rebates only if labelled "net".

## Traps

- Numerator and denominator must cover exactly the same members; a mismatch inflates PMPM for small groups. #trap
- A single high-cost claimant can move a small group's PMPM by 30% or more; check [[high-cost-claimants]] first. #trap
- Incurred PMPM for recent months is incomplete until [[ibnr]] completion is applied. #trap
- Do not average monthly PMPM values; recompute from summed cost and summed member months. #trap

## Reference

- Typical commercial medical PMPM range in our book: 380 to 520.
- Trend is reported as the change in PMPM over the same months a year earlier.
- Rolling-12 PMPM uses the last twelve complete paid months.

## Notes

- Account managers often ask for PMPM excluding claimants over the stop-loss attachment point; see [[stop-loss]].
