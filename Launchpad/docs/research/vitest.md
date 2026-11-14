# Vitest

- Used for: zero-back-end tests of the front-end store and the in-page demo (`frontend/src/store/store.test.ts`, `npm test`). Python tests stay in `tests/` (pytest).
- Version: vitest 5.1.0 (configured in `frontend/vite.config.ts` under `test`, node environment, no DOM).
- Links: https://vitest.dev/guide/ · https://vitest.dev/api/vi.html#vi-usefaketimers
- Gotchas
  - `vi.useFakeTimers()` + `vi.advanceTimersByTime()` drive the demo's scripted timeline in milliseconds.
  - `vite.config.ts` needs `/// <reference types="vitest/config" />` for the `test` key to type-check.
  - Console output from passing tests may not show; write to a file when debugging.
  - The render smoke test (`src/App.test.tsx`) runs in happy-dom (`// @vitest-environment happy-dom`, dev dependency 21.0.4) with `createRoot` + `act`. Server rendering (`renderToString`) is no good for store-driven views: zustand returns its initial state as the server snapshot.
