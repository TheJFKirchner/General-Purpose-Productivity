---
description: Scoring member health risk from diagnoses so cost can be compared fairly across populations.
template: concept
---

# risk-adjustment

## Overview

- Risk adjustment scores each member's expected cost from diagnoses, age and sex. #definition
- Used to compare groups fairly and to explain cost differences at renewal.
- Scores come from a licensed grouper run monthly by the data platform team.

## How it fits

- Diagnoses come from [[claims-header]] primary and secondary diagnosis fields.
- Risk-adjusted [[pmpm]] = PMPM / average risk score.
- Large risk score jumps often trace to [[high-cost-claimants]].

## Decisions

- 2026-02-28: Client reports use a 12-month diagnosis window ending three months before the report month.
- 2026-07-12: Members with fewer than six months of eligibility get the demographic-only score.

## Traps

- Scores are relative to the grouper's reference population, not our book; 1.0 is not our average. #trap
- New members have demographic-only scores, which understate risk for sick new joiners. #trap
- Comparing scores across grouper versions is invalid; check the version column. #trap

## Reference

- Risk score: expected cost relative to the reference population average of 1.0. #definition
- Normalised score: risk score divided by the book average for the same period. #formula

## Notes

- The grouper version changed in 2026-04; scores before and after are not comparable.
