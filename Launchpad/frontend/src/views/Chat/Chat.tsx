/* The chat screen (header tab "Plan"): one card with the Planner / CLI switch on top and the two
   conversations under it. Both panes stay mounted, so flipping loses nothing: logs, scroll, expanded rows and typed
   drafts are kept. The switch is a WAI-ARIA tablist (two tabs, Left / Right / Home / End), and each tab says when its
   side has something waiting on you (a coral count) or is working (a pulsing dot). */
import './Chat.css';
import { useRef, type KeyboardEvent as RKeyboardEvent, type ReactNode } from 'react';
import { actions, sel, useComputed, useLaunchpad, type ChatSide } from '../../store';
import { MessagesSquare, Terminal } from '../../components/icons';
import Plan from '../Plan/Plan';
import Code from '../Code/Code';

const SIDES: { side: ChatSide; label: string; icon: ReactNode; hint: string }[] = [
  { side: 'planner', label: 'Planner', icon: <MessagesSquare />, hint: 'Plan with the Planner: rounds of questions, then a plan you approve and launch' },
  { side: 'code', label: 'CLI', icon: <Terminal />, hint: 'A plain CLI chat in a connected folder: the harness behaves as it does in a terminal, with its standard tools, permission prompts and modes' },
];
const sideTabId = (s: ChatSide) => `chatsw-${s}`;
const sidePanelId = (s: ChatSide) => `chatpane-${s}`;

export default function ChatScreen() {
  const side = useLaunchpad(st => st.ui.chatSide);
  const listRef = useRef<HTMLDivElement>(null);
  const v = useComputed(st => ({
    planner: { wait: sel.plannerWaiting(st), busy: sel.plannerBusy(st) },
    code: { wait: sel.codeWaiting(st), busy: sel.codeBusy(st) },
  }));

  const onKey = (e: RKeyboardEvent<HTMLDivElement>) => {
    const k = SIDES.findIndex(s => s.side === side);
    let next = -1;
    if (e.key === 'ArrowRight') next = (k + 1) % SIDES.length;
    else if (e.key === 'ArrowLeft') next = (k - 1 + SIDES.length) % SIDES.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = SIDES.length - 1;
    if (next < 0) return;
    e.preventDefault();
    actions.setChatSide(SIDES[next].side);
    listRef.current?.querySelector<HTMLButtonElement>(`#${sideTabId(SIDES[next].side)}`)?.focus();
  };

  return (
    <section className="view card chat-screen" id="viewChat" aria-label="Chat">
      <div className="chat-switch-bar">
        <div className="chat-switch" role="tablist" aria-label="Conversation" ref={listRef} onKeyDown={onKey}>
          {SIDES.map(s => {
            const on = side === s.side, st = v[s.side];
            const status = st.wait ? `${st.wait} waiting on you` : st.busy ? 'working' : '';
            return (
              <button key={s.side} type="button" role="tab" id={sideTabId(s.side)} aria-selected={on} aria-controls={sidePanelId(s.side)}
                tabIndex={on ? 0 : -1} data-tip={`text:${s.hint}`} className={st.wait ? 'has-wait' : undefined}
                aria-label={status ? `${s.label}, ${status}` : s.label} onClick={() => actions.setChatSide(s.side)}>
                {s.icon}<span>{s.label}</span>
                {st.wait ? <span className="sw-badge" aria-hidden="true">{st.wait}</span>
                  : st.busy ? <span className="sw-busy" aria-hidden="true" /> : null}
              </button>
            );
          })}
        </div>
        <p className="chat-switch-note">Two separate conversations. Switching keeps both, including what you have typed.</p>
      </div>
      <div className="chat-pane-slot" role="tabpanel" id={sidePanelId('planner')} aria-labelledby={sideTabId('planner')} hidden={side !== 'planner'}><Plan /></div>
      <div className="chat-pane-slot" role="tabpanel" id={sidePanelId('code')} aria-labelledby={sideTabId('code')} hidden={side !== 'code'}><Code /></div>
    </section>
  );
}
