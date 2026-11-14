# Radix UI Dialog

- Used for: every modal in the front end (shared modal, pen editor, Settings) through one wrapper, `frontend/src/components/Dialog.tsx`. Gives focus trap, Esc, outside click, `aria-modal`, scroll lock and hides the rest of the page from screen readers. Unstyled: all looks come from `theme.css` (`.scrim`, `.modal`).
- Version: @radix-ui/react-dialog 1.3.x (React 19).
- Links: https://www.radix-ui.com/primitives/docs/components/dialog
- Gotchas
  - Every `Dialog.Content` needs a `Dialog.Title` (else a console.error, which fails the vitest runs that count errors). Pass `aria-describedby={undefined}` when there is no Description (else a warning).
  - Without a `Dialog.Trigger`, Radix returns focus to nothing on close (it focuses its trigger ref). The wrapper records the focused element in `onOpenAutoFocus` and focuses it again in `onCloseAutoFocus`.
  - Content sits inside the Overlay (the "scrollable overlay" pattern), so the Overlay keeps the old `#scrim` / `#edScrim` ids and `.scrim.open` classes the tests use. When closed nothing is rendered.
  - Only `[data-state=open]` has an animation, so closing unmounts at once (Presence waits for an exit animation only if one is set).
  - Esc is handled by the topmost Radix layer only (editor over the report modal works). The editor keeps its own window-capture Esc handler (asks once when dirty) and prevents Radix's.
  - Uses inline styles (pointer-events, scroll lock): allowed by the page CSP (`style-src 'unsafe-inline'`). Works in happy-dom.
