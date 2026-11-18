---
description: Warehouse table with one row per medical claim header; the main source for paid and allowed amounts.
template: table
---

# claims-header

## Overview

- Holds one row per medical claim header from the claims platform. #table
- Loaded nightly from the claims platform extract; the load finishes around 06:00. #source-system
- Covers professional and facility claims. Pharmacy claims are in a separate table.
- Column definitions are in the data dictionary file next to this page.

## How it fits

- Joins to the member eligibility table on member id and service date.
- Feeds [[pmpm]], [[medical-loss-ratio]], [[high-cost-claimants]] and [[stop-loss]] reporting.
- Lag triangles for [[ibnr]] are built from paid date and incurred date on this table.

## Grain and keys

- One row per claim header version: claim id plus version number. #table
- An adjustment creates a new version; the latest version has the current status.
- Join key to claim lines: claim id plus version number.

## Traps

- Summing all versions double counts adjusted claims; filter to the latest version or net reversals. #trap
- Denied claims stay in the table with paid amount zero; they still count in claim volume unless filtered. #trap
- Service date is the first date of service on the header; long facility stays span months. #trap
- Paid amount excludes member cost share; allowed amount includes it. #trap
- Claims for terminated members can arrive months later; do not drop rows that fall outside eligibility without checking. #trap

## Reference

- Retention: seven years online, older years in the archive schema.
- Load schedule: nightly, with a full refresh on the first Sunday of each month.
- Status values: paid, denied, pending, reversed.
- The dictionary file holds column types and allowed values.

## Notes

- The claims platform team owns the extract; raise load failures in their queue.
- A backfill of 2024 facility claims ran in 2026-05; totals for that year changed slightly.
