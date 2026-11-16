# Step 1: gather context

Goal: know what the work set out to do, what it did, and where the evidence lives, before asking the user anything.

## What to look for

| Look for | Usually found in |
| --- | --- |
| Original goal, as first written | Project plan, request brief, an analysis folder's `README.md` |
| What was done | Plan status, analysis `sections/`, hand-over notes |
| Results, with numbers | Report output, commentary files, dashboard summary tables |
| Visuals that already exist | Analysis `output/` report and its section tables; dashboard pages and the tables behind them |
| Commentary that already exists | `commentary/` JSON files (id, commentary, source) |
| Who it was for, and what it feeds | Project plan, the request |

- Start from what the user named. Project plan not named: ask for its path in one line.
- Follow links from the plan one level. Do not survey the whole project.
- Existing commentary is checked against the numbers before it is reused. A line the figures do not support ("more than twice" when it is 1.8 times): correct it on the slide and tell the user.

## How

- Small project (five files or fewer, each under about 200 lines): read them yourself. No subagents.
- Larger: you do not read the documents. Subagents do; one per document or folder, four at most, in parallel.
- Data files (CSV, query results): never sent to a subagent to summarise. Note the path and what it holds.
- Later, at steps 4 and 6, you may read the specific table or lines whose numbers go on a slide.
- You read only their returns.

Subagent brief (fill the brackets):

```
Read [paths]. Read-only; write nothing.
I am preparing a presentation about this work. Return, in under 300 words:
1. Original goal: quote the line that states it, with file and line.
2. How success was to be judged, if stated.
3. What was done: the approach in 3 to 5 steps.
4. Results: each finding as one sentence with its number, and the file the number is in.
5. Visuals that exist: for each, its name, where it is, what it shows, any dropdown, filter or tab it has and the options, and where the table behind it lives.
6. Commentary that exists: path, and how many items.
7. Anything unfinished, assumed, or disputed.
8. Documents this one links to that look important, unread.
Do not interpret beyond the text. Say "not stated" where it is not.
```

## Then

Tell the user, in the conversation, in this shape. Save nothing.

| | |
| --- | --- |
| Goal as first written | ... |
| How it was met | ... |
| What came out | 3 to 5 findings with numbers |
| Also done, off the goal | candidates to leave out |
| Visuals available | each existing visual: what it shows, its dropdowns or filters, where its data is |
| Sources found | documents and commentary: path each |
| Not found | what is missing |

This table is where Interview 1's recommended answers come from (`SKILL.md`, "Interviews"). Go to step 2.
