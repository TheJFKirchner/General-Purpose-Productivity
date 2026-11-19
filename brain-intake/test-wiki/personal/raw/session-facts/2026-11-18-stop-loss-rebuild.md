# Session facts: stop-loss-rebuild

- 2026-11-18: In claims-header, paid_date is empty for pending claims; filter on claim status before using paid date. (page: claims-header)
- 2026-11-18: Most current client stop-loss contracts are 12/15, so 12/15 should be the default basis for specific claims, not 12/12. (page: stop-loss)
- 2026-11-18: The specific attachment point applies per member per contract year, not per calendar year. (page: stop-loss)
- 2026-11-18: Vision claims are loaded quarterly from the vision vendor into a separate schema.
- 2026-11-18: Trend for any group under 100 members should use rolling-12 PMPM, not only Client C; monthly values swing too much to read. (page: trend-analysis)
- 2026-11-18: The trend table in renewal packs shows 24 months; the first 12 are the base period and the last 12 the current period.
- 2026-11-18: Client B's 50,000 high-cost threshold counts medical plus pharmacy. (page: q4-renewal-analysis)
- 2026-11-18: The eligibility load now finishes before the claims load, so same-day joins are safe after 08:00.
