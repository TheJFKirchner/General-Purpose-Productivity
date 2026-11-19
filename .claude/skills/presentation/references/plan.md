# Full mode, steps 2 and 4: the brief and the storyboard

Both live in `plan.md`. Both are agreed with the user, not written for them.

- What to settle with the user, and in what order: `references/full-mode.md`, "Interviews". How to ask: the grilling skill.
- This page holds the tables those interviews draw on, and the storyboard format.

## The brief (step 2)

- Each row of Interview 1 becomes a line of the Brief table in `plan.md`. Takeaways, In and Left out are bulleted lists under it.
- A line the sources cannot fill and the user cannot answer is recorded as an open item, not guessed.

**Gate 1:** show the filled brief. User confirms. Then create the folder and write it into `plan.md`.

## Audience sets the depth

| Audience | Background | Method and data | Results | Close with |
| --- | --- | --- | --- | --- |
| Executives | None, or one slide | One line, if any | Most of the deck; takeaways first | The decision or the ask |
| Data science partners | Short | Data used, validation, method flow, limits | With caveats and sample sizes | Open questions |
| Business partners | Enough to follow | Light: one method slide | What changed and what it means for them | What changes for them, and when |
| Own team | None | As needed | Yes | Who does what next |
| Decision committee | None; they set the question | One line, plus what was checked | The answer first, then the proof | The decision, with owner and date |

Mixed room: build for the most senior person; put the rest in the appendix. Every term must still be understood by the least expert person in the room: define it on first use, in a bullet or the footnote.

## Type sets the shape

| Type | Slides | Shape |
| --- | --- | --- |
| Quick update | 3 to 5 | Answer, the one or two proofs, next step. No background, no agenda |
| Results readout | 8 to 12 | Goal, approach (short), findings, takeaways, next steps |
| Method review | 8 to 14 | Goal, data and validation, method, results, limits, open questions |
| Proposal | 6 to 10 | Problem, what we propose, evidence, cost and risk, the ask |

- Presented live: about one slide per one to two minutes.
- Asking for a decision: the answer comes first, whatever the type's shape says. Keep a third of the time for discussion.
- State the answer at the open and at the close. Not on every slide between.
- Leave these out unless the user wants them: the goal slide when the audience set the question themselves; the agenda under 10 slides; a takeaways slide under 10 slides when the closing ask already restates the answer; a method or data slide for a decision audience (make it a backup).
- Sent to be read: sub lines and captions carry more; still one point per slide.

## Storyboard (step 4)

One block per slide, in `plan.md`. Every line is required; a slide that cannot fill them is not ready.

```
### 4. Churn fell from 5.1% to 3.1% after launch

- Section: Results
- Pattern: CH-02 (a design library id; `add-slide.js --pattern CH-02`) (no library: a layout name, such as `chart-commentary`)
- Showing: monthly early churn for customers on the new and old onboarding, April to October
- Purpose: the main proof that the change worked. Serves takeaway 1
- On the page: line chart, new onboarding highlighted, launch marked; the October figure called out; 3 commentary bullets (when the drop started, that it held, what the old group did)
- Visual from: analysis report, "Churn by month" chart
- Cut: onboarding = new and old; region = all; April to October. Reason: shows the gap opening after launch
- Footnote: what is measured, the period, the source, in the audience's words
- Source: finding 3; `reports/churn`, `python run.py data churn_by_month by_month`
```

| Line | Holds |
| --- | --- |
| Heading | The headline: the slide's point as a full sentence. Not a topic |
| Section | 3 to 5 across the deck, two words at most (they show in the bottom bar) |
| Pattern | With a design library: the code and link of the component this slide follows, from its `index.md`, chosen by its "Good for" lines, not by subject. Without one: a layout from `references/slides.md` |
| Showing | What the audience sees, in plain words |
| Purpose | What the slide does for the story, and which takeaway it serves |
| On the page | The visual (kind, exact metric, highlighted item) or "no visual"; how many commentary bullets and what each covers; numbers called out. Rules: `references/charts.md` |
| Visual from | The existing visual this slide rebuilds, by the name the user knows it by. "New" when you designed it; "none" for no visual |
| Cut | The one setting of every dropdown, filter and tab, and the reason for that cut. The user's choice from Interview 1 |
| Footnote | The slide's one-line source note: what is measured, the period, where it is from. Any term not yet defined is defined here |
| Source | Where the numbers or the text come from. Existing commentary: its file and id |

Rules:

- Read the headlines top to bottom. They must tell the story and reach the brief's Answer.
- Every takeaway is served by at least one slide. Every slide's Purpose names a takeaway, or says what it sets up. Neither: cut the slide.
- Commentary: most slides with a visual carry 2 to 4 bullets that talk the audience through it. How much depends on the audience and setting (`references/writing.md`, "Commentary").
- Slides can run as a sequence (claim, proof, what it means). Say so in Purpose; do not force each slide to stand alone.
- Every visual the user picked has a slide, at the cut they chose. Their picks are not reopened in the storyboard.
- Each "In" finding has a slide. Nothing under "Left out" has one, except a backup slide the questions step adds.
- Title slide: its headline is the answer when we ask for a decision, otherwise the subject.
- The recommendation slide gives the reason for the chosen figure or option over the nearest alternative, on the slide. No reason in the brief (an accepted open item): the slide carries a visible "reason to be confirmed by <who>" line, and it is listed at gate 2. Never invent the reason.
- A figure you derived that is not in the sources goes on a main slide only after the user agrees it in Interview 2, and the story is reconciled with it.
- A closing ask with no owner or date and nothing new merges into the slide that states the effect.
- A table and a chart on one slide never show the same numbers.
- A slide that states an effect (points of rate, dollars, days) gives its base or a worked example, and what it means for this audience.
- Cut what the audience table says this audience does not need.
- Detail someone may ask for goes to the appendix, after the closing slide.

Choosing patterns: read the library's `index.md` only. Do not open its slide files; the builder subagent does that. Do not use the same pattern on more than two slides running. Check a component's Related codes before settling. Nothing fits: say so to the user and agree the nearest, or agree to add one (`new-component.md` in the design library).

Draft every block, then run Interview 2 (`references/full-mode.md`, "Interviews"): the headlines as a numbered list first, then the slides by section. Run step 5 (`references/questions.md`) once the story is settled, so its questions join the same interview. Then gate 2.
