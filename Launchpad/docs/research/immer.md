# Immer

- Used for: writing the store's reducer and actions as plain mutations on a draft (the vanilla handlers ported almost line for line) while the store stays immutable (`frontend/src/store/core.ts` `run()`).
- Version: immer 11.2.10.
- Links: https://immerjs.github.io/immer/ · https://immerjs.github.io/immer/freezing
- Gotchas
  - Auto-freeze is on: anything put into the state is frozen. Code that keeps its own copy and mutates it later (the demo's agent records, `by_model`) must emit copies, not shared references.
  - A recipe that returns a value replaces the state; `run()` wraps recipes so their return value goes to the caller instead.
  - The state uses plain keyed objects, not Map/Set (no `enableMapSet()` needed, JSON-like data).
