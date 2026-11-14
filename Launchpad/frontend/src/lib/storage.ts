/* localStorage helpers: JSON in and out, never throw (storage may be off). Keys used by the app:
   - lp.files       File Explorer: open folders, selected file, raw/formatted, tree width, collapsed (see store)
   - lp.editorView  pen editor layout: side | edit | preview */
export const LS_FILES = 'lp.files';
export const LS_EDITOR_VIEW = 'lp.editorView';

export function lsGet<T>(key: string, fallback: T): T {
  try {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(key);
    if (raw == null) return fallback;
    return (JSON.parse(raw) as T) ?? fallback;
  } catch { return fallback; }
}

export function lsSet(key: string, value: unknown): void {
  try { if (typeof localStorage !== 'undefined') localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage off */ }
}
