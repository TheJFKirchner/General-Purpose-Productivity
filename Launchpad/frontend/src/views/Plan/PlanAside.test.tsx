// @vitest-environment happy-dom
/* Plan tab + right-hand aside against the in-page demo: the controls send the same messages as the vanilla page. */
import { afterEach, expect, it, vi } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { UiMessage } from '../../contract';
import { dispatch, getState, useLaunchpad } from '../../store';
import { setTransport } from '../../store/core';
import { initialState } from '../../store/initial';
import { Demo } from '../../demo/Demo';
import { TipHost } from '../../components';
import Plan from './Plan';
import Aside from '../Aside/Aside';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

const buttons = (root: Element, text: string) => [...root.querySelectorAll('button')].filter(b => (b.textContent || '').trim() === text) as HTMLButtonElement[];
function setValue(el: HTMLInputElement | HTMLTextAreaElement, v: string) {
  const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')!;
  d.set!.call(el, v);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

it('plan chat, rounds, plan card, promotion, Incoming and the feed send the vanilla messages', async () => {
  vi.useFakeTimers();
  useLaunchpad.setState(initialState(), true);
  const demo = new Demo(dispatch, 1);
  const sent: UiMessage[] = [];
  setTransport(m => { sent.push(m); demo.receive(m); return true; });
  const errors: unknown[] = [];
  const onErr = vi.spyOn(console, 'error').mockImplementation((...a) => { errors.push(a); });

  const host = document.createElement('div'); document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<><main><Plan /><Aside /></main><TipHost /></>); });
  const step = async (ms: number) => { await act(async () => { vi.advanceTimersByTime(ms); }); };
  const click = async (b: Element | undefined) => { expect(b).toBeTruthy(); await act(async () => { (b as HTMLElement).click(); }); };
  const last = () => sent[sent.length - 1];

  await act(async () => { demo.start(); });
  await step(10_000);
  const plan = host.querySelector('#viewPlan')!;
  expect(plan.querySelector('h1')?.textContent).toBe('Q3 inpatient trend refresh');
  expect(plan.querySelector('#modeLine')?.textContent).toContain('Session C');
  /* the top of the Plan view has no New plan, model chip or promote button any more: the picker under the chat box */
  expect(plan.querySelector('.chat-head #newPlan, #pmModel, #pmPromote')).toBeNull();
  const pk = plan.querySelector('#pkBtn') as HTMLButtonElement;
  expect(pk.textContent).toContain('Claude · Sonnet');

  /* promotion by hand: pick the top model on the running session */
  await click(pk);
  const opus = plan.querySelector('#pkMenu [data-option="claude:opus"]') as HTMLButtonElement;
  expect(opus.textContent).toContain('promote this plan');
  await click(opus);
  expect(last()).toEqual({ type: 'planner_choose', option_id: 'claude:opus', session_id: 'S-C' });
  await step(1_000);
  expect(pk.textContent).toContain('Claude · Opus');
  expect(pk.textContent).toContain('promoted');
  expect(plan.querySelector('.sys.promo')).toBeTruthy();

  /* question round 1: an option per question; the round_answer goes once every question has an answer */
  const round = plan.querySelector('#round-r1')!;
  expect(round.querySelectorAll('.q')).toHaveLength(2);
  await click(buttons(round, 'Yes')[0]);
  expect(sent.some(m => m.type === 'round_answer')).toBe(false);
  await click(buttons(round, 'Change')[0]);
  const ta = round.querySelector('textarea') as HTMLTextAreaElement;
  await act(async () => { setValue(ta, 'Only the director group'); });
  await click(buttons(round, 'Save')[0]);
  expect(last()).toEqual({ type: 'round_answer', roundId: 'r1', answers: { a: { accepted: true }, b: { accepted: false, text: 'Only the director group' } } });
  expect(round.querySelector('.round-actions')).toBeNull();
  expect(round.querySelectorAll('.q.done')).toHaveLength(2);

  /* round 2: Accept all picks */
  await step(3_000);
  const r2 = plan.querySelector('#round-r2')!;
  expect(r2).toBeTruthy();
  await click(buttons(r2, 'Accept all picks')[0]);
  expect(last()).toMatchObject({ type: 'round_answer', roundId: 'r2' });

  /* the plan card arrives; Ask for changes sets the composer's placeholder; Approve sends plan_approve */
  await step(4_000);
  const card = plan.querySelector('.plancard')!;
  expect(card).toBeTruthy();
  expect(card.querySelector('h3')?.textContent).toBeTruthy();
  /* the agent per step when it is not the Builder (folder agents, purpose colours once the crew list is in) */
  await step(500);
  expect([...card.querySelectorAll('.steps .stepagent')].map(e => [e.textContent, e.getAttribute('data-purpose')])).toEqual([['Sql builder', 'building'], ['Sql reviewer', 'reviewing']]);
  /* the skills a step names (approved with the plan); one not found in the folders is greyed */
  expect([...card.querySelectorAll('.steps .chip.skill')].map(e => [e.textContent, e.classList.contains('gone')])).toEqual(
    [['claims-glossary', false], ['sql-style', false], ['readmission-rules', true]]);
  /* Send plan to CLI: chat_from_plan, then the card says it went (the draft stays approvable) */
  await click(buttons(card, 'Send plan to CLI')[0]);
  expect(last()).toEqual({ type: 'chat_from_plan', session_id: 'S-C' });
  expect(getState().ui.chatSide).toBe('code');
  await step(1_000);
  expect(card.querySelector('.pc-sent')?.textContent).toContain('Sent to the CLI');
  expect(buttons(card, 'Send to CLI again')).toHaveLength(1);
  const fromPlan = Object.values(getState().chats).find(c => c.mode === 'plan');
  expect(fromPlan).toBeTruthy();
  await click(buttons(card, 'Ask for changes')[0]);
  expect((plan.querySelector('#msgInput') as HTMLInputElement).placeholder).toBe('What should change in the plan?');
  await click(card.querySelector('.apsw')!);
  expect(card.querySelector('.apsw')?.textContent).toBe('Click again: approve everything');
  await click(buttons(card, 'Approve and launch')[0]);
  expect(last()).toEqual({ type: 'plan_approve', session_id: 'S-C' });
  await step(2_000);
  expect(card.classList.contains('approved')).toBe(true);
  expect(card.querySelector('.pc-status')?.textContent).toBe('Approved. Run C launched.');
  expect(card.querySelector('.pc-actions')).toBeNull();

  /* composer sends user_message and shows the bubble */
  const input = plan.querySelector('#msgInput') as HTMLInputElement;
  const lbl = plan.querySelector('label[for="msgInput"]') as HTMLLabelElement;
  expect(lbl?.textContent).toBe('Message the planner');
  expect(document.querySelectorAll('#msgInput')).toHaveLength(1);            // the label names exactly this input
  await act(async () => { setValue(input, 'hello there'); });
  await act(async () => { (plan.querySelector('#composer') as HTMLFormElement).requestSubmit(); });
  expect(last()).toEqual({ type: 'user_message', text: 'hello there' });
  expect([...plan.querySelectorAll('.bubble.me')].some(b => b.textContent === 'hello there')).toBe(true);
  expect(input.value).toBe('');

  /* "+ New plan": the session has a run now, so no confirm; with one folder it sends new_session at once */
  /* aside: orbit planets + run rows, Incoming cards, feed rows */
  const aside = host.querySelector('aside')!;
  expect(aside.querySelectorAll('#orbit .planet').length).toBeGreaterThanOrEqual(2);
  expect(aside.querySelectorAll('.runrow').length).toBeGreaterThanOrEqual(3);
  expect(aside.querySelectorAll('.feed-list .act').length).toBeGreaterThan(3);

  const q1 = aside.querySelector('#item-A-q1');
  if (q1 && !q1.classList.contains('settled')) {
    await click(buttons(q1, 'admit_dt')[0]);
    expect(last()).toEqual({ type: 'queue_response', id: 'A-q1', answer: 'admit_dt' });
    expect(q1.querySelector('.settle')?.textContent).toContain('Sent: “admit_dt”.');
  }
  const bq = aside.querySelector('#item-B-q2')!;
  expect(bq.classList.contains('blocking')).toBe(true);
  const other = bq.querySelector('form.other input') as HTMLInputElement;
  await act(async () => { setValue(other, 'Use both'); });
  await act(async () => { (bq.querySelector('form.other') as HTMLFormElement).requestSubmit(); });
  expect(last()).toEqual({ type: 'queue_response', id: 'B-q2', answer: 'Use both' });

  /* filters: Permissions hides questions */
  await click(buttons(aside, 'Permissions')[0]);
  expect((aside.querySelector('#item-B-q2') as HTMLElement | null)?.hidden ?? true).toBe(true);
  await click(buttons(aside, 'All')[0]);

  /* feed row click pins the agent */
  const row = aside.querySelector('.feed-list .act') as HTMLButtonElement;
  await click(row);
  expect(getState().ui.sel).toBe(row.dataset.hoverAgent);
  expect(row.classList.contains('pin')).toBe(true);

  /* run row opens Missions focused on that run */
  const runRow = [...aside.querySelectorAll('.runrow')].find(b => b.getAttribute('data-tip') === 'run:S-A') as HTMLElement;
  await click(runRow);
  expect(getState().ui.view).toBe('missions');
  expect(getState().ui.focus).toBe('S-A');

  await act(async () => { root.unmount(); });
  demo.stop();
  onErr.mockRestore();
  expect(errors, JSON.stringify(errors).slice(0, 600)).toHaveLength(0);
});
