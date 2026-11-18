/* Usage helpers: formats, stable colours, the chart option and CSV for every combination of period / bucket / split / measure
   (against the in-page demo history), sessions sort. Zero back end. */
import { describe, expect, it } from 'vitest';
import { USAGE_MEASURES, type UsageBucket, type UsagePeriod, type UsageSplit } from '../contract';
import { demoUsage } from '../demo/usageDemo';
import {
  buildCsv, buildOption, bucketTotals, coloursFor, resetColours, csvName, fillBuckets, fmtValue, BAR_MAX, BAR_RADIUS, topSegments, hasData, labelInterval, lonePoints, OTHER_COLOUR, PALETTE, parseDay, sortSessions, valuesOf, type ChartTheme,
} from './usageChart';
import type { UsageSeries } from '../contract';

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
        const o = buildOption(d, m, bucket, split, TH, { motion: 'none' }) as unknown as { series: { data: number[] }[]; xAxis: { data: string[] } };
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
    const o = buildOption(d, 'cost', 'day', 'agent', TH, { motion: 'none' }) as unknown as { tooltip: { formatter: (p: unknown) => string } };
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
    expect(hasData(d, 'input_tokens')).toBe(false);
    expect(hasData(d, 'cost')).toBe(true);
  });
});

/* ---------- the area chart ---------- */
type Pt = number | { value: number; itemStyle?: { opacity: number } };
type Opt = {
  animation: boolean; animationDuration?: number;
  xAxis: { data: string[]; boundaryGap: boolean; axisLine: { show: boolean }; splitLine: { show: boolean }; axisLabel: { interval: number } };
  yAxis: { min: number; axisLine: { show: boolean }; splitLine: { show: boolean } };
  tooltip: { trigger: string; axisPointer: { type: string; snap: boolean }; formatter: (p: unknown) => string };
  series: { id: string; type: string; stack: string; smooth: number; smoothMonotone: string; areaStyle: { color: { type: string; colorStops: { color: string }[] } }; lineStyle: { width: number; color: string }; itemStyle: { opacity: number }; data: Pt[] }[];
};
const zero5 = (n: number) => ({ input_tokens: Array(n).fill(0), output_tokens: Array(n).fill(0), cache_read_tokens: Array(n).fill(0), cache_write_tokens: Array(n).fill(0) });
const ser = (key: string, cost: number[], members: string[] = []): UsageSeries => ({ key, label: key === '__other__' ? 'Other' : key, members, values: { cost, ...zero5(cost.length) }, totals: { cost: cost.reduce((a, b) => a + b, 0), input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, calls: 1 } });
const day = (key: string) => ({ key, label: key, start: key, end: key, partial: false });
const value = (p: Pt) => (typeof p === 'number' ? p : p.value);
const visible = (p: Pt) => typeof p !== 'number' && p.itemStyle?.opacity === 1;

describe('area chart option', () => {
  it('draws smooth monotone stacked areas with a fading fill, faint horizontal gridlines only, y from zero', () => {
    resetColours();
    const d = demoUsage({ period: '30d', bucket: 'day', split: 'model' });
    const o = buildOption(d, 'cost', 'day', 'model', TH) as unknown as Opt;
    expect(o.series.length).toBe(d.series.length);
    for (const s of o.series) {
      expect(s.type).toBe('line');
      expect(s.stack).toBe('total');
      expect(s.smooth).toBeGreaterThan(0);
      expect(s.smoothMonotone).toBe('x');                     // horizontal handles: never below zero or above the real values
      expect(s.areaStyle.color.type).toBe('linear');
      expect(s.areaStyle.color.colorStops.at(-1)!.color).toMatch(/,0\.0\d*\)$/);
      expect(s.lineStyle.width).toBeLessThanOrEqual(2.5);
      expect(s.itemStyle.opacity).toBe(0);                    // points only on hover
    }
    expect(o.series.map(s => s.id)).toEqual(d.series.map(s => s.key));
    expect(o.xAxis.splitLine.show).toBe(false);
    expect(o.xAxis.axisLine.show).toBe(false);
    expect(o.yAxis.axisLine.show).toBe(false);
    expect(o.yAxis.splitLine.show).toBe(true);
    expect(o.yAxis.min).toBe(0);
    expect(o.xAxis.boundaryGap).toBe(false);
    expect(o.tooltip.axisPointer).toMatchObject({ type: 'line', snap: true });
    expect(o.animation).toBe(true);
    expect(o.animationDuration).toBeGreaterThan(0);          // the one-time draw-in
  });
  it('morphs quickly after the first draw and stands still when asked', () => {
    const d = demoUsage({ period: '7d', bucket: 'day', split: 'cli' });
    expect((buildOption(d, 'cost', 'day', 'cli', TH, { motion: 'update' }) as unknown as Opt).animationDuration).toBe(0);
    expect((buildOption(d, 'cost', 'day', 'cli', TH, { motion: 'none' }) as unknown as Opt).animation).toBe(false);
  });
  it('thins the date labels as the period grows', () => {
    expect(labelInterval(7)).toBe(0);
    expect(Math.ceil(30 / (labelInterval(30) + 1))).toBeLessThanOrEqual(7);
    expect(Math.ceil(90 / (labelInterval(90) + 1))).toBeLessThanOrEqual(7);
  });
  it('a legend pill hides a series without changing the colours of the others; Other stays grey', () => {
    resetColours();
    const d = demoUsage({ period: 'all', bucket: 'day', split: 'agent' });
    const all = buildOption(d, 'cost', 'day', 'agent', TH) as unknown as Opt;
    const gone = d.series[1].key;
    const part = buildOption(d, 'cost', 'day', 'agent', TH, { hidden: [gone] }) as unknown as Opt;
    expect(part.series.map(s => s.id)).not.toContain(gone);
    for (const s of part.series) expect(s.lineStyle.color).toBe(all.series.find(x => x.id === s.id)!.lineStyle.color);
    expect(part.series.find(s => s.id === '__other__')!.lineStyle.color).toBe(OTHER_COLOUR);
    const i = d.buckets.findIndex((_, k) => d.series.some(s => s.values.cost[k] > 0));
    expect(part.tooltip.formatter([{ dataIndex: i }])).toContain('Total shown');
  });
  it('the tooltip lists the series largest first, with exact figures and the total in bold', () => {
    const d = { buckets: [day('2026-11-16'), day('2026-11-17')], series: [ser('Small', [0.5, 1]), ser('Big', [2, 3]), ser('__other__', [0.25, 0], ['Drafter', 'Role Reviewer'])] };
    const html = (buildOption(d, 'cost', 'day', 'agent', TH) as unknown as Opt).tooltip.formatter([{ dataIndex: 0 }]);
    expect(html.indexOf('Big')).toBeLessThan(html.indexOf('Small'));
    expect(html.indexOf('Small')).toBeLessThan(html.indexOf('Other'));
    expect(html).toContain('Drafter, Role Reviewer');
    expect(html).toMatch(/<b>Total<\/b>.*<b>[^<]*2[.,]75[^<]*<\/b>/);
  });
});

describe('sparse data', () => {
  it('one bucket with data: centred, with clear points (no line can show it)', () => {
    resetColours();
    const d = { buckets: [day('2026-11-17')], series: [ser('Claude', [0.42]), ser('Cursor', [0.1])] };
    const o = buildOption(d, 'cost', 'day', 'cli', TH) as unknown as Opt;
    expect(o.xAxis.boundaryGap).toBe(true);
    for (const s of o.series) expect(visible(s.data[0])).toBe(true);
    expect(lonePoints([0.42])).toEqual([true]);
  });
  it('a series seen in one bucket only gets a visible point there, and nowhere else', () => {
    expect(lonePoints([0, 0.3, 0, 0, 0.1, 0.2, 0])).toEqual(Array(7).fill(false));   // several days: its band shows it
    const v = [0, 0, 0.3, 0, 0, 0, 0, 0, 0];
    expect(lonePoints(v)).toEqual([false, false, true, false, false, false, false, false, false]);
    const d = { buckets: v.map((_, i) => day(`2026-11-${String(i + 1).padStart(2, '0')}`)), series: [ser('Builder', v)] };
    const s = (buildOption(d, 'cost', 'day', 'agent', TH) as unknown as Opt).series[0];
    expect(s.data.map(visible)).toEqual(lonePoints(v));
    expect(s.data.map(value)).toEqual(v);
  });
  it('fills the days the reply skipped with zeros, so the line spans the whole period', () => {
    const d = { range: { start: '2026-11-11', end: '2026-11-17' }, buckets: [day('2026-11-12'), day('2026-11-16')], series: [ser('Claude', [1, 2])] };
    const f = fillBuckets(d, 'day');
    expect(f.buckets.map(b => b.key)).toEqual(['2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14', '2026-11-15', '2026-11-16', '2026-11-17']);
    expect(f.series[0].values.cost).toEqual([0, 1, 0, 0, 0, 2, 0]);
    expect(f.series[0].values.output_tokens).toEqual([0, 0, 0, 0, 0, 0, 0]);
    expect(f.series[0].totals).toBe(d.series[0].totals);
    expect(f.buckets[1]).toBe(d.buckets[0]);                  // the server's own bucket objects are kept
  });
  it('fills skipped weeks from Monday to Monday and marks the cut ones partial', () => {
    const d = { range: { start: '2026-10-29', end: '2026-11-17' }, buckets: [{ key: '2026-11-09', label: 'Week of 9 Nov', start: '2026-11-09', end: '2026-11-15', partial: false }], series: [ser('Claude', [3])] };
    const f = fillBuckets(d, 'week');
    expect(f.buckets.map(b => b.key)).toEqual(['2026-10-26', '2026-11-02', '2026-11-09', '2026-11-16']);
    expect(f.buckets[0]).toMatchObject({ start: '2026-10-29', end: '2026-11-01', partial: true });
    expect(f.buckets[3]).toMatchObject({ start: '2026-11-16', end: '2026-11-17', partial: true });
    expect(f.series[0].values.cost).toEqual([0, 0, 3, 0]);
  });
  it('leaves a complete reply, one with no range, and one it cannot place exactly as sent', () => {
    for (const period of PERIODS) for (const bucket of BUCKETS) {
      const d = demoUsage({ period, bucket, split: 'cli' });
      expect(fillBuckets(d, bucket)).toBe(d);
    }
    const none = { range: null, buckets: [], series: [] };
    expect(fillBuckets(none, 'day')).toBe(none);
    const odd = { range: { start: '2026-11-16', end: '2026-11-17' }, buckets: [day('2026-10-01')], series: [ser('x', [1])] };
    expect(fillBuckets(odd, 'day')).toBe(odd);
  });
});

/* ---------- the bar form ---------- */
type BarPt = number | { value: number; itemStyle?: { borderRadius?: number[] } };
type BarOpt = {
  animation: boolean; animationDuration?: number; stateAnimation: { duration: number };
  xAxis: { boundaryGap: boolean; data: string[] };
  tooltip: { trigger: string; transitionDuration: number; confine: boolean; axisPointer: { type: string; snap: boolean; animation: boolean; shadowStyle: { opacity: number } };
    position: (point: number[], params: unknown, el: unknown, rect: unknown, size: { contentSize: number[]; viewSize: number[] }) => number[]; formatter: (p: unknown) => string };
  series: { id: string; type: string; stack: string; barMaxWidth: number; barCategoryGap: string; itemStyle: { color: string; borderRadius: number }; emphasis: { focus: string }; data: BarPt[] }[];
};
const rounded = (p: BarPt) => typeof p !== 'number' && !!p.itemStyle?.borderRadius && p.itemStyle.borderRadius[0] === BAR_RADIUS && p.itemStyle.borderRadius[2] === 0;
const bars = (d: Parameters<typeof buildOption>[0], o: Parameters<typeof buildOption>[5] = {}) => buildOption(d, 'cost', 'day', 'agent', TH, { type: 'bar', ...o }) as unknown as BarOpt;

describe('bar chart option', () => {
  const d3 = { buckets: [day('2026-11-15'), day('2026-11-16'), day('2026-11-17')], series: [ser('A', [1, 2, 0]), ser('B', [0.5, 0, 0]), ser('C', [0.2, 0, 0.4])] };
  it('stacks every visible series as bars with a sensible maximum width and the same colours as the line form', () => {
    resetColours();
    const o = bars(d3), l = buildOption(d3, 'cost', 'day', 'agent', TH) as unknown as Opt;
    for (const s of o.series) {
      expect(s.type).toBe('bar');
      expect(s.stack).toBe('total');
      expect(s.barMaxWidth).toBe(BAR_MAX);
      expect(parseFloat(s.barCategoryGap)).toBeGreaterThanOrEqual(30);
      expect(s.emphasis.focus).toBe('none');                       // the other series never dim
    }
    expect(BAR_MAX).toBeLessThanOrEqual(40);
    expect(o.series.map(s => s.itemStyle.color)).toEqual(l.series.map(s => s.lineStyle.color));
    expect(new Set(o.series.map(s => s.itemStyle.color)).size).toBe(o.series.length);
    expect(o.xAxis.boundaryGap).toBe(true);
  });
  it('rounds the top corners of the top-most visible segment of each bar only', () => {
    const o = bars(d3);
    expect(o.series.map(s => s.data.map(rounded))).toEqual([[false, true, false], [false, false, false], [true, false, true]]);   // C on top in buckets 1 and 3, A alone in 2
    expect(topSegments([[1, 2, 0], [0.5, 0, 0], [0.2, 0, 0.4]], [0, 1, 2], 3)).toEqual([2, 0, 2]);
  });
  it('moves the rounded top down when a legend pill hides the top series', () => {
    const o = bars(d3, { hidden: ['C'] });
    expect(o.series.map(s => s.id)).toEqual(['A', 'B']);
    expect(o.series.map(s => s.data.map(rounded))).toEqual([[false, true, false], [true, false, false]]);
    expect(o.series.flatMap(s => s.data).map(p => (typeof p === 'number' ? p : p.value))).toEqual([1, 2, 0, 0.5, 0, 0]);   // bucket 3 empty: nothing drawn, place kept
  });
  it('triggers the tooltip by bucket with a soft gliding band and the same card, eased and confined', () => {
    const o = bars(d3);
    expect(o.tooltip.trigger).toBe('axis');
    expect(o.tooltip.axisPointer).toMatchObject({ type: 'shadow', snap: true, animation: true, z: 1 });   // behind the bars
    expect(o.tooltip.axisPointer.shadowStyle.opacity).toBeLessThan(0.6);
    expect(o.tooltip.transitionDuration).toBeGreaterThan(0);
    expect(o.tooltip.confine).toBe(true);
    expect(o.stateAnimation.duration).toBeGreaterThan(0);
    const line = (buildOption(d3, 'cost', 'day', 'agent', TH) as unknown as BarOpt).tooltip.formatter([{ dataIndex: 0 }]);
    expect(o.tooltip.formatter([{ dataIndex: 0 }])).toBe(line);
    expect(o.tooltip.formatter([{ axisValue: '2026-11-17' }])).toMatch(/0[.,]40/);
  });
  it('places the tooltip beside the hovered bar, never over it, and inside the chart', () => {
    const at = (i: number) => 100 + i * 200;                       // bucket centres; band 200 px, so bars are capped at BAR_MAX
    const o = bars(d3, { pixelOf: at });
    const size = { contentSize: [180, 120], viewSize: [620, 320] };
    const [x1, y1] = o.tooltip.position([90, 200], [{ dataIndex: 0 }], null, null, size);
    expect(x1).toBeGreaterThanOrEqual(at(0) + BAR_MAX / 2);       // to the right of the first bar
    const [x3] = o.tooltip.position([510, 200], [{ dataIndex: 2 }], null, null, size);
    expect(x3 + 180).toBeLessThanOrEqual(at(2) - BAR_MAX / 2);    // no room on the right: to the left of the last bar
    expect(x3).toBeGreaterThanOrEqual(0);
    expect(y1).toBeGreaterThanOrEqual(0);
    expect(y1 + 120).toBeLessThanOrEqual(320);
    const [xa, ya] = o.tooltip.position([115, 40], [{ dataIndex: 0 }], null, null, size);
    expect([xa, ya]).toEqual([x1, y1]);                           // the pointer moving inside one bucket does not move the card
  });
  it('one bucket draws one centred bar of capped width; reduced motion stands still', () => {
    const o = bars({ buckets: [day('2026-11-17')], series: [ser('A', [0.3])] }, { reduced: true, motion: 'none' });
    expect(o.xAxis.boundaryGap).toBe(true);
    expect(o.series[0].barMaxWidth).toBe(BAR_MAX);
    expect(rounded(o.series[0].data[0])).toBe(true);
    expect(o.animation).toBe(false);
    expect(o.tooltip.transitionDuration).toBe(0);
    expect(o.tooltip.axisPointer.animation).toBe(false);
    expect(o.stateAnimation.duration).toBe(0);
  });
  it('switching Line / Bar gets one quick transition', () => {
    const o = bars(d3, { motion: 'switch' });
    expect(o.animation).toBe(true);
    expect(o.animationDuration).toBeGreaterThan(0);
    expect(o.animationDuration).toBeLessThanOrEqual(400);
  });
});
