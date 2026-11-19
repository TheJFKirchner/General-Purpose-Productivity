---
name: commentary
description: Generated commentary for dashboards that need text across many filter scenarios or on each data refresh, or when the user asks for generated commentary. The commentary-generator subagent writes one commentary.json from small summary tables. Not a default step. Not for reports or decks; their authors write bullets from findings.
---

# Commentary

- For a dashboard that needs text across many filter scenarios or on each refresh, or when the user asks for generated commentary.
- Not a default step. Reports and decks do not use it: the author writes bullets directly from findings and results.
- Templated text ("cost was $X, up Y%") belongs in the dashboard code, not here.

## Steps

1. **Agree the units with the user.** One unit per section: an id (C1, C2 ...), the question it answers (one plain sentence, no numbers), a length. Attach it to the section whose data it describes: `commentary: 'C1'` in that section's meta (one line in its `.jsx`). A summary unit, if wanted, is written last from the other units' commentary.
2. **Agree the filters.** Per unit, pick the filters the commentary follows: one scenario per value, plus "all". For every other filter that reaches the section, either cover its values too or accept that the commentary hides when it is set, and tell the user which. A requested filter that does not reach the section: tell the user and write the "all" version only. More than about 50 scenarios per unit: narrow.
3. **Make the tables.** In the dashboard folder: `npm run tables -- --sections <id,id> --by <column,column>`. It writes a new file each run; use the name it prints. Never write your own script against the engine. The tables must answer the question, not just copy the chart: a trend question needs a comparison period (for example first half against first half).
4. **Gather the notes.** If the project map shows a findings file, copy the findings that bear on each unit (definitions, basis, causes) into its Notes. Note the dashboard's number format.
5. **Launch `commentary-generator` once** for all units and scenarios, with the brief below. Never write commentary in this conversation.
6. **Check and show.** No scripts: read the tables file by eye. Per unit, check every number in one item, plus every bullet that compares scenarios; each source names its cells. A unit the tables cannot answer is not shipped: add the comparison to the section's analytic, or change the question with the user. If there is a findings file, check no bullet contradicts a finding; regenerate any unit that does. Open the dashboard with a filter set and check the text shows. Show the user each unit; ask keep, edit or regenerate. Hand edits go straight into `commentary.json`.
7. **Update the map.** Append to the `dashboard/` row of the project map in `CLAUDE.md`: "Commentary: `dashboard/commentary.json`. C1 on <section title> (<id>), per <filter>; C2 on ..., all only; hides when <other filter> is set. Regenerate with the commentary skill."

Brief for the subagent:

```
Tables file: <the name npm run tables printed> (each scenario has its already_on_page)
Write to: <dashboard root>/commentary.json
Audience: <who reads it>          Tone: <optional line>
Unit C1, section <section id>: <question> | Length: <n bullets or one paragraph>
  Notes: <findings: definitions, basis, causes>
  Format: <as the dashboard shows it, for example $804.6K, 14.1%>
  Scenarios: all; region=East; region=West ...
  Context: <optional: the "all" scenario, only if comparisons across scenarios are wanted>
Unit C2, section ...
```

## The output: `commentary.json`

In the dashboard project's root folder. A JSON list, one item per unit per scenario:

| Field | What it is |
| --- | --- |
| `id` | `C1`, `C2` ... One per unit; every scenario of a unit shares it |
| `commentary` | List of strings, one per bullet |
| `source` | `<section id>, <filters>: <table or metric keys>; <computation>` |
| `filters` | Object of column: value for the filters the scenario sets to something other than All. Left out for "all" |

An item shows only when its `filters` equal the filters currently set (other than All) among those that reach its section. No `filters`: shown only when none is set. No match: nothing shown.

`commentary.json` stays as saved until regenerated on purpose.

## Each refresh

Read the current `commentary.json` first, then rerun steps 3 to 6 with its ids and filters (and step 7 if the units changed). Tell the user any headline that changed (largest, fastest, direction of change). To redo only some units, say so in the brief; the subagent keeps the rest. Never generated when someone views the dashboard.
