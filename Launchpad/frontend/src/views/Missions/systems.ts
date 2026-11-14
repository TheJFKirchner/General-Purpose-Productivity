/* Missions animation engine (view-local, never in the store). Ported from the vanilla page, lines 2116-2133 and
   2227-2319: builders are ships that fly out to their step, orbit it while working and fly home when done; astronaut
   lookups are diamonds that fly out to the file belt and back. Every activity event flashes a ping on the agent.
   React draws the static parts of each system; this engine owns only the children of each svg's <g class="dyn">,
   which React never renders into. All text goes in through textContent (escaped). */
import { getState, sel, type Activity, type Agent, type AppState, type Session } from '../../store';
import { cleanName, REDUCED, toolCat, toolShort } from '../../lib/format';

export const SYS = { CX: 200, CY: 168, R: 100, BELT: 146, DUR: REDUCED ? 0 : 1300 };
const NS = 'http://www.w3.org/2000/svg';

/** The 36 rocks of the outer belt (fixed positions, as in the vanilla page). */
export const ROCKS = Array.from({ length: 36 }, (_, k) => {
  const a = k / 36 * Math.PI * 2 + Math.sin(k * 7.3) * 0.08, r = SYS.BELT + Math.sin(k * 3.1) * 6;
  return { cx: +(SYS.CX + r * Math.cos(a)).toFixed(1), cy: +(SYS.CY + r * Math.sin(a)).toFixed(1), r: +(1.1 + (k % 3) * .6).toFixed(1) };
});

interface P { x: number; y: number }
/** Where step `n` sits on the inner ring (steps evenly spaced from 12 o'clock). */
export function stepXY(s: Session, n: number | string | null | undefined): (P & { ang: number }) | null {
  const st = (s.run && s.run.steps) || [], k = st.findIndex(x => String(x.n) === String(n));
  if (k < 0) return null;
  const ang = -Math.PI / 2 + k * 2 * Math.PI / st.length;
  return { x: SYS.CX + SYS.R * Math.cos(ang), y: SYS.CY + SYS.R * Math.sin(ang), ang };
}

const ease = (u: number) => u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
function bez(a: P, b: P, u: number, bend: number): P {
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1, k = len * .35 * bend;
  const cx = (a.x + b.x) / 2 - dy / len * k, cy = (a.y + b.y) / 2 + dx / len * k;
  return { x: (1 - u) * (1 - u) * a.x + 2 * (1 - u) * u * cx + u * u * b.x, y: (1 - u) * (1 - u) * a.y + 2 * (1 - u) * u * cy + u * u * b.y };
}

interface Ship {
  id: string; sid: string; role: string; mode: 'out' | 'work' | 'back'; t0: number; from: P; key: string;
  belt: number; phi: number; bend: number; trail: string[];
  pos?: P; prev?: P; head?: number;
  el?: SVGGElement; tr?: SVGPolylineElement; lb?: SVGTextElement;
}
interface Ping { g: SVGGElement; c: SVGCircleElement; t: SVGTextElement; t0: number }

export class SystemsEngine {
  private svgs = new Map<string, SVGSVGElement>();
  private ships = new Map<string, Ship>();
  private pings: Ping[] = [];

  /** Called by each system's svg ref (null when it unmounts). */
  setSvg(sid: string, el: SVGSVGElement | null): void {
    if (el) this.svgs.set(sid, el); else this.svgs.delete(sid);
  }

  private reconcileShip(s: Session, a: Agent, now: number): void {
    let sh = this.ships.get(a.agent_id);
    const present = !sel.isFinished(s) && a.status !== 'done' && (a.role === 'builder' || a.status === 'working');
    const key = a.role === 'astronaut' ? 'belt' : 'step' + a.step, star = { x: SYS.CX, y: SYS.CY };
    if (present) {
      if (!sh) {
        sh = { id: a.agent_id, sid: s.id, role: a.role, mode: 'out', t0: now, from: star, key, belt: Math.random() * Math.PI * 2, phi: Math.random() * 6.28, bend: Math.random() < .5 ? 1 : -1, trail: [] };
        this.ships.set(a.agent_id, sh);
      } else if (sh.mode === 'back') { Object.assign(sh, { from: sh.pos || star, mode: 'out', t0: now, key }); if (a.role === 'astronaut') sh.belt = Math.random() * Math.PI * 2; }
      else if (sh.key !== key) Object.assign(sh, { from: sh.pos || star, mode: 'out', t0: now, key });
    } else if (sh && sh.mode !== 'back') Object.assign(sh, { from: sh.pos || star, mode: 'back', t0: now });
  }

  private shipPos(st: AppState, sh: Ship, s: Session, a: Agent, now: number, dt: number): P | null {
    const { CX, CY, BELT } = SYS, star = { x: CX, y: CY }, waiting = sel.agentWaiting(st, a);
    if (!REDUCED && !waiting && a.status === 'working') sh.phi += dt / 1000 * 2 * Math.PI / 3.4;
    const work = (): P => {
      if (sh.role === 'astronaut') {
        const t = now / 1000, j = REDUCED || waiting ? 0 : 1;
        return { x: CX + BELT * Math.cos(sh.belt) + j * 5 * Math.sin(t * 2.3 + sh.phi), y: CY + BELT * Math.sin(sh.belt) + j * 4 * Math.cos(t * 1.7 + sh.phi) };
      }
      const p = stepXY(s, a.step) || { x: CX, y: CY - SYS.R };
      return { x: p.x + 22 * Math.cos(sh.phi), y: p.y + 22 * Math.sin(sh.phi) };
    };
    let p: P;
    if (sh.mode === 'out') { const u = SYS.DUR ? (now - sh.t0) / SYS.DUR : 1, end = work(); if (u >= 1) { sh.mode = 'work'; p = end; } else p = bez(sh.from, end, ease(u), sh.bend); }
    else if (sh.mode === 'work') p = work();
    else { const u = SYS.DUR ? (now - sh.t0) / SYS.DUR : 1; if (u >= 1) return null; p = bez(sh.from, star, ease(u), sh.bend); }
    sh.pos = p; return p;
  }

  private ensureShipEl(sh: Ship, svg: SVGSVGElement, a: Agent): void {
    if (sh.el && sh.el.isConnected) return;
    const dyn = svg.querySelector('.dyn'); if (!dyn) return;
    sh.tr = document.createElementNS(NS, 'polyline') as SVGPolylineElement; sh.tr.setAttribute('class', 'trail ' + sh.role); sh.trail = [];
    sh.el = document.createElementNS(NS, 'g') as SVGGElement; sh.el.setAttribute('class', 'ship ' + sh.role);
    sh.el.setAttribute('data-tip', 'agent:' + a.agent_id); sh.el.setAttribute('data-agent', a.agent_id); sh.el.setAttribute('data-hover-agent', a.agent_id);
    const add = (tag: string, attrs: Record<string, string>) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); sh.el!.appendChild(e); };
    add('circle', { class: 'sel', r: '13' }); add('circle', { class: 'hit', r: '13' });
    if (sh.role === 'astronaut') { add('path', { class: 'astro', d: 'M0 -8L8 0L0 8L-8 0Z' }); add('circle', { class: 'core', r: '2' }); }
    else add('path', { class: 'body', d: 'M11 0L-7 -7L-3.5 0L-7 7Z' });
    sh.lb = document.createElementNS(NS, 'text') as SVGTextElement; sh.lb.setAttribute('class', 'ship-lbl'); sh.lb.textContent = cleanName(a.name) || a.agent_id;
    dyn.prepend(sh.tr); dyn.append(sh.lb, sh.el);
  }

  private removeShip(sh: Ship): void { sh.el?.remove(); sh.tr?.remove(); sh.lb?.remove(); this.ships.delete(sh.id); }

  /** A tool call (new, or denied / failed): a ring that grows and fades on the agent that made it. */
  ping(a: Activity): void {
    const st = getState();
    if (st.ui.view !== 'missions' || REDUCED || a.session_id == null) return;
    const svg = this.svgs.get(a.session_id); if (!svg || !svg.isConnected) return;
    const sh = this.ships.get(a.agent_id);
    const p = sh && sh.pos ? sh.pos : a.role === 'orchestrator' ? { x: SYS.CX, y: SYS.CY - 24 } : null; if (!p) return;
    const dyn = svg.querySelector('.dyn'); if (!dyn) return;
    const cls = a.status === 'denied' || a.status === 'failed' ? a.status : toolCat(a.tool);
    const g = document.createElementNS(NS, 'g') as SVGGElement; g.setAttribute('class', 'ping ' + cls); g.setAttribute('transform', `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`);
    const c = document.createElementNS(NS, 'circle') as SVGCircleElement; c.setAttribute('r', '6');
    const t = document.createElementNS(NS, 'text') as SVGTextElement; t.setAttribute('y', '-12'); t.textContent = a.status === 'denied' ? 'denied' : a.status === 'failed' ? 'failed' : toolShort(a.tool);
    g.append(c, t); dyn.appendChild(g);
    this.pings.push({ g, c, t, t0: performance.now() });
    if (this.pings.length > 40) this.pings.shift()!.g.remove();
  }

  /** One animation frame (only while the Missions tab is showing). */
  frame(now: number, dt: number): void {
    const st = getState();
    if (st.ui.view !== 'missions') return;
    for (const [sid, svg] of this.svgs) {
      const s = st.sessions[sid]; if (!s || !svg.isConnected) continue;
      for (const a of sel.agentsOf(st, sid)) if (a.role === 'builder' || a.role === 'astronaut') this.reconcileShip(s, a, now);
    }
    const eff = st.ui.hov || st.ui.sel;
    for (const sh of [...this.ships.values()]) {
      const a = st.agents[sh.id], s = st.sessions[sh.sid], svg = this.svgs.get(sh.sid);
      if (!a || !s || !svg || !svg.isConnected) { this.removeShip(sh); continue; }
      const p = this.shipPos(st, sh, s, a, now, dt);
      if (!p) { this.removeShip(sh); continue; }
      this.ensureShipEl(sh, svg, a); if (!sh.el || !sh.lb || !sh.tr) continue;
      if (sh.prev && Math.hypot(p.x - sh.prev.x, p.y - sh.prev.y) > 0.05) sh.head = Math.atan2(p.y - sh.prev.y, p.x - sh.prev.x) * 180 / Math.PI;
      sh.prev = p;
      sh.el.setAttribute('transform', `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})${sh.role === 'builder' ? ` rotate(${(sh.head ?? -90).toFixed(0)})` : ''}`);
      /* a builder circling its step planet: the label never drops onto the planet (just above it at most) */
      const dock = sh.role === 'builder' && sh.mode === 'work' ? stepXY(s, a.step) : null;
      const ly = dock ? Math.min(p.y - 15, dock.y - 22) : p.y - 15;
      sh.lb.setAttribute('x', p.x.toFixed(1)); sh.lb.setAttribute('y', ly.toFixed(1));
      sh.lb.classList.toggle('hl', eff === sh.id);
      sh.el.classList.toggle('wait', sel.agentWaiting(st, a));
      sh.el.classList.toggle('idle', a.status === 'idle');
      sh.el.classList.toggle('hl', eff === sh.id);
      if (!REDUCED) { sh.trail.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`); if (sh.trail.length > 18) sh.trail.shift(); sh.tr.setAttribute('points', sh.trail.join(' ')); }
    }
    this.pings = this.pings.filter(pg => {
      const u = (now - pg.t0) / 1800;
      if (u >= 1 || !pg.g.isConnected) { pg.g.remove(); return false; }
      pg.c.setAttribute('r', (7 + 24 * u).toFixed(1)); pg.g.style.opacity = (1 - u).toFixed(2); pg.t.setAttribute('y', (-12 - 16 * u).toFixed(1));
      return true;
    });
  }

  /** Drop the ships and pings (unmount). The svg map is kept: refs re-register themselves. */
  dispose(): void { for (const sh of [...this.ships.values()]) this.removeShip(sh); for (const p of this.pings) p.g.remove(); this.pings = []; }
}
