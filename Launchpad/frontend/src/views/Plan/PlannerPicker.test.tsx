// @vitest-environment happy-dom
/* The planner picker under the planner's chat box, against the in-page demo: options from the server (Cursor disabled),
   keyboard menu, the empty state of a new plan (a choice applies at once), a choice the running plan cannot take
   (noted for the next plan), auto-promote and its rules, New plan. */
import { expect, it } from 'vitest';
import { act } from 'react';
import { getState } from '../../store';
import { click, doc, q, qa, sentOf, step, useDemoApp } from '../../test/demoApp';

useDemoApp();

const btn = () => q<HTMLButtonElement>('#pkBtn')!;
const menu = () => q('#pkMenu');
const opt = (id: string) => q<HTMLButtonElement>(`#pkMenu [data-option="${id}"]`);
const press = async (k: string, shift = false) => {
  await act(async () => { (doc().activeElement as HTMLElement).dispatchEvent(new KeyboardEvent('keydown', { key: k, shiftKey: shift, bubbles: true, cancelable: true })); });
};

it('shows the current choice, lists the server options with Cursor disabled, and Escape / arrows / Tab work', async () => {
  expect(q('#viewPlan .chat-head #newPlan')).toBeNull();
  expect(q('#pmModel')).toBeNull();
  expect(q('#pmPromote')).toBeNull();
  expect(btn().textContent).toContain('Claude · Sonnet');
  expect(btn().getAttribute('aria-haspopup')).toBe('menu');

  await click(btn());
  expect(menu()).toBeTruthy();
  expect(btn().getAttribute('aria-expanded')).toBe('true');
  expect(doc().activeElement).toBe(opt('claude:sonnet'));            // focus on the current choice
  expect(opt('claude:sonnet')!.getAttribute('aria-checked')).toBe('true');
  const cursor = qa<HTMLButtonElement>('#pkMenu [data-option^="cursor:"]');
  expect(cursor.length).toBeGreaterThan(0);
  for (const c of cursor) { expect(c.getAttribute('aria-disabled')).toBe('true'); expect(c.textContent).toContain('not available yet'); }
  await click(cursor[0]);                                             // disabled: nothing sent, menu stays
  expect(sentOf('planner_choose')).toHaveLength(0);

  /* every item is reachable with the arrow keys and with Tab */
  opt('claude:sonnet')!.focus();
  await press('ArrowDown');
  expect(doc().activeElement).toBe(opt('claude:opus'));
  await press('End');
  expect(doc().activeElement?.id).toBe('pkNewPlan');
  await press('Tab');
  expect(doc().activeElement).toBe(opt('claude:sonnet'));
  await press('Tab', true);
  expect(doc().activeElement?.id).toBe('pkNewPlan');
  await press('ArrowUp');
  expect(doc().activeElement?.id).toBe('pkRules');
  await press('ArrowUp');
  expect(doc().activeElement?.id).toBe('pkAuto');

  await press('Escape');
  expect(menu()).toBeNull();
  expect(doc().activeElement).toBe(btn());

  /* ArrowUp on the button opens it again */
  await press('ArrowUp');
  expect(menu()).toBeTruthy();
});

it('new plan: before the first message a choice applies at once; a step down on a running plan is noted for the next plan', async () => {
  await click(btn());
  await click(q('#pkNewPlan'));                                        // Session C has an unlaunched plan: confirm first
  expect(q('#pkNewPlan')?.textContent).toContain('Set this plan aside?');
  await click(q('#pkNewPlan'));
  const dm = q('.dirmenu');
  if (dm && !dm.hidden) await click(qa('.dirmenu button[role="menuitem"]')[0]);
  await step(1_000);
  expect(sentOf('new_session')).toHaveLength(1);
  const sid = getState().current!;
  expect(getState().sessions[sid].plannerStarted).toBe(false);

  /* empty state: the new plan takes Opus at once, no note */
  await click(btn());
  expect(opt('claude:opus')!.textContent).not.toContain('next new plan');
  await click(opt('claude:opus'));
  expect(sentOf('planner_choose').at(-1)).toEqual({ type: 'planner_choose', option_id: 'claude:opus', session_id: sid });
  await step(1_000);
  expect(btn().textContent).toContain('Claude · Opus');
  expect(q('#pkNote')).toBeNull();

  /* the plan starts; a step down to Sonnet now applies to the next new plan, and the row says so */
  const input = q<HTMLInputElement>('#msgInput')!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'plan a small thing'); input.dispatchEvent(new Event('input', { bubbles: true })); });
  await act(async () => { input.form!.requestSubmit(); });
  await step(1_000);
  expect(getState().sessions[sid].plannerStarted).toBe(true);
  await click(btn());
  expect(opt('claude:sonnet')!.textContent).toContain('from your next new plan');
  await click(opt('claude:sonnet'));
  await step(1_000);
  expect(btn().textContent).toContain('Claude · Opus');                // this plan keeps Opus
  expect(q('#pkNote')?.textContent).toContain('Claude · Sonnet applies to your next new plan');
  await click(btn());
  expect(opt('claude:sonnet')!.textContent).toContain('next plan');
});

it('auto-promote toggle sends the setting; Rules shows the criteria read-only', async () => {
  await click(btn());
  const auto = q<HTMLButtonElement>('#pkAuto')!;
  expect(auto.textContent).toContain('Auto-promote to Opus');
  expect(auto.getAttribute('aria-checked')).toBe('true');
  await click(auto);
  expect(sentOf('set_settings').at(-1)).toEqual({ type: 'set_settings', patch: { planner_auto_promote: false } });
  await step(500);
  expect(q('#pkAuto')!.getAttribute('aria-checked')).toBe('false');

  await click(q('#pkRules'));
  expect(menu()).toBeNull();
  const modal = q('.modal');
  expect(modal?.textContent).toContain('Promotion rules');
  expect(modal?.textContent).toContain('read-only');
  expect(modal?.querySelector('textarea')).toBeNull();
});
