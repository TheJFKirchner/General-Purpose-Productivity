# Fontsource (Inter, Sora)

- Used for: bundling the two Orbit fonts so they show on every machine with nothing fetched from the internet. `frontend/src/fonts.css` declares the faces; Vite copies the woff2 files into `dist/assets` (served by `app/server.py` from the same origin, CSP `font-src 'self'`).
- Packages: @fontsource-variable/inter and @fontsource-variable/sora 5.x (SIL Open Font License 1.1).
- Links: https://fontsource.org/fonts/inter · https://fontsource.org/fonts/sora · https://fontsource.org/docs/getting-started/variable
- Gotchas
  - The package CSS (`wght.css`) pulls in every subset (Cyrillic, Greek, Vietnamese...), and Vite would copy all of them into `dist`. `fonts.css` names only the Latin and Latin Extended files (about 180 KB total; the browser downloads Latin Extended only if a page uses those characters).
  - The faces are declared under the plain names `Inter` and `Sora`, so the `--body` / `--disp` tokens did not change.
  - The `url()`s point into `node_modules` with a relative path; Vite resolves and hashes them at build time.
