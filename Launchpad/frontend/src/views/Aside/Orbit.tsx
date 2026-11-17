/* "In orbit": the planner as the sun, runs in flight as planets on two rings (step arcs, letter, "needs you"),
   their builders / Explorers (role astronaut) as moons, free Explorers and the Visualizer as sun satellites; plus the run list.
   Ported from prototype/launchpad-orbit.html 1880-1985 (buildOrbit, placeBodies, frame, renderLegend).
   The structure is React; the positions are written straight onto the <g> elements every animation frame
   (view-local, not in the store). Hovering the orbit pauses it; reduced motion keeps it still. */
import { useCallback, useLayoutEffect, useRef, type ReactNode } from 'react';
import { actions, sel, useComputed, type Agent, type RunStep, type Session } from '../../store';
import { AutoAnswersSwitch, AutopilotSwitch, Letter, SunIcon } from '../../components';
import { useAnimationFrame } from '../../lib/hooks';
import { REDUCED, tokShort, tparts, usd } from '../../lib/format';
import { P_LABEL } from '../../lib/labels';

const OV = { CX: 190, CY: 85, rings: [{ rx: 160, ry: 52, period: 120 }, { rx: 98, ry: 29, period: 85 }] };
type Body = { kind: 'sat'; phase: number } | { kind: 'planet'; ring: number; phase: number } | { kind: 'moon'; parent: number; phase: number };
interface BodyView { idx: number; a: Agent; wait: boolean }
interface PlanetView {
  idx: number; s: Session; wait: boolean; arcs: { key: string; status: string; d: string }[];
  m: number; cur: RunStep | null; flash: number; moons: BodyView[];
}

/* orbit time survives re-renders and remounts, like the vanilla Orbit.ft */
let orbitT = 0;

function arcPath(r: number, a0: number, a1: number): string {
  const p = (a: number) => `${(r * Math.cos(a)).toFixed(2)} ${(r * Math.sin(a)).toFixed(2)}`;
  return `M${p(a0)}A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${p(a1)}`;
}

function BodyShape({ a, wait }: { a: Agent; wait: boolean }): ReactNode {
  const cls = wait ? ' wait' : a.status === 'idle' ? ' idle' : '';
  if (a.role === 'visual') return <><circle className="hit" r={9} /><rect className={`moon${cls}`} x={-4.5} y={-4.5} width={9} height={9} rx={2.5} /></>;
  if (a.role === 'astronaut') return <><circle className="hit" r={9} /><path className={`astro${cls}`} d="M0 -5.5L5.5 0L0 5.5L-5.5 0Z" /></>;
  return <><circle className="hit" r={9} /><circle className={`moon${cls}`} r={4.6} /></>;
}

export function Orbit() {
  const v = useComputed(st => {
    const runs = sel.inFlight(st), sats = sel.sunSats(st), now = Date.now();
    const bodies: Body[] = [];
    const satList = sats.map((a, k) => { bodies.push({ kind: 'sat', phase: k / sats.length * Math.PI * 2 }); return { idx: bodies.length - 1, a, wait: sel.agentWaiting(st, a) }; });
    const per = [0, 0], idx = [0, 0];
    runs.forEach((_s, k) => { per[k % 2]++; });
    const planets = runs.map((s, k) => {
      const ring = k % 2, j = idx[ring]++;
      const pi = bodies.push({ kind: 'planet', ring, phase: j / per[ring] * Math.PI * 2 + (ring ? Math.PI * 0.35 : -Math.PI * 0.15) }) - 1;
      const steps = s.run ? s.run.steps : [], m = steps.length, span = m ? Math.PI * 2 / m : 0, gap = m > 1 ? Math.min(0.34, span * 0.3) : 0.001;
      const arcs = steps.map((x, q) => { const a0 = -Math.PI / 2 + q * span + gap / 2; return { key: `${x.n}-${q}`, status: x.status, d: arcPath(17, a0, a0 + span - gap) }; });
      const moons = sel.moonsOf(st, s.id).map((a, q, arr) => { bodies.push({ kind: 'moon', parent: pi, phase: q / arr.length * Math.PI * 2 }); return { idx: bodies.length - 1, a, wait: sel.agentWaiting(st, a) }; });
      const cur = sel.currentStep(s);
      return { idx: pi, s, wait: sel.waitingCount(st, s.id) > 0, arcs, m, cur, flash: now - s.flash < 1500 ? s.flash : 0, moons };
    });
    const label = runs.length ? `Runs in flight: ${runs.map(s => `${sel.sLabel(s)}, ${sel.sName(s)}, ${sel.stepsDone(s)} of ${s.run ? s.run.steps.length : 0} steps done`).join('; ')}` : 'No runs in flight';
    return { bodies, satList, planets, halo: sel.curPlannerStatus(st), label };
  });

  const els = useRef<(SVGGElement | null)[]>([]);
  const bodiesRef = useRef<Body[]>(v.bodies);
  bodiesRef.current = v.bodies;
  const paused = useRef(false);

  const place = useCallback(() => {
    const t = orbitT, pos: [number, number][] = [];
    bodiesRef.current.forEach((b, k) => {
      let x: number, y: number;
      if (b.kind === 'planet') { const r = OV.rings[b.ring], th = b.phase + t * 2 * Math.PI / r.period; x = OV.CX + r.rx * Math.cos(th); y = OV.CY + r.ry * Math.sin(th); }
      else if (b.kind === 'moon') { const p = pos[b.parent] || [OV.CX, OV.CY], ph = b.phase + t * 2 * Math.PI / 16; x = p[0] + 26 * Math.cos(ph); y = p[1] + 15 * Math.sin(ph); }
      else { const ph = b.phase + t * 2 * Math.PI / 22; x = OV.CX + 28 * Math.cos(ph); y = OV.CY + 19 * Math.sin(ph); }
      pos[k] = [x, y];
      const el = els.current[k];
      if (el) el.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
    });
  }, []);
  useLayoutEffect(() => { els.current.length = v.bodies.length; place(); });
  const tick = useCallback((_now: number, dt: number) => {
    if (paused.current || REDUCED) return;
    orbitT += dt / 1000; place();
  }, [place]);
  useAnimationFrame(tick);

  const setEl = (k: number) => (el: SVGGElement | null) => { els.current[k] = el; };
  return (
    <svg id="orbit" viewBox="0 0 380 170" role="img" aria-label={v.label}
      onPointerEnter={() => { paused.current = true; }} onPointerLeave={() => { paused.current = false; }}>
      {OV.rings.map((r, k) => <ellipse key={k} className={`ring ${k ? 'inner' : 'outer'}`} cx={OV.CX} cy={OV.CY} rx={r.rx} ry={r.ry} />)}
      <g data-tip="planner" transform={`translate(${OV.CX} ${OV.CY})`}>
        <circle className="hit" r={18} /><circle className={`halo ${v.halo}`} r={14} /><circle className="sun" r={12} /><circle className="sun-core" r={3.5} />
      </g>
      {v.satList.map(b => <g key={'sat:' + b.a.agent_id} ref={setEl(b.idx)} data-tip={`agent:${b.a.agent_id}`}><BodyShape a={b.a} wait={b.wait} /></g>)}
      {v.planets.map(p => (
        <PlanetGroup key={'run:' + p.s.id} p={p} setEl={setEl} />
      ))}
    </svg>
  );
}

function PlanetGroup({ p, setEl }: { p: PlanetView; setEl: (k: number) => (el: SVGGElement | null) => void }) {
  return (
    <>
      <g ref={setEl(p.idx)} data-tip={`run:${p.s.id}`}>
        <circle className="hit" r={22} />
        {p.s.autopilot ? <circle className="apring" r={22} /> : null}
        {p.flash ? <circle key={p.flash} className="flash" r={13} /> : null}
        {p.arcs.map(a => <path key={a.key} className={`arc ${a.status}`} d={a.d} />)}
        <circle className={`planet${p.wait ? ' wait' : ''}`} r={12} />
        <text className="plabel">{p.s.letter}</text>
        <text className={`sublabel${p.wait ? ' wait' : ''}`} y={33}>{p.wait ? 'needs you' : p.cur ? `step ${p.cur.n}/${p.m}` : ''}</text>
      </g>
      {p.moons.map(b => <g key={'moon:' + b.a.agent_id} ref={setEl(b.idx)} data-tip={`agent:${b.a.agent_id}`}><BodyShape a={b.a} wait={b.wait} /></g>)}
    </>
  );
}

/* run list under the orbit: the planner row, one row per run in flight (with its Autopilot switch), notes */
export function RunList() {
  const v = useComputed(st => {
    const runs = sel.inFlight(st), finished = sel.allSessions(st).filter(sel.isFinished).length;
    const p = sel.curPlanner(st), ps = sel.curPlannerStatus(st);
    return {
      ps, plannerLine: `· ${P_LABEL[ps] || ps} · ${tokShort(tparts(p))}`, plannerCost: usd(st.current != null ? sel.plannerCostOf(st, st.current) : 0), finished,
      runs: runs.map(s => {
        const wait = sel.waitingCount(st, s.id), cur = sel.currentStep(s), steps = s.run ? s.run.steps : [], m = steps.length;
        const workers = sel.moonsOf(st, s.id).filter(a => a.status === 'working').map(a => a.name);
        const line = [wait ? `Needs you (${wait})` : '', cur ? `Step ${cur.n}/${m} · ${cur.title}` : 'Starting', workers.length ? workers.join(', ') : ''].filter(Boolean).join(' · ');
        return { id: s.id, letter: s.letter, name: sel.sName(s), wait, line, cost: usd(sel.sessionTotal(st, s.id)), segs: steps.map(x => x.status) };
      }),
    };
  });
  return (
    <ul className="runs" id="runList">
      <li>
        <button type="button" className="runrow one" data-tip="planner" onClick={() => actions.setChatSide('planner')}>
          <SunIcon status={v.ps} /><span className="nm">Planner <span className="pst">{v.plannerLine}</span></span><span className="cost">{v.plannerCost}</span>
        </button>
      </li>
      {v.runs.map(r => (
        <li key={r.id}>
          <button type="button" className="runrow" data-tip={`run:${r.id}`} onClick={() => actions.focusRun(r.id)}>
            <Letter state={r.wait ? 'wait' : ''}>{r.letter}</Letter>
            <span className="nm">{r.name}</span>
            <span className="cost" title="Session total (Orchestrator + step agents + Explorer + Visualizer)">{r.cost}</span>
            <span className={`st${r.wait ? ' wait' : ''}`}>{r.line}</span>
            <span className="segs" aria-hidden="true">{r.segs.map((x, k) => <i key={k} className={x} />)}</span>
          </button>
          <div className="apline"><AutopilotSwitch sessionId={r.id} /><AutoAnswersSwitch sessionId={r.id} /></div>
        </li>
      ))}
      {!v.runs.length ? <li className="fl-note">No runs in flight. Approve a plan to launch one.</li> : null}
      {v.finished ? <li className="fl-note">{v.finished} finished · <button type="button" onClick={() => actions.setView('missions')}>see Missions</button></li> : null}
    </ul>
  );
}
