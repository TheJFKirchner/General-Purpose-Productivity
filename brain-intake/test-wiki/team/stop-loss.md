---
description: Excess-loss insurance that caps a self-funded employer's claim cost; how analytics measures and reports it.
template: concept
---

# stop-loss

## Overview

- Stop-loss is insurance a self-funded employer buys so that very large claims do not land fully on the employer. #definition
- Two kinds: specific (per member) and aggregate (whole group). Most of our clients buy specific only.
- Analytics reports stop-loss exposure monthly to account managers and quarterly to the actuarial team. #reporting
- The carrier reimburses the employer; reimbursements never appear in the claims tables.

## How it fits

- Exposure is driven by [[high-cost-claimants]]: every member over the attachment point is a stop-loss claimant.
- Reimbursements reduce net plan cost, so they change [[pmpm]] and [[medical-loss-ratio]] only when the report says "net".
- Paid amounts come from [[claims-header]]; member counts come from [[member-months]].
- Open stop-loss claims are not part of [[ibnr]]; the actuarial team reserves for them separately. #actuarial

## Decisions

- 2026-03-02: Account manager reports show gross and net side by side, never net alone. #reporting
- 2026-06-15: Lasered members are reported in their own row, not folded into the group total.
- 2026-09-01: Pharmacy claims count toward the specific deductible only when the contract says so; default is medical only.

## Traps

- Specific claims are measured on a paid basis within the contract period (12/12) unless the contract says otherwise; do not use incurred dates by default. #trap
- The specific attachment point applies per member per contract year, not per calendar year. #trap
- A lasered member has a higher attachment point than the group; using the group value overstates reimbursement. #trap
- Claims with a reversal and re-bill appear twice in [[claims-header]]; net them before summing toward the deductible. #trap
- Do not compare stop-loss premium to reimbursements in the same month; reimbursements lag by two to four months. #trap
- Aggregate attachment is a percentage of expected claims, not of premium. #trap

## Reference

- Specific attachment point (specific deductible): the claim cost per member per contract year above which the carrier pays. #definition
- Aggregate attachment point: total group claims, as a percentage of expected claims (commonly 125%), above which the carrier pays. #definition
- Lasering: setting a higher attachment point for one named member at renewal. #definition
- Contract basis written as incurred/paid months, e.g. 12/12, 12/15, 15/12. #definition
- Reimbursement formula: `max(0, member paid in contract period - member attachment point)`. #formula
- Run-out: the months after the contract ends during which paid claims still count (the second number in 12/15 is the paid window).

## Notes

- Contract terms live with the account team; analytics receives a summary sheet per client at renewal.
- When the summary sheet and the contract disagree, the contract wins; raise it with the account manager.
