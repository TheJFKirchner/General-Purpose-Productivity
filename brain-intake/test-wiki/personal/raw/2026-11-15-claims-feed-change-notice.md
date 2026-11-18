# Claims platform change notice (sample)

From: claims platform team
Date: 2026-11-15

Summary of changes going live on 2026-12-01:

1. Adjusted claims will be sent as a full replacement version instead of a reversal row plus a re-bill row.
   In the claims-header table this means each adjustment adds one new version, and the old version is
   marked superseded rather than reversed. Queries that net reversals will stop finding reversal rows.
2. The nightly load window moves later; expect the claims-header load to finish around 07:30 instead of 06:00.
3. Dental claims will move to a new dental vendor from 2027-01-01. Dental data is not loaded into the
   warehouse today and will not be after the move; requests for dental data go to the benefits team.

No action is needed from analytics before go-live, apart from reviewing any query that relies on reversal rows.
Contact the claims platform queue with questions.
