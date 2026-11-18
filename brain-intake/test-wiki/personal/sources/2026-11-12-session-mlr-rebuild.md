---
origin: session
origin_name: mlr-rebuild
user: analyst
date: 2026-11-12
status: approved
input: personal/raw/session-facts/2026-11-12-mlr-rebuild.md
---

Summary: Rebuilt the monthly MLR view for two clients. Found a lag pattern in stop-loss reimbursements and a naming detail in the actuarial factor files.

## [[stop-loss]] > Traps
- Carrier reimbursements booked in December usually relate to claims paid in September or October.

## [[ibnr]]
- The actuarial factor file names the valuation month in the file name, not inside the file.

## Unplaced
- The finance premium table refreshes on the third business day of each month.
