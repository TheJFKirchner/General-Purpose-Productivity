# Full mode, step 5: hard questions

Before gate 2, a reviewer who has seen nothing but `plan.md` asks what this audience will ask. Cheaper to fix a storyboard than a deck.

## Who asks

- A read-only subagent on the strongest model available (Opus). It gets the path to `plan.md` and nothing else: not the conversation, not the sources.
- It takes the seat of the most senior person in the brief's Audience line.

## Brief for the reviewer

```
Read [path to plan.md]. Read-only; write nothing. Read no other file.

You are [audience role from the brief]. You care about [what they care about, from the brief]. You will sit
through this presentation. It is part of [the "Part of" line]. You did not do the work and you are short of time.

From the brief and the storyboard, write the 10 questions you would ask. Think about:
- Business impact: what this is worth, what it costs, who is affected, what changes because of it.
- The original goal: was it met, by how much, and how do we know.
- The wider project or initiative: what this means for it, what it unblocks or puts at risk, what happens next.
- What your own expertise makes you doubt: the comparison, the period, the data, what was left out.
- What you would have to decide or defend to your own boss after this meeting.

Do not ask about slide design or wording.

Return a table, hardest first:
| # | Question, in your own voice | Why you ask it | Slide that prompts it | Does the storyboard answer it? (yes / partly / no) |
Then one line: the single question most likely to derail the meeting.
```

## Sort the answers with the user

The questions join Interview 2 (`references/full-mode.md`, "Interviews") as one table with your recommended pick for each, put to the user once. Ask a question on its own only where the user may know the answer or who has it. For each question, the pick is one of:

| Decision | What changes |
| --- | --- |
| Answer on a slide | Add or change a storyboard row |
| Backup slide | Add an appendix block (pattern BK-01, the library's answer-with-bars slide; no library: `chart-commentary` with the question as the kicker) |
| Say it | Add to that slide's speaker notes. Deck also circulated or sent to be read: the answer must be on the slide too (a bullet or the footnote); notes alone do not reach a reader |
| Cannot answer yet | Record under "Open questions"; the user decides whether to present before it is answered |
| Not relevant | Drop it; no record |

- Record the kept questions and their decisions in `plan.md`, "Questions".
- Three backup slides at most. More than that: the storyboard is missing something; fix the main story.
- Three or more "cannot answer yet" on things this audience cares about: say plainly that the work may not be ready to present. The user decides.
- A question that exposes a gap in the main story (why this figure, what it costs, what happens next) changes a main slide, not the appendix.
- "Already answered: yes" questions need nothing.

Then gate 2: the user approves the storyboard with these changes in it.

## Running it again

Only when the user asks, after the deck is built. Same brief, but give the reviewer `presentation.html` to read between `<!-- SLIDES:START -->` and `<!-- SLIDES:END -->`. New questions go through the same table.
