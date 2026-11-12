# behavior rules

- lead swap: `PlanTile` click -> that measure leads in `SpotlightCard` + `TwinTrend`; old lead returns to tile row. built into `BandConsole`
- hover: shadow only `3px 3px 0 var(--shadow)`, never movement. `RailMenu` items slide 8px. `LedgerTable` rows tint `--rowTint`
- link glow: `useLinkGlow` -> pass `active` + `onActive` to both `PlanSplit` and `LedgerTable`
- `MixStack`: hovering a category dims the others (built in)
- `TwinTrend` tooltip: both years at hovered month, solid guide line in `--ink`
- motion: `motion` prop on `BandConsole` (default true): chart draw-in, `TickBar` growth, `useTickUp` count-up. auto-off under `prefers-reduced-motion`
- `SlabButton`: hover = background only
- `PulseGrid` `gate`: `RangeGate` sliders hide groups whose change falls outside the chosen range; shows "n of m shown"
- `FlowRibbon`: hovering a name on either side dims the rest and relabels the other side with that name's amounts only
- `PaceLines` + `PeriodSwitch`: switch changes which smoothing is drawn bold; the others stay as grey context
- `FindingPanel` `table` prop (ViewFlip): button flips the panel between chart and its numbers
- estimates: always `estimateStyle` (dashed, pale); never the same fill as final values
