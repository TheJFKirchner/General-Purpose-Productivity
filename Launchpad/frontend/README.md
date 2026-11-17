# Launchpad front end (React + Vite + TypeScript)

The React port of `prototype/launchpad-orbit.html` (the vanilla page, kept unchanged and served at `/classic`).
Display + input only: all agent work stays in Python. The websocket contract is the header of `app/server.py`.

## Commands (from this folder)

| Command | What it does |
|---|---|
| `npm install` | once, installs the packages (Node only on the builder's machine; coworkers never need it) |
| `npm run dev` | dev server at http://localhost:5173 with the in-page demo (no back end needed); `?speed=4` runs it faster |
| `npm run typecheck` | type check (`tsc --noEmit`) |
| `npm test` (or `npx vitest run`) | vitest, zero back end. The default environment is node; the test files that render the app opt in to happy-dom with a `// @vitest-environment happy-dom` first line |
| `npm run build` | type check, then build to `dist/` (committed, served by Python) |

Served by `app/server.py`: `GET /` = `dist/index.html` when it exists, else the vanilla page; `GET /assets/<file>` =
`dist/assets/`; `GET /classic` = always the vanilla page. Real mode needs `?port=&code=` in the URL (the launcher adds
them); without them the page runs the demo. Nothing loads from the internet: everything is bundled.

## Layout

| Path | What |
|---|---|
| `src/contract.ts` | types for every server event (`ServerEvent`) and UI message (`UiMessage`) |
| `src/store/` | the whole app state (`types.ts`, starting values in `initial.ts`), the zustand store + transport + `run` recipe helper (`core.ts`), the reducer for every server event (`reducer.ts`), shared state changes used by both reducer and actions (`mutations.ts`), UI actions (`actions.ts`), derived values (`selectors.ts`), the public surface (`index.ts`) |
| `src/bridge.ts` | `connect()` (websocket or demo), `send(msg)` |
| `src/demo/` | the ported in-page demo (`Demo.ts`, data in `data.ts`, the made-up visual options in `visuals.ts`; built-in agent files sit at `app/agents/<folder>/agent.md` and the planner criteria at `app/agents/planner/promotion.md`, as on the server): two runs, the planner and its picker (planner_choice / planner_choose: Claude options, Cursor disabled), CLI chats (also from a plan) and their picker (cli_choice / cli_choose / chat_model), the crew with two folder agents and ticking use counts, a plan whose steps 3-4 name folder agents (steps 1 and 3 name skills, one not found), skills in both folders (d2's `sql-style` is shadowed when d2 is ticked as additional; `DEMO_SKILLS` in data.ts), skill settings and the Additional ticks, agent draft / create / remove, undefined roles (`rolesDemo.ts`: `release-checker` 1 use and not listed, `frontend-dev` -> keep, `copy-editor` -> not yet, `data-migrator` -> one reviewer question then define; the plan's step 2 carries role `frontend-dev`; merge, dismiss, review, decide, define with role).
 Typing "fail" in Draft for me shows the error; a name starting `launchpad-` shows a server problem |
| `src/lib/` | `markdown.ts` (escaped md / docHtml), `format.ts` (usd, tokens, ago, toolCat ...), `storage.ts` (localStorage), `labels.ts`, `hooks.ts` (`useNow`, `useAnimationFrame`) |
| `src/components/` | shared pieces (below); import them from the `components/index.ts` barrel. `Modal.tsx` is the generic modal host (`openModal`); `archiveModals.tsx` holds the report / plan / archive modals built on it. `Header.tsx` is the top bar. Exception: `views/Plan/PlanLog.tsx` imports its components directly, because `archiveModals.tsx` renders `PlanLog` and the barrel would become a cycle |
| `src/theme.css` | the design tokens (see Design system) + all global / shared CSS |
| `src/fonts.css` | the bundled Sora and Inter faces (Latin + Latin Extended woff2 from @fontsource-variable) |
| `src/views/<Name>/` | one folder per screen, each with its own CSS (vanilla class names kept, sizes from the tokens) |
| `src/views/Chat/` | the chat screen (header tab "Plan"): the Planner / CLI switch over `views/Plan` (Planner side) and `views/Code` (CLI side, the former Free Flight tab); both panes stay mounted |
| `src/views/Plan/` | the planner chat (`Plan.tsx`), its log entries (`PlanLog.tsx`) and, under the chat box, the planner picker (`PlannerPicker.tsx`; the Auto answers switch is NOT here any more, it sits beside Autopilot on the plan card, the Orbit run row and each running Missions system): the shared `ModelPicker` (below) plus "Auto-promote to <top model>" + Rules (the criteria, read-only modal) and New plan (with its "Set this plan aside?" confirm). Reads `sel.plannerPickerView`; sends through `actions.choosePlanner` / `setAutoPromote` / `newPlan` |
| `src/components/ModelPicker.tsx` | the CLI-then-model picker under a chat box, one component for both chats: a compact button ("Claude · Sonnet") whose menu opens upward with a "CLI" dropdown (the harnesses, grouped by `sel.pickerHarnesses` from the server's flat options; unavailable ones listed with the server's note, not selectable), then only the shown CLI's models; changing the CLI picks its first model (the menu stays open on its models); the caller may add items after a separator (`extra`). Ids from its `id` prefix: `pk*` (planner), `cpk*` (CLI chat). Styles `.pk-*` in theme.css |
| `src/views/Code/` | the CLI chat (`Code.tsx`): under its box the `ModelPicker` without auto-promote / New plan (`CliPicker`, `#cliControls`), reading `sel.cliPickerView`, sending `actions.chooseCli` (cli_choose); no model chip in the header |
| `src/views/Settings/` | Settings is the fifth full view (header Settings button, `ui.view === 'settings'`; no dialog). Sections in order: `Connections.tsx` (the server's list of connections, id + display name, each with Test -> `connection_test`; shows not tested / testing / not installed / installed but not reachable (with the error) / installed and reachable / installed but Launchpad cannot use it yet; the one place that names "Claude Code" and "Cursor"), `McpLibrary.tsx` (servers with status and tool count, add / edit form: command + arguments + environment variables or URL + headers, secret values masked and sent back unchanged, Test, Remove with a confirm, "Import from <source>" from `mcp_imports`), then Working directories and the general settings in `Settings.tsx`. Reads `st.mcp` / `st.connTests` / `st.mcpImports`; sends through `actions.testConnection` / `saveMcpServer` / `removeMcpServer` / `testMcpServer` / `listMcpImports` / `importMcpServers` / `setAgentMcp`. Demo: `src/demo/mcpDemo.ts` |
| `src/views/Crew/` | Crew hero cards + the definition reader (`Crew.tsx`, with a Skills section: "All skills" / "Choose" checklist via `actions.setAgentSkills`, unknown names greyed, the CLI chat "All (handled by the CLI)") and the Add an agent dialog (`AgentForm.tsx`). `McpPicker.tsx` = the library-MCP picker under Skills on every agent's detail (connected servers only, none ticked by default, an assigned server that is not connected stays listed with a warning, a note when `mcp_supported === false`; the hero card shows an "MCP n" warning chip for assigned servers that are not connected). Undefined roles: `UsedRoles.tsx` = the "Used but not defined" section at the top of the cards (the server's visible roles from `roles_list`: uses, last used, skills, folders, failed / blocked / sent-back markers; Review, Merge with a confirm, Dismiss; a one-line empty state) and `RoleReview.tsx` = the review screen that replaces the cards while `st.roleOpen` is set (progress, the reviewer's question cards, the five tests in fixed order, verdict marked as a recommendation, skill notes, review cost via `usd()`, three decision buttons none pre-pressed, then the define hand-off to AgentForm or a one-line note on when a kept / not-yet role returns). Styles in `Crew.css` |

| `src/views/Aside/`, `src/views/Visuals/` | the right-hand panels shown beside the screens: Aside = Incoming queue, orbit, activity feed, and on the Files tab (`ui.view === 'files'`) `Repos.tsx` instead of orbit + Incoming: the Repos panel (one collapsible card per git repo grouped under its connected folder: branch, status chips Up to date / N ahead / N behind / Changes / Not linked, changed files with tick boxes and +/- counts, "Commit message" box, Commit / Commit and push / Push, Refresh, Check remote; clicking a file opens it in Files via `actions.gitOpenFile`) plus the `WaitingLine` ("N waiting", opens the Plan tab where Incoming shows). Reads `st.git` and `sel.gitGroups` / `gitChips` / `gitIsOpen`; sends through `actions.gitScan` / `gitRefresh` / `gitFetch` / `gitCommit` / `gitPush`; opening the Files tab sends `git_scan`. Demo data: `src/demo/gitDemo.ts`; Visuals = the visual options panel (`frames.ts` builds the sandboxed frames) |
| `src/test/demoApp.tsx` | shared harness for view tests (renders `App` on the demo, helpers `q`, `click`, `sentOf` ...). Tests sit next to what they test: `*.test.ts(x)` beside the component / view / store file |
| `src/App.tsx`, `src/components/Header.tsx`, `src/components/Sidebar.tsx` | shell: header (brand, connection, usage), the left sidebar navigation, all views (kept mounted, `hidden` tab panels), aside, visuals slot, overlays. `Sidebar.tsx` holds `NAV`, the one list of views (label, icon, `group` main | bottom): a new view = one entry there + its slot in `App.tsx` + its name in `View`. Collapsed = icons only (names stay for screen readers, tooltips via `data-tip="text:..."`), kept in localStorage `lp.sidebarCollapsed`; at 1240 px and below it is icons only whatever the choice (no toggle), at 980 px and below it becomes a row above the views |

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
- `ui`: `view` (plan | missions | crew | files | settings), `chatSide` (planner | code: the chat screen's switch; `actions.setChatSide`), `conn`, `demo`, `queueFilter`, `feedRun`/`feedAgent`, `hov`/`sel` (agent highlight), `focus`/`focusScroll`,
  two-click confirms `stopConfirm`/`apConfirm`, `pickerChoosing` (planner_choose sent, until planner_model / planner_choice), `cliChoosing` (cli_choose sent, until cli_choice), `newPlanBusy`, `newChatBusy`, `vis {open, wide, width}`,
  `settingsMsg`/`settingsAddPath`/`picking`, `dirMenu`, `toasts`
- `sessions[id]` (+ `order`, `current`): letter, folder/dirId/cwd, status, meta, roundTag, draft/draftV/draftRev,
  run {name, steps[{n,title,status,built,report_path,agent,agent_display,agent_fallback,agent_purpose}]}, runDraftV/runRev, report, approving, stopping, reportSent,
  cleared, flash/flashN, autopilot, codeSending/codeSentV (Send plan to CLI), planner fields (plannerId, plannerStatus, plannerModel, promoted, promoting; from planner_model: plannerHarness, plannerStart, plannerTop, plannerLabel, plannerOption, plannerStarted, plannerAuto, switchableTo),
  visualSets[{set_id, brief, options (each with `drawn_with`), picked_id, pending, `library` (asked for; null = not asked),
  `drawn_with` (used), `libraries` (available for the folder), `library_note` ("drawn in ECharts, styled like X" on a fallback)}], visSel, visSeen, `log` (planner chat), `typing`
- `sessions[id].autoAnswers` = the Auto answers switch (server state: `auto_answers` event / snapshot `auto_answers`); it is for builders only. An `auto_answer` event (a builder's question decided with its own recommendation) settles that Incoming card in place, or adds a settled `decided` queue item (compact line marked "Auto", "Decided by the Builder (Auto answers on)"); never a planner-chat entry. `queue_resolved` by `auto` does the same
- planner `log` entries: `auto {agent, step, title, answer}` · `bubble {who, text}` · `sys {text, cls?: promo|err}` · `visnote {text, setId}` (has a Show
  button: `actions.visShowSet`) · `round {roundId}` (data in `rounds[roundId]`) · `plancard {draft, draftV, rev, state}`
  (use `sel.planCardView(s, entry)` for approved / superseded / button label / status line). `preLog`/`preTyping` =
  lines before any session exists.
- `rounds[id]`: questions, answers, sent, actionsHidden
- `plannerChoice`: the last planner_choice (options with `available` / `note`, `choice` = what the next new plan starts on, `auto_promote`, `top_model` / `top_label`, `promotion_off`, `pinned`, `rules`). `sel.plannerPickerView` combines it with the current session: the button label, the CLIs for the dropdown (`harnesses`, `harness` = the one shown on open), each model item's hint ("promote this plan · costs more", "from your next new plan", "not available yet"), the "applies to your next new plan" note
- `cliChoice`: the last cli_choice (same options, `choice` = what the next new chat starts on). `sel.cliPickerView` combines it with the open chat: before its first message a pick applies at once; after it, items say "from your next new chat" and the note "<choice> applies to your next new chat; this chat keeps <label>"
- `agents[agent_id]` (agent_usage records), `acts` (activity, oldest first, max 600; `sel.feedRows` = newest first),
  `lastAct`, `tokens`/`cost`/`usageEv`/`byRole` (the server's app usage), `chatTotals[chat_id]` (usage scope chat), and per session `total` / `plannerCost` / `crewAgents` / `crewTok` / `stepTotals` (usage scope session, snapshot, run_finished). Cost totals are summed on the server only (`app/costs.py`): the page adds nothing up (`sel.sessionTotal`, `plannerCostOf`, `crewCountOf`, `crewTokensOf`, `stepTotalsOf`, `appTotals`, `chatUsage` just read these); the one cost formatter is `usd()` in `lib/format.ts` (`{ approx: true }` = the header's "~$1.23"). The in-page demo does its own arithmetic
- `queue`: Incoming cards in arrival order, `ui: open|sent|timedout|autopilot|auto|ended`, `leaving` while fading;
  kind `report` cards are added by run_finished (id `report:<session_id>`). Order with `sel.orderedQueue`.
- CLI chats: `chats[id]` {mode, model, harness, label, optionId, written (someone wrote to it: CLI and model fixed; from chat_started / chat_model `started`, or a message the page sent), cwd, dirId, busy, log, streamId, typing, agentIds}, `chatOrder`,
  `currentChat`, `chatPending`, `codeModePref`, `chatFromPlan` (session whose plan was sent; its `chat_started` keeps Plan mode,
  also matched by `from_session_id`), `chatItems[id]` (inline cards, `ui: open|sent|done`, `result`).
  Chat `log` entries: `bubble {who, text, streaming?}` · `sys {text, cls?}` · `tool {act}` · `card {itemId}`.
- Crew: `crewDefs` (crew_list agents with `purpose`, `uses`, `builtin`, `step_worker`, `skill_setting` "all" | [names] | "cli"), `crewSkills` (crew_list.skills: found in the folder + the additional folders, `shadowed` marked), `crewLoading`, `crewDirId` (crew_list.dir_id),
  `crewDirPick` (folder picked in Crew, sent as `get_crew {dir_id}`), `toolChoices`, `crewUses[name]` (live from `agent_uses`),
  `crewForm` {open, fields, problems, error, saving, draftText, drafting, draftError, drafted, role, cost} (role = the tally role being defined: agent_draft / agent_create carry it, the title reads "Define an agent", `cost` = the drafting call's usage shown with the draft), `crewRemoving`, `crewError`, `crewFlash`.
  Purposes are planning, exploring, building, reviewing and other (`PURPOSES` in `lib/labels.ts`; a folder agent with a missing or unknown purpose is Other and gets its own Crew section; Other is addable in the form and guarded like building by the server). The CLI chat's card shows the CLI and model actually chosen (`sel.crewModel`, from `cli_choice`).
  Selectors: `sel.purposeOf`, `crewModel`, `isBuiltin`, `usesOf`, `crewDir`, `stepAgent(defs, step)` (null = the Builder; `fallback` when
  `agent_fallback`; colour from the step's `agent_purpose`, else `defsForSession` = the crew list only when it lists the session's own folder), `agentFormProblems`, `problemField` / `problemText` (server problems -> form fields), `plannerWaiting` / `codeWaiting`.
- Undefined roles (`store/roles.ts` handles the events): `roles {loaded, threshold, resurface, entries}` (the last `roles_list`; `sel.visibleRoles` = the ones to show, `sel.roleMarkers` counts the listed failed / blocked / sent-back uses), `reviews[role]` {reviewId, status starting | running | case | failed | refused, model, progress lines, phase, case, error, deciding, decided {decision, reviewerVerdict}, saved {agent, casePath}} (one per role, so the screen outlives the role leaving the list), `roleOpen` (the role whose review screen shows in Crew). Actions: `roleReview` (open + `review_start`; a case still waiting for a decision is just shown), `roleDecide` (`review_decide`; define also sends `agent_draft` with the role and the form opens filled on `agent_drafted`), `roleDraft`, `roleOpenForm`, `roleDismiss`, `roleMerge`, `openRole` / `closeRole`. The reviewer's questions are queue items with `review_id` / `role` / `test` and no session: Incoming labels them with a role chip and an "Open review of <role>" button; the review screen shows the same cards (`QueueCard` exported from `views/Aside/Incoming.tsx`, `scope="review"` gives them their own ids). `sel.roleRestNote` and `sel.relPath` (a case path always shown relative) are display helpers; nothing is decided here
- `mcp {loaded, servers, assignments, connections, importSources, error}` (the last `mcp_library`; the lists of connections and import sources are the server's), `connTests[id]` (testing | done + the `connection_test` answer), `mcpImports[source]` (loading | candidates). Selectors `sel.mcpConnected`, `mcpAssigned`, `mcpProblems`
- `settings {directories, values, can_pick}`; each directory has `is_default` (the primary) and `is_additional` (ticked: joins new sessions and chats). Actions: `makeDefaultDir` ("Make primary"), `setAdditionalDir(dirId, on)` (sends the whole `additional_dir_ids` list)
- Run / draft steps may carry `skills` and `skills_unknown` (plan-step skills; the plan card shows them as chips, unknown ones greyed) and `role` (the role the step runs under: a "Role: <name>" chip with its own icon on the plan card, tooltip "This step runs on the Builder under the role name ...")
- `git` (Repos panel): `available` (null until answered, false = git not installed), `loaded`, `scanning`, `repos` (git_repos, each replaced by its git_result), `busy[repoId]` (operation in flight), `error` / `note` (git's text / success note per repo), `unticked[repoId]` (everything is ticked by default, new files too), `message[repoId]` (commit message being typed), `open[repoId]` (card opened by hand; default open while it has changes or something to report)
- `fx` (File Explorer: cache, loading, err, open, sel, raw, collapsed, width; persisted to localStorage) · `files`
  (file_content per `root|path`) · `editor` (pen editor: text, dirty, banner, conflict, pane, backups ...)

Not in the store (view-local animation): orbit body positions, solar-system ships/trails/pings. For pings use
`onActivityPing((act, isNew) => ...)` (returns an unsubscribe).

## Shared components (`src/components`)

`Markdown` (the only `dangerouslySetInnerHTML`; `doc` for YAML-headed files; `label` = aria-label, makes it a named
region) · `Pill` (button: `variant`, `size` md | sm | xs, `icon`; an icon with no label = round icon button, needs
`aria-label`) · `Tag` (kind tag with its icon), `Chip`, `Letter`, `Status`, `Empty` (`icon`, `title`, one line),
`Loading` (spinner line), `Badge`, `SunIcon`, `DirChip` · `ChatBubble` (long user text folds with Show all; `plan` = the plan sent to the CLI, folded and formatted), `SysLine`, `TypingDots` · `Card`, `ViewFrame`
(vhead look) · `AutopilotSwitch` (role=switch) · `PenButton` (opens the editor) · `Dialog`, `DialogTitle`, `DialogX`
(the dialog primitive, below; `Modal.tsx`) · `openModal`/`closeModal` (generic modal; actions may be a function for live labels and
may carry an `icon`) · `openReport`, `openPlan`, `openArchive` (read-only planning chat: the real `PlanLog` inside
`.msgs.archived`, whose CSS hides buttons and forms) · `DirMenu` via `actions.chooseDir(anchorEl, dirId => ...)` · `PurposeTag` (purpose label + icon in its colours) and `StepAgent` (the agent on a plan step, or the coral Builder-fallback chip), `PURPOSE_ICON` ·
`TipHost` (put `data-tip="planner|cursession|allagents|chat|run:<sid>|agent:<id>|step:<n>:<sid>"` on any element, or
`data-tip="text:Short label"` for a plain label) · `data-hover-agent="<agent_id>"` sets the shared hover highlight
`ui.hov` (feed rows, stars and ships all carry it; pinning from Missions scrolls `#feedList [data-hover-agent]` rows) ·
`Toasts` (`actions.toast`) · `Tooltip.tsx` is `TipHost` and its `tipContent` · `ModelPicker` (the CLI-then-model picker under both chat boxes; see Layout) · `icons.ts` (the icon set).

Two-click confirms with a 4 s window live in the store (`toggleAutopilot`, `stopRun`); the picker's
"New plan → Set this plan aside?", Settings "Confirm remove" and Crew "Confirm remove" (folder agents) confirms are local to their views. Promotion by hand is picking the top model in the planner picker (one click; the item says it costs more).

## Design system (polish pass, Nov 2026)

Same Orbit look as the vanilla page: the colour tokens and fonts are unchanged; everything else is a token so screens
stay consistent. Rule: never write a colour, spacing, radius, font size or shadow as a number in a view's CSS; use a
token. Raw `px` only for hairlines (1px), layout widths / heights and alignment offsets. The one hard-coded colour outside
`:root` is the feed select's chevron (a data-URI SVG cannot read CSS variables; it is `--muted`).

**Tokens** (`:root` in `src/theme.css`)

| Group | Tokens |
|---|---|
| Colour (Orbit, unchanged) | `--bg --card --ink --muted --line --line2 --indigo --indigo-dk --indigo-soft --indigo-ink --lilac --moon --coral --coral-soft --coral-ink --green --green-soft --green-ink` |
| Agent purposes | `--purpose-planning` / `-exploring` / `-building` / `-reviewing` / `-other` (green), each with `-soft` and `-ink` (Okabe-Ito based hues toned to Orbit: indigo, sky blue, amber, plum; always shown with a label and an icon too). Put `data-purpose="<purpose>"` on an element and use `--pc` / `--pc-soft` / `--pc-ink` inside it |
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
- Tabs: the sidebar is a vertical WAI-ARIA tablist (`role=tab`, `aria-selected`, roving tabindex, Up / Down / Home / End; Settings is the last tab, shown at the bottom);
  each view slot in `App.tsx` is its `role=tabpanel`.
- Menu: `DirMenu` is `role=menu` with `menuitem`s (Up / Down / Home / End; Esc returns focus to the opener). The model pickers (`ModelPicker`, planner and CLI chat) are `aria-haspopup=menu` on their button (Up / Down on it open the menu on the current choice) and a `role=menu`: the "CLI" dropdown is a `menuitem` with `aria-haspopup=menu` / `aria-expanded` whose nested `role=menu` (opened inline, so the menu's scroll box never clips it) holds one `menuitemradio` per CLI (unavailable ones `aria-disabled`, still focusable; Enter / Space / Right open it, Left or Esc close it and focus returns to the dropdown); then the model `menuitemradio`s, and in the planner's a `menuitemcheckbox` (auto-promote), Rules and New plan `menuitem`s; Up / Down / Home / End and Tab / Shift+Tab reach every item, Esc or a click outside closes the menu and focus returns to the button.
- Switch: `AutopilotSwitch` and `AutoAnswersSwitch` are `role=switch` with `aria-checked`, shown side by side (the two are told apart: Auto answers has its own label, a `CircleHelp` icon from `components/icons.ts`, an `aria-label` and a tooltip saying it answers builders' questions with their own recommendation and that Autopilot is the one for permission requests). The chat screen's Planner / CLI switch is a two-tab `role=tablist` (Left / Right / Home / End); each tab's label says when its side is waiting on you (coral count) or working (dot).
- Crew: cards are buttons (aria-label sums up purpose, source, model, uses); opening one moves focus to the detail heading, "All agents" returns it to the card. The Add an agent dialog marks invalid fields with `aria-invalid` + `aria-describedby` to the inline message and focuses the first one after a failed save.
- Tooltips: `TipHost` shows on hover and on keyboard focus, sets `aria-describedby="tip"` on the focused element, Esc
  hides it; `text:` labels appear after 350 ms. Text with a tip that is not a button gets `tabIndex={0}`.
- The feed filters stay native `<select>` (styled, with a chevron).
- The Missions activity feed takes at most about a third of the right-hand panel (`.feed` in `views/Aside/Aside.css`, `max-height:34%`); its list scrolls inside it and Incoming gets the rest.

**States**: `Empty` (icon + title + one line) for empty screens and lists, `Loading` for anything waiting on the back
end, `.warn` for errors, and a coral bar under the header when the connection is lost. Titles wrap
(`overflow-wrap:anywhere`), one-line meta truncates with an ellipsis. Scrollbars are thin, `--line2` on transparent.

**Layout**: holds from 980 to 1920 px wide (pywebview opens at 1360 x 880, minimum 980 x 640). The header (brand, connection, usage, avatar) stays on one
row: the usage pill truncates (the full figures are in its tooltip); the section navigation is the left sidebar. At 1240 px and below the sidebar is icons only, the "Whole app"
label and the connection text are hidden (still announced) and the aside narrows to 360 px.

**Fonts and security**: Sora and Inter are bundled (`src/fonts.css`), nothing loads from the internet and the page CSP
in `app/server.py` (`font-src 'self'`) did not change. Radix uses inline styles, which that CSP already allows. The
Visuals frames keep their own CSP and sandbox (`views/Visuals/frames.ts`); the polish pass did not touch them.

## Where each vanilla screen is (`prototype/launchpad-orbit.html`)

| Screen (task) | HTML | JS | CSS now in |
|---|---|---|---|
| Plan chat (2a) | 647-670 | 1209-1616, model 1617-1667, autopilot 1669-1698 | theme.css (chat, rounds, plan cards), `views/Plan/Plan.css` |
| Aside: Incoming, orbit, activity feed (2a) | 738-763 | queue 1700-1878, orbit 1880-1985, feed 2321-2404 | `views/Aside/Aside.css` |
| Free Flight (2b), now the chat screen's CLI side | 672-698 | 2429-2676 | `views/Code/Code.css` (switch: `views/Chat/Chat.css`) |
| Visuals panel (2b) | 764-779 | 2678-2972 | `views/Visuals/Visuals.css` |
| Missions (2c) | 700-707 | 2109-2320, 2394-2427 | `views/Missions/Missions.css` |
| Crew (2c), now hero cards + Add an agent | 709-723 | 3324-3400 (the reader) | `views/Crew/Crew.css` |
| Files + pen editor (2c) | 725-736, 784-792 | 3081-3192, 3227-3322 | `views/Files/Files.css` |
| Settings (2c) | (modal) | 2990-3063 | `views/Settings/Settings.css` |
| Event handling (done, in the store) | | 1063-1103 and the on*() handlers | |
| Demo (done, `src/demo`) | | 3458-4268 | |
