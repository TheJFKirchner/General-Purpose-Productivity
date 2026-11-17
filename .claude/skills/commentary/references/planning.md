# Planning commentary for a dashboard, deck or report

- Plan first, build second. Work through the questions with the user. Ask; never assume.
- The answers become `commentary_plan.md`, the source of truth for the deliverable.
- Analysis folders (the `analysis` skill): not needed. See `analysis.md`.

## Questions

**1. What is the deliverable?**
- Dashboard, deck or report? Who reads it, and what decisions does it support?
- Do the files exist yet (dashboard, `.pptx`, `.html`)? Where will they live?

**2. How does the data update?**
- Which tables feed it, and how often are they refreshed (daily, monthly, once)?
- Which column marks the snapshot (for example `paid_month`)? That is the "as-of".
- After a refresh, do older snapshots stay viewable? Then each snapshot needs its own commentary.
- Can past data be restated? (Commentary is left alone and flagged, not silently rewritten.)

**3. What filters does the reader have?**
- List every filter on the page.
- For each: must the commentary change when it changes? Those are **commentary filters**. The commentary ignores the rest; the page should say so.
- Count the combinations per snapshot (for example 3 platforms × 4 funding types = 12). Keep each group of commentary under 50.

**4. How is the commentary split into files?**
- Dashboards: one output file per snapshot. Every other commentary filter lives inside that snapshot's file.
- Decks and reports: one output file per run.

**5. When does commentary run, and who runs it?**
- Decks and reports: once, in a session, per edition.
- Dashboards: after each data refresh, on the user's machine (by hand or a local scheduler). Never when someone views the dashboard.

**6. What commentary goes where?**
- Each slide, section or panel with commentary is a **unit**. For each: where it sits, the question it answers (one plain sentence, no numbers), the tables behind it, its length.
- Comparisons and targets it mentions (vs last month, vs target) must be in its tables; otherwise the numbers cannot be checked.

**7. Grouping and audience**
- Units on one subject for one audience: written together (one writer call), so they read as a set.
- Executive summary needed? Written last, only from the other units' checked commentary.
- Should a unit see last period's commentary (to say "as flagged last month...")?

**8. Review and rules**
- Who reviews before it is shown? Are numbers the checker could not verify shown or hidden?
- When should commentary be regenerated on purpose (new data story, plan change)? Otherwise saved commentary stays as is.

## The plan: `commentary_plan.md`

- Write it beside the deliverable, in this outline. Get the user's OK, then build the shell from it (`shell.md`).
- Short: readable in two minutes.
- Worked examples: `examples/*/commentary_plan.md` in this skill folder.

```markdown
# Commentary plan: <deliverable>

## Deliverable
<type, audience, files, where it lives>

## Data and refresh
- Tables: <names, what each holds>
- Refresh: <how often, by what>
- Snapshot column: <column> (rule: latest value)
- History: <do older snapshots stay viewable?>

## Filters
| Filter | Commentary changes with it? | Values / count |
| --- | --- | --- |

## Output files
<one per run | one per snapshot, other filters inside>; about <n> commentary entries per snapshot

## When it runs
<in session per edition | after each refresh, by whom, how>

## Commentary units
| Unit | Where | Question it answers | Tables | Length | Group |
| --- | --- | --- | --- | --- | --- |

## Groups
| Group | Audience | Units | Notes (summary, uses last period, tone sample) |
| --- | --- | --- | --- |

## Review and rules
- Review: <who, when>
- Unverified numbers: <shown | hidden>
- Regenerate when: <...>

## Open questions
- <anything still to confirm>
```

Plan changes later: update `commentary_plan.md` first, then the shell.
