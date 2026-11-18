// @vitest-environment happy-dom
/* Usage view against the in-page demo: sidebar entry, header total opens it, request on open and on control change (not on
   measure), totals, legend, sessions table (running first, sort, narrow with a removable chip), CSV, note and the empty state. */
import { expect, it, vi } from 'vitest';
import { act } from 'react';
import { dispatch, getState } from '../../store';
import { useDemoApp, step, q, qa, click, sentOf, byText } from '../../test/demoApp';

useDemoApp();
const open = async () => { await click(q('header .usage')); await step(1000); };
const last = () => sentOf('usage_get').at(-1) as { period: unknown; bucket: string; split: string; session?: string | null };

it('opens from the header total and the sidebar, and keeps the hover tip', async () => {
  const pill = q('header .usage')!;
  expect(pill.tagName).toBe('BUTTON');
  expect(pill.getAttribute('data-tip')).toBe('allagents');
  await open();
  expect(getState().ui.view).toBe('usage');
  expect(q('#tab-usage')!.getAttribute('aria-selected')).toBe('true');
  expect(last()).toMatchObject({ period: '30d', bucket: 'day', split: 'cli' });
});

it('shows totals, a legend, the note and the sessions table with running ones first', async () => {
  await open();
  expect(qa('.us-totals li')).toHaveLength(5);
  expect(qa('.us-legend li').length).toBeGreaterThan(0);
  expect(q('#usNote')!.textContent).toContain('equivalent costs, not a bill');
  const states = qa('#usSessions tbody .status').map(s => s.textContent);
  const firstFinished = states.indexOf('Finished');
  expect(firstFinished).toBeGreaterThan(0);
  expect(states.slice(0, firstFinished).every(s => s === 'Running')).toBe(true);
});

it('asks again for period, bucket and split but not for the measure', async () => {
  await open();
  const n = sentOf('usage_get').length;
  await click(byText('.us-ctl .seg button', 'Week'));
  await step(500);
  expect(last()).toMatchObject({ bucket: 'week' });
  await click(byText('.us-ctl .seg button', 'Agent'));
  await click(byText('.us-ctl .seg button', 'All'));
  await step(500);
  expect(last()).toMatchObject({ period: 'all', split: 'agent', bucket: 'week' });
  expect(qa('.us-legend li').some(li => li.textContent!.startsWith('Other'))).toBe(true);
  const m = sentOf('usage_get').length;
  expect(m).toBeGreaterThan(n);
  const sel = q<HTMLSelectElement>('#usMeasure')!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!.call(sel, 'cache_read_tokens'); sel.dispatchEvent(new Event('change', { bubbles: true })); });
  await step(500);
  expect(sentOf('usage_get').length).toBe(m);
  expect(qa('.us-totals li.on .us-tl')[0].textContent).toBe('Cache read tokens');
});

it('a session row narrows the chart with a chip that clears it, and sorts by cost', async () => {
  await open();
  const first = qa('#usSessions tbody tr')[3];
  await click(first.querySelector('.us-rowb'));
  await step(500);
  expect(last().session).toBeTruthy();
  expect(q('#usSessionChip')).toBeTruthy();
  const rowsBefore = qa('#usSessions tbody tr').length;
  await click(q('#usSessionChip button'));
  await step(500);
  expect(q('#usSessionChip')).toBeNull();
  expect(last().session).toBeNull();
  expect(qa('#usSessions tbody tr').length).toBe(rowsBefore);
  await click(byText('.us-sortb', 'Cost'));
  expect(q('th[aria-sort="descending"]')!.textContent).toContain('Cost');
});

it('Download CSV hands the chart data to a download', async () => {
  await open();
  const create = vi.fn(() => 'blob:x');
  (URL as unknown as { createObjectURL: unknown }).createObjectURL = create;
  (URL as unknown as { revokeObjectURL: unknown }).revokeObjectURL = () => {};
  await click(q('#usCsv'));
  expect(create).toHaveBeenCalledTimes(1);
});

it('an empty log says nothing is recorded yet; an empty period offers the controls', async () => {
  await open();
  const zero = { cost: 0, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0 };
  await act(async () => { dispatch({ type: 'usage_data', range: { start: '2026-11-11', end: '2026-11-17' }, buckets: [], series: [], totals: zero, sessions: [] }); });
  expect(q('#viewUsage .empty')!.textContent).toContain('Nothing recorded in this period.');
  expect(q('.us-controls')).toBeTruthy();
  await click(byText('.us-ctl .seg button', 'All'));
  await act(async () => { dispatch({ type: 'usage_data', range: null, buckets: [], series: [], totals: zero, sessions: [] }); });
  expect(q('#viewUsage .empty')!.textContent).toBe('Nothing recorded yet.Spend is recorded from now on.');
  expect(q<HTMLButtonElement>('#usCsv')!.disabled).toBe(true);
});

it('ignores a reply or push for controls the page no longer has, and stops the pushes when the screen is left', async () => {
  await open();
  const zero = { cost: 0, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0 };
  const before = getState().usage.data;
  await act(async () => { dispatch({ type: 'usage_data', request: { period: '7d', bucket: 'week', split: 'model', session: null }, range: null, buckets: [], series: [], totals: zero, sessions: [], pushed: true }); });
  expect(getState().usage.data).toBe(before);
  await click(q('#tab-plan'));
  expect(sentOf('usage_stop')).toHaveLength(1);
});
