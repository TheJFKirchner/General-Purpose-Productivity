/* Left sidebar: the section navigation (WAI-ARIA tabs, vertical: role=tablist / tab, aria-selected, aria-controls the
   panel in App.tsx, roving tabindex, Up / Down / Home / End; tabs are state, no router). The working views sit
   at the top, Settings at the bottom apart from them. Collapsible to icons only (the choice is kept in localStorage).
   Adding a view = one entry in NAV (plus its slot in App.tsx and its View name in the store). */
import { useEffect, useRef, useState, type KeyboardEvent as RKeyboardEvent, type ReactNode } from 'react';
import { actions, sel, useComputed, useLaunchpad, type View } from '../store';
import { lsGet, lsSet, LS_SIDEBAR } from '../lib/storage';
import { FolderTree, MessagesSquare, Orbit, PanelLeftClose, PanelLeftOpen, Settings, Users, Workflow } from './icons';

type NavEntry = { view: View; label: string; icon: ReactNode; title?: string; group: 'main' | 'bottom' };

/** The one list of views, in display order. */
const NAV: NavEntry[] = [
  { view: 'plan', label: 'Plan', icon: <MessagesSquare />, group: 'main', title: 'The chat screen: the Planner and the CLI, one switch apart' },
  { view: 'missions', label: 'Missions', icon: <Orbit />, group: 'main' },
  { view: 'crew', label: 'Crew', icon: <Users />, group: 'main' },
  { view: 'files', label: 'Files', icon: <FolderTree />, group: 'main' },
  { view: 'workflows', label: 'Workflows', icon: <Workflow />, group: 'main', title: 'Workflows: studies and reports you run more than once, with review stops' },
  { view: 'settings', label: 'Settings', icon: <Settings />, group: 'bottom', title: 'Settings: connections, MCP servers, connected folders, timers, models' },
];

export const tabId = (v: View) => `tab-${v}`;
export const panelId = (v: View) => `panel-${v}`;

function useMediaQuery(query: string): boolean {
  const mq = () => (typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(query) : null);
  const [on, setOn] = useState(() => mq()?.matches ?? false);
  useEffect(() => {
    const m = mq();
    if (!m) return;
    const f = () => setOn(m.matches);
    f();
    m.addEventListener('change', f);
    return () => m.removeEventListener('change', f);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps
  return on;
}

export function Sidebar() {
  const view = useLaunchpad(st => st.ui.view);
  const { running, chatWaiting, wfWait, wfGoing } = useComputed(st => ({ running: sel.inFlight(st).length, chatWaiting: sel.plannerWaiting(st) + sel.codeWaiting(st), wfWait: sel.wfWaiting(st), wfGoing: sel.wfRunning(st) }));
  const [pref, setPref] = useState<boolean>(() => lsGet<boolean>(LS_SIDEBAR, false) === true);
  /* at 1240 px and below the sidebar is icons only whatever the choice (the views need the room); the choice returns when the window widens */
  const narrow = useMediaQuery('(max-width: 1240px)');
  const collapsed = pref || narrow;
  const navRef = useRef<HTMLElement>(null);

  const toggle = () => { const n = !pref; setPref(n); lsSet(LS_SIDEBAR, n); };

  const onKey = (e: RKeyboardEvent<HTMLElement>) => {
    const k = NAV.findIndex(t => t.view === view);
    if (k < 0) return;
    let next = -1;
    if (e.key === 'ArrowDown') next = (k + 1) % NAV.length;
    else if (e.key === 'ArrowUp') next = (k - 1 + NAV.length) % NAV.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = NAV.length - 1;
    if (next < 0) return;
    e.preventDefault();
    actions.setView(NAV[next].view);
    navRef.current?.querySelector<HTMLButtonElement>(`#${tabId(NAV[next].view)}`)?.focus();
  };

  const tab = (t: NavEntry) => {
    const on = view === t.view;
    const badge = t.view === 'plan' && chatWaiting > 0 && !on
      ? <span className="nbadge warn" aria-label={`${chatWaiting} waiting in the chats`}>{chatWaiting}</span>
      : t.view === 'workflows' && wfWait > 0
        ? <span className="nbadge warn" aria-label={`${wfWait} review${wfWait === 1 ? '' : 's'} waiting for you`}>{wfWait}</span>
      : t.view === 'workflows' && wfGoing > 0 && !on
        ? <span className="nbadge" aria-label={`${wfGoing} workflow${wfGoing === 1 ? '' : 's'} running`}>{wfGoing}</span>
      : t.view === 'missions' && running > 0
        ? <span className="nbadge" aria-label={`${running} in flight`}>{running}</span>
        : null;
    return (
      <button key={t.view} type="button" role="tab" id={tabId(t.view)} aria-selected={on} aria-controls={panelId(t.view)} tabIndex={on ? 0 : -1}
        title={collapsed ? undefined : t.title} data-tip={collapsed ? `text:${t.label}` : undefined} onClick={() => actions.setView(t.view)}>
        {t.icon}<span className="side-txt">{t.label}</span>{badge}
      </button>
    );
  };

  return (
    <div className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      <nav ref={navRef} role="tablist" aria-orientation="vertical" aria-label="Sections" onKeyDown={onKey}>
        <div className="side-main">{NAV.filter(t => t.group === 'main').map(tab)}</div>
        <div className="side-bottom">{NAV.filter(t => t.group === 'bottom').map(tab)}</div>
      </nav>
      {narrow ? null : (
        <button type="button" className="side-toggle" aria-expanded={!pref} aria-label={pref ? 'Expand the sidebar' : 'Collapse the sidebar'}
          data-tip={pref ? 'text:Expand the sidebar' : undefined} onClick={toggle}>
          {pref ? <PanelLeftOpen /> : <PanelLeftClose />}<span className="side-txt">Collapse</span>
        </button>
      )}
    </div>
  );
}
