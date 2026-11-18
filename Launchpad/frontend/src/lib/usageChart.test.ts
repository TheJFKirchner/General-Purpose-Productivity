/* Usage helpers: formats, stable colours, the chart option and CSV for every combination of period / bucket / split / measure
   (against the in-page demo history), sessions sort. Zero back end. */
import { describe, expect, it } from 'vitest';
import { USAGE_MEASURES, type UsageBucket, type UsagePeriod, type UsageSplit } from '../contract';
import { demoUsage } from '../demo/usageDemo';
import {
  buildCsv, buildOption, bucketTotals, coloursFor, resetColours, csvName, fmtValue, hasBars, OTHER_COLOUR, PALETTE, parseDay, sortSessions, valuesOf, type ChartTheme,
} from './usageChart';

/** hue angle of a #rrggbb colour, degrees */
function hueOf(hex: string): number {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
  const mx = Math.max(r, g, b), d = mx - Math.min(r, g, b);
  if (!d) return 0;
  const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
}
const TH: ChartTheme = { ink: '#000', muted: '#666', line: '#ddd', card: '#fff' };
const PERIODS: UsagePeriod[] = ['7d', '30d', '90d', 'all'];
const BUCKETS: UsageBucket[] = ['day', 'week'];
const SPLITS: UsageSplit[] = ['cli', 'model', 'agent'];

describe('formats', () => {
  it('cost is currency, tokens are compact on the axis and whole in full', () => {
    expect(fmtValue('cost', 1.234)).toMatch(/1[.,]23/);
    expect(fmtValue('cost', 0.0042)).toMatch(/0[.,]0042/);
    expect(fmtValue('cost', 5, 'axis')).not.toMatch(/[.,]00/);
    expect(fmtValue('input_tokens', 1_250_000, 'axis').length).toBeLessThan(8);
    expect(fmtValue('input_tokens', 1234567)).toMatch(/1\D?234\D?567/);
  });
  it('reads a day as a local date', () => { const d = parseDay('2026-11-17'); expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 10, 17]); });
});

describe('colours', () => {
  it('Other is grey and the palette has no repeats', () => {
    expect(coloursFor('model', [{ key: '__other__' }])).toEqual([OTHER_COLOUR]);
    expect(new Set(PALETTE).size).toBe(PALETTE.length);
    expect(PALETTE.length).toBeGreaterThanOrEqual(7);
  });
  it('a series keeps its colour while the others change', () => {
    resetColours();
    const first = coloursFor('agent', [{ key: 'Builder' }, { key: 'Planner' }]);
    expect(coloursFor('agent', [{ key: 'Planner' }, { key: 'Builder' }, { key: 'Explorer' }]).slice(0, 2)).toEqual([first[1], first[0]]);
  });
  it('no two series on screen share a colour, however many names were seen across control changes', () => {
    resetColours();
    const names = ['Planner', 'Builder', 'Explorer', 'Orchestrator', 'Visualizer', 'CLI', 'Workflow: Builder', 'Workflow: Explorer', 'Role Reviewer', 'Drafter', 'Copy reviewer'];
    const views = [names.slice(0, 6), names.slice(2, 8), names.slice(5, 11), names.slice(0, 3).concat(names.slice(6, 9)), names.slice(4, 10), names.slice(0, 6), names.slice(6, 11).concat('Planner')];
    for (const v of views) {
      const series = [...v.map(key => ({ key })), { key: '__other__' }];
      const cols = coloursFor('agent', series);
      expect(new Set(cols).size).toBe(series.length);
    }
  });
  it('the largest series get clearly different hues', () => {
    resetColours();
    const cols = coloursFor('model', [{ key: 'Sonnet 4.5' }, { key: 'Opus 4.5' }, { key: 'Haiku 4.5' }]);
    for (let i = 0; i < cols.length; i++) for (let k = i + 1; k < cols.length; k++) {
      const d = Math.abs(hueOf(cols[i]) - hueOf(cols[k]));
      expect(Math.min(d, 360 - d)).toBeGreaterThanOrEqual(30);
    }
  });
});

describe('demo history draws every combination', () => {
  for (const period of PERIODS) for (const bucket of BUCKETS) for (const split of SPLITS) {
    it(`${period} / ${bucket} / ${split}`, () => {
      const d = demoUsage({ period, bucket, split });
      expect(d.buckets.length).toBeGreaterThan(0);
      expect(d.series.length).toBeGreaterThan(0);
      for (const s of d.series) for (const m of USAGE_MEASURES) expect(s.values[m]).toHaveLength(d.buckets.length);
      for (const m of USAGE_MEASURES) {
        const sum = bucketTotals(d.series, m, d.buckets.length).reduce((a, b) => a + b, 0);
        expect(sum).toBeCloseTo(d.totals[m], 3);
        expect(d.series.reduce((t, x) => t + x.totals[m], 0)).toBeCloseTo(d.totals[m], 3);
        const o = buildOption(d, m, bucket, split, TH, false) as unknown as { series: { data: number[] }[]; xAxis: { data: string[] } };
        expect(o.series).toHaveLength(d.series.length);
        expect(o.xAxis.data).toEqual(d.buckets.map(b => b.key));
      }
      expect(buildCsv(d).trim().split('\r\n')).toHaveLength(d.buckets.length * d.series.length + 1);
      if (bucket === 'week') for (const b of d.buckets) expect(parseDay(b.key).getDay()).toBe(1);   // weeks start on Monday
      expect(d.request).toEqual({ period, bucket, split, session: null });
    });
  }
  it('groups the small agents as Other, and one session narrows the chart', () => {
    const a = demoUsage({ period: 'all', bucket: 'day', split: 'agent' });
    expect(a.series.length).toBeLessThanOrEqual(7);
    expect(a.series.some(s => s.key === '__other__' && s.label === 'Other' && s.members.length > 0)).toBe(true);
    const id = a.sessions[0].id;
    const n = demoUsage({ period: 'all', bucket: 'day', split: 'agent', session: id });
    expect(n.totals.cost).toBeCloseTo(a.sessions[0].cost, 3);
    expect(n.totals.cost).toBeLessThan(a.totals.cost);
  });
  it('has running sessions, several kinds and both CLIs', () => {
    const d = demoUsage({ period: 'all', bucket: 'week', split: 'cli' });
    expect(d.sessions.filter(s => s.running).length).toBeGreaterThan(0);
    expect(new Set(d.sessions.map(s => s.kind))).toEqual(new Set(['plan', 'chat', 'workflow', 'review']));
    expect(d.sessions.map(s => s.kind_label)).toContain('CLI chat');
    expect(d.series.map(s => s.label).sort()).toEqual(['Claude', 'Cursor']);
  });
  it('the tooltip escapes labels and shows the bucket total', () => {
    const d = demoUsage({ period: '7d', bucket: 'day', split: 'agent' });
    d.series[0].label = '<img src=x>';
    const o = buildOption(d, 'cost', 'day', 'agent', TH, false) as unknown as { tooltip: { formatter: (p: unknown) => string } };
    const i = d.buckets.findIndex((_, k) => valuesOf(d.series[0], 'cost', d.buckets.length)[k] > 0);
    const html = o.tooltip.formatter([{ dataIndex: Math.max(i, 0) }]);
    expect(html).not.toContain('<img');
    expect(html).toContain('Total');
  });
});

describe('sessions and CSV', () => {
  it('running first, then by cost or time', () => {
    const d = demoUsage({ period: 'all', bucket: 'day', split: 'cli' });
    const byCost = sortSessions(d.sessions, { key: 'cost', dir: 'desc' });
    const run = byCost.filter(s => s.running).length;
    expect(byCost.slice(0, run).every(s => s.running)).toBe(true);
    const rest = byCost.slice(run).map(s => s.cost);
    expect(rest).toEqual([...rest].sort((a, b) => b - a));
    const byTime = sortSessions(d.sessions, { key: 'time', dir: 'asc' }).slice(run).map(s => Date.parse(s.started_at));
    expect(byTime).toEqual([...byTime].sort((a, b) => a - b));
  });
  it('CSV follows the contract: one row per bucket and series, commas quoted, formula-looking labels kept as text', () => {
    const z = { input_tokens: [0], output_tokens: [0], cache_read_tokens: [0], cache_write_tokens: [0] };
    const d = { buckets: [{ key: '2026-11-16', label: 'Week of 16 Nov', start: '2026-11-17', end: '2026-11-22', partial: true }], series: [{ key: 'a', label: '=SUM(A1), "x"', members: [], totals: { cost: 1.5, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, calls: 1 }, values: { cost: [1.5], ...z } }] };
    const rows = buildCsv(d).trim().split('\r\n');
    expect(buildCsv(d).startsWith('\uFEFF')).toBe(true);          // for Excel; trim() above strips it
    expect(rows[0]).toBe('period_start,period_end,group,cost_usd,input_tokens,output_tokens,cache_read_tokens,cache_write_tokens');
    expect(rows[1]).toBe('2026-11-17,2026-11-22,"\'=SUM(A1), ""x""",1.5,0,0,0,0');
    expect(csvName('model', 'week', true)).toBe('launchpad-usage-by-model-per-week-one-session.csv');
    expect(hasBars(d, 'input_tokens')).toBe(false);
    expect(hasBars(d, 'cost')).toBe(true);
  });
});
