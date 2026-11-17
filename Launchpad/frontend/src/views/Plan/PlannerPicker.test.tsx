// @vitest-environment happy-dom
/* The planner picker under the planner's chat box, against the in-page demo: two levels (a CLI dropdown with Cursor
   listed but not selectable, then that CLI's models), keyboard menu, the empty state of a new plan (a choice applies at once), a choice the running plan cannot take
   (noted for the next plan), auto-promote and its rules, New plan. */
import { expect, it, vi } from 'vitest';
import { act } from 'react';
import { actions, dispatch, getState } from '../../store';
import { click, doc, q, qa, sentOf, step, useDemoApp } from '../../test/demoApp';

useDemoApp();

const btn = () => q<HTMLButtonElement>('#pkBtn')!;
const menu = () => q('#pkMenu');
const opt = (id: string) => q<HTMLButtonElement>(`#pkMenu [data-option="${id}"]`);
const press = async (k: string, shift = false) => {
  await act(async () => { (doc().activeElement as HTMLElement).dispatchEvent(new KeyboardEvent('keydown', { key: k, shiftKey: shift, bubbles: true, cancelable: true })); });
};

const cli = () => q<HTMLButtonElement>('#pkCli')!;
const harness = (h: string) => q<HTMLButtonElement>(`#pkCliList [data-harness="${h}"]`);

it('shows the current choice, a CLI dropdown then only that CLI\'s models, and Escape / arrows / Tab work', async () => {
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
  expect(opt('claude:sonnet')!.textContent).toContain('Sonnet');
  /* two levels: the CLI dropdown first (Claude), then only Claude's models; no Cursor models listed */
  expect(cli().textContent).toContain('Claude');
  expect(cli().getAttribute('aria-haspopup')).toBe('menu');
  expect(qa('#pkMenu [data-option^="cursor:"]')).toHaveLength(0);
  expect(qa('#pkMenu [data-option]').map(e => e.getAttribute('data-option'))).toEqual(['claude:sonnet', 'claude:opus']);

  /* every item is reachable with the arrow keys and with Tab */
  await press('ArrowDown');
  expect(doc().activeElement).toBe(opt('claude:opus'));
  await press('End');
  expect(doc().activeElement?.id).toBe('pkNewPlan');
  await press('Tab');
  expect(doc().activeElement).toBe(cli());                            // the CLI dropdown is the first item
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

it('CLI dropdown: keyboard opens it, an unavailable CLI is listed but cannot be chosen, changing the CLI picks its first model', async () => {
  await click(btn());
  await click(cli());
  expect(q('#pkCliList')).toBeTruthy();
  expect(cli().getAttribute('aria-expanded')).toBe('true');
  expect(doc().activeElement).toBe(harness('claude'));                // focus on the shown CLI
  expect(harness('claude')!.getAttribute('aria-checked')).toBe('true');
  const cursor = harness('cursor')!;
  expect(cursor.getAttribute('aria-disabled')).toBe('true');
  expect(cursor.textContent).toContain('not available yet');
  await press('ArrowDown');
  expect(doc().activeElement).toBe(cursor);                           // listed and reachable, but ...
  await click(cursor);                                                // ... not selectable: nothing sent, list stays
  expect(sentOf('planner_choose')).toHaveLength(0);
  expect(q('#pkCliList')).toBeTruthy();
  expect(cli().textContent).toContain('Claude');
  /* Escape closes the CLI list first (focus back on the dropdown), then the menu */
  cursor.focus();
  await press('Escape');
  expect(q('#pkCliList')).toBeNull();
  expect(menu()).toBeTruthy();
  expect(doc().activeElement).toBe(cli());
  await press('ArrowRight');                                          // Right opens it too, Left closes it
  expect(q('#pkCliList')).toBeTruthy();
  await press('ArrowLeft');
  expect(q('#pkCliList')).toBeNull();
  await press('Escape');
  expect(menu()).toBeNull();
});

it('changing the CLI shows that CLI\'s models and picks the first one', async () => {
  /* a second CLI that is available (the server's table decides; nothing is hard-coded in the page) */
  const pc = getState().plannerChoice!;
  const alt = (m: string, ml: string) => ({ id: `alt:${m}`, harness: 'alt', harness_label: 'Alt', model: m, model_label: ml, label: `Alt · ${ml}`, available: true, note: null });
  await act(async () => { dispatch({ type: 'planner_choice', ...pc, options: [...pc.options, alt('fast', 'Fast'), alt('deep', 'Deep')] }); });
  const choose = vi.spyOn(actions, 'choosePlanner').mockImplementation(() => {});   // the demo back end does not know "alt"
  await click(btn());
  await click(cli());
  await click(harness('alt'));
  expect(choose).toHaveBeenLastCalledWith('alt:fast');
  expect(menu()).toBeTruthy();                                        // stays open on the new CLI's models
  expect(cli().textContent).toContain('Alt');
  expect(qa('#pkMenu [data-option]').map(e => e.getAttribute('data-option'))).toEqual(['alt:fast', 'alt:deep']);
  expect(doc().activeElement?.getAttribute('data-option')).toBe('alt:fast');
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

it('the auto-promote toggle and New plan have accessible names', async () => {
  await click(btn());
  expect(q('#pkAuto')!.getAttribute('aria-label')).toMatch(/^Auto-promote to Opus, (on|off)/);
  expect(q('#pkNewPlan')!.getAttribute('aria-label')).toBe('New plan');
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
