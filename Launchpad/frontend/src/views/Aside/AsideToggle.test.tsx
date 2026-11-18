// @vitest-environment happy-dom
/* Closing and reopening the right-hand panel against the in-page demo: the strip takes its place, the waiting count sits
   above the arrow (live, read as "N waiting", gone at zero), the choice survives a reload, and it works on Files and Usage. */
import { expect, it } from 'vitest';
import { act } from 'react';
import { dispatch, getState, sel, useLaunchpad } from '../../store';
import { initialState } from '../../store/initial';
import { LS_ASIDE } from '../../lib/storage';
import { useDemoApp, step, q, click } from '../../test/demoApp';

useDemoApp();
const closeBtn = () => q('#asideClose');

it('closes to a slim strip with the waiting count, and opens again', async () => {
  expect(q('aside .queue')).toBeTruthy();
  const waiting = sel.openCount(getState());
  expect(waiting).toBeGreaterThan(0);
  /* the handle sits on the panel itself (centred on its boundary with the view by CSS), not in a card's head */
  expect(q('aside > #asideClose')).toBeTruthy();
  expect(q('.fl-head #asideClose, .feed #asideClose, #repos #asideClose')).toBeNull();
  expect(closeBtn()!.tagName).toBe('BUTTON');
  expect(closeBtn()!.getAttribute('aria-label')).toContain('Close the side panel');
  expect(closeBtn()!.getAttribute('aria-expanded')).toBe('true');
  expect(closeBtn()!.getAttribute('data-tip')).toBe('text:Close the panel');
  await click(closeBtn());
  await step(10);
  expect(q('aside .queue')).toBeNull();
  expect(q('aside.aside-strip')).toBeTruthy();
  expect(getState().ui.asideClosed).toBe(true);
  expect(JSON.parse(localStorage.getItem(LS_ASIDE)!)).toBe(true);
  expect(q('#asideCount')!.textContent).toContain(`${waiting} waiting`);
  expect(q('.aside-mid > .aside-count-slot + #asideOpen')).toBeTruthy();   // the count just above the arrow, together at mid-height
  expect(q('.aside-count-slot')!.getAttribute('role')).toBe('status');
  expect(q('#asideOpen')!.getAttribute('aria-label')).toContain(`${waiting} waiting`);
  expect(q('#asideOpen')!.getAttribute('data-tip')).toBe('text:Show In orbit and Incoming');
  expect(document.activeElement).toBe(q('#asideOpen'));
  await click(q('#asideOpen'));
  await step(10);
  expect(q('aside.aside-strip')).toBeNull();
  expect(q('aside .queue')).toBeTruthy();
  expect(q('aside')!.classList.contains('aside-in')).toBe(true);
  expect(document.activeElement).toBe(q('#asideClose'));
  expect(JSON.parse(localStorage.getItem(LS_ASIDE)!)).toBe(false);
});

it('the count follows Incoming live and is gone at zero', async () => {
  await click(closeBtn());
  const before = sel.openCount(getState());
  await act(async () => { dispatch({ type: 'queue_item', id: 'zz-q', kind: 'question', session_id: null, agent: 'Builder', title: 'One more?', body: 'Pick one', options: ['a', 'b'] } as never); });
  expect(sel.openCount(getState())).toBe(before + 1);
  expect(q('#asideCount')!.textContent).toContain(`${before + 1} waiting`);
  await act(async () => { useLaunchpad.setState(st => ({ ...st, queue: [] })); });
  expect(q('#asideCount')).toBeNull();
  expect(q('.aside-count-slot')).toBeTruthy();                 // the live region stays
  expect(q('#asideOpen')!.getAttribute('aria-label')).not.toContain('waiting');
});

it('stays closed across a reload and on the Files and Usage views', async () => {
  await click(closeBtn());
  expect(initialState().ui.asideClosed).toBe(true);             // what a reload starts from
  await click(q('#tab-files'));
  await step(500);
  expect(q('aside.aside-strip')).toBeTruthy();
  expect(q('#repos')).toBeNull();
  expect(q('#asideOpen')!.getAttribute('data-tip')).toBe('text:Show Repos');
  await click(q('#asideOpen'));
  await step(500);
  expect(q('#repos')).toBeTruthy();
  expect(q('aside > #asideClose')).toBeTruthy();
  await click(closeBtn());
  await click(q('#tab-usage'));
  await step(500);
  expect(q('aside.aside-strip')).toBeTruthy();
  expect(q('#viewUsage')).toBeTruthy();
});
