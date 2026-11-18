---
description: Data dictionary for the claims-header table. Maintained by the data platform team only.
---

# claims-header dictionary

| Column | Type | Description | Allowed values |
|---|---|---|---|
| claim_id | varchar(20) | Claim identifier from the claims platform | |
| version_no | int | Version of the claim header; increments on adjustment | 1 and up |
| member_id | varchar(15) | Member identifier | |
| group_id | varchar(10) | Employer group identifier | |
| service_from_date | date | First date of service on the header | |
| service_to_date | date | Last date of service on the header | |
| paid_date | date | Date the claim was paid | |
| claim_status | varchar(10) | Current status of this version | paid, denied, pending, reversed |
| claim_type | char(1) | Professional or facility | P, F |
| billed_amt | decimal(12,2) | Amount billed by the provider | |
| allowed_amt | decimal(12,2) | Contracted allowed amount | |
| paid_amt | decimal(12,2) | Amount paid by the plan | |
| member_resp_amt | decimal(12,2) | Deductible, copay and coinsurance | |
| provider_id | varchar(15) | Billing provider identifier | |
| place_of_service | char(2) | Place of service code | |
| primary_dx | varchar(8) | Primary diagnosis code | |
| load_ts | timestamp | Time the row was loaded | |

## Change history

- 2026-05: backfill of 2024 facility rows.
- 2025-11: member_resp_amt added.

## Load notes

- Source: claims platform nightly extract.
- Monthly full refresh on the first Sunday.
- Rows are never deleted; reversals arrive as new versions.
- Owner: data platform team.
- Change requests go through the data platform intake form.
- Last reviewed 2026-10.
- Column order matches the extract file.
- No personal analyst notes belong here.
- Analysts should read the table page for traps.
- This file is excluded from brain intake.
