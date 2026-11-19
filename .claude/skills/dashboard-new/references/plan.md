# The plan (PLAN.md)

One short file in the dashboard folder: the tables, the sections per tab, and where each filter lives. Steps 3 and
4 just follow it.

## Its shape
```markdown
# Plan: <dashboard title>

## Data
| Table | From (file, query, script, or a report's source) | One row is | Columns |
|---|---|---|---|
| claims | ../inputs/claims.csv (the report's SOURCES "claims") | one claim | month, region, product, paid |

## Tabs and sections
| Tab | Section | Answers (plan goal) | Shows | Reads | Copy from |
|---|---|---|---|---|---|
| Overview | Headline | Is cost rising? | KPI tiles: latest month, change on last year | claims | (new) |
| Overview | Cost by region | Where is it rising? | Change by region, half width | claims | report: region_cost |

## Filters
| Filter | Column | Applies to | Level | Fast / slow | Why |
|---|---|---|---|---|---|
| Region | region | every section but Cost by region | dashboard | fast | a WHERE on loaded rows |

## Rules to keep
- Drops cancelled claims (old_report.py: load())
- A threshold or period the report uses is never typed into `Analysis/`: it comes from the analytics file's
  `DEFAULTS` through `from_report`.
```

## Laying it out
- One tab per question or audience. One tab is fine for a small dashboard.
- In a tab: headline KPI tiles first, then the trend, then the breakdown, then detail tables.
- One section, one idea. Show the answer directly: a rate or a change, not a long total.
- A change compares like periods (the same months a year earlier), never a window holding a one-off spike. Write
  the period in Rules to keep and in the note.
- The title says what it shows ("Paid per member by month"), not the chart type or a slogan.
- A section that compares regions is not narrowed by the region filter (it takes `filters=[...]` without it).
- A section's number (`s3_...`) is permanent; reports point to it.

## Filters: the part to get right
**Level** comes from what it applies to:

| Applies to | Level | In the config |
|---|---|---|
| Every section | dashboard (above the tabs) | no `tab` or `section` |
| The sections on one tab | tab | `"tab": "<tab id>"` |
| One section | section | `"section": "<section id>"` |

Never repeat one filter in several sections; move it up a level. A switch that only changes the view (count vs
amount, chart vs table) is not a filter; it stays inside its section.

**Fast or slow:** slow (re-queries the source) when the value is passed into a query or API call, picks which file
or snapshot is read, is a run argument or a date typed in before each run, or its data is too big to load for
every value. Otherwise fast. Prefer fast. Write the reason under **Why**.
