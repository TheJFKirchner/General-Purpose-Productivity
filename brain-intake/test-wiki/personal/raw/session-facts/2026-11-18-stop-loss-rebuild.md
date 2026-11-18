# Session facts: stop-loss-rebuild

- 2026-11-18: In claims-header, paid_date is empty for pending claims; filter on claim status before using paid date.
- 2026-11-18: Most current client stop-loss contracts are 12/15, so 12/15 should be the default basis for specific claims, not 12/12.
- 2026-11-18: The specific attachment point applies per member per contract year, not per calendar year.
- 2026-11-18: Vision claims are loaded quarterly from the vision vendor into a separate schema.
- 2026-11-18: Incurred PMPM in the actuarial appendix should use the same completion month as the MLR view.
- 2026-11-18: Completion factors for Medicare business arrive in a separate file from the commercial factors.
- 2026-11-18: Client B's 50,000 high-cost threshold counts medical plus pharmacy.
- 2026-11-18: The eligibility load now finishes before the claims load, so same-day joins are safe after 08:00.
