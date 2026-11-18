# Sample project: Client A stop-loss renewal pack

A sample project folder for testing BrainSight and BrainSight-first routing. Not a wiki page; it sits
outside `personal/` and `team/`, so `brain.py` never indexes it.

- Goal: build the stop-loss section of Client A's 2027 renewal pack: exposure, lasered members,
  reimbursement lag, and two attachment-point options.
- Data: claims-header (paid amounts), member eligibility, the carrier's laser list.
- `brainsight.md` lists which wiki sections to read: planning rows for the main conversation,
  work rows to hand to the sub-agent that writes the queries.
- Test with: `brain.py candidates --sight sample-project/brainsight.md` from the wiki root.
