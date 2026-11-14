# Vite (+ React plugin, TypeScript)

- Used for: building the React front end in `frontend/` to static files in `frontend/dist/`, served by `app/server.py`; `npm run dev` for local work with the in-page demo.
- Versions (2026-11-13): vite 8.3.8 (Rolldown-based), @vitejs/plugin-react 6.3.0, typescript pinned ~5.9.3, react / react-dom 19.3.
- Links: https://vite.dev/guide/ · https://vite.dev/config/shared-options.html#base · https://vite.dev/guide/build.html · https://github.com/vitejs/vite-plugin-react
- Gotchas
  - `base: './'` makes `index.html` reference `./assets/...`, so the page works from `/` on any port without templating.
  - Output is a flat `dist/assets/` with hashed names; the server serves only plain file names from there with explicit content types (Windows can map `.js` to `text/plain`, which `nosniff` then blocks).
  - The page CSP (`script-src 'self' 'unsafe-inline'`) is fine for the build: one module script + one stylesheet, no inline code. The dev server is not served through Python, so the CSP does not apply there.
  - plugin-react 6 lists babel / oxc / react-compiler as optional peers; none are needed.
  - TypeScript 7 (the native port) was the npm "latest"; 5.9 is pinned to keep `tsc --noEmit` predictable.
