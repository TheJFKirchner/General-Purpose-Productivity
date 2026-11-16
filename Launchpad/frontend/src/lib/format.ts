/* Formatting helpers (ported from the vanilla page). */
import type { TokenCounts } from '../contract';

const kfmt = (n: unknown): string => { const v = +(n as number) || 0; return v >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : v >= 1000 ? (v / 1000).toFixed(1) + 'k' : String(Math.round(v)); };
export const usd = (v: unknown): string => { const x = +(v as number) || 0; return x > 0 && x < 0.01 ? '<$0.01' : '$' + x.toFixed(2); };

/** Token parts: i = uncached input, o = output, cr = cache read, cw = cache write. */
export interface TokParts { i: number; o: number; cr: number; cw: number }
type Countish = (TokenCounts & { input?: number; output?: number; cache_read?: number; cache_write?: number }) | null | undefined;

const tokf = (a: Record<string, unknown>, k: string, old: string): number => +((a[k] ?? a[old]) as number) || 0;
/** tokens = input + cache read + cache write + output (the server's definition). */
export const tok = (a: Countish): number => a ? tokf(a as Record<string, unknown>, 'input_tokens', 'input') + tokf(a as Record<string, unknown>, 'output_tokens', 'output') + tokf(a as Record<string, unknown>, 'cache_read_tokens', 'cache_read') + tokf(a as Record<string, unknown>, 'cache_write_tokens', 'cache_write') : 0;
export const tparts = (a: Countish): TokParts => {
  if (!a) return { i: 0, o: 0, cr: 0, cw: 0 };
  const r = a as Record<string, unknown>;
  return { i: tokf(r, 'input_tokens', 'input'), o: tokf(r, 'output_tokens', 'output'), cr: tokf(r, 'cache_read_tokens', 'cache_read'), cw: tokf(r, 'cache_write_tokens', 'cache_write') };
};
export const tsum = (list: Countish[]): TokParts => list.reduce<TokParts>((t, a) => { const p = tparts(a); return { i: t.i + p.i, o: t.o + p.o, cr: t.cr + p.cr, cw: t.cw + p.cw }; }, { i: 0, o: 0, cr: 0, cw: 0 });
/** What the page shows: "tokens" = uncached input + output; cache reads/writes are always shown apart. */
export const tokShort = (p: TokParts): string => `${kfmt(p.i + p.o)} tokens${p.cr + p.cw ? ` + ${kfmt(p.cr + p.cw)} cache` : ''}`;
export const tokLong = (p: TokParts): string => `input ${kfmt(p.i)} (uncached) · output ${kfmt(p.o)} · cache read ${kfmt(p.cr)} · cache write ${kfmt(p.cw)}`;

export const mmss = (ms: number): string => { const s = Math.max(0, Math.ceil(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
export function ago(t: number, now = Date.now()): string { const s = Math.floor((now - t) / 1000); return s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m` : `${Math.floor(s / 3600)}h`; }
export const clock = (ts: unknown): string => { const d = new Date(ts as string); return isNaN(+d) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); };

export const cleanName = (n: unknown): string => String(n ?? '').replace(/(\s*·\s*step\s*\d+)+\s*$/i, '');
export const modelName = (m: unknown): string => { const t = String(m || ''); return /opus/i.test(t) ? 'Opus' : /sonnet/i.test(t) ? 'Sonnet' : /haiku/i.test(t) ? 'Haiku' : t; };
export const baseName = (p: unknown): string => String(p || '').replace(/[\\/]+$/, '').split(/[\\/]/).pop() || String(p || '');
export const fmtBytes = (n: unknown): string => { const v = +(n as number) || 0; return v >= 1048576 ? (v / 1048576).toFixed(1) + ' MB' : v >= 1024 ? (v / 1024).toFixed(1) + ' kB' : v + ' B'; };
export const fmtTime = (t: unknown): string => {
  if (t == null || t === '') return '';
  const d = typeof t === 'number' ? new Date(t < 1e12 ? t * 1000 : t) : new Date(t as string);
  return isNaN(+d) ? String(t) : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
};

/** Sessions are lettered A, B, ... Z, AA, AB ... in the order the page first sees them. */
export function letterFor(i: number): string { let s = ''; i++; while (i > 0) { const r = (i - 1) % 26; s = String.fromCharCode(65 + r) + s; i = Math.floor((i - 1) / 26); } return s; }

/** Tool names: "mcp__<server>__<name>" shows as <name>; category drives the chip colour (read / write / bash / custom). */
export const toolShort = (t: unknown): string => String(t || '?').replace(/^mcp__.+?__/, '');
export const toolCat = (t: unknown): 'bash' | 'read' | 'write' | 'custom' => {
  const s = toolShort(t);
  return s === 'Bash' ? 'bash' : /^(Read|Grep|Glob|LS|NotebookRead|WebFetch|WebSearch)$/.test(s) ? 'read' : /^(Write|Edit|MultiEdit|NotebookEdit)$/.test(s) ? 'write' : 'custom';
};

/** True when the user asked for reduced motion (animations off). */
export const REDUCED: boolean = typeof window !== 'undefined' && !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
