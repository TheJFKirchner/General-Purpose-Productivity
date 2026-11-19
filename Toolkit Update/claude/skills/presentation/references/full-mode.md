# Full mode

For a real readout: interview-led, with a hard-questions reviewer and a builder subagent. The user is interviewed at every gate; never build straight from the request. Used with the **grilling** skill: grilling says how to interview (rounds, numbered questions, a recommended answer each, waiting); this page says what has to be settled.

## Steps

In order. Gate = stop until the user approves.

| # | Step | Gate | Read |
| --- | --- | --- | --- |
| 1 | Find the facts. No questions yet | | "Step 1: facts" below |
| 2 | Interview 1: settle the brief | **Gate 1:** user confirms the brief | "Interviews" below; `references/plan.md` (audience and type tables) |
| 3 | `node <skill>/scripts/create-presentation.js --plan-only --title "<title>" -o <deck>/presentation.html`. Write the brief into `plan.md`; add the deck's map row (`SKILL.md`, "Where the deck goes") | | |
| 4 | Draft the storyboard, one block per slide | | `references/plan.md`; the library's `index.md` if there is one; `references/charts.md` ("Which chart"); `references/writing.md` ("Commentary") |
| 5 | Hard questions from a read-only reviewer, then Interview 2 on the storyboard and the questions | **Gate 2:** user confirms the storyboard | `references/questions.md` |
| 6 | Builder subagent builds and checks. Then you do the writing pass on its screenshots | | "Delegating"; you read `references/writing.md` only |
| 7 | Walk through the deck with the user, fixing slide by slide | **Gate 3:** user signs off | "Walk-through" below |

- Before gate 1: look only, create nothing. No HTML before gate 2.
- Existing deck with a `plan.md`: read it first. Changes go through the storyboard block, then the slide.

## Step 1: facts

Know what the work set out to do, what it did, and where the evidence lives, before asking anything.

| Look for | Usually in |
| --- | --- |
| Findings already collected | `findings.md` from the map: each row has its plan item and source. Read it yourself, first |
| Original goal, as first written; who it is for | The project plan from the map, the request |
| Results, with numbers | Findings, analysis report output, dashboard summary tables |
| Visuals that already exist | The analysis report, dashboard pages, and the analytic or table behind each |
| Commentary that already exists | A dashboard's `commentary.json` (id, commentary, source) |

- Small project (five files or fewer, each under about 200 lines): read them yourself. Larger: one read-only subagent per document or folder, four at most, in parallel; you read only their returns. Never send data files to a subagent; note the path.
- Existing commentary is checked against the numbers before reuse. A line the figures do not support: correct it and tell the user.

Subagent brief (fill the brackets):

```
Read [paths]. Read-only; write nothing. I am preparing a presentation about this work. Return, in under 300 words:
1. Original goal: quote the line that states it, with file and line. 2. How success was to be judged, if stated.
3. What was done, in 3 to 5 steps. 4. Results: each finding as one sentence with its number and the file it is in.
5. Visuals that exist: name, where, what it shows, any dropdown, filter or tab and its options, where its table lives.
6. Commentary that exists: path, how many items. 7. Anything unfinished, assumed or disputed.
8. Linked documents that look important, unread. Do not interpret beyond the text. Say "not stated" where it is not.
```

Then tell the user, in the conversation (save nothing): goal as first written; how it was met; 3 to 5 findings with numbers; work off the goal (candidates to leave out); visuals available, with their filters; sources found; not found.

## Interviews

- **Facts are never asked.** Step 1 finds them.
- **Draft first, then ask.** Rows marked Draft go to the user as one drafted brief (or storyboard): "anything to change?". Only Ask rows become questions. About 8 questions an interview, in 2 or 3 rounds.
- **Missing things first.** Open Interview 1 with one batch: everything step 1 could not find, each with "do you have this, or who does?".
- **Every Ask question carries a recommended answer**, worded so "yes" accepts it. No basis for one: say so.
- **Plain words.** Describe a slide by what the audience sees, never by component code.
- **The user's picks stand.** Raise a concern once, in one line with your fix, only when a pick cannot work as asked.
- **Ask once.** An item accepted as open is recorded, not raised again, and listed at the gate.
- **The record is `plan.md`.** Interview 1 fills Brief, Terms, Takeaways, In, Left out. Interview 2 fills Storyboard and Questions.

### Interview 1: the brief (gate 1)

| Settle | Draft or Ask | Recommended answer from |
| --- | --- | --- |
| Not found: what step 1 could not find | Ask, first, as one batch | None. Ask who has it |
| Audience: who is in the room, most senior, least expert, what each cares about | Ask | The request; the project plan |
| What we want from them: decision, approval, feedback, awareness | Ask | The plan's goal and success lines |
| Setting: live, sent to be read, or both. Minutes, as its own question | Ask | The request |
| Who presents, and whose voice the text fits | Ask | The request |
| Tone document: a path, or none | Ask, once | None |
| Why this answer: for a recommendation, why this over the nearest alternative | Ask | Often in no file |
| What it means for them, in their terms, with its base | Ask | The sources |
| After the decision: who does what by when | Ask, when we want a decision | Often in no file |
| Answer and takeaways: one sentence, two to four bullets | Ask, after audience | Findings ranked by what this audience cares about |
| Visuals to use | Ask: step 1's list, your picks marked | The takeaways each supports |
| The cut of each: the one setting of every filter, and why | Ask: one table (visual, cut, reason) | The cut that proves its takeaway |
| Original goal, part of, how it was met | Draft | Step 1 |
| What they already know, type | Draft | `references/plan.md` tables |
| In, left out | Draft | Step 1's findings and "off the goal" list |
| Terms: one name and plain definition per measure; sign convention | Draft | The sources; the least expert person's words |

### Interview 2: the storyboard (gate 2)

Draft the whole storyboard, run the reviewer (step 5), then interview once with both in hand.

| Settle | Draft or Ask | Recommended answer from |
| --- | --- | --- |
| The story: the headlines in order | Ask: numbered list, "anything to change?" | Your draft |
| Cuts and merges among slides you added (not the user's) | Ask, naming each, one question | Audience and type tables |
| Real choices: two reasonable treatments of a slide you added | Ask, both in plain words | Your pick and why |
| How much commentary, across the deck | Ask, one question | `references/writing.md`, "Commentary" |
| Hard questions: the reviewer's, each with your pick | Ask: the table | `references/questions.md` |
| Hard questions the user may know the answer to | Ask, each on its own | None |
| Derived figures not in the sources, before a main slide | Ask, each on its own | How it was computed |
| Open items: present with them unanswered, or wait | Ask, once, at the end | What is missing, who will care |
| Sections, each slide's pattern, what is on each page | Draft | The layouts or the library index; `references/plan.md` |

- A hard question that changes a main slide: change the draft, show the changed headlines once.
- Three or more unanswered hard questions this audience cares about: say plainly the work may not be ready; recommend waiting or presenting as interim.

## Delegating

| Step handed over | Give the subagent | You read |
| --- | --- | --- |
| Read source documents | The step 1 brief above | Its return |
| Hard questions | The brief in `references/questions.md`, the path to `plan.md` | `references/questions.md` |
| Build the deck (always) | The path to `plan.md`; `references/slides.md`, `references/charts.md`, `references/writing.md`; the skill folder's full path; the design library path, if any. Tell it: fill the `<!-- BRIEF -->` comment from the plan's brief and storyboard headlines, follow each block's Pattern link, take every number from the block's Source, screenshot and look at every slide, and return slide ids, anything that did not fit its pattern, anything it could not source, the screenshot folder | Nothing. Then look at the screenshots |
| Change slides after the walk-through | The slide ids, the change, the same three references | Nothing |

Always yours: the interviews, the storyboard, the gates, the walk-through. One-line wording fixes you may make yourself by slide id.

Do not read in the main conversation: library slide files (the builder opens the linked ones), `references/slides.md` (the builder's), anything below `<!-- SLIDES:END -->`, the scripts unless one fails.

## Rules that apply only here

- Present the goal and how it was met, not everything that was done. Work off the goal goes under "Left out", one line each.
- The audience decides depth. Every slide's Purpose names a takeaway or what it sets up; neither, cut it.
- Text follows `references/writing.md`; the user's tone document overrides it.

## Walk-through (step 7)

1. Give the user the path to `presentation.html`. Keys: arrows or space, F full screen, S speaker view, Esc overview.
2. Go section by section. Ask what is wrong, missing, or does not sound like them.
3. Fix slide by slide. A change that alters the story also changes its storyboard block; note it under "Review notes".
4. Offer the browser editor for wording: `node <skill>/scripts/edit-html.js <deck>/presentation.html`. Click text to edit, Save, Ctrl+C to stop.
5. PDF: open `presentation.html?print-pdf` and print to PDF.

**Gate 3:** the user says it is ready.
