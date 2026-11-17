# Building the commentary shell

`commentary_shell.json`: one per deliverable, beside it.

- It is `commentary_plan.md` in the form the scripts read: every piece of commentary, where it sits, what it must answer, which tables it may use, its length.
- Never holds commentary. Each run saves a copy with the commentary written in (`running.md`).
- Build only from the agreed plan (`planning.md`). Not settled by the plan: ask.
- Exception: analysis folders (the `analysis` skill). Their shell is generated (`analysis.md`).
- Plan changes: update the plan first, then the shell.

## 1. Steps

1. **Placements.** Every slide, report section or dashboard panel in the plan's units table. Put `{{commentary:C1}}` exactly where the text goes.
2. **One unit per placement.** `id`: `C1`, `C2`, `C3` ... in the order units are first written. Never changes, never reused: a new unit takes the next number; a removed unit's number stays retired. The history hangs on it. (Older shells with word ids still run.)
3. **`covers`**: the plan's "question it answers" (section 2).
4. **Tables.** The aggregated tables behind that placement's visuals, the same files the visuals use. CSV or Parquet, inside the deliverable's `data/` folder, at most 50 rows and 15 columns each. Too big: aggregate upstream (top N plus "other"); nothing is ever truncated.
5. **`style`** from the plan's length (section 3).
6. **Generators** from the plan's groups (section 4).
7. **Dashboards only:** `as_of` from the snapshot column, and `dimensions` on every generator from the commentary filters (section 5).
8. **Check:** `validate_shell.py <shell>`, then `status.py <shell>`. Fix every SHELL and UNIT line before generating.

## 2. Writing the `covers` line

The question the reader needs answered at that placement, in plain words.

| Weak | Strong |
| --- | --- |
| "Commentary on costs" | "Which diagnosis categories drove the month-over-month change" |
| "Explain the chart" | "Whether the increase is price or volume, by care setting" |
| "Cost rose 4.2% because of circulatory" (dictates the answer) | "What drove the change in October diagnosis cost" |
| "How we did against the 4-hour SLA" (target not in any table) | Same, with the target added as a column or a small targets table |

- Tie it to what is on the page at that placement. Ask nothing the unit's tables cannot show.
- Name the comparison (vs last month, vs prior year, vs target). It must be in the tables: a figure only in the covers line cannot be verified and comes back flagged.
- Never write the answer or a number into it. Validation rejects lines with fill-in slots (`{slot}`, `%s`, `<slot>`, `[SLOT]`): those are templates and belong in code.

## 3. Style

| Placement | Typical style |
| --- | --- |
| Slide body | `{"format": "bullets", "bullets": 3, "max_words": 25}` |
| Small slide panel, dashboard card | `{"format": "bullets", "bullets": 2, "max_words": 20}` |
| Narrative report section | `{"format": "paragraph", "bullets": 1, "max_words": 70}` |

`bullets` is a maximum: fewer when the data supports fewer points, never more. No bullet over `max_words`.

## 4. Generators

Generator = one writer call (one per filter combination on dashboards). Its units are written together and see each other's tables.

- One subject, one audience → one generator (for example four diagnosis slides).
- At most 12 distinct tables across a generator's units. More: split it.
- Executive summary: its own generator with `"inputs": "commentary"`, units with `"tables": []`. Runs last; reads only the other units' verified commentary.

| Field | Notes |
| --- | --- |
| `audience` | Required. Who reads it, e.g. "finance leadership" |
| `samples` | Optional tone samples, at most 3 files of about 150 words. Tone only; never reused |
| `use_prior` | Optional. Gives the writer last period's commentary for the same unit. Dashboards: the previous snapshot. Decks/reports also need `prior_file`: the last edition's output file or its `commentary_outputs` folder (newest file is used) |
| `dimensions` | Dashboards: required, explicit (`[]` for one commentary per snapshot) |
| `combinations` | Dashboards, optional: explicit allowed list instead of every combination in the data |
| `model` | Optional override of the default writer model |
| `inputs` | `"commentary"` for a summary generator |

## 5. Dashboards

- `as_of`: `{"table": "<table>", "field": "<column>", "rule": "max"}`: where the snapshot is read from. Never the run date. Each snapshot gets its own output files.
- `dimensions` per generator: only the plan's commentary filters. Other dashboard filters are ignored; say so on the dashboard.
- Each dimension must be a column in every table of that generator.
- Snapshot as a dimension (so each period keeps its own commentary): name it the same as `as_of.field`, or set `as_of.dimension`. It is pinned to the as-of at each refresh, and tables keep history up to the as-of so trends still work.
- Keep combinations per generator under 50; the run stops a generator above that and reports it.
- No `deliverable_files` needed: the dashboard looks commentary up at run time.

## 6. Field reference

```json
{
  "deliverable": "q3_cost_review",
  "medium": "deck",
  "deliverable_files": ["cost_review.pptx"],
  "data_dir": "data",
  "as_of": null,
  "show_unverified": false,
  "generators": {
    "1": {"audience": "finance leadership", "samples": ["samples/exec_tone.txt"]},
    "2": {"audience": "executive committee", "inputs": "commentary"}
  },
  "units": [
    {"id": "dx_category", "generator": 1, "placement": "slide 3",
     "covers": "which diagnosis categories drove the month-over-month change",
     "tables": ["data/dx_by_category.csv"],
     "style": {"format": "bullets", "bullets": 3, "max_words": 25}},
    {"id": "exec_summary", "generator": 2, "placement": "slide 1",
     "covers": "the three things the committee must know about October cost",
     "tables": [], "style": {"format": "bullets", "bullets": 3, "max_words": 22}}
  ]
}
```

| Top-level field | Required | Notes |
| --- | --- | --- |
| `deliverable` | yes | Unique name; written into every output file |
| `medium` | yes | `deck`, `report` or `dashboard` |
| `deliverable_files` | decks, reports | Files holding the placeholders; enables the two-way placeholder check and fill |
| `data_dir` | no | Default `data`, relative to the shell. Every table must sit inside it |
| `as_of` | dashboards | `table`, `field`, optional `rule` (max/min) and `dimension` |
| `show_unverified` | no | Dashboards: show unverified bullets (default false) |
| `derive` | no | `false` turns off the automatic change, share and rank columns. Use when the tables already hold every ratio and difference needed |
| `question` | no | The overall question the deliverable answers. Passed to the writer with every call |

Unit fields: `id`, `generator`, `placement`, `covers`, `tables`, `style`. All required.

Optional unit field `notes`: findings no table shows (a cause, a known data issue, what a code means). The writer uses them to explain why; takes no numbers from them.

## 7. What validation checks

- **Shell-level (stops everything):** bad `medium`; missing deliverable, generators or units; data folder missing; dashboard without `as_of`, or its field missing; generator without `audience`; dashboard generator without explicit `dimensions`; more than 12 tables in a generator; samples over the limit; duplicate unit ids; a placeholder with no unit; a deliverable file missing.
- **Unit-level (in session: ask; in batch: that unit fails, the run continues):** no or templated `covers`; no placement; bad style; no tables; unknown generator; a table missing, outside `data/`, or not CSV/Parquet; a dimension that is not a column; a unit with no placeholder.
- **At generate time:** row and column limits, per unit.

## 8. Checklist

- [ ] Every unit is in `commentary_plan.md` and passes the free-form test
- [ ] One placeholder per unit in the deliverable, and no stray placeholders
- [ ] Every covers line is a question the unit's own tables can answer
- [ ] Targets and comparisons named in covers lines are in a table
- [ ] Tables are the same aggregated files the visuals use, each within 50 × 15
- [ ] Generators match the plan's groups, at most 12 tables each
- [ ] Dashboards: `as_of` and `dimensions` match the plan's snapshot column and commentary filters
- [ ] `validate_shell.py` clean, `status.py` shows every unit as "none yet"
