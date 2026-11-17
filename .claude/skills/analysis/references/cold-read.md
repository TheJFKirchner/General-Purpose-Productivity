# Step 7: cold read (gate 3)

A reader who has seen only the report says what it concludes. Compare that with the brief.

## How

1. Get the report as a reader sees it: `python run.py text` (title, answer, headings, commentary, each visual's title, note and values).
2. Start a fresh subagent. Give it only that text. Not the brief, README, storyline or this conversation.
   - No subagent tool: do the step 4 comparison yourself against the printed text. Say at hand-over that no independent read was done.
3. Ask exactly this:

```
You are a busy reader who has never seen this data. Read the report below once. Answer briefly:
1. What question is this report answering?
2. What is the answer?
3. What three things should you take away?
4. What would you do next because of it?
5. Was there any word, label or figure you could not work out, such that it got in the way of the answer? Say "none" if not.
6. Which section, if removed, would you not miss?
7. What did you expect to be told that was not there?
```

4. Compare with the brief in `README.md`:

| Reader's answer | Passes when |
| --- | --- |
| 1, 2 | Match the brief's Question and the storyline's Answer |
| 3, 4 | Meet the brief's Success and "How it will be used" |
| 5 | "None", or only terms that do not affect the answer |
| 6 | "None", or the section holds the only proof (chart, table or export) of something the answer states |
| 7 | Nothing the brief put in scope, including any "Things to test" row |

5. Fix what failed, at its source:

| Failure | Fix |
| --- | --- |
| Wrong or vague conclusion | Storyline order, a section's `QUESTION` or `NOTES`; rerun commentary |
| Did not understand a term | Rename it in the summary table, chart labels or `note` |
| Would not miss a section | Remove it from `REPORT`. First move any figure the answer states into another section's summary table |
| Expected something in scope | Add it to an existing section's summary table. New section only if the storyline needs a new claim |

6. Anything failed: rerun once, new subagent. Two reads at most. After the second: fix the labels and wording it flagged, do not read again, report what still fails at hand-over.
7. Browser available: open the report; check the charts drew and nothing overlaps.

## Record

`README.md`, "Cold read": the date, pass or fail per row above, what was changed.
