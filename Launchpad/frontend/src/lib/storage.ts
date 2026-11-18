/* localStorage helpers: JSON in and out, never throw (storage may be off). Keys used by the app:
   - lp.files       File Explorer: open folders, selected file, raw/formatted, tree width, collapsed (see store)
   - lp.editorView  pen editor layout: side | edit | preview
   - lp.sidebarCollapsed / lp.asideClosed  the left sidebar and the right-hand panel (below)
   - lp.usageChart  the Usage chart's form: line | bar */
export const LS_FILES = 'lp.files';
export const LS_EDITOR_VIEW = 'lp.editorView';
/** Sidebar navigation: true = collapsed to icons only. */
export const LS_SIDEBAR = 'lp.sidebarCollapsed';
/** Right-hand panel (In orbit / Incoming, Repos on the Files tab): true = closed to a slim strip. */
export const LS_ASIDE = 'lp.asideClosed';
/** Usage chart form: 'line' (default) | 'bar'. */
export const LS_USAGE_CHART = 'lp.usageChart';

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
