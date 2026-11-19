# Writing slide text

Full mode. Slides should read the way the presenter talks. Apply at step 6 (build) and again before gate 3. Quick mode uses the short list in `references/slides.md`, "Text".

Order of authority: the user's tone document, then this page.

## Tone document (optional)

- A file the user gives once: past slide text, how they tell a story, phrases they use or avoid.
- Ask for it in the interview (step 2). None given: use this page alone. Do not ask again.
- Match its sentence length, punctuation, and how blunt or warm it is. Where it conflicts with a rule below, it wins.
- Record its path in `plan.md` under Brief. Never copy it into the presentation folder.

## What each piece of text does

| Text | Job | Limit |
| --- | --- | --- |
| Headline | States the finding or the point as a full sentence | 2 lines |
| Kicker (small label above) | The section name, exactly as in the bottom bar | 3 words |
| Sub line | The one fact that supports the headline | 1 sentence |
| Commentary bullet | Talks the audience through the visual: what to look at, what it means, why it matters | 2 to 4 per slide, about 18 words each. Do not split one thought into two bullets to meet the count |
| Other bullet | One fact or one action each | 4 per slide, 12 words each |
| Chart caption | What the chart proves, with the number | 1 sentence |
| Source line | Where the numbers came from, and the period | 1 line |
| Takeaway | What the audience should remember or do | 3 per slide |
| Speaker notes | What to say that is not on the slide | Short |

- Read the headlines in order with nothing else. They must tell the whole story.
- One name per thing across the deck, taken from the Terms table in `plan.md` ("loss per unit" everywhere, not "costs" on one slide). One sign convention: "+6.0%" everywhere or "6.0%" everywhere.
- One figure for one thing. Do not show "about 6%", 6.1% and 6.0% as if they were the same number; say which is the fit and which is the selection.
- Terms the least expert person in the audience would not know are defined on first use.
- An effect figure has a base or a worked example, with the arithmetic checked: "multiplies the indication by 1.029: an indicated +8.0% becomes about +11.1%".
- Reword a headline whose last line is a single word. After any rewording, say the headline aloud: it must still sound like speech ("The latest two years show no speeding up", not "At 5.7%, the latest 8 quarters show no speeding up").
- Every number has a unit, a period, and something to compare it to.
- Reader does not know the data: no column names, codes, or unexplained abbreviations.

## Commentary

The slides should talk the audience through the story, not leave them to read a chart alone.

- A slide with a visual carries commentary bullets beside or under it, unless a single number says it all.
- Order: what to look at, what it means, why it matters to this audience. The last can be a bold "so what" line.
- Each bullet points at something the audience can see in the visual, in the visual's words, and says what it means. Pointing alone is not enough: a bullet that only repeats the headline, a label, or a table cell is cut.
- One bullet deals with what a sceptic would spot first: the flat stretch, the outlier, the short period.
- Figures in a bullet are ones the visual shows, or are derived from them (a difference, a ratio). A figure that is not on the visual goes on the visual, in the footnote, or out.
- The biggest movement the visual shows gets a bullet, even when it is not the headline's subject. Otherwise drop that row from the visual.
- A bullet never argues against the slide's own headline without resolving it.

| Setting | Commentary |
| --- | --- |
| Sent to be read, or a mixed room | Fuller: 3 to 4 bullets on most slides |
| Presented live to executives | Lighter: 1 to 2 bullets; the rest in speaker notes |
| Method review with technical partners | 3 to 4 bullets, including the caveat or sample size |
| Title, divider, statement, big number | None |

## Rules

Strong: fix on one sighting.

| # | Do not | Before | After |
| --- | --- | --- | --- |
| 1 | Headline that names a topic or a mood | "Customer churn overview" / "A milestone moment for growth" | "Churn fell from 5.1% to 3.1% after the onboarding change" |
| 2 | Caption that describes the chart | "This chart shows retention by region" | "West kept 91% of new customers, 7 points above any other region" |
| 3 | Deny a claim nobody made | "It's not just a revenue story, it's a retention story" | "Retention drove most of the Q3 growth" |
| 4 | Closing one-liner that repeats the point | "Churn fell 2 points. That's the real win." | "Churn fell 2 points." |
| 5 | Saying that sounds deep | "Data is the currency of good decisions" | "Managers who review pipeline weekly close 12% more deals" |
| 6 | Lead-in before the point | "Here's what we found:" / "Let's dive in" | Start with the finding |
| 7 | Three items because three sounds complete | "Faster reporting, deeper insights, greater agility" | "Reports now refresh daily instead of monthly" |
| 8 | Filler words: robust, pivotal, leverage, landscape, seamless, unlock, key, crucial, showcase, underscore | "A robust pipeline underscores a pivotal shift" | "Pipeline grew 40%, mostly in enterprise" |
| 9 | Dressed-up verbs for is, are, has | "The dashboard serves as a single source" | "The dashboard is the single source" |
| 10 | Unnamed authority | "Experts agree the market is shifting" | "Subscriptions were 46% of sales, up from 31% (sales data)" |
| 11 | Repeat the headline as the first bullet | Headline "Churn"; bullet "Churn fell this quarter" | Bullet adds a new fact |
| 12 | Vague cause: "driven by", "linked to", "plays a role" | "Growth was driven by several factors" | "Two thirds of the growth came from renewals" |

Weak: fix when two or more appear on the same slide.

| # | Do not | Fix |
| --- | --- | --- |
| 13 | Bold label before every bullet ("**Sales:** up 5%") | Plain sentence, or a table |
| 14 | Title Case In Headlines, emoji, arrows as decoration | Sentence case, no decoration |
| 15 | Dashes joining clauses | Comma, colon, or two sentences |
| 16 | Stacked hedges ("may potentially suggest") | One hedge, and say why ("the test covered two regions") |
| 17 | Every bullet opening with the same word | Merge, or vary the subject |
| 18 | Passive with no owner ("it was decided") | Name who did it |

## Check before gate 3

1. Headlines alone tell the story. Kickers match the bar's section names.
1. Deck circulated or sent to be read: every slide makes sense with the speaker notes hidden.
2. Search the deck for each strong rule. Fix every hit.
3. No number, name, or date changed by the rewrite. Compare against `plan.md` sources.
4. Read each slide aloud in the presenter's voice. Anything they would not say: rewrite.

Rules adapted from the humanizer skill (github.com/blader/humanizer, MIT).
