# lucide-react

- Used for: the front end's one icon set. Every icon is imported through `frontend/src/components/icons.ts` (tree-shaken: only those names are bundled).
- Version: lucide-react 1.x (ISC licence).
- Links: https://lucide.dev/icons/ · https://lucide.dev/guide/packages/lucide-react
- Gotchas
  - Size and stroke are set in CSS (`.lucide` in `theme.css`), not with the `size` prop, so buttons and chips scale icons by context.
  - Icons render with `aria-hidden="true"`; an icon-only button needs `aria-label` (and `data-tip="text:..."` for a hover label).
  - Icons are SVG with no text, so `textContent` of a button stays its label (the tests rely on that).
  - Older alias names (`AlertTriangle`, `Loader2`) still exist in 1.x; check new names on lucide.dev before adding.
