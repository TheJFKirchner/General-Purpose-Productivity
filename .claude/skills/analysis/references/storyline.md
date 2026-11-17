# Step 4: the answer and its storyline (gate 2)

Written after analysing, before any HTML. Gate 2: the analysis ends, the report starts.

## Analysing (step 3)

- Quick look: a short script in the session.
- Worth keeping or rerunning: a section file (`sections.md`).
- No charts, no HTML.

| Request | Explore |
| --- | --- |
| Pointed | Compute what was asked. Nothing else |
| Open | The brief's "Things to test", in order. Nothing else. One section file per test worth keeping |

The list:

- Fill each row's Result in the README, one line: what it showed, with the figure, or "no effect".
- Cause located: run the remaining tests on those records only (the 220 claims, not the whole file).
- "Not run": only when the result so far makes the test pointless. Say why.
- Something off the list looks relevant: do not chase it. Ask the user to add it. Auto: add at most two rows, marked "added".
- Same limit after gate 2. A finding while building the report that changes the answer: back to gate 2.
- List finished, no answer: stop, show the user the results. Do not start checking other fields.

## How

1. **Answer first:** two sentences that meet the brief's Success line. Cannot: keep analysing, or go back to the user.
2. **List the claims** a reader must accept to believe it. One claim = one section (an existing file, or one still to write).
   - Section files that prove no claim: left out of the report, not deleted.
   - Open question: claims come from tests that showed something. No-effect tests: one line each under "Not included".
3. **One visual per claim:** the one that makes it obvious to someone new to the data (`charts.md`). A second only if the claim cannot be seen without it.
4. **Cut.** Remove a section and reread. Answer just as convincing: it stays out.
5. **Write it** in `README.md`, "Storyline". Show the user, with the figures behind each claim. No HTML yet.
6. **On their yes** (auto: once the answer meets the Success line): set `REPORT` in `config.py` to the chosen sections in storyline order, e.g. `REPORT = ["s1", "s4", "s2"]`. Not agreed: back to analysing, or to gate 1 if the question moved.

## Shape

| Position | Job |
| --- | --- |
| Top of report | The answer (written by the commentary step, from the sections) |
| First section | The size of the thing: how big, how many, how much |
| Middle sections | Where it is and why: the breakdown or cause |
| Last section (only if needed) | What the reader acts on: the records to fix, the exceptions. Not a recap; the answer at the top is the recap |

| Request type | Typical sections |
| --- | --- |
| Compare two sources | How far apart overall; then one section per cause, largest first, each with its size and the records behind it |
| Relationship | Is there one and how strong; does it hold across groups; what breaks it |
| Change and drivers | How big the change is; which few things drive it; price or volume; one-off or lasting |
| Outliers | What normal looks like; who is outside it; why they are (or are not) explained |

## Limits

- 2 to 5 sections. More: the question is too wide. Split it or go back to gate 1.
- A section: visuals on the same data making the same point. Usually 1 or 2, never more than 3.
- No profiling section, no "data overview", no table of everything.
- Findings that do not serve the answer, and section files left out: one line each under "Not included".

## Format in README.md

```markdown
**Answer:** <two sentences>

| Section | Claim it proves | Visual |
| --- | --- | --- |
| s1 | The two sources agree on 96% of claims; the gap is 4,100 claims | Bar: matched, only in A, only in B |
| s4 | ... | ... |

**Not included:** <one line each, e.g. "s3 line of business: no effect">
```

## Checklist

- [ ] The answer meets the brief's Success line
- [ ] Every section has one claim; the claims in order read as an argument
- [ ] No section survives only because the data was available
- [ ] User agreed it is the answer. README "Approved" line. Auto: "auto mode, not yet confirmed"
- [ ] `REPORT` lists the storyline's sections, in order, nothing else
