// @vitest-environment happy-dom
/* Missions against the in-page demo: a system per run, Stop run (two clicks), star pinning, step agents. */
import { it, expect, vi } from 'vitest';
import { act } from 'react';
import { actions, getState } from '../../store';
import { useDemoApp, step, q, qa, doc, click, byText, sentOf } from '../../test/demoApp';

useDemoApp();

it('Missions: a system per run with its steps; Stop run takes two clicks; Move to Landed', async () => {
  await act(async () => { actions.setView('missions'); });
  await step(300);
  const cells = qa('#missionList .sys-cell');
  expect(cells.length).toBeGreaterThanOrEqual(2);
  const a = cells.find(c => c.querySelector('svg[data-sys="S-A"]'))!;
  expect(a.querySelectorAll('.st-planet').length).toBe(getState().sessions['S-A'].run!.steps.length);
  expect(a.querySelector('.star-g')?.getAttribute('data-tip')).toBe('run:S-A');
  expect(a.querySelector('g.dyn')).toBeTruthy();
  expect(q('#missionSum')?.textContent).toMatch(/in flight · \d+ on the pad · \d+ finished/);

  await click(byText('#missionList .sys-cell button', 'Stop run'));
  expect(sentOf('run_stop')).toHaveLength(0);
  expect(byText('#missionList button', 'Confirm stop')).toBeTruthy();
  await click(byText('#missionList button', 'Confirm stop'));
  expect(sentOf('run_stop')).toHaveLength(1);
  await step(3_000);
  const stopped = qa('#missionList .sys-cell.fin');
  expect(stopped.length).toBeGreaterThanOrEqual(1);
  await click(byText('#missionList .sys-cell.fin button', 'Move to Landed'));
  expect(byText('#missionList .pad h3', 'Landed')).toBeTruthy();
});

it('Missions: clicking a star pins its agent and scrolls that agent\'s feed row into view', async () => {
  await act(async () => { actions.setView('missions'); });
  await step(300);
  const star = q('#missionList svg[data-sys="S-A"] .star-g')!;
  const id = star.getAttribute('data-agent')!;
  expect(id).toBeTruthy();
  const rows = qa(`#feedList [data-hover-agent="${id}"]`);
  expect(rows.length).toBeGreaterThan(0);                    // both sides use the same attribute
  const spy = vi.fn();
  for (const r of rows) { r.scrollIntoView = spy; Object.defineProperty(r, 'offsetParent', { configurable: true, get: () => doc().body }); }
  await act(async () => { star.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  expect(getState().ui.sel).toBe(id);
  expect(spy).toHaveBeenCalledTimes(1);
});

it('Missions: steps with their own agent show it under the system', async () => {
  await act(async () => { actions.setView('missions'); });
  await step(300);
  const b = qa('#missionList .sys-cell').find(c => c.querySelector('svg[data-sys="S-B"]'))!;
  expect(b.querySelector('.sys-agents')?.textContent).toContain('Step 3');
  expect(b.querySelector('.sys-agents .stepagent')?.textContent).toBe('Sql reviewer');
  expect(b.querySelector('.st-agent[data-purpose="reviewing"]')).toBeTruthy();
});
