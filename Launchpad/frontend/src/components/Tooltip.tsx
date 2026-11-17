/* Hover cards (#tip). Put data-tip="<key>" on any element; the TipHost (mounted once in App) shows the card on
   hover / focus, follows the pointer and refreshes live. Keys (as in the vanilla page):
     planner · cursession · allagents · chat · run:<session_id> · agent:<agent_id> · step:<n>:<session_id>
     text:<plain words>  (a short label, e.g. for an icon-only button; shown after a short delay)
   Keyboard: the card also shows when the element gets focus, and is tied to it with aria-describedby; Esc hides it.
   Also: data-hover-agent="<agent_id>" on ships, stars and feed rows sets the shared hover highlight (ui.hov). */
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { actions, sel, useLaunchpad, type AppState, type Agent } from '../store';
import { cleanName, modelName, tokLong, tokShort, toolShort, tparts, tsum, usd } from '../lib/format';
import { MODE_LABEL, P_LABEL, PURPOSE_LABEL, STEP_LABEL, S_LABEL, roleLabel } from '../lib/labels';

function Usage({ a }: { a: Agent | null | undefined }) {
  if (!a) return <span className="m">No usage reported yet</span>;
  const t = tparts(a);
  return <>Cost <b>{usd(a.cost_usd)}</b> · {tokShort(t)} · {a.tool_calls || 0} tool calls<br /><span className="m">{tokLong(t)}</span></>;
}

/** The card content for one data-tip key (null = nothing to show). */
export function tipContent(st: AppState, key: string): ReactNode {
  const c = key.indexOf(':'), k = c < 0 ? key : key.slice(0, c), id = c < 0 ? '' : key.slice(c + 1);
  if (k === 'text') return id || null;
  if (k === 'planner') {
    const p = sel.curPlanner(st), all = Object.values(st.agents).filter(a => a.role === 'planner'), cs = sel.curSess(st), ps = sel.curPlannerStatus(st);
    return <>
      <b>Planner</b> <span className="m">· {P_LABEL[ps] || ps}{cs && cs.plannerModel ? ' · ' + modelName(cs.plannerModel) + (cs.promoted ? ' (promoted)' : '') : ''}</span><hr /><Usage a={p} />
      {p && Array.isArray(p.by_model) && p.by_model.length ? <><hr />By model<ul>{p.by_model.map((m, i) => <li key={i}>{modelName(m.model)}: {usd(m.cost_usd)}{m.input_tokens != null || m.output_tokens != null ? <> <span className="m">· {tokShort(tparts(m))}</span></> : null}</li>)}</ul></> : null}
      {all.length > 1 ? <><hr />All planners so far: <b>{usd(all.reduce((t, a) => t + (+a.cost_usd || 0), 0))}</b> <span className="m">({all.length} sessions)</span></> : null}
    </>;
  }
  if (k === 'run') {
    const s = st.sessions[id]; if (!s) return null;
    const orch = sel.orchestratorOf(st, id), cur = sel.currentStep(s), steps = (s.run && s.run.steps) || [];
    const done = steps.filter(x => x.status === 'done'), crew = sel.crewOf(st, id), pc = sel.plannerCostOf(st, id), status = sel.sStatus(st, s);
    return <>
      <b>{sel.sLabel(s)} · {sel.sName(s)}</b><br /><span className="m">{S_LABEL[status] || s.status}{cur ? ` · step ${cur.n}/${steps.length}: ${cur.title}` : ''}</span>
      {s.autopilot ? <><hr /><b>Autopilot ON</b> <span className="m">· permission requests are approved without asking</span></> : null}
      <hr />Orchestrator · <Usage a={orch} />
      <hr />Session total <b>{usd(sel.sessionTotal(st, id))}</b> <span className="m">· Orchestrator + step agents + Explorer + Visualizer · {crew.length} agents · {tokShort(tsum(crew))}</span>
      {pc ? <><br /><span className="m">Planner (separate): {usd(pc)}</span></> : null}
      {done.length ? <><hr />Done so far<ul>{done.slice(-5).map(x => <li key={x.n}>{x.n}. {x.title}{x.built.length ? <> <span className="m">· {x.built.slice(0, 3).join(', ')}{x.built.length > 3 ? '…' : ''}</span></> : null}</li>)}</ul></> : <><hr /><span className="m">No steps done yet</span></>}
    </>;
  }
  if (k === 'agent') {
    const a = st.agents[id]; if (!a) return null;
    const s = a.session_id != null ? st.sessions[a.session_id] : null, wait = !!s && sel.agentWaiting(st, a);
    const where = [s ? sel.sLabel(s) : 'No session', a.step != null ? `step ${a.step}` : '', wait ? 'waiting on you' : a.status].filter(Boolean).join(' · ');
    const la = sel.lastActOf(st, id);
    const s2 = s && a.step != null ? ((s.run && s.run.steps) || []).find(x => String(x.n) === String(a.step)) : null;
    return <>
      <b>{cleanName(a.name) || a.agent_id}</b> <span className="m">· {roleLabel(a.role)}</span><br /><span className="m">{where}{s2 ? ` · ${s2.title}` : ''}</span>
      {la ? <><hr />{la.status === 'started' ? 'Now' : 'Last call'}: <b>{toolShort(la.tool)}</b>{la.status === 'denied' || la.status === 'failed' ? <> <span className="m">({la.status})</span></> : null}<br /><span className="m">{String(la.summary || '').slice(0, 120)}</span></> : null}
      <hr /><Usage a={a} />
    </>;
  }
  if (k === 'allagents') {
    const t = sel.appTotals(st), by: Record<string, number> = {};
    for (const a of Object.values(st.agents)) { const r = a.role || 'other'; by[r] = (by[r] || 0) + (+a.cost_usd || 0); }
    const rows = Object.entries(by).sort((x, y) => y[1] - x[1]);
    return <>
      <b>Whole app</b> <span className="m">· every agent since launch: all planners, every session, CLI chats, the Visualizer</span><hr />
      Cost <b>{usd(t.cost)}</b> · {tokShort(t.parts)}<br /><span className="m">{tokLong(t.parts)}</span>
      {rows.length ? <ul>{rows.map(([r, v]) => <li key={r}>{roleLabel(r)}: {usd(v)}</li>)}</ul> : null}
      {st.usageFromServer && t.from === 'agents' && Math.abs(st.cost - t.cost) > 0.005 ? <span className="m">Server total: {usd(st.cost)}</span> : null}
      <hr /><span className="m">"tokens" = uncached input + output; cache reads and writes are shown apart. The planner figure in the chat header is the current session's planner only.</span>
    </>;
  }
  if (k === 'cursession') {
    const s = sel.curSess(st); if (!s) return <><b>Session total</b><br /><span className="m">No session yet</span></>;
    const n = sel.crewOf(st, s.id).length;
    return <>
      <b>{sel.sLabel(s)} · session total {usd(sel.sessionTotal(st, s.id))}</b><br /><span className="m">Orchestrator + step agents + Explorer + Visualizer; {n ? `${n} agents` : 'no run agents yet'}</span>
      <hr />Planner (separate) {usd(sel.plannerCostOf(st, s.id))}
    </>;
  }
  if (k === 'chat') {
    const u = sel.chatUsage(st), ch = sel.curChat(st); if (!u || !ch) return <><b>CLI</b><br /><span className="m">No chat yet</span></>;
    const p = { i: u.in, o: u.out, cr: u.cr, cw: u.cw };
    return <><b>This chat</b> <span className="m">· {MODE_LABEL[ch.mode]}{ch.model ? ' · ' + modelName(ch.model) : ''}</span><hr />Cost <b>{usd(u.cost)}</b> · {tokShort(p)} · {u.tools} tool calls<br /><span className="m">{tokLong(p)}</span></>;
  }
  if (k === 'step') {
    const c2 = id.indexOf(':'), n = id.slice(0, c2), s = st.sessions[id.slice(c2 + 1)];
    const stp = s && s.run && s.run.steps.find(x => String(x.n) === n); if (!s || !stp) return null;
    const ag = sel.agentsOf(st, s.id);
    const who = ag.filter(a => String(a.step) === n && a.role !== 'orchestrator' && a.status !== 'done').map(a => `${cleanName(a.name)} (${a.status})`);
    const wait = st.queue.filter(i => sel.qOpen(i) && i.session_id === s.id && String(i.step) === n).length;
    const builders = ag.filter(a => a.role === 'builder' && String(a.step) === n);
    const cost = builders.reduce((t, a) => t + (+a.cost_usd || 0), 0), toks = tsum(builders);
    const calls = builders.length ? builders.reduce((t, a) => t + (+a.tool_calls || 0), 0) : st.acts.filter(a => a.session_id === s.id && String(a.step) === n).length;
    const assigned = sel.stepAgent(sel.defsForSession(st, s), stp);
    return <>
      <b>Step {stp.n} · {stp.title}</b><br /><span className="m">{sel.sLabel(s)} · {STEP_LABEL[stp.status] || stp.status}</span>
      <br /><span className="m">Done by {assigned ? (assigned.fallback ? `the ${assigned.label} (${assigned.name || 'the named agent'} is not available here)` : `${assigned.label} (${PURPOSE_LABEL[assigned.purpose].toLowerCase()} agent)`) : 'the Builder'}</span>
      <hr />Cost <b>{usd(cost)}</b> · {tokShort(toks)} · {calls} tool calls<br /><span className="m">{tokLong(toks)}</span><br /><span className="m">{builders.length ? `builder${builders.length > 1 ? 's' : ''} on this step` : 'no builder on this step yet'}</span>
      {wait ? <><hr /><b>{wait} waiting on you</b> in Incoming</> : null}
      {who.length ? <><hr />On it: {who.join(', ')}</> : null}
      {stp.built.length ? <><hr />Built<ul>{stp.built.slice(0, 6).map(b => <li key={b}>{b}</li>)}</ul></> : null}
      {stp.report_path ? <><hr /><span className="m">Step report: {stp.report_path}</span></> : null}
    </>;
  }
  return null;
}

const TEXT_DELAY = 350;

export function TipHost() {
  const st = useLaunchpad();
  const [tip, setTip] = useState<{ key: string; x: number; y: number } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const view = st.ui.view;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let described: HTMLElement | null = null;
    let shownKey: string | null = null;
    const clearTimer = () => { if (timer) { clearTimeout(timer); timer = null; } };
    const undescribe = () => { if (described) { described.removeAttribute('aria-describedby'); described = null; } };
    const show = (t: { key: string; x: number; y: number } | null) => { shownKey = t ? t.key : null; setTip(t); };
    const move = (e: PointerEvent) => {
      const t = e.target as Element | null;
      const ag = t && t.closest ? t.closest<HTMLElement>('[data-hover-agent]') : null;
      actions.setHover(ag && ag.dataset.hoverAgent ? ag.dataset.hoverAgent : null);
      const el = t && t.closest ? t.closest<HTMLElement>('[data-tip]') : null;
      const key = el && el.dataset.tip;
      if (!key) { clearTimer(); if (shownKey) show(null); return; }
      const next = { key, x: e.clientX, y: e.clientY };
      if (key === shownKey) { setTip(next); return; }
      clearTimer();
      if (key.startsWith('text:')) { if (shownKey) show(null); timer = setTimeout(() => { timer = null; show(next); }, TEXT_DELAY); }
      else show(next);
    };
    const focusIn = (e: FocusEvent) => {
      if (byPointer) return;                         // focus from a click: the hover card already handled it
      const t = e.target as Element | null, el = t && t.closest ? t.closest<HTMLElement>('[data-tip]') : null;
      if (!el || !el.dataset.tip) return;
      clearTimer(); undescribe();
      if (!el.hasAttribute('aria-describedby')) { el.setAttribute('aria-describedby', 'tip'); described = el; }
      const r = el.getBoundingClientRect(); show({ key: el.dataset.tip, x: r.left, y: r.bottom });
    };
    const hide = () => { clearTimer(); undescribe(); show(null); };
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { hide(); actions.clearSelection(); } };
    document.addEventListener('pointermove', move);
    document.addEventListener('focusin', focusIn);
    document.addEventListener('focusout', hide);
    document.addEventListener('scroll', hide, true);
    document.addEventListener('keydown', key);
    /* a click hides the card (the control may turn disabled or vanish, and then sends no more pointer events) */
    let byPointer = false;
    const down = () => { byPointer = true; setTimeout(() => { byPointer = false; }, 0); if (shownKey || timer) hide(); };
    document.addEventListener('pointerdown', down, true);
    return () => {
      clearTimer(); undescribe();
      document.removeEventListener('pointerdown', down, true);
      document.removeEventListener('pointermove', move); document.removeEventListener('focusin', focusIn);
      document.removeEventListener('focusout', hide); document.removeEventListener('scroll', hide, true); document.removeEventListener('keydown', key);
    };
  }, []);
  useEffect(() => { setTip(null); }, [view]);

  const content = tip ? tipContent(st, tip.key) : null;
  useLayoutEffect(() => {
    const el = ref.current; if (!el || !tip || !content) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    let left = tip.x + 14, top = tip.y + 16;
    if (left + w > innerWidth - 8) left = Math.max(8, tip.x - w - 14);
    if (top + h > innerHeight - 8) top = Math.max(8, tip.y - h - 12);
    el.style.left = left + 'px'; el.style.top = top + 'px';
  });
  const isText = !!tip && tip.key.startsWith('text:');
  return <div className={`tip${isText ? ' text' : ''}`} id="tip" role="tooltip" ref={ref} style={{ display: content ? 'block' : 'none' }}>{content}</div>;
}
