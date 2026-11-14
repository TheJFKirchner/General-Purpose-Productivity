# React port of the front end, then a visual polish pass

Status: built
Date: 2026-11-13

Built as planned, with these differences: state uses Zustand + immer; the polish pass added three small things beyond restyling (a "Go to Plan" button on the empty Missions screen, a bar shown when the connection drops, an X button on dialogs); the seven small gaps the port left were closed at the start of the polish task.

The Launchpad front end is one vanilla file, `prototype/launchpad-orbit.html` (about 4,275 lines: 615 CSS, 170 HTML, 3,480 JS). This feature ports it to React + Vite + TypeScript in `frontend/`, served by the same Python server inside the same pywebview window, with the same look and behaviour. Once the port is checked, a separate second pass makes the UI look more professional while keeping the Orbit theme. The Python back end and the websocket contract do not change.

James approved building this while away ("plan this migration out and make the changes"), so there was no interview. The assumptions below stand in for it and are his to correct.

## Assumptions

1. The port is like-for-like: same screens, same behaviour, same websocket messages. No features added or removed in the port itself.
2. The websocket contract in the `app/server.py` header stays authoritative and unchanged. The front end remains display + input only.
3. Source lives in `frontend/`; the build goes to `frontend/dist/` and is kept in the project ([2026-11-08-foundation.md](2026-11-08-foundation.md), App stack: built files are committed so coworkers need Python only, never Node).
4. `GET /` serves `frontend/dist/index.html` when it exists and falls back to the vanilla file when it does not. The vanilla page stays reachable at `GET /classic` for comparison. `prototype/launchpad-orbit.html` is not edited or deleted.
5. The page still gets its port and access code from the URL query (`?port=&code=`). No templating.
6. The page CSP stays as it is. Nothing is fetched from the internet at run time: every library and font is bundled by Vite and served from the same origin.
7. The in-page demo (runs when the URL has no port and code) is ported too, so `npm run dev` works without the back end.
8. The visual sidecar keeps its security model exactly: sandboxed `srcdoc` iframes, their own meta CSP, ECharts inlined from `/vendor/echarts.min.js`, the navigation guard.
9. Model text is never put into the DOM unescaped. The markdown function is ported with its escaping, and its output is the only use of `dangerouslySetInnerHTML`.
10. State is one typed store (React context + reducer, or Zustand; the foundation builder picks). No router: the tabs are state.
11. Polish pass: same Orbit colour tokens and fonts (Sora, Inter), same layout. Allowed: spacing / radius / type scales as tokens, an icon set, accessible primitives for dialogs, tooltips, menus and tabs, bundled fonts, focus, hover, empty and loading states. Not allowed: a new colour scheme, moving screens around, or a component library that brings its own look.
12. Launchpad is not a git repo, so there is no feature branch, no commit and no security review. The untouched vanilla file is the fallback.

## Shared interface (tasks 2a to 2c build to this; task 1 creates it)

- `frontend/src/contract.ts`: TypeScript types for every server-to-UI event and UI-to-server message, taken from the `app/server.py` header.
- `frontend/src/store/`: the whole app state and a reducer that handles every server event. View builders read state through hooks and do not add event handling of their own.
- `frontend/src/bridge.ts`: `connect()`, `send(message)`, demo switch.
- `frontend/src/demo/`: the ported in-page demo.
- `frontend/src/lib/`: markdown (escaped), formatting helpers, localStorage helpers.
- `frontend/src/components/`: shared pieces (modal, toasts, tooltip, buttons, cards, chat bubble).
- `frontend/src/theme.css`: the `:root` tokens copied unchanged, plus global styles.
- `frontend/src/views/<Name>/`: one folder per screen, each with its own CSS file. Task 1 leaves a placeholder component in each.

## Tasks

### 1. Foundation
- Goal: a building, running React app shell with all state, the bridge, the demo and the shared pieces in place, and the server serving it.
- Builder: factory-builder, Opus.
- Owns: `frontend/` (all of it at this stage), `app/server.py` (page and asset routes only), `tests/` (new tests for the routes), `.claude/launch.json` if needed.
- Read: `prototype/launchpad-orbit.html` (state 1031, Bridge 1046 to 1103, Demo from about 3459, CSS 8 to 622), `app/server.py` header and routes 120 to 186, the App stack and UI direction decisions (now [2026-11-08-foundation.md](2026-11-08-foundation.md) and [2026-11-08-orbit-ui-direction.md](2026-11-08-orbit-ui-direction.md)) and the ECharts and frames lines of [2026-11-13-visual-sidecar.md](2026-11-13-visual-sidecar.md), `tests/test_fixes.py` 80 to 93.
- Done when: `npm run build` succeeds with no TypeScript errors; `python -m pytest` passes; `python -m app.launch --fake --no-window --port 8766 --code dev` serves the React shell at `/` with nav, the right-hand aside frame and placeholder views; `/classic` serves the vanilla page; `/` falls back to the vanilla page when `frontend/dist` is missing; the store handles every server event in the contract; the in-page demo drives the store.
- Runs: first, alone.

### 2a. Plan screen and the right-hand aside
- Goal: Plan view (planner chat, question rounds, plan draft cards, approve / send back, planner model control), Activity feed, "In orbit" SVG, Incoming queue.
- Builder: factory-builder, Opus.
- Owns: `frontend/src/views/Plan/`, `frontend/src/views/Aside/`.
- Runs: after 1, in parallel with 2b and 2c.

### 2b. Free Flight and the Visuals panel
- Goal: Free Flight chat (permission, plan and question cards, modes, interrupt) and the visual sidecar panel with its sandboxed frames.
- Builder: factory-builder, Opus.
- Owns: `frontend/src/views/Flight/`, `frontend/src/views/Visuals/`.
- Runs: after 1, in parallel with 2a and 2c.

### 2c. Missions, Crew, Files, Settings
- Goal: Missions (animated systems per run), Crew reader, File Explorer with the markdown editor modal, Settings modal.
- Builder: factory-builder, Opus.
- Owns: `frontend/src/views/Missions/`, `frontend/src/views/Crew/`, `frontend/src/views/Files/`, `frontend/src/views/Settings/`.
- Runs: after 1, in parallel with 2a and 2b.

Done for 2a to 2c: every control and state the vanilla screen has exists in the React one and sends the same messages; `npx tsc --noEmit` is clean; nothing outside the owned folders is changed (a gap in the shared interface is reported, not patched). These builders do not run `npm run build`; the orchestrator builds once after all three.

### 3. Test the migration
- Build once, run `python -m pytest`, open the fake demo and compare each screen with `/classic`. Defects go back to the builder that owns the screen (one fix round).

### 4. Polish pass (separate from the port)
- Goal: a more professional look on the same Orbit theme, within assumption 11.
- Builder: factory-builder, Opus, UI.
- Owns: `frontend/` (styles and components; no behaviour or contract changes).
- Done when: build and tests pass; spacing, radius and type sizes come from tokens; icons are consistent; dialogs, tooltips and tabs are keyboard-usable with visible focus; fonts are bundled; every screen has sensible empty and loading states; colours are the existing tokens.
- Runs: after 3.

### 5. Review
- `factory-ui-reviewer` once on the fake demo, then at most one fix round. Update `CLAUDE.md` and the decisions (then one combined file; now the `## Decisions` section below) to describe the new front end.

## Decisions

Recorded in the former combined decisions file as "React front end (2026-11-13; built while the user was away, on recorded assumptions: Features/2026-11-13-react-port.md)".

- The front end is now `frontend/`: React + Vite + TypeScript, built to `frontend/dist/` (kept in the project, so running the app needs Python only; run `npm run build` in `frontend/` after any front-end change)
- Serving: `GET /` = `frontend/dist/index.html` when it exists, else the vanilla page; `GET /assets/<file>` = the build's hashed files; `GET /classic` = the vanilla page, always. Port and access code still come from the URL query. Page CSP unchanged
- `prototype/launchpad-orbit.html` is kept as the reference and fallback and is no longer updated; new UI work goes in `frontend/`
- State: Zustand + immer, one reducer for every server event (`src/store/`); views only read state and call actions. The in-page demo (no port / code in the URL) is ported, so `npm run dev` works without the back end
- Visual frames: same security model as before (sandboxed srcdoc iframes, own meta CSP, ECharts inlined, navigation guard)
- Look: same Orbit colours, fonts and layout; spacing / radius / type / shadow / motion tokens in `src/theme.css`; icons = lucide-react; dialogs = @radix-ui/react-dialog (unstyled); Sora and Inter bundled (@fontsource-variable, Latin). Nothing fetched from the internet at run time
- Front-end tests: vitest + happy-dom (`npx vitest run` in `frontend/`)
- Library notes: docs/research/ (vite, zustand, immer, vitest, lucide-react, radix-dialog, fontsource)
