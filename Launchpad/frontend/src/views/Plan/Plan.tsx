/* The chat screen's Planner side: the planner chat for the current session (the switch is in views/Chat).
   Ported from prototype/launchpad-orbit.html: HTML 647-670; chat head 1272-1280; composer 1533-1538; "+ New plan"
   with its "Set this plan aside?" confirm 1540-1561; planner model chip + Promote 1617-1667; Visuals button 2851-2854;
   live planner / session figures 1988-1996. The log entries (rounds, plan cards, notes) are in PlanLog.tsx. */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import './Plan.css';
import { actions, sel, useComputed, useCurrentSession, useLaunchpad } from '../../store';
import { Empty, Pill } from '../../components';
import { MessagesSquare, Plus, Send, Sparkles } from '../../components/icons';
import { tokShort, tparts, usd } from '../../lib/format';
import { S_LABEL } from '../../lib/labels';
import { PlanLog } from './PlanLog';

const PH_DEFAULT = 'Reply, ask something back, or say “draft now”';
const PH_CHANGES = 'What should change in the plan?';

export default function Plan() {
  const s = useCurrentSession();
  const preLog = useLaunchpad(st => st.preLog);
  const preTyping = useLaunchpad(st => st.preTyping);
  const v = useComputed(st => {
    const c = sel.curSess(st), m = (c && c.meta) || {};
    const name = (c && (c.run ? sel.sName(c) : m.name && !/^new session$/i.test(m.name) ? m.name : c.draft ? sel.sName(c) : 'New plan')) || m.name || st.preName || 'New plan';
    const what = m.mode ? [m.mode, m.status].filter(Boolean).join(' · ') : c && c.run ? S_LABEL[c.status] : 'Planning';
    const dl = c ? sel.dirLabelOf(st, c.dirId, c.cwd) : '';
    const p = sel.curPlanner(st);
    const sets = c ? c.visualSets : [], unseen = sets.length - ((c && c.visSeen) || 0);
    return {
      name,
      modeLine: c ? `${sel.sLabel(c)}${dl ? ' · in ' + dl : ''} · ${what}` : 'Planning',
      modeTitle: c ? ((sel.dirById(st, c.dirId) || { path: '' }).path || c.cwd || '') : '',
      roundTag: (c ? c.roundTag : st.preRoundTag) || 'Getting started',
      pm: sel.plannerModelView(st),
      plannerCost: usd(p && p.cost_usd),
      plannerTok: tokShort(tparts(p)),
      sessCost: usd(st.current != null ? sel.sessionTotal(st, st.current) : 0),
      visBtn: sets.length > 0 && !sel.visShown(st),
      visCount: unseen > 0 ? `${unseen} new` : String(sets.length),
      visWarn: unseen > 0,
    };
  });
  const newPlanBusy = useLaunchpad(st => st.ui.newPlanBusy);
  /* on screen = the chat screen with the switch on Planner (the pane stays mounted on the Claude Code side) */
  const view = useLaunchpad(st => (st.ui.view === 'plan' && st.ui.chatSide === 'planner' ? 'plan' : 'other'));
  const replaying = useLaunchpad(st => st.replaying);

  const sid = s ? s.id : null;
  const log = s ? s.log : preLog;
  const typing = s ? s.typing : preTyping;

  /* composer */
  const [text, setText] = useState('');
  const [ph, setPh] = useState(PH_DEFAULT);
  const inputRef = useRef<HTMLInputElement>(null);
  const onChanges = useCallback(() => { setPh(PH_CHANGES); inputRef.current?.focus(); }, []);

  /* "+ New plan": with an unlaunched plan in this session the first click asks "Set this plan aside?" (4 s) */
  const [npConfirm, setNpConfirm] = useState(false);
  const npTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearNp = () => { if (npTimer.current) { clearTimeout(npTimer.current); npTimer.current = null; } };
  useEffect(() => () => clearNp(), []);
  /* a session switch resets the placeholder and the confirm (vanilla setCurrent -> newPlanBusy(false)) */
  useEffect(() => { setPh(PH_DEFAULT); setNpConfirm(false); clearNp(); }, [sid]);
  useEffect(() => { if (newPlanBusy) { setNpConfirm(false); clearNp(); } }, [newPlanBusy]);
  const onNewPlan = (btn: HTMLButtonElement) => {
    const unlaunched = !!s && !s.run && s.log.some(e => (e.kind === 'bubble' && e.who === 'me') || e.kind === 'plancard');
    if (unlaunched && !npConfirm) {
      setNpConfirm(true); clearNp();
      npTimer.current = setTimeout(() => { npTimer.current = null; setNpConfirm(false); }, 4000);
      return;
    }
    clearNp(); setNpConfirm(false);
    actions.chooseDir(btn, dirId => actions.newPlan(dirId));
  };

  /* keep the newest line in view (new entries, typing, session switch, back on this tab, end of a replay) */
  const msgsRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = msgsRef.current;
    if (el && view === 'plan') el.scrollTop = el.scrollHeight;
  }, [sid, log.length, typing, view, replaying]);

  const pm = v.pm;
  return (
    <div className="chat-pane" id="viewPlan" aria-label="Planner chat">
      <div className="chat-head">
        <div>
          <small id="modeLine" title={v.modeTitle}>{v.modeLine}</small>
          <h1 id="planName">{v.name}</h1>
        </div>
        <div className="head-tags">
          <div className="head-row">
            <Pill variant="soft" size="sm" id="visOpen" hidden={!v.visBtn} title="Show the planner's visual options" icon={<Sparkles />} onClick={() => actions.openVis(true)}>
              Visuals<span className={`nbadge${v.visWarn ? ' warn' : ''}`}>{v.visCount}</span>
            </Pill>
            <Pill size="sm" variant={npConfirm && !newPlanBusy ? 'danger' : 'default'} id="newPlan" disabled={newPlanBusy}
              title="Start a new session; runs already in flight keep going" icon={newPlanBusy || npConfirm ? undefined : <Plus />} onClick={e => onNewPlan(e.currentTarget)}>
              {newPlanBusy ? 'Starting…' : npConfirm ? 'Set this plan aside?' : 'New plan'}
            </Pill>
            <span className="round-tag" id="roundTag">{v.roundTag}</span>
          </div>
          {pm ? (
            <div className="pm-row" id="pmRow">
              <span className={`modelchip${pm.session.promoted ? ' promoted' : ''}`} id="pmModel" data-tip="planner" title={pm.chipTitle}>{pm.chip}</span>
              {pm.showPromote ? (
                <Pill size="xs" variant={pm.confirm ? 'danger' : 'default'} id="pmPromote" disabled={pm.session.promoting} title={pm.promoteTitle}
                  onClick={() => actions.promotePlanner(pm.session.id)}>{pm.promoteLabel}</Pill>
              ) : null}
            </div>
          ) : null}
          <span className="pcost">
            <span data-tip="planner" tabIndex={0}>Planner <b>{v.plannerCost}</b> · <span>{v.plannerTok}</span></span>
            {' · '}
            <span data-tip="cursession" tabIndex={0}>Session total <b>{v.sessCost}</b></span>
          </span>
        </div>
      </div>
      <div className="msgs" id="msgs" aria-live="polite" ref={msgsRef}>
        {!log.length && !typing ? (
          <Empty className="log-empty" icon={<MessagesSquare />} title="Plan with the Planner">
            Say what you want built. The planner asks a few short rounds of questions, then drafts a plan you can read, change and approve.
          </Empty>
        ) : null}
        <PlanLog entries={log} sid={sid} typing={typing} onChanges={onChanges} />
      </div>
      <form className="composer" id="composer" autoComplete="off"
        onSubmit={e => { e.preventDefault(); if (actions.sendPlannerMessage(text)) setText(''); }}>
        <label htmlFor="msgInput" className="sr">Message the planner</label>
        <input id="msgInput" ref={inputRef} value={text} onChange={e => setText(e.target.value)} placeholder={ph} />
        <Pill variant="primary" type="submit" icon={<Send />}>Send</Pill>
      </form>
    </div>
  );
}
