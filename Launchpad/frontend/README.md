# Launchpad front end (React + Vite + TypeScript)

The React port of `prototype/launchpad-orbit.html` (the vanilla page, kept unchanged and served at `/classic`).
Display + input only: all agent work stays in Python. The websocket contract is the header of `app/server.py`.

## Commands (from this folder)

| Command | What it does |
|---|---|
| `npm install` | once, installs the packages (Node only on the builder's machine; coworkers never need it) |
| `npm run dev` | dev server at http://localhost:5173 with the in-page demo (no back end needed); `?speed=4` runs it faster |
| `npx tsc --noEmit` | type check |
| `npm test` | store + demo tests and a DOM render smoke test of the shell (vitest + happy-dom, zero back end) |
| `npm run build` | type check, then build to `dist/` (committed, served by Python) |

Served by `app/server.py`: `GET /` = `dist/index.html` when it exists, else the vanilla page; `GET /assets/<file>` =
`dist/assets/`; `GET /classic` = always the vanilla page. Real mode needs `?port=&code=` in the URL (the launcher adds
them); without them the page runs the demo. Nothing loads from the internet: everything is bundled.

## Layout

| Path | What |
|---|---|
| `src/contract.ts` | types for every server event (`ServerEvent`) and UI message (`UiMessage`) |
| `src/store/` | the whole app state (`types.ts`), the reducer for every server event (`reducer.ts`), UI actions (`actions.ts`), derived values (`selectors.ts`) |
| `src/bridge.ts` | `connect()` (websocket or demo), `send(msg)` |
| `src/demo/` | the ported in-page demo (`Demo.ts`, data in `data.ts`): two runs, the planner, Claude Code chats (also from a plan), the crew with two folder agents and ticking use counts, a plan whose steps 3-4 name folder agents, agent draft / create / remove. Typing "fail" in Draft for me shows the error; a name starting `launchpad-` shows a server problem |
| `src/lib/` | `markdown.ts` (escaped md / docHtml), `format.ts` (usd, tokens, ago, toolCat ...), `storage.ts` (localStorage), `labels.ts`, `hooks.ts` (`useNow`, `useAnimationFrame`) |
| `src/components/` | shared pieces (below) |
| `src/theme.css` | the design tokens (see Design system) + all global / shared CSS |
| `src/fonts.css` | the bundled Sora and Inter faces (Latin + Latin Extended woff2 from @fontsource-variable) |
| `src/views/<Name>/` | one folder per screen, each with its own CSS (vanilla class names kept, sizes from the tokens) |
| `src/views/Chat/` | the chat screen (header tab "Plan"): the Planner / Claude Code switch over `views/Plan` (Planner side) and `views/Code` (Claude Code side, the former Free Flight tab); both panes stay mounted |
| `src/views/Crew/` | Crew hero cards + the definition reader (`Crew.tsx`) and the Add an agent dialog (`AgentForm.tsx`) |
| `src/App.tsx`, `src/shell/Header.tsx` | shell: header + tabs, all views (kept mounted, `hidden` tab panels), aside, visuals slot, overlays |

## State and hooks

One zustand store, changed only through immer recipes inside the store. Views never write it and never handle server
events: they read state and call `actions.*` (or `send`).

```ts
import { useLaunchpad, useComputed, useCurrentSession, useSession, actions, send, sel, onActivityPing } from '../../store';
const view = useLaunchpad(st => st.ui.view);                  // one value (return state values, not new objects)
const { open, total } = useComputed(st => ({ open: sel.openCount(st), total: sel.appTotals(st).cost }));  // derived
const s = useCurrentSession();                                // session in the Plan tab
actions.approve(s.id);                                        // anything that changes state
send({ type: 'get_crew' });                                   // a plain message with no local change
```

Selectors that build new arrays/objects must go through `useComputed`, not `useLaunchpad(selector)` (zustand would loop).

State shape (`src/store/types.ts`, all plain keyed objects):
- `ui`: `view` (plan | missions | crew | files), `chatSide` (planner | code: the chat screen's switch; `actions.setChatSide`), `conn`, `demo`, `queueFilter`, `feedRun`/`feedAgent`, `hov`/`sel` (agent highlight), `focus`/`focusScroll`,
  two-click confirms `stopConfirm`/`apConfirm`/`pmConfirm`, `newPlanBusy`, `newChatBusy`, `vis {open, wide, width}`,
  `settingsOpen`/`settingsMsg`/`settingsAddPath`/`picking`, `dirMenu`, `toasts`
- `sessions[id]` (+ `order`, `current`): letter, folder/dirId/cwd, status, meta, roundTag, draft/draftV/draftRev,
  run {name, steps[{n,title,status,built,report_path,agent,agent_display,agent_fallback,agent_purpose}]}, runDraftV/runRev, report, approving, stopping, reportSent,
  cleared, flash/flashN, autopilot, codeSending/codeSentV (Send plan to Claude Code), planner fields (plannerId, plannerStatus, plannerModel, promoted, promoting ...),
  visualSets[{set_id, brief, options (each with `drawn_with`), picked_id, pending, `library` (asked for; null = not asked),
  `drawn_with` (used), `libraries` (available for the folder), `library_note` ("drawn in ECharts, styled like X" on a fallback)}], visSel, visSeen, `log` (planner chat), `typing`
- planner `log` entries: `bubble {who, text}` · `sys {text, cls?: promo|err}` · `visnote {text, setId}` (has a Show
  button: `actions.visShowSet`) · `round {roundId}` (data in `rounds[roundId]`) · `plancard {draft, draftV, rev, state}`
  (use `sel.planCardView(s, entry)` for approved / superseded / button label / status line). `preLog`/`preTyping` =
  lines before any session exists.
- `rounds[id]`: questions, answers, sent, actionsHidden
- `agents[agent_id]` (agent_usage records), `acts` (activity, oldest first, max 600; `sel.feedRows` = newest first),
  `lastAct`, `tokens`/`cost`/`usageEv` (server usage)
- `queue`: Incoming cards in arrival order, `ui: open|sent|timedout|autopilot|auto|ended`, `leaving` while fading;
  kind `report` cards are added by run_finished (id `report:<session_id>`). Order with `sel.orderedQueue`.
- Claude Code chats: `chats[id]` {mode, model, cwd, dirId, busy, log, streamId, typing, agentIds}, `chatOrder`,
  `currentChat`, `chatPending`, `codeModePref`, `chatFromPlan` (session whose plan was sent; its `chat_started` keeps Plan mode,
  also matched by `from_session_id`), `chatItems[id]` (inline cards, `ui: open|sent|done`, `result`).
  Chat `log` entries: `bubble {who, text, streaming?}` · `sys {text, cls?}` · `tool {act}` · `card {itemId}`.
- Crew: `crewDefs` (crew_list agents with `purpose`, `uses`, `builtin`, `step_worker`), `crewLoading`, `crewDirId` (crew_list.dir_id),
  `crewDirPick` (folder picked in Crew, sent as `get_crew {dir_id}`), `toolChoices`, `crewUses[name]` (live from `agent_uses`),
  `crewForm` {open, fields, problems, error, saving, draftText, drafting, draftError, drafted}, `crewRemoving`, `crewError`, `crewFlash`.
  Selectors: `sel.purposeOf`, `isBuiltin`, `usesOf`, `crewDir`, `stepAgent(defs, step)` (null = the Builder; `fallback` when
  `agent_fallback`; colour from the step's `agent_purpose`, else `defsForSession` = the crew list only when it lists the session's own folder), `agentFormProblems`, `problemField` / `problemText` (server problems -> form fields), `plannerWaiting` / `codeWaiting`.
- `settings {directories, values, can_pick}`
- `fx` (File Explorer: cache, loading, err, open, sel, raw, collapsed, width; persisted to localStorage) · `files`
  (file_content per `root|path`) · `editor` (pen editor: text, dirty, banner, conflict, pane, backups ...)

Not in the store (view-local animation): orbit body positions, solar-system ships/trails/pings. For pings use
`onActivityPing((act, isNew) => ...)` (returns an unsubscribe).

## Shared components (`src/components`)

`Markdown` (the only `dangerouslySetInnerHTML`; `doc` for YAML-headed files; `label` = aria-label, makes it a named
region) · `Pill` (button: `variant`, `size` md | sm | xs, `icon`; an icon with no label = round icon button, needs
`aria-label`) · `Tag` (kind tag with its icon), `Chip`, `Letter`, `Status`, `Empty` (`icon`, `title`, one line),
`Loading` (spinner line), `Badge`, `SunIcon`, `DirChip` · `ChatBubble` (long user text folds with Show all; `plan` = the plan sent to Claude Code, folded and formatted), `SysLine`, `TypingDots` · `Card`, `ViewFrame`
(vhead look) · `AutopilotSwitch` (role=switch) · `PenButton` (opens the editor) · `Dialog`, `DialogTitle`, `DialogX`
(the dialog primitive, below) · `openModal`/`closeModal` (generic modal; actions may be a function for live labels and
may carry an `icon`) · `openReport`, `openPlan`, `openArchive` (read-only planning chat: the real `PlanLog` inside
`.msgs.archived`, whose CSS hides buttons and forms) · `DirMenu` via `actions.chooseDir(anchorEl, dirId => ...)` · `PurposeTag` (purpose label + icon in its colours) and `StepAgent` (the agent on a plan step, or the coral Builder-fallback chip), `PURPOSE_ICON` ·
`TipHost` (put `data-tip="planner|cursession|allagents|chat|run:<sid>|agent:<id>|step:<n>:<sid>"` on any element, or
`data-tip="text:Short label"` for a plain label) · `data-hover-agent="<agent_id>"` sets the shared hover highlight
`ui.hov` (feed rows, stars and ships all carry it; pinning from Missions scrolls `#feedList [data-hover-agent]` rows) ·
`Toasts` (`actions.toast`) · `icons.ts` (the icon set).

Two-click confirms with a 4 s window live in the store (`toggleAutopilot`, `stopRun`, `promotePlanner`); the
"New plan → Set this plan aside?", Settings "Confirm remove" and Crew "Confirm remove" (folder agents) confirms are local to their views.

## Design system (polish pass, Nov 2026)

Same Orbit look as the vanilla page: the colour tokens and fonts are unchanged; everything else is a token so screens
stay consistent. Rule: never write a colour, spacing, radius, font size or shadow as a number in a view's CSS; use a
token. Raw `px` only for hairlines (1px), layout widths / heights and alignment offsets. The one hard-coded colour outside
`:root` is the feed select's chevron (a data-URI SVG cannot read CSS variables; it is `--muted`).

**Tokens** (`:root` in `src/theme.css`)

| Group | Tokens |
|---|---|
| Colour (Orbit, unchanged) | `--bg --card --ink --muted --line --line2 --indigo --indigo-dk --indigo-soft --indigo-ink --lilac --moon --coral --coral-soft --coral-ink --green --green-soft --green-ink` |
| Agent purposes | `--purpose-planning` / `-exploring` / `-building` / `-reviewing`, each with `-soft` and `-ink` (Okabe-Ito based hues toned to Orbit: indigo, sky blue, amber, plum; always shown with a label and an icon too). Put `data-purpose="<purpose>"` on an element and use `--pc` / `--pc-soft` / `--pc-ink` inside it |
| Named uses of old hard-coded values | `--on-accent` (text on indigo / coral / green / ink) · `--surface-quiet` · `--surface-settled` · `--surface-done` · `--surface-ended` · `--overline` · `--tip-muted` · `--scrim` |
| Spacing (4px grid) | `--sp-0` 2 · `--sp-1` 4 · `--sp-1-5` 6 · `--sp-2` 8 · `--sp-2-5` 10 · `--sp-3` 12 · `--sp-4` 16 · `--sp-5` 20 · `--sp-6` 24 · `--sp-7` 28 · `--sp-8` 32 |
| Radius | `--r-xs` 6 · `--r-sm` 8 · `--r-md` 12 · `--r-lg` 16 · `--r-xl` 20 (cards) · `--r-pill` |
| Type | `--fs-2xs` 11 · `--fs-xs` 12 · `--fs-sm` 13 · `--fs-md` 14 · `--fs-base` 15 · `--fs-lg` 16 · `--fs-xl` 18 · `--fs-2xl` 20 · `--fs-3xl` 24; `--lh-tight` 1.3 · `--lh-snug` 1.4 · `--lh-body` 1.55; `--disp` (Sora) · `--body` (Inter) · `--mono` |
| Shadow | `--shadow-xs` (pills on the page) · `--shadow-sm` (raised buttons, selected segments) · `--shadow` (cards) · `--shadow-lg` (dialogs, menus, panels, tooltip) · `--ring` (field focus) |
| Sizes | controls `--ctl-lg` 44 · `--ctl-md` 40 · `--ctl-sm` 32 · `--ctl-xs` 26; `--chip-h` 22 (chips, tags, status, letters); `--count-h` 18 (count badges); icons `--icon-xs` 12 · `--icon-sm` 14 · `--icon-md` 16 · `--icon-lg` 20 |
| Motion | `--ease` · `--t-fast` .12s · `--t-base` .2s · `--t-slow` .3s; all motion stops under `prefers-reduced-motion` (the orbit and systems also stand still: `REDUCED` in `lib/format.ts`) |
| Layers | `--z-panel` · `--z-scrim` · `--z-editor` · `--z-toast` · `--z-menu` · `--z-tip` |

**Type hierarchy**: view title Sora 24/600 · dialog title Sora 20 · panel / section title Sora 15-18 · card title Sora
15-16 · body Inter 14-15 · meta Inter 12-13 muted · overline (QUESTION 1, ON THE PAD, role groups) 11/700 uppercase,
letter-spaced, muted.

**Buttons, chips, fields**: `.pill` is the one button (md 40 · `.sm` 32 · `.xs` 26 · `.icon` square); variants default,
`primary`, `soft`, `ghost`, `danger`, `sugg`, `pickedbtn`. Hover, active (scale .97), disabled (.5, not-allowed) and the
global `:focus-visible` outline (2px indigo) are shared. Chips, tags, status pills, `.aptag`, `.round-tag`, `.dirchip`
and letters share `--chip-h`; counters share `--count-h`. Text fields use `.field` (or the form selectors listed with it
in theme.css): lilac border on hover, indigo border + `--ring` on focus. `.seg` is the segmented toggle (aria-pressed).

**Icons**: lucide-react only, imported from `src/components/icons.ts` (add new names there). Sized by CSS (16px; 14px
in sm / xs buttons; 12px in chips). No text glyphs or emoji as icons. Kept on purpose: the step and star marks drawn
inside the Missions SVG systems.

**Accessible primitives**
- Dialogs: `components/Dialog.tsx` wraps Radix Dialog (focus trap, Esc, outside click, focus back to the opener, the
  page hidden from screen readers while open). Styled only by `.scrim` / `.modal`; every dialog needs a `DialogTitle`.
- Tabs: the header is a WAI-ARIA tablist (`role=tab`, `aria-selected`, roving tabindex, Left / Right / Home / End);
  each view slot in `App.tsx` is its `role=tabpanel`.
- Menu: `DirMenu` is `role=menu` with `menuitem`s (Up / Down / Home / End; Esc returns focus to the opener).
- Switch: `AutopilotSwitch` is `role=switch` with `aria-checked`. The chat screen's Planner / Claude Code switch is a two-tab `role=tablist` (Left / Right / Home / End); each tab's label says when its side is waiting on you (coral count) or working (dot).
- Crew: cards are buttons (aria-label sums up purpose, source, model, uses); opening one moves focus to the detail heading, "All agents" returns it to the card. The Add an agent dialog marks invalid fields with `aria-invalid` + `aria-describedby` to the inline message and focuses the first one after a failed save.
- Tooltips: `TipHost` shows on hover and on keyboard focus, sets `aria-describedby="tip"` on the focused element, Esc
  hides it; `text:` labels appear after 350 ms. Text with a tip that is not a button gets `tabIndex={0}`.
- The feed filters stay native `<select>` (styled, with a chevron).

**States**: `Empty` (icon + title + one line) for empty screens and lists, `Loading` for anything waiting on the back
end, `.warn` for errors, and a coral bar under the header when the connection is lost. Titles wrap
(`overflow-wrap:anywhere`), one-line meta truncates with an ellipsis. Scrollbars are thin, `--line2` on transparent.

**Layout**: holds from 1100 to 1920 px wide (pywebview opens at 1360 x 880, minimum 980 x 640). The header stays on one
row: the usage pill truncates (the full figures are in its tooltip). At 1240 px and below the tab icons, the "Whole app"
label, the connection text and the Settings label are hidden (still announced) and the aside narrows to 360 px.

**Fonts and security**: Sora and Inter are bundled (`src/fonts.css`), nothing loads from the internet and the page CSP
in `app/server.py` (`font-src 'self'`) did not change. Radix uses inline styles, which that CSP already allows. The
Visuals frames keep their own CSP and sandbox (`views/Visuals/frames.ts`); the polish pass did not touch them.

## Where each vanilla screen is (`prototype/launchpad-orbit.html`)

| Screen (task) | HTML | JS | CSS now in |
|---|---|---|---|
| Plan chat (2a) | 647-670 | 1209-1616, model 1617-1667, autopilot 1669-1698 | theme.css (chat, rounds, plan cards), `views/Plan/Plan.css` |
| Aside: Incoming, orbit, activity feed (2a) | 738-763 | queue 1700-1878, orbit 1880-1985, feed 2321-2404 | `views/Aside/Aside.css` |
| Free Flight (2b), now the chat screen's Claude Code side | 672-698 | 2429-2676 | `views/Code/Code.css` (switch: `views/Chat/Chat.css`) |
| Visuals panel (2b) | 764-779 | 2678-2972 | `views/Visuals/Visuals.css` |
| Missions (2c) | 700-707 | 2109-2320, 2394-2427 | `views/Missions/Missions.css` |
| Crew (2c), now hero cards + Add an agent | 709-723 | 3324-3400 (the reader) | `views/Crew/Crew.css` |
| Files + pen editor (2c) | 725-736, 784-792 | 3081-3192, 3227-3322 | `views/Files/Files.css` |
| Settings (2c) | (modal) | 2990-3063 | `views/Settings/Settings.css` |
| Event handling (done, in the store) | | 1063-1103 and the on*() handlers | |
| Demo (done, `src/demo`) | | 3458-4268 | |

Each placeholder file lists the selectors and actions its screen needs in its header comment.
