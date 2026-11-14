/* Missions: one animated solar system per run, then "On the pad" and "Landed" chips.
   Vanilla source: prototype/launchpad-orbit.html HTML 700-707; JS 2109-2320 (systems, ships, pings) and 2394-2427
   (highlight, stop, plan / archive modals).
   Each run = a system. Star = orchestrator (letter; ✓ done, ■ stopped, ✕ failed; coral when it needs you). Inner ring =
   plan steps as planets; routes from the star turn green as steps finish. Outer dashed belt = the project files.
   Ships, trails and pings are drawn by the view-local engine in systems.ts. */
import './Missions.css';
import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import { actions, getState, onActivityPing, sel, useLaunchpad, type AppState, type Session } from '../../store';
import { AutopilotSwitch, DirChip, Letter, Pill, Status, StepAgent, ViewFrame, openArchive, openPlan, openReport } from '../../components';
import { useAnimationFrame } from '../../lib/hooks';
import { REDUCED, usd } from '../../lib/format';
import { AP_HINT, S_LABEL } from '../../lib/labels';
import { ROCKS, SYS, SystemsEngine, stepXY } from './systems';
import { FileText, MessagesSquare, Plus, Rocket, Send } from '../../components/icons';

const { CX, CY, R } = SYS;

function Rocks() {
  return <g className="rocks" style={{ transformOrigin: `${CX}px ${CY}px` }}>{ROCKS.map((p, k) => <circle key={k} className="rock" cx={p.cx} cy={p.cy} r={p.r} />)}</g>;
}

/** Pin an agent; when it is now pinned, scroll its newest visible row in the activity feed into view. */
function pinAgent(id: string): void {
  actions.selectAgent(id);
  if (getState().ui.sel !== id) return;
  const esc = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(id) : id.replace(/"/g, '\\"');
  const rows = document.querySelectorAll<HTMLElement>(`#feedList [data-hover-agent="${esc}"], #feedList [data-agent="${esc}"]`);
  const row = [...rows].find(el => !el.hidden && el.offsetParent !== null);
  if (row) row.scrollIntoView({ block: 'nearest', behavior: REDUCED ? 'auto' : 'smooth' });
}

export default function Missions() {
  const st = useLaunchpad();
  const engine = useRef<SystemsEngine | null>(null);
  if (!engine.current) engine.current = new SystemsEngine();

  /* animation + pings (the engine checks that the Missions tab is showing) */
  const frame = useCallback((now: number, dt: number) => engine.current!.frame(now, dt), []);
  useAnimationFrame(frame);
  useEffect(() => onActivityPing(a => engine.current!.ping(a)), []);
  useEffect(() => () => engine.current!.dispose(), []);

  /* "Open in Missions" from the side panel: scroll that run into view */
  const { view, focus, focusScroll } = st.ui;
  useEffect(() => {
    if (view !== 'missions' || !focusScroll) return;
    actions.consumeFocusScroll();
    const el = document.getElementById('sys-' + getState().order.indexOf(focus ?? ''));
    if (el) el.scrollIntoView({ block: 'nearest', behavior: REDUCED ? 'auto' : 'smooth' });
  }, [view, focus, focusScroll]);

  const sys = sel.visibleSystems(st), planning = sel.onThePad(st), landed = sel.landed(st);
  const running = sys.filter(s => s.status === 'running').length;
  const finished = sel.allSessions(st).filter(sel.isFinished).length;
  const sum = `${running} in flight · ${planning.length} on the pad · ${finished} finished · hover anything for details, click an agent to pin it`;

  /* clicks on a star or a ship pin that agent (buttons handle themselves) */
  const onClick = (e: MouseEvent<HTMLDivElement>) => {
    const t = e.target as Element;
    if (t.closest('button')) return;
    const ag = t.closest<Element>('[data-agent]'), id = ag && ag.getAttribute('data-agent');
    if (id) pinAgent(id);
  };

  return (
    <ViewFrame id="viewMissions" label="Missions" title="Missions" sub={<span id="missionSum">{sum}</span>} tools={<NewPlanButton st={st} />} bodyClass={null}>
      <div className="vbody" id="missionList" onClick={onClick}>
        {sys.length ? (
          <div className="sys-grid">{sys.map(s => <SystemCell key={s.id} st={st} s={s} engine={engine.current!} />)}</div>
        ) : (
          <div className="sys-empty">
            <svg className="sys-svg" viewBox="0 0 400 336" aria-hidden="true">
              <Rocks /><circle className="belt" cx={CX} cy={CY} r={SYS.BELT} /><circle className="stepring" cx={CX} cy={CY} r={R} /><circle className="star off" cx={CX} cy={CY} r={24} />
            </svg>
            <p><b>Nothing in flight</b>Approve a plan in the Plan tab and its run appears here as a system of its own.</p>
            <Pill size="sm" variant="soft" icon={<MessagesSquare />} onClick={() => actions.setChatSide('planner')}>Go to Plan</Pill>
          </div>
        )}
        {planning.length ? <div className="pad"><h3>On the pad</h3><div className="chips">{planning.map(s => <PadChip key={s.id} st={st} s={s} />)}</div></div> : null}
        {landed.length ? <div className="pad"><h3>Landed</h3><div className="chips">{landed.map(s => <LandedChip key={s.id} s={s} />)}</div></div> : null}
      </div>
    </ViewFrame>
  );
}

/** "+ New plan" in the Missions header: asks "Set this plan aside?" first when the current plan has not launched. */
function NewPlanButton({ st }: { st: AppState }) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const busy = st.ui.newPlanBusy;
  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    const s = sel.curSess(st);
    const unlaunched = !!s && !s.run && s.log.some(x => (x.kind === 'bubble' && x.who === 'me') || x.kind === 'plancard');
    if (timer.current) clearTimeout(timer.current);
    if (unlaunched && !armed) { setArmed(true); timer.current = setTimeout(() => setArmed(false), 4000); return; }
    setArmed(false);
    actions.chooseDir(e.currentTarget, dirId => actions.newPlan(dirId));
  };
  return (
    <Pill size="sm" variant={armed && !busy ? 'danger' : 'default'} data-newplan="1" disabled={busy} onClick={onClick} icon={busy || armed ? undefined : <Plus />}>
      {busy ? 'Starting…' : armed ? 'Set this plan aside?' : 'New plan'}
    </Pill>
  );
}

function SystemCell({ st, s, engine }: { st: AppState; s: Session; engine: SystemsEngine }) {
  const sid = s.id;
  const svgRef = useCallback((el: SVGSVGElement | null) => engine.setSvg(sid, el), [engine, sid]);
  const status = sel.sStatus(st, s), fin = sel.isFinished(s), steps = s.run ? s.run.steps : [], N = steps.length;
  const letterState = status === 'waiting' ? 'wait' : s.status === 'done' ? 'done' : fin ? 'off' : '';
  const orch = sel.orchestratorOf(st, sid);
  const starCls = fin ? s.status : status === 'waiting' ? 'wait' : 'run';
  const starHalo = !fin && (status === 'waiting' || (orch && orch.status === 'working'));
  const eff = st.ui.hov || st.ui.sel;
  const line = sel.nowLine(st, s);
  const dir = sel.dirById(st, s.dirId);
  const now = Date.now();

  return (
    <section className={`sys-cell${fin ? ' fin ' + s.status : ''}${status === 'waiting' ? ' wait' : ''}${s.autopilot && !fin ? ' ap' : ''}${st.ui.focus === sid ? ' focus' : ''}`} id={`sys-${st.order.indexOf(sid)}`}>
      <div className="sys-top">
        <Letter state={letterState}>{s.letter}</Letter>
        <h2>{sel.sName(s)}</h2>
        <DirChip label={sel.dirLabelOf(st, s.dirId, s.cwd)} path={(dir && dir.path) || s.cwd || ''} />
        {s.autopilot && !fin ? <span className="aptag" title={AP_HINT}>Autopilot</span> : null}
        <Status status={status} label={S_LABEL[status] || status} />
        <span className="m-cost" title="Session total: Orchestrator + step agents + Explorer + Visualizer. The planner is counted separately."><b>{usd(sel.sessionTotal(st, sid))}</b> session</span>
      </div>
      <svg className="sys-svg" viewBox="0 0 400 336" data-sys={sid} role="img" aria-label={`${sel.sLabel(s)}: ${line}`} ref={svgRef}>
        <Rocks />
        <circle className="belt" cx={CX} cy={CY} r={SYS.BELT} />
        <circle className="stepring" cx={CX} cy={CY} r={R} />
        {steps.map(x => {
          const p = stepXY(s, x.n)!, c = Math.cos(p.ang), sn = Math.sin(p.ang);
          return <line key={'r' + x.n} className={`route ${x.status}`} x1={(CX + 30 * c).toFixed(1)} y1={(CY + 30 * sn).toFixed(1)} x2={(CX + (R - 17) * c).toFixed(1)} y2={(CY + (R - 17) * sn).toFixed(1)} />;
        })}
        {steps.map(x => {
          const p = stepXY(s, x.n)!, px = p.x.toFixed(1), py = p.y.toFixed(1);
          const mark = x.status === 'done' ? '✓' : x.status === 'failed' ? '✕' : x.status === 'blocked' ? '!' : String(x.n);
          const title = String(x.title || '');
          const burst = x.status === 'done' && String(s.flashN) === String(x.n) && now - s.flash < 1600;
          const ag = sel.stepAgent(sel.defsForSession(st, s), x);
          return (
            <g key={'s' + x.n} data-tip={`step:${x.n}:${sid}`}>
              <circle className="hit" cx={px} cy={py} r={18} />
              {ag ? <circle className={`st-agent${ag.fallback ? ' fallback' : ''}`} data-purpose={ag.purpose} cx={px} cy={py} r={17} /> : null}
              {x.status === 'in_progress' ? <circle className="st-halo" cx={px} cy={py} r={19} /> : x.status === 'blocked' ? <circle className="st-halo blocked" cx={px} cy={py} r={16} /> : null}
              {burst ? <g key={'b' + s.flash}><circle className="burst" cx={px} cy={py} r={14} /><circle className="burst b2" cx={px} cy={py} r={14} /></g> : null}
              <circle className={`st-planet ${x.status}`} cx={px} cy={py} r={13} />
              <text className={`st-num ${x.status}`} x={px} y={py}>{mark}</text>
              {N <= 8 ? <text className="st-title" x={px} y={(p.y + 27).toFixed(1)}>{title.length > 18 ? title.slice(0, 17) + '…' : title}</text> : null}
            </g>
          );
        })}
        <g data-tip={`run:${sid}`} data-agent={orch ? orch.agent_id : ''} data-hover-agent={orch ? orch.agent_id : undefined} className={`star-g${eff && orch && eff === orch.agent_id ? ' hl' : ''}`}>
          {s.autopilot && !fin ? <circle className="apring" cx={CX} cy={CY} r={33} /> : null}
          {starHalo ? <circle className={`star-halo ${status === 'waiting' ? 'wait' : ''}`} cx={CX} cy={CY} r={26} /> : null}
          <circle className="hit" cx={CX} cy={CY} r={30} />
          <circle className="sel" cx={CX} cy={CY} r={30} />
          <circle className={`star ${starCls}`} cx={CX} cy={CY} r={24} />
          <text className="star-lbl" x={CX} y={CY}>{fin ? ({ done: '✓', stopped: '■', failed: '✕' } as Record<string, string>)[s.status] : s.letter}</text>
        </g>
        <g className="dyn" />
      </svg>
      <div className={`sys-now${status === 'waiting' ? ' wait' : ''}`} title={line}>{line}</div>
      <StepAgents st={st} s={s} />
      <div className="row"><SystemActions st={st} s={s} /></div>
    </section>
  );
}

/** Steps done by an agent other than the Builder: "Step 3 · SQL reviewer" chips under the system. */
function StepAgents({ st, s }: { st: AppState; s: Session }) {
  const list = (s.run ? s.run.steps : []).map(x => ({ x, a: sel.stepAgent(sel.defsForSession(st, s), x) })).filter(r => r.a);
  if (!list.length) return null;
  return (
    <ul className="sys-agents" aria-label="Steps with their own agent">
      {list.map(({ x, a }) => (
        <li key={x.n}><span className="sa-n">Step {x.n}</span><StepAgent a={a!} step={`Step ${x.n}, ${x.title}`} /></li>
      ))}
    </ul>
  );
}

function SystemActions({ st, s }: { st: AppState; s: Session }) {
  const sid = s.id, fin = sel.isFinished(s);
  return <>
    {s.status === 'running' ? <AutopilotSwitch sessionId={sid} /> : null}
    {s.status === 'running' ? (st.ui.stopConfirm === sid
      ? <Pill size="sm" variant="danger" onClick={() => actions.stopRun(sid)}>Confirm stop</Pill>
      : <Pill size="sm" disabled={s.stopping} onClick={() => actions.stopRun(sid)}>{s.stopping ? 'Stopping…' : 'Stop run'}</Pill>) : null}
    {s.report ? <>
      <Pill size="sm" variant="primary" icon={<FileText />} onClick={() => openReport(sid)}>Read report</Pill>
      <Pill size="sm" disabled={s.reportSent} icon={s.reportSent ? undefined : <Send />} onClick={() => actions.sendReport(sid)}>{s.reportSent ? 'Sent to planner' : 'Send to planner'}</Pill>
    </> : null}
    {s.draft ? <Pill size="sm" variant="soft" onClick={() => openPlan(sid)}>Read plan</Pill> : null}
    {fin && s.draft && !sel.draftLaunched(s) ? <Pill size="sm" variant="primary" icon={<Rocket />} disabled={s.approving} onClick={() => actions.approve(sid)}>{s.approving ? 'Launching…' : 'Approve new plan'}</Pill> : null}
    {sel.hasChat(s) && sid !== st.current ? <Pill size="sm" variant="ghost" icon={<MessagesSquare />} onClick={() => openArchive(sid)}>Planning chat</Pill> : null}
    {fin ? <Pill size="sm" variant="ghost" onClick={() => actions.clearSystem(sid)}>Move to Landed</Pill> : null}
  </>;
}

function PadChip({ st, s }: { st: AppState; s: Session }) {
  const sid = s.id;
  return (
    <span className="pchip">
      <Letter state="off">{s.letter}</Letter><span className="pn">{sel.sName(s)}</span>
      {s.draft ? <>
        <Pill size="xs" variant="soft" onClick={() => openPlan(sid)}>Read plan</Pill>
        {sel.draftLaunched(s) ? null : <Pill size="xs" variant="primary" disabled={s.approving} onClick={() => actions.approve(sid)}>{s.approving ? 'Launching…' : 'Approve and launch'}</Pill>}
      </> : <span className="mut">{sid === st.current ? 'planning in the chat' : 'set aside, no draft'}</span>}
      {sel.hasChat(s) && sid !== st.current ? <Pill size="xs" variant="ghost" onClick={() => openArchive(sid)}>Chat</Pill> : null}
    </span>
  );
}

function LandedChip({ s }: { s: Session }) {
  const sid = s.id;
  return (
    <span className="pchip">
      <Letter state={s.status === 'done' ? 'done' : s.status === 'failed' ? 'wait' : 'off'}>{s.letter}</Letter><span className="pn">{sel.sName(s)}</span>
      <Status status={s.status} label={S_LABEL[s.status]} />
      <Pill size="xs" variant="soft" onClick={() => openReport(sid)}>Report</Pill>
      <Pill size="xs" disabled={s.reportSent} onClick={() => actions.sendReport(sid)}>{s.reportSent ? 'Sent' : 'Send to planner'}</Pill>
    </span>
  );
}
