/* Usage screen: the usage_data handler used by reducer.ts. The server groups, buckets and sums; nothing is added up here. */
import type { UsageDataEvent } from '../contract';
import type { Ctx } from './core';

export function onUsageData(c: Ctx, ev: UsageDataEvent): void {
  const u = c.st.usage, r = ev.request, w = u.want;
  /* a reply (or a push) for controls the page no longer has is ignored; the page has asked for the newer ones */
  if (r && w && (r.period !== w.period || r.bucket !== w.bucket || r.split !== w.split || (r.session ?? null) !== (w.session ?? null))) {
    if (!ev.pushed) u.pending = Math.max(0, u.pending - 1);
    return;
  }
  const { type: _t, ...data } = ev;
  void _t;
  u.data = { ...data, buckets: Array.isArray(ev.buckets) ? ev.buckets : [], series: Array.isArray(ev.series) ? ev.series : [], sessions: Array.isArray(ev.sessions) ? ev.sessions : [] };
  if (!ev.pushed) u.pending = Math.max(0, u.pending - 1);
}
