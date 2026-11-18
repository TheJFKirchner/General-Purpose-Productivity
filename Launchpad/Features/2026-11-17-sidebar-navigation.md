# Sidebar navigation

Status: built
Date: 2026-11-17

The tab list at the top of the window becomes a sidebar on the left, because more views are coming (Settings became a view in request 27 and Workflows follows in request 30) and a sidebar organises them better. Approved but not started: it is built after request 27 (Settings, connections and MCP) is finished and accepted, because both touch the same front-end files, and before request 30 so the Workflows view is added to the new navigation once.

Feature branch: `feature/sidebar-navigation`, created from `feature/settings-connections-mcp` (request 27), not from main, because request 27 was not yet merged when the user said to move on and the sidebar needs its Settings view. Merge request 27's branch first, then this one.

## What was built, and where it differs from the plan

- `frontend/src/components/Sidebar.tsx`: Plan, Missions, Crew and Files at the top, Settings at the bottom behind a divider, all from one list so a new view is one entry. The "waiting" and "in flight" badges moved here from the old tabs. The header now holds only the brand, connection status, cost and avatar.
- Collapse to icons only with a toggle; the choice is remembered in the browser's local storage.
- Added beyond the plan: at 1240 px wide and below the sidebar is icons only whatever the saved choice, and at 980 px and below it becomes a row above the views.
- Checked: front-end tests (90 passed) and the build. Not checked: it has not been looked at in a running window; the one UI review is held for request 30 (workflows), which shows the sidebar too.
- Builder's note: the open sidebar takes about 200 px; if views feel tight, start it collapsed by default.

## Assumptions (shown to the user, uncorrected)

1. The tab list becomes a sidebar on the left with an icon and a label per view, in today's order.
2. It can be collapsed to icons only, and remembers that choice.
3. Settings sits at the bottom of the sidebar, apart from the working views.
4. Nothing else moves: the right-hand panel and every view's content stay as they are.

## Decisions

- **Sidebar before Workflows (Q12 of the workflows interview).** Built first as its own small request so the sixth view is added to the new navigation once, instead of to the tab bar and then moved.
- **Front end only.** No websocket or back-end change is expected.

## Task: sidebar

- **Goal:** replace the top tab list with the sidebar.
- **Builder:** factory-builder, Sonnet, UI.
- **Owns:** `frontend/` (and the lines about navigation in `frontend/README.md`; CLAUDE.md "Current state" gets one bullet).
- **Read first:** `frontend/README.md`, `frontend/src/App.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/store/types.ts`, the Orbit `theme.css`.
- **Done when:** every view is reachable from the sidebar; the active view is marked; collapse works and persists across a reload; Settings is at the bottom; the tab list is gone; the layout holds at the window's minimum size; `npx vitest run` passes and `npm run build` succeeds.
