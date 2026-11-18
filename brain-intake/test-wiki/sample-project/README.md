# Sample project: Client A stop-loss renewal pack

A sample project folder for testing BrainCite and BrainCite-first routing. Not a wiki page; it sits
outside `personal/` and `team/`, so `brain.py` never indexes it.

- Goal: build the stop-loss section of Client A's 2027 renewal pack: exposure, lasered members,
  reimbursement lag, and two attachment-point options.
- Data: claims-header (paid amounts), member eligibility, the carrier's laser list.
- `braincite.md` lists the wiki sections and whole pages this project draws on, in a Team table and
  a Personal table, with a reason to read each.
- Test with: `brain.py candidates --cite sample-project/braincite.md` from the wiki root, and open
  an entry with `brain.py section "stop-loss" "Traps" --side team`.
