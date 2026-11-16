/* Top bar: brand, the section tabs (WAI-ARIA tabs: role=tablist / tab, aria-selected, aria-controls the panel in
   App.tsx, roving tabindex, Left / Right / Home / End; tabs are state, no router), Settings, connection, whole-app
   usage, avatar. A coral bar under it says when the connection to the back end is lost. */
import { useRef, type KeyboardEvent as RKeyboardEvent, type ReactNode } from 'react';
import { actions, sel, useComputed, useLaunchpad, type View } from '../store';
import { tokShort } from '../lib/format';
import { FolderTree, MessagesSquare, Orbit, Settings, Users, Wallet, WifiOff } from './icons';

const TABS: { view: View; label: string; icon: ReactNode; title?: string }[] = [
  { view: 'plan', label: 'Plan', icon: <MessagesSquare />, title: 'The chat screen: the Planner and the CLI, one switch apart' },
  { view: 'missions', label: 'Missions', icon: <Orbit /> },
  { view: 'crew', label: 'Crew', icon: <Users /> },
  { view: 'files', label: 'Files', icon: <FolderTree /> },
];

export const tabId = (v: View) => `tab-${v}`;
export const panelId = (v: View) => `panel-${v}`;

export function Header() {
  const view = useLaunchpad(st => st.ui.view);
  const conn = useLaunchpad(st => st.ui.conn);
  const { cost, toks, running, chatWaiting } = useComputed(st => {
    const t = sel.appTotals(st);
    return { cost: `~$${t.cost.toFixed(2)}`, toks: tokShort(t.parts), running: sel.inFlight(st).length, chatWaiting: sel.plannerWaiting(st) + sel.codeWaiting(st) };
  });
  const listRef = useRef<HTMLDivElement>(null);

  const onKey = (e: RKeyboardEvent<HTMLDivElement>) => {
    const k = TABS.findIndex(t => t.view === view);
    let next = -1;
    if (e.key === 'ArrowRight') next = (k + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (k - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = TABS.length - 1;
    if (next < 0) return;
    e.preventDefault();
    actions.setView(TABS[next].view);
    listRef.current?.querySelector<HTMLButtonElement>(`#${tabId(TABS[next].view)}`)?.focus();
  };

  return (
    <>
      <header>
        <div className="brand">
          <svg viewBox="0 0 40 40" aria-hidden="true"><circle className="lg-ring" cx="20" cy="20" r="18" /><circle className="lg-ring2" cx="20" cy="20" r="11" /><circle className="lg-sun" cx="20" cy="20" r="5" /><circle className="lg-moon" cx="34" cy="11" r="3.5" /></svg>
          <b>Launchpad</b><span>by COSMO</span>
        </div>
        <nav aria-label="Sections">
          <div className="tabs" role="tablist" aria-label="Sections" ref={listRef} onKeyDown={onKey}>
            {TABS.map(t => {
              const on = view === t.view;
              return (
                <button key={t.view} type="button" role="tab" id={tabId(t.view)} aria-selected={on} aria-controls={panelId(t.view)} tabIndex={on ? 0 : -1}
                  title={t.title} onClick={() => actions.setView(t.view)}>
                  {t.icon}{t.label}
                  {t.view === 'plan' && chatWaiting > 0 && !on ? <span className="nbadge warn" aria-label={`${chatWaiting} waiting in the chats`}>{chatWaiting}</span> : null}
                  {t.view === 'missions' && running > 0 ? <span className="nbadge" aria-label={`${running} in flight`}>{running}</span> : null}
                </button>
              );
            })}
          </div>
          <button type="button" className="navset" aria-haspopup="dialog" title="Settings: connected folders, timers, models" onClick={() => actions.openSettings()}><Settings /><span className="navset-txt">Settings</span></button>
        </nav>
        <div className="hdr-right">
          <span className="conn" role="status" title={conn.text}><span className="dot" style={{ background: conn.color }} /><span className="conn-txt">{conn.text}</span></span>
          <span className="usage" data-tip="allagents" tabIndex={0} aria-label={`Whole app usage ${cost}, ${toks}`}><Wallet /><span className="u-txt"><span className="u-lbl">Whole app · </span>{cost} · {toks}</span></span>
          <span className="avatar" role="img" aria-label="You">J</span>
        </div>
      </header>
      {conn.text === 'Disconnected' ? (
        <div className="connbar" role="alert"><WifiOff />Disconnected from Launchpad. <span>Actions cannot be sent until it is back; close and reopen Launchpad if this lasts.</span></div>
      ) : null}
    </>
  );
}
