# Zustand

- Used for: the front end's single app store (`frontend/src/store/core.ts`). Chosen over React context + reducer because the bridge and the in-page demo must read and change state outside React, and components can subscribe to one slice.
- Version: zustand 5.1.0.
- Links: https://github.com/pmndrs/zustand · https://zustand.docs.pmnd.rs/
- Gotchas
  - v5 uses `useSyncExternalStore`: a selector that returns a new object or array on every call loops ("getSnapshot should be cached"). Select stored values only; derive with `useComputed(fn)` (memoised on the state object) in `src/store/index.ts`.
  - All changes go through `run(recipe)` (immer `produce` + `setState(next, true)`), never `setState` with partial objects from views.
  - A tiny second store holds the generic modal (React nodes and callbacks stay out of the immer state).
