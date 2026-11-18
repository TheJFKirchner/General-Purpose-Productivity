# Sample project: Client A stop-loss renewal pack

A sample project folder for testing BrainCite and BrainCite-first routing. Not a wiki page; it sits
outside `personal/` and `team/`, so `brain.py` never indexes it.

- Goal: build the stop-loss section of Client A's 2027 renewal pack: exposure, lasered members,
  reimbursement lag, and two attachment-point options.
- Data: claims-header (paid amounts), member eligibility, the carrier's laser list.
- `braincite.md` lists the wiki pages and sections this project draws on, with ids (T1.., P1..)
  and a Reads count per entry. Its counts are all 0 in the sample.
- Test with, from this folder: `brain.py --wiki .. candidates` and `brain.py --wiki .. read --no-count T3 P1`.
