/* Store core: the zustand store, the immer-based runner every change goes through, side effects (timers,
   activity pings), toasts and the transport hook the bridge registers. Views never import this file directly:
   use the hooks, selectors and actions exported from src/store/index.ts. */
import { create } from 'zustand';
import { produce, type Draft } from 'immer';
import type { UiMessage } from '../contract';
import type { Activity, AppState } from './types';
import { initialState } from './initial';
import { LS_FILES, lsSet } from '../lib/storage';

/** The app store. `useLaunchpad()` = whole state; `useLaunchpad(st => st.ui.view)` = one value (keep selectors cheap). */
export const useLaunchpad = create<AppState>()(() => initialState());
export const getState = (): AppState => useLaunchpad.getState();

/* ---------- side effects collected during one change, run after the state is updated ---------- */
export interface Fx {
  timers: { ms: number; fn: () => void; key?: string }[];
  pings: { a: Activity; isNew: boolean }[];
}
export interface Ctx { st: Draft<AppState>; fx: Fx }

let active: Ctx | null = null;
const keyed = new Map<string, ReturnType<typeof setTimeout>>();
type PingListener = (a: Activity, isNew: boolean) => void;
const pingListeners = new Set<PingListener>();

/** Run one change against an immer draft of the state. Nested calls reuse the same draft. */
export function run<T>(recipe: (c: Ctx) => T): T {
  if (active) return recipe(active);
  const fx: Fx = { timers: [], pings: [] };
  const prev = useLaunchpad.getState();
  let result!: T;
  const next = produce(prev, draft => {
    active = { st: draft, fx };
    try { result = recipe(active); } finally { active = null; }
  });
  if (next !== prev) {
    useLaunchpad.setState(next, true);
    persistFiles(prev, next);
  }
  for (const t of fx.timers) {
    if (t.key) { const old = keyed.get(t.key); if (old) clearTimeout(old); }
    const h = setTimeout(() => { if (t.key) keyed.delete(t.key); t.fn(); }, t.ms);
    if (t.key) keyed.set(t.key, h);
  }
  for (const p of fx.pings) for (const l of pingListeners) { try { l(p.a, p.isNew); } catch (e) { console.error(e); } }
  return result;
}

/** Schedule `fn` after the current change; a key replaces an earlier timer with the same key. */
export function later(c: Ctx, ms: number, fn: () => void, key?: string): void { c.fx.timers.push({ ms, fn, key }); }

/** Missions pings: called for every new tool call and for each denied/failed one (after the state has it). */
export function onActivityPing(cb: PingListener): () => void { pingListeners.add(cb); return () => { pingListeners.delete(cb); }; }

/* ---------- toasts ---------- */
export function toast(c: Ctx, text: string): void {
  if (c.st.quiet) return;
  const id = ++c.st.seq;
  c.st.ui.toasts.push({ id, text });
  later(c, 2800, () => run(c2 => { c2.st.ui.toasts = c2.st.ui.toasts.filter(t => t.id !== id); }));
}

/* ---------- transport (registered by src/bridge.ts) ---------- */
type Transport = (msg: UiMessage) => boolean;
let transport: Transport = () => false;
export function setTransport(t: Transport): void { transport = t; }
/** Send one UI -> server message. Returns false when it could not be sent (a "Not connected" toast follows). */
export function send(msg: UiMessage): boolean { return transport(msg); }

/* ---------- File Explorer layout persistence (localStorage lp.files) ---------- */
function persistFiles(prev: AppState, next: AppState): void {
  const a = prev.fx, b = next.fx;
  if (a.open === b.open && a.sel === b.sel && a.raw === b.raw && a.collapsed === b.collapsed && a.width === b.width) return;
  lsSet(LS_FILES, { open: b.open, sel: b.sel, raw: b.raw, collapsed: b.collapsed, width: b.width });
}
