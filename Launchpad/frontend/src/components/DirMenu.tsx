/* "Run it in which folder?" menu, opened by actions.chooseDir(anchorEl, cb) when more than one folder is connected.
   A keyboard menu (role=menu / menuitem): focus starts on the first folder, Up / Down / Home / End move, Esc or a
   click outside closes, and focus goes back to the button that opened it. */
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent as RKeyboardEvent } from 'react';
import { actions, getState, useLaunchpad } from '../store';
import { baseName } from '../lib/format';
import { Folder } from './icons';

export function DirMenu() {
  const anchor = useLaunchpad(st => st.ui.dirMenu);
  const settings = useLaunchpad(st => st.settings);
  const ref = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const dirs = (settings ? settings.directories : []).slice().sort((a, b) => (b.is_default ? 1 : 0) - (a.is_default ? 1 : 0));

  useLayoutEffect(() => {
    if (!anchor || !ref.current) {
      setPos(null);
      /* closed: give focus back to the opener when it was inside the menu (or nowhere) */
      const o = opener.current; opener.current = null;
      if (o && o.isConnected && (document.activeElement === document.body || !document.activeElement)) o.focus();
      return;
    }
    if (!opener.current) opener.current = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : null;
    const m = ref.current;
    setPos({
      top: Math.min(anchor.bottom + 6, innerHeight - m.offsetHeight - 8),
      left: Math.max(8, Math.min(anchor.right - m.offsetWidth, innerWidth - m.offsetWidth - 8)),
    });
    m.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus();
  }, [anchor]);

  useEffect(() => {
    if (!anchor) return;
    const down = (e: PointerEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) actions.closeDirMenu(); };
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { opener.current?.focus(); actions.closeDirMenu(); } };
    document.addEventListener('pointerdown', down, true);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('pointerdown', down, true); document.removeEventListener('keydown', key); };
  }, [anchor]);

  /* after a pick the opener is often gone or disabled ("Starting…", or Missions hidden by the switch to Plan):
     focus the message box of the tab that is showing, else the opener when it can still take focus */
  const pick = (dirId: string) => {
    const o = opener.current;
    actions.pickDirFromMenu(dirId);
    setTimeout(() => {
      const { view: v, chatSide } = getState().ui;
      const box = document.getElementById(v === 'plan' ? (chatSide === 'code' ? 'codeInput' : 'msgInput') : '');
      const target = box && box.offsetParent !== null ? box : o && o.isConnected && !(o as HTMLButtonElement).disabled && o.offsetParent !== null ? o : null;
      target?.focus();
    }, 0);
  };

  const onKey = (e: RKeyboardEvent<HTMLDivElement>) => {
    const items = [...(ref.current?.querySelectorAll<HTMLButtonElement>('button[role="menuitem"]:not(:disabled)') || [])];
    if (!items.length) return;
    const k = items.indexOf(document.activeElement as HTMLButtonElement);
    let next = -1;
    if (e.key === 'ArrowDown') next = (k + 1) % items.length;
    else if (e.key === 'ArrowUp') next = (k - 1 + items.length) % items.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = items.length - 1;
    else if (e.key === 'Tab') { e.preventDefault(); actions.closeDirMenu(); return; }
    if (next >= 0) { e.preventDefault(); items[next].focus(); }
  };

  return (
    <div className="dirmenu" ref={ref} role="menu" aria-label="Run it in which folder?" hidden={!anchor} onKeyDown={onKey}
      style={pos ? { top: pos.top, left: pos.left } : undefined}>
      <div className="dm-h" aria-hidden="true">Run it in which folder?</div>
      {dirs.map(d => (
        <button key={d.dir_id} type="button" role="menuitem" disabled={d.exists === false} onClick={() => pick(d.dir_id)}>
          <Folder />
          <b>{d.name || baseName(d.path)}</b>
          {d.is_default ? <span className="chip ok">Default</span> : null}
          {d.exists === false ? <span className="chip warnc">Missing</span> : null}
          <small>{d.path}</small>
        </button>
      ))}
    </div>
  );
}
