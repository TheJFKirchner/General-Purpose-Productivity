/* In-page demo for the Usage screen: about six weeks of made-up, varied history (every kind of session, three models, two
   CLIs, many agents so "Other" appears, two running sessions), grouped the way the server groups it. Deterministic, so
   the screen and its tests always see the same figures; "today" is the real day so the history always ends now. Shapes follow
   the app/server.py header ("Usage screen"): bucket objects, series with `values` / `totals` / `members`, "__other__" for the rest. */
import type { UsageBucket, UsageBucketInfo, UsageDataEvent, UsageMeasure, UsagePeriod, UsageRequest, UsageSeries, UsageSession, UsageSessionKind, UsageSplit } from '../contract';
import { USAGE_MEASURES, USAGE_OTHER_KEY } from '../contract';

interface Call { at: number; session: string; cli: string; model: string; agent: string; cost: number; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_write_tokens: number }
interface DemoSession { id: string; kind: UsageSessionKind; folder: string; label: string; daysAgo: number; hour: number; running: boolean; span: number; agents: [agent: string, model: string, cli?: string][] }

const SESSIONS: DemoSession[] = [
  { id: 'u-plan-1', kind: 'plan', folder: 'Claims analytics', label: 'Claims loader rebuild', daysAgo: 41, hour: 9, running: false, span: 3, agents: [['Planner', 'Sonnet'], ['Builder', 'Sonnet'], ['Explorer', 'Haiku'], ['Orchestrator', 'Sonnet']] },
  { id: 'u-chat-1', kind: 'chat', folder: 'Claims analytics', label: 'CLI chat', daysAgo: 38, hour: 14, running: false, span: 1, agents: [['CLI chat', 'Sonnet']] },
  { id: 'u-plan-2', kind: 'plan', folder: 'Readmissions', label: 'Readmissions tab', daysAgo: 33, hour: 10, running: false, span: 5, agents: [['Planner', 'Opus'], ['sql-builder', 'Sonnet'], ['Explorer', 'Haiku'], ['Orchestrator', 'Sonnet'], ['Visualizer', 'Haiku'], ['sql-reviewer', 'Sonnet']] },
  { id: 'u-wf-1', kind: 'workflow', folder: 'Readmissions', label: 'Monthly readmission study', daysAgo: 29, hour: 8, running: false, span: 2, agents: [['Stage: pull data', 'Sonnet'], ['Stage: analyse', 'Opus'], ['Stage: write-up', 'Sonnet']] },
  { id: 'u-chat-2', kind: 'chat', folder: 'Demo shop', label: 'CLI chat', daysAgo: 26, hour: 16, running: false, span: 2, agents: [['CLI chat', 'Opus']] },
  { id: 'u-plan-3', kind: 'plan', folder: 'Demo shop', label: 'Checkout page tidy-up', daysAgo: 22, hour: 11, running: false, span: 4, agents: [['Planner', 'Sonnet'], ['Builder', 'Sonnet'], ['frontend-dev', 'Sonnet'], ['Explorer', 'Haiku'], ['Orchestrator', 'Sonnet'], ['copy-editor', 'Haiku'], ['release-checker', 'Haiku']] },
  { id: 'u-review-1', kind: 'review', folder: 'Demo shop', label: 'Review of frontend-dev', daysAgo: 19, hour: 15, running: false, span: 1, agents: [['Reviewer', 'Sonnet']] },
  { id: 'u-chat-3', kind: 'chat', folder: 'Claims analytics', label: 'CLI chat', daysAgo: 16, hour: 9, running: false, span: 1, agents: [['CLI chat', 'Sonnet', 'Cursor']] },
  { id: 'u-plan-4', kind: 'plan', folder: 'Claims analytics', label: 'Reconciliation report', daysAgo: 13, hour: 10, running: false, span: 4, agents: [['Planner', 'Opus'], ['Builder', 'Sonnet'], ['Explorer', 'Haiku'], ['Orchestrator', 'Sonnet'], ['sql-reviewer', 'Sonnet'], ['Visualizer', 'Haiku']] },
  { id: 'u-wf-2', kind: 'workflow', folder: 'Readmissions', label: 'Monthly readmission study', daysAgo: 9, hour: 8, running: false, span: 2, agents: [['Stage: pull data', 'Sonnet'], ['Stage: analyse', 'Opus'], ['Stage: write-up', 'Sonnet']] },
  { id: 'u-review-2', kind: 'review', folder: 'Readmissions', label: 'Review of release-checker', daysAgo: 6, hour: 13, running: false, span: 1, agents: [['Reviewer', 'Sonnet']] },
  { id: 'u-plan-5', kind: 'plan', folder: 'Demo shop', label: 'Order export', daysAgo: 4, hour: 9, running: false, span: 3, agents: [['Planner', 'Sonnet'], ['Builder', 'Sonnet'], ['Explorer', 'Haiku'], ['Orchestrator', 'Sonnet'], ['data-migrator', 'Sonnet']] },
  { id: 'u-plan-6', kind: 'plan', folder: 'Claims analytics', label: 'Denials dashboard', daysAgo: 1, hour: 10, running: true, span: 2, agents: [['Planner', 'Opus'], ['Builder', 'Sonnet'], ['Explorer', 'Haiku'], ['Orchestrator', 'Sonnet'], ['Visualizer', 'Haiku']] },
  { id: 'u-chat-4', kind: 'chat', folder: 'Demo shop', label: 'CLI chat', daysAgo: 0, hour: 8, running: true, span: 1, agents: [['CLI chat', 'Sonnet']] },
];

/* a small seeded generator: the same numbers every time */
function rng(seed: number): () => number { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
const PRICE: Record<string, number> = { Opus: 1, Sonnet: 0.35, Haiku: 0.08 };

function buildCalls(today: Date): Call[] {
  const out: Call[] = [];
  const r = rng(20261117);
  for (const s of SESSIONS) {
    for (let d = 0; d < s.span; d++) {
      const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - s.daysAgo + d, s.hour, 0, 0);
      if (day.getTime() > Date.now() && !s.running) continue;
      for (const [agent, model, cli] of s.agents) {
        const n = 1 + Math.floor(r() * 3);
        for (let k = 0; k < n; k++) {
          const at = new Date(day.getTime() + (k * 11 + Math.floor(r() * 40)) * 60000);
          const cost = Math.round((0.02 + r() * 0.6) * (PRICE[model] || 0.3) * 1000) / 1000;
          const w = cost * 40000;
          out.push({ at: at.getTime(), session: s.id, cli: cli || 'Claude', model, agent, cost,
            input_tokens: Math.round(w * 0.04 * (0.5 + r())), output_tokens: Math.round(w * 0.06 * (0.5 + r())),
            cache_read_tokens: Math.round(w * 0.8 * (0.5 + r())), cache_write_tokens: Math.round(w * 0.12 * (0.5 + r())) });
        }
      }
    }
  }
  return out.filter(c => c.at <= Date.now() + 86400000).sort((a, b) => a.at - b.at);
}

const pad = (n: number) => String(n).padStart(2, '0');
const dayKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const mondayOf = (d: Date) => addDays(d, -((d.getDay() + 6) % 7));
const bucketKey = (t: number, b: UsageBucket) => { const d = new Date(t); return dayKey(b === 'week' ? mondayOf(d) : d); };
const zero = () => ({ cost: 0, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0 });
const GROUP_TOP = 6;                                   // as the server: at most 7 series, the 6 largest named
const DAYS: Record<string, number> = { '7d': 7, '30d': 30, '90d': 90 };
const MONTH = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' });

/** The demo's answer to usage_get (the same shape the server sends). */
export function demoUsage(q: { period: UsagePeriod; bucket: UsageBucket; split: UsageSplit; session?: string | null }, now: Date = new Date()): UsageDataEvent {
  const request: UsageRequest = { period: q.period, bucket: q.bucket, split: q.split, session: q.session || null };
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const all = buildCalls(today);
  const firstDay = all.length ? new Date(all[0].at) : today;
  const from = q.period === 'all' ? new Date(firstDay.getFullYear(), firstDay.getMonth(), firstDay.getDate()) : addDays(today, 1 - DAYS[q.period]);
  const start = from.getTime();
  const inPeriod = all.filter(c => c.at >= start);
  const calls = q.session ? inPeriod.filter(c => c.session === q.session) : inPeriod;

  /* every bucket from the first to today, empty ones included */
  const buckets: UsageBucketInfo[] = [];
  for (let d = q.bucket === 'week' ? mondayOf(from) : from; d <= today; d = addDays(d, q.bucket === 'week' ? 7 : 1)) {
    const key = dayKey(d);
    if (q.bucket === 'day') buckets.push({ key, label: MONTH.format(d), start: key, end: key, partial: false });
    else {
      const s = d < from ? from : d, e = addDays(d, 6) > today ? today : addDays(d, 6);
      buckets.push({ key, label: `Week of ${MONTH.format(d)}`, start: dayKey(s), end: dayKey(e), partial: d < from || addDays(d, 6) > today });
    }
  }

  const sKey = (c: Call) => (q.split === 'cli' ? c.cli : q.split === 'model' ? c.model : c.agent);
  const spend = new Map<string, number>();
  for (const c of calls) spend.set(sKey(c), (spend.get(sKey(c)) || 0) + c.cost);
  const ranked = [...spend.entries()].sort((a, b) => b[1] - a[1]).map(e => e[0]);
  const keep = new Set(ranked.length > GROUP_TOP + 1 ? ranked.slice(0, GROUP_TOP) : ranked);
  const blank = (key: string, label: string, members: string[] = []): UsageSeries => ({
    key, label, members, totals: { ...zero(), calls: 0 },
    values: { cost: buckets.map(() => 0), input_tokens: buckets.map(() => 0), output_tokens: buckets.map(() => 0), cache_read_tokens: buckets.map(() => 0), cache_write_tokens: buckets.map(() => 0) },
  });
  const map = new Map<string, UsageSeries>();
  for (const k of ranked) if (keep.has(k)) map.set(k, blank(k, k));
  const rest = ranked.filter(k => !keep.has(k));
  if (rest.length) map.set(USAGE_OTHER_KEY, blank(USAGE_OTHER_KEY, 'Other', rest));
  const totals = { ...zero(), calls: 0, sessions: new Set(calls.map(c => c.session)).size };
  for (const c of calls) {
    const s = map.get(keep.has(sKey(c)) ? sKey(c) : USAGE_OTHER_KEY)!;
    const i = buckets.findIndex(b => b.key === bucketKey(c.at, q.bucket));
    if (i < 0) continue;
    s.totals.calls++; totals.calls++;
    for (const m of USAGE_MEASURES as UsageMeasure[]) { s.values[m][i] += c[m]; s.totals[m] += c[m]; totals[m] += c[m]; }
  }
  const series = [...map.values()];
  for (const s of series) for (const m of USAGE_MEASURES) s.values[m] = s.values[m].map(v => Math.round(v * 1e6) / 1e6);

  const sessions: UsageSession[] = [];
  for (const s of SESSIONS) {
    const mine = inPeriod.filter(c => c.session === s.id);
    if (!mine.length) continue;
    const t = zero();
    for (const c of mine) for (const m of USAGE_MEASURES) t[m] += c[m];
    const planner = mine.filter(c => c.agent === 'Planner').reduce((a, c) => a + c.cost, 0);
    sessions.push({
      id: s.id, kind: s.kind, kind_label: KIND[s.kind], label: s.label, folder: { dir_id: 'd-' + s.folder, name: s.folder, path: 'C:/Demo/' + s.folder }, run_folder: null,
      started_at: new Date(today.getFullYear(), today.getMonth(), today.getDate() - s.daysAgo, s.hour, 0, 0).toISOString(), last_at: new Date(mine[mine.length - 1].at).toISOString(),
      running: s.running, planner_cost: planner, calls: mine.length, agents: [...new Set(mine.map(c => c.agent))], models: [...new Set(mine.map(c => c.model))], clis: [...new Set(mine.map(c => c.cli))], ...t,
    });
  }
  sessions.sort((a, b) => (+b.running - +a.running) || b.last_at.localeCompare(a.last_at));

  return {
    type: 'usage_data', request, range: calls.length || inPeriod.length ? { start: dayKey(from), end: dayKey(today) } : null,
    buckets, series, totals, sessions, sessions_total: sessions.length, skipped_lines: 0, pushed: false,
  };
}
const KIND: Record<UsageSessionKind, string> = { plan: 'Plan', chat: 'CLI chat', workflow: 'Workflow run', review: 'Review', other: 'Other' };
