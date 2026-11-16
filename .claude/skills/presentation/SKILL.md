---
name: presentation
description: Build a slide presentation (reveal.js HTML with ECharts charts) from work that already exists (a project plan, an analysis folder, a dashboard, commentary). Interview-led, not automatic. Gathers context with subagents, agrees a brief (original goal, audience, what is in and out), workshops a storyboard, has a reviewer raise the questions the audience will ask, then builds the deck and walks through it with the user. Use for "make a presentation / deck / slides / readout on ...", or to change an existing presentation folder. Not for a .pptx file, and not for a written report (that is the analysis skill).
---

# Presentation

Existing work in, one HTML deck out. The work is usually an analysis or a dashboard whose visuals already exist: the user says which ones go in and which cut of each, and the deck hard-codes them. The user is interviewed at every gate; never build straight from a request.

Used with the **grilling** skill. Grilling says how to interview (rounds, numbered questions, a recommended answer for each, waiting). This skill says what has to be found out and settled. See "Interviews".

## The folder

Three files per presentation. Create nothing else.

```
presentations/<yyyy-mm-name>/
  plan.md             brief, in and out, sources, storyboard, questions, review notes   you write
  presentation.html   the slides (reveal.js)                                            scaffolded; you fill slides with Edit
  styles.css          the whole look: colours, fonts, sizes                             copied; edit only to restyle
```

- Sources (documents, charts, commentary) are pointed to from `plan.md`, never copied in.
- The tone document belongs to the user, not the presentation. `plan.md` records its path.

## Steps

In order. Gate = stop until the user approves.

| # | Step | Gate | Read |
| --- | --- | --- | --- |
| 1 | Find the facts: project plan, linked documents, where charts and commentary live. No questions to the user yet | | `references/context.md` |
| 2 | Grill for the brief: settle everything under "Interview 1" | **Gate 1:** user confirms the brief | "Interviews" below; `references/plan.md` for the audience and type tables |
| 3 | `node <skill>/scripts/create-presentation.js --plan-only --title "<title>" -o <folder>/presentation.html`. It copies the blank plan (`references/plan-template.md`). Write the brief and takeaways into `plan.md` | | |
| 4 | Draft the storyboard, one block per slide | | `references/plan.md`; `library/index.md`; `references/charts.md` (rules and "Which chart"); `references/writing.md` ("Commentary") |
| 5 | Hard questions: a read-only reviewer asks what this audience will ask. Then grill once on the storyboard and the questions: "Interview 2" | **Gate 2:** user confirms the storyboard | `references/questions.md` |
| 6 | Hand the build to a builder subagent: scaffold, fill each slide from its Pattern link, check. Then you do the writing pass on its screenshots | | See "Delegating". You read `references/writing.md` only |
| 7 | Walk through the deck with the user. Fix slide by slide | **Gate 3:** user signs off | `references/slides.md`, "Walk-through" |

Existing presentation folder: read its `plan.md` first. Changes go through the storyboard row, then the slide.

## Interviews

Run both interviews with the grilling skill. What follows is its subject matter: what to settle, which items are real questions, and where your recommended answer comes from.

How this skill shapes the grilling:

- **Facts are never asked.** The goal as first written, what was done, the numbers, where files live: step 1 finds them.
- **Draft first, then ask.** Rows marked Draft are things the files or the request already answer. Write them up as one drafted brief (or one drafted storyboard) and put the whole draft to the user as a single question: "anything to change?". Only rows marked Ask become questions of their own.
- **The frontier is the Ask rows only.** About 8 questions an interview, in 2 or 3 rounds. More than that: you are asking things you could have drafted.
- **Missing things first.** Open Interview 1 with one batch: everything step 1 could not find, each with "do you have this, or who does?". These are the answers that take the user longest to get.
- **Every Ask question carries a recommended answer**, worded so "yes" accepts it. No basis for one: say so; do not invent it.
- **Ask in plain words.** Describe a slide by what the audience sees, never by component code or pattern name.
- **The user's picks stand.** A visual, cut, slide or wording the user chose is used as chosen. Do not question it, offer alternatives to it, or ask them to justify it. Raise a concern only when the pick cannot work as asked (it will not fit a slide legibly, its numbers cannot be traced, it contradicts its own headline): once, in one line, with the fix you will apply unless they say otherwise.
- **Ask once.** An item the user accepted as open is recorded and not raised again in a later round or step. It is listed at the gate.
- **The session ends at the gate.** Every row settled or accepted as open, and the user confirms. Nothing is built before that.
- **The record is `plan.md`**, not a separate decisions file (this replaces the grilling skill's `Features/` record). Interview 1 fills Brief, Terms, Takeaways, In and Left out. Interview 2 fills Storyboard and Questions.
- Grilling skill not available: same content, in rounds of numbered questions with a recommended answer each.

### Interview 1: the brief (gate 1)

| Settle | What it is | Draft or Ask | Recommended answer from |
| --- | --- | --- | --- |
| Not found | Each thing step 1 could not find that the deck needs | Ask, first, as one batch | None. Ask who has it |
| Audience | Who is in the room, who is most senior, who is least expert, what each cares about | Ask | The request; who the project plan says it is for |
| What we want from them | A decision, approval, feedback, or awareness | Ask | The project plan's goal and success lines |
| Setting | Presented live, sent to be read, or both. Minutes available, as its own question | Ask | The request |
| Who presents | The user, or someone else whose voice the text should fit | Ask | The request |
| Tone document | A path, or none | Ask, once | None |
| Why this answer | For a recommendation: why this figure or option over the nearest alternative, and who can say | Ask | Often in no file |
| What it means for them | The effect in the audience's own terms (dollars, price, workload), with its base | Ask | The sources if they say |
| After the decision | Who does what by when once it is made | Ask, when we want a decision | Often in no file |
| Answer and takeaways | The one sentence, and two to four bullets the audience should leave with | Ask, after audience is settled | Findings ranked by what this audience cares about |
| Visuals to use | Which of the existing visuals go in the deck | Ask: step 1's list of visuals, your suggested picks marked, "which do you want?" | The takeaways each visual supports |
| The cut of each | For every chosen visual with a dropdown, filter or tab: the one setting to show, and the reason for that cut | Ask: one table (visual, cut, reason), your suggestion filled in | The cut that proves the takeaway it serves |
| Original goal, part of, how it was met | From the project plan | Draft | Step 1 |
| What they already know, type | From the audience and what we want | Draft | `references/plan.md`, audience and type tables |
| In, left out | Findings that prove the takeaways; work that does not serve the goal | Draft | Step 1's findings and its "off the goal" list |
| Terms | One name and one plain definition for each measure, and the sign convention | Draft | The sources; the least expert person's vocabulary |

### Interview 2: the storyboard (gate 2)

Draft the whole storyboard, then run the hard-questions reviewer (step 5) on it, then interview once with both in hand.

| Settle | What it is | Draft or Ask | Recommended answer from |
| --- | --- | --- | --- |
| The story | The headlines in order: do they tell it and reach the answer | Ask: the numbered list, "anything to change?" | Your draft |
| Cuts and merges | Among slides you added, not ones the user asked for: any that could go or combine | Ask, naming each candidate, one question | The audience and type tables; your view, stated |
| Real choices | A slide you added where two different treatments are both reasonable. Never for a visual the user picked | Ask, describing both in plain words | Your pick and why |
| How much commentary | Fuller or lighter, across the deck | Ask, one question | Audience and setting (`references/writing.md`, "Commentary") |
| Hard questions | The reviewer's questions as one table, each with your pick (answer on a slide, backup slide, say it, cannot answer yet, drop) | Ask: the table, "anything to change?" | `references/questions.md` |
| Hard questions the user can add to | Any where the user may know the answer, or who does | Ask, each on its own | None |
| Derived figures | Any figure you computed that is not in the sources, before it goes on a main slide | Ask, each on its own | State how it was computed |
| Open items | Present with these unanswered, or wait | Ask, once, at the end | State what is missing and who in the audience will care |
| Sections, each slide's pattern, what is on each page | Bottom-bar names, the library component, the visual and bullets | Draft | `library/index.md`; `references/plan.md` |

- A hard question that changes a main slide: change the draft, show the changed headlines once.
- Three or more hard questions unanswered on things this audience cares about: say plainly the work may not be ready, and recommend waiting or presenting as interim. Do not recommend simply going ahead.

## References

| File | Holds | Origin |
| --- | --- | --- |
| `references/context.md` | Step 1: what to find, the subagent brief | Ours |
| `references/plan.md` | Steps 2 and 4: interview, audience and type tables, storyboard rules | Ours |
| `references/questions.md` | Step 5: the reviewer's brief, sorting the answers | Ours |
| `references/writing.md` | Slide text rules, tone document | Ours, rules from humanizer |
| `references/slides.md` | For the builder: scaffold, slide HTML, using patterns, bottom bar, look, checks. Also the walk-through | revealjs-skill, adapted |
| `references/charts.md` | Chart rules, ECharts patterns, sizing | revealjs-skill, moved to ECharts |
| `references/advanced-features.md` | Fragments, notes, backgrounds, transitions. Only when asked | revealjs-skill |
| `references/base-styles.css` | The theme each deck's `styles.css` is copied from | revealjs-skill, adapted |
| `references/plan-template.md` | Blank `plan.md` | Ours |
| `library/index.md` | The slide library's index: every component by purpose, with its code, what it looks like, what it is good for, and related components. Generated | Ours |
| `references/new-component.md` | Adding a component to the library: what it must include, its structure, rebuilding the index. Only when asked | Ours |
| `library/<purpose>/slides.html` | The sample slides themselves. For the builder | Ours |
| `library/index.html` | The same index as a page, for the user to browse | Ours |

## Do not read

| File | Read only when |
| --- | --- |
| `library/<purpose>/slides.html` | Never, in the main conversation. You plan from `library/index.md`; the builder subagent opens the slides the plan links to |
| `references/slides.md` above "Walk-through", `references/advanced-features.md` | Never, in the main conversation. They are the builder's |
| `presentation.html` below `<!-- SLIDES:END -->` | Never. It is the engine |
| `styles.css` below the `:root` block | Adding a class for a repeated pattern |
| `scripts/*.js` | A script fails |

## Delegating

| Step handed over | Give the subagent | You read |
| --- | --- | --- |
| Read source documents | The brief in `references/context.md` | `references/context.md` |
| Hard questions | The brief in `references/questions.md`, the path to `plan.md` | `references/questions.md` |
| Build the deck (always handed over) | The path to `plan.md`; `references/slides.md`, `references/charts.md`, `references/writing.md`; the skill folder's full path (Pattern links are relative to it); tell it to follow each block's Pattern link, take every number from the block's Source, screenshot and look at every slide, and return: slide ids, anything that did not fit its pattern, anything it could not source, the screenshot folder | Nothing. Then look at the screenshots |
| Change slides after the walk-through | The slide ids, the change, the same three references | Nothing |

Always yours (you hold the gates): the interview, the storyboard, the walk-through. One-line wording fixes to a slide you may make yourself by its id.

## Rules

- Before gate 1: look only. Create nothing.
- No HTML before gate 2.
- Present the goal and how it was met, not everything that was done. Work that does not serve the goal goes under "Left out" in `plan.md`, one line each.
- The audience decides depth. Cut background the audience already has.
- Every slide makes one point, stated in its headline. A slide with no point is cut.
- A visual shows one metric or one relationship and proves its slide's headline. No exploratory charts.
- Every visual is one fixed cut, hard-coded, chosen for a stated reason. No dropdowns, filters, tabs, toggles, tooltips or links to a live dashboard on a slide.
- Every number on a slide traces to a source listed in `plan.md`.
- Text follows `references/writing.md`; the user's tone document overrides it.
- Colours and fonts live only in `styles.css`. Slides and chart JSON use its variables, never their own colours.
- Every storyboard block links to its pattern in the library. Planning reads the index only; the builder reads the linked slides.
- Slides are filled and changed with Edit, one at a time, by id. Never rewrite `presentation.html` whole.

## Needs

- Node.js, for the scripts.
- Internet when a deck is opened: reveal.js and ECharts load from a CDN.
- Edge or Chrome, for `screenshot.js`.
- Optional: `puppeteer` for `check-overflow.js`.

Deck structure, scripts and references adapted from github.com/ryanbbrown/revealjs-skill (MIT, see `LICENSE-revealjs-skill`).
