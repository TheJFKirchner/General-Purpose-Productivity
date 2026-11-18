---
description: Members whose claims pass a cost threshold in a period; how they are found and reported.
template: concept
---

# high-cost-claimants

## Overview

- A high-cost claimant (HCC) is a member whose paid claims in a period pass a threshold, default 100,000. #definition
- A small number of HCCs drive a large share of cost in most groups.
- Reported monthly to account managers with diagnosis category, never with member names. #reporting

## How it fits

- Paid amounts come from [[claims-header]], latest versions only.
- Members above the [[stop-loss]] attachment point are a subset of HCCs.
- HCCs explain most large swings in small-group [[pmpm]].

## Decisions

- 2026-01-18: Default threshold is 100,000 paid in a rolling 12 months; clients can choose 50,000.
- 2026-05-27: Reports show diagnosis category only; no diagnosis codes for groups under 100 members. #regulatory

## Traps

- Thresholds are on paid, not allowed; mixing them changes who qualifies. #trap
- Include pharmacy cost only if the client's report definition says so. #trap
- For groups under 50 members, an HCC may be identifiable even without a name; suppress detail. #trap #regulatory

## Reference

- Rolling 12 months: the last twelve complete paid months.
- Diagnosis category: the grouper's top-level category for the member's highest-cost condition.

## Notes

- Account managers often want HCC lists before renewal meetings; plan for the request in the month before.
