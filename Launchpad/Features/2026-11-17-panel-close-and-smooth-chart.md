# Closable right-hand panel and a smooth Usage chart

Status: built
Date: 2026-11-17

Two front-end tweaks asked for directly, without a planning interview. The right-hand panel (In orbit / Incoming, or Repos on Files) can now be closed to a slim strip and reopened, with a red count of waiting items above the reopen arrow. The Usage chart (request 32) changed from stacked bars to smooth stacked area lines in an executive-dashboard style, because the user did not like the bar chart.

Built on `feature/usage-monitor` (request 32's branch). Not committed at the time of writing.

## Decisions

- **Closing the panel.** A close button sits at the top right of the panel's first card. Closed, the panel is a slim card at the right edge, the same width as the collapsed sidebar, holding a reopen arrow with a count just above it of the Incoming items waiting on the user (questions, permission requests, workflow reviews). No count at zero. The choice is remembered in the browser's local storage and applies on every view. The current view takes the freed width.
- **Narrow windows (980 px and below).** The panel already stacks under the view there; closed, it becomes a slim row under the view with the count and a "Show In orbit and Incoming" control.
- **The chart stays on ECharts.** The user asked which library was used; it is ECharts, which can draw the wanted style, so only the chart type and styling changed.
- **Chart style.** Smooth stacked area lines (a thin line per series, a soft fill fading to transparent), faint horizontal gridlines only, no axis lines, a y-axis from zero, at most about seven date labels. Hover shows a slim guide line, points on each series and a tooltip listing series largest first with the total in bold. The legend is pills that switch a series on and off. Smoothing never overshoots the real values, so a line cannot dip below zero.
- **Sparse data.** Empty days in the period are drawn as zero so the line spans the period; every point is marked when there are three buckets or fewer, and a series that appears in only one bucket gets a visible point.
- **Totals row.** The chosen measure is shown first and large, the other four smaller beside it.
- **Animation.** One draw-in when the chart first appears, a quick change for measure and legend, none for period, bucket or session changes, and none at all when the user has reduced motion switched on.

## Follow-up the same day (user feedback on the first version)

- **Line or bar.** A "Chart" switch (Line / Bar) sits with the other chart controls. It opens on Line and the choice is remembered in the browser's local storage. Switching does not ask the server again.
- **A new bar chart, not the original one.** The user said the first bar chart's hover animations were not smooth. The new one is built around hovering: stacked bars at most 36 px wide with rounded corners on the top visible segment only; a soft band behind the hovered day or week that glides to the next one; the other series never dim or resize; the tooltip is triggered by the day or week, not by a segment, sits beside the hovered bar, stays inside the chart and only moves when the day changes (the line view now does the same). Known limits: the band appears and disappears at once when the pointer enters or leaves the chart, and in a narrow chart the tooltip can sit over neighbouring bars.
- **The panel's close control moved.** The user wanted it in the middle of the page, not the top-right corner of the panel. It is now a slim handle centred in the gap between the view and the panel at the panel's mid-height, and stays there while the panel's lists scroll. Closed, the reopen arrow sits at the same mid-height on the strip with the red count just above it. In a narrow window, where the panel is under the view, the handle is centred horizontally on that boundary.

## Checked

- Front-end tests (171 passed after the follow-up) and the build.
- Seen in the running zero-token demo at the normal window size: the panel closing and reopening with its count, the line chart split by CLI and by agent, and after the follow-up the bar chart with its hover band and tooltip and the handle at mid-height. The builder also swept the pointer across the bars slowly and quickly and found the tooltip steady across the gaps.

## Not checked

- The Visuals panel opened while the right-hand panel is closed; it now covers the right edge of the view instead of the panel's space.
- The chart against the user's real log, which holds a single day of data.
