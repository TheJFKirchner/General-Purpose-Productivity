---
description: My checklist for reviewing claims and eligibility SQL before results go to a client.
---

# sql-review-checklist

## Overview

- I run this list on every query that feeds a client-facing number.
- It catches the mistakes I have actually made, not every possible mistake.

## Checks

- Claims filtered to the latest version, or reversals netted. See [[claims-header]].
- Denied claims excluded from cost, kept in volume only when asked.
- Member months built with the 15th-of-month rule. See [[member-months]].
- Numerator and denominator cover the same members and months.
- Paid versus allowed used consistently through the query.
- Date filters on paid date for paid views, service date for incurred views.
- Pharmacy included or excluded on purpose, and labelled.
- Group ids checked against the current client list; merged groups have two ids.
- Small-cell suppression applied to any table with member counts under 11. #regulatory

## Traps

- Joining claims to eligibility on member id alone duplicates rows for members with two spans. #trap
- A left join from members to claims followed by a WHERE on a claim column turns into an inner join. #trap
- Integer division in some engines truncates PMPM; cast to decimal first. #trap

## Reference

- Suppression threshold: 11 members, per the data use agreement. #regulatory
- Standard date window for renewals: 24 complete paid months.

## Notes

- Keep reviewed queries in the team query library with a short header comment.
- Ask a second analyst to run the checks on any query I wrote the same day. #todo
- Time taken per review is usually 15 to 30 minutes.
- Most findings in 2026 were version filtering and join duplication.
- Re-run the checks after any change to the date window.
