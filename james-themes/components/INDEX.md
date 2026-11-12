# components index

Pick by what you need to show, then open only that file. "Use when" is the reader's question, never the axes.

## Show one number and what stands behind it

| name | use when you want to show | path |
|---|---|---|
| `SpotlightCard` | The page's lead measure against its target | `cards/SpotlightCard.jsx` |
| `PlanTile` | A supporting measure against its target | `cards/PlanTile.jsx` |
| `SplitDial` | A number plus the parts composing it | `cards/SplitDial.jsx` |
| `RangeCard` | A number placed within its recent range | `cards/RangeCard.jsx` |
| `StreakCard` | How long something has persisted, period by period | `cards/StreakCard.jsx` |
| `RankCard` | Where one group stands among its peers | `cards/RankCard.jsx` |
| `DriverCard` | One sentence naming the biggest driver | `cards/DriverCard.jsx` |
| `CardRow` | Lays several title cards in a row | `cards/CardRow.jsx` |

## Compare a metric over time

| name | use when you want to show | path |
|---|---|---|
| `TwinTrend` | This period's path against the prior period's | `charts/TwinTrend.jsx` |
| `PaceLines` | Rate of change against an assumption, several smoothings | `charts/PaceLines.jsx` |
| `PulseGrid` | Same metric over time across many groups | `charts/PulseGrid.jsx` |
| `CompletionCap` | Over time, with a still-incomplete recent portion | `charts/CompletionCap.jsx` |
| `PlanDrift` | A gap to target accumulating over time | `charts/PlanDrift.jsx` |
| `YearPair` | A few periods, two years side by side | `charts/YearPair.jsx` |
| `RankClimb` | How groups' rank order shifts over time | `charts/RankClimb.jsx` |

## Compare groups at one point in time

| name | use when you want to show | path |
|---|---|---|
| `SlopeShift` | Before and after for several groups | `charts/SlopeShift.jsx` |
| `GapDumbbell` | Actual, target and prior for unequal-sized groups | `charts/GapDumbbell.jsx` |
| `PlanSplit` | Which groups are over or under target | `charts/PlanSplit.jsx` |
| `RankRail` | Rank groups by one value | `charts/RankRail.jsx` |
| `TileAtlas` | Compare states fairly, whatever their size | `pictorial/TileAtlas.jsx` |

## Explain what a total or a change is made of

| name | use when you want to show | path |
|---|---|---|
| `TrendBridge` | Walk from start to end by driver | `charts/TrendBridge.jsx` |
| `DriverStrip` | Each part's share of one total | `charts/DriverStrip.jsx` |
| `ParetoStack` | Few drivers explain most of a total | `charts/ParetoStack.jsx` |
| `MixStack` | How composition shifts across periods | `charts/MixStack.jsx` |
| `FlowRibbon` | One total split two ways at once | `charts/FlowRibbon.jsx` |
| `CapsuleCount` | Volume share beside cost share, as countable units | `pictorial/CapsuleCount.jsx` |

## Show the detail rows

| name | use when you want to show | path |
|---|---|---|
| `LedgerTable` | Exact figures by group, with inline meters | `tables/LedgerTable.jsx` |
| `RowMeter` | A value's size inside a table cell | `indicators/RowMeter.jsx` |
| `PivotLedger` | Let the reader regroup rows and columns | `tables/PivotLedger.jsx` |
| `CsvButton` | Let the reader take the numbers away | `controls/CsvButton.jsx` |

## Add context to any chart

| name | use when you want to show | path |
|---|---|---|
| `PeriodSwitch` | Let the reader change the time smoothing | `controls/PeriodSwitch.jsx` |
| `RangeGate` | Let the reader hide groups outside a range | `controls/RangeGate.jsx` |
| `FilterChips` | Show which filters the page reflects | `controls/FilterChips.jsx` |
| `assumptionBand` | Shade the expected range behind a line | `charts/chartKit.js` |
| `eventMarks` | Mark a dated event on a time chart | `charts/chartKit.js` |
| `estimateStyle` | Mark values that are not final | `charts/chartKit.js` |
| `CommentaryNote` | A written takeaway under a chart | `layout/CommentaryNote.jsx` |
| `SourceLine` | State data-through date and basis | `layout/SourceLine.jsx` |
| `ViewFlip` | Flip a panel between chart and table | `layout/FindingPanel.jsx` |
| `TickBar` | Actual against target and prior, inline | `indicators/TickBar.jsx` |
| `DeltaMark` | Direction and size of a change, inline | `indicators/DeltaMark.jsx` |

## Build the page

| name | use when you want to show | path |
|---|---|---|
| `BandConsole` | A full page with one lead measure | `layout/BandConsole.jsx` |
| `RailMenu` | Section links down the side | `layout/RailMenu.jsx` |
| `CommandBand` | Headline area holding the lead measure | `layout/CommandBand.jsx` |
| `FindingPanel` | Frame a chart under its finding | `layout/FindingPanel.jsx` |
| `PanelPair` | Place two panels side by side | `layout/PanelPair.jsx` |
| `ChartSlate` | Hold a chart inside the band | `cards/ChartSlate.jsx` |
| `SlabButton` | Any button, on band or white | `controls/SlabButton.jsx` |

## Wire behavior and shared pieces

| name | use when you want to show | path |
|---|---|---|
| `ChartMount` | Render any chart option; only echarts import | `charts/ChartMount.jsx` |
| `chartKit` | Shared chart fonts, axes, tooltip, helpers | `charts/chartKit.js` |
| `useLinkGlow` | Link hover between a table and chart | `behaviors/useLinkGlow.js` |
| `useTickUp` | Count a number up on load | `behaviors/useTickUp.js` |
| `rules` | Hover, motion, linking and swap rules | `behaviors/rules.md` |
| `groundwork` | Font, status colors, reset for every page | `foundation/groundwork.css` |
| `ConsoleDemo` | Working overview page, four themes | `examples/ConsoleDemo.jsx` |
| `ExtrasDemo` | Working page: pictorial, pivot, downloads | `examples/ExtrasDemo.jsx` |
| `toCsv` | Turn rows into CSV text and save | `behaviors/toCsv.js` |
| `shade` | Light-to-dark shading for pictorial visuals | `pictorial/shade.js` |
| `usTiles` | State tile layout and state names | `pictorial/usTiles.js` |
| `TrendDemo` | Working trend page with every chart | `examples/TrendDemo.jsx` |

## Restricted: only when the user explicitly asks for it by name

| name | use when you want to show | path |
|---|---|---|
| `BodyLens` | Amounts placed on a body figure | `pictorial/BodyLens.jsx` |

- never pick `BodyLens` on your own, even for clinical breakdowns; default to `ParetoStack` or `RankRail`

## shapes

- measure: `{ id, label, actual, plan, lastYear, min, max, fmt, delta, up, good, note, sentence, labels, cur, prior }`
- `t` = one theme's `chart.js` default export (`../<theme>/chart.js`)
- group rows: `[{ name, value }]`; before/after rows: `[{ name, from, to }]`; target rows: `[{ name, actual, plan, lastYear }]`
- every chart takes `t`, `label` (screen-reader text), optional `fmt`, `motion`, `height`

## choosing between neighbors

- over time, one group: `TwinTrend` (levels) vs `PaceLines` (rate of change)
- over time, many groups: `PulseGrid`; add `gate` when there are more groups than fit
- recent periods not final: `CompletionCap`, never a plain line
- vs target over time: `PlanDrift`; vs target by group: `PlanSplit` (amounts) or `GapDumbbell` (fair across sizes)
- made-of, a change: `TrendBridge` (drivers in order) or `DriverStrip` (shares only); many drivers: `ParetoStack`
- made-of, across periods: `MixStack`; split two ways: `FlowRibbon`
- by state: `TileAtlas`; rank order changing: `RankClimb`; lopsided volume vs cost: `CapsuleCount`
- downloads: `LedgerTable csv=` (small button, top right of the table); `FindingPanel download=` ("Download all", top right of the section)

## adding a component

- put it in its type folder (`layout/ cards/ indicators/ controls/ tables/ charts/ pictorial/ behaviors/`); new type -> new folder + one css file
- unique two-word PascalCase name; no generic names (`Card`, `Chart`, `Table`, `Button`, `Dashboard`)
- css classes prefixed `jt-`; colors from `var(--*)` or `t` only
- add one row above under the intent it serves; "use when" <= 8 words, phrased as the reader's question
