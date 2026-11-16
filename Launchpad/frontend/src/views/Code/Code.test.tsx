// @vitest-environment happy-dom
/* The chat screen against the in-page demo: the Planner / CLI switch (both sides kept, drafts survive, what
   is waiting shows on the switch), every former Free Flight control on the CLI side sending the same
   messages, and the Visuals panel. */
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import ChatScreen from '../Chat/Chat';
import VisualsPanel from '../Visuals/Visuals';
import { actions, dispatch, getState, useLaunchpad } from '../../store';
import type { UiMessage } from '../../contract';
import { setTransport } from '../../store/core';
import { initialState } from '../../store/initial';
import { Demo } from '../../demo/Demo';
import { visLib } from '../Visuals/frames';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root, demo: Demo, sent: UiMessage[];
const step = async (ms: number) => { await act(async () => { vi.advanceTimersByTime(ms); }); };
const $ = <T extends Element = HTMLElement>(q: string) => host.querySelector<T>(q);
const btn = (text: string, scope: ParentNode = host) => [...scope.querySelectorAll('button')].find(b => b.textContent === text) as HTMLButtonElement;
const setValue = (el: HTMLInputElement | HTMLTextAreaElement, v: string) => {
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, v);
  el.dispatchEvent(new Event('input', { bubbles: true }));
};
const click = async (el: Element) => { await act(async () => { (el as HTMLElement).click(); }); };
const key = async (k: string, shift = false, target: EventTarget = document) => { await act(async () => { target.dispatchEvent(new KeyboardEvent('keydown', { key: k, shiftKey: shift, bubbles: true, cancelable: true })); }); };

beforeEach(async () => {
  /* no server here: the frames use the ECharts stand-in, loaded before any frame exists (quiet test output) */
  vi.stubGlobal('fetch', () => Promise.reject(new Error('no server in tests')));
  await visLib();
  vi.useFakeTimers();
  useLaunchpad.setState(initialState(), true);
  demo = new Demo(dispatch, 1);
  sent = [];
  setTransport(m => { sent.push(m); demo.receive(m); return true; });
  host = document.createElement('div'); document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(<><main><ChatScreen /></main><VisualsPanel /></>); });
});
afterEach(async () => {
  await act(async () => { root.unmount(); });
  host.remove(); demo.stop(); vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals();
});

it('the switch flips between two kept conversations; typed drafts survive; arrow keys move it', async () => {
  const planner = $('#chatsw-planner')!, code = $('#chatsw-code')!;
  expect(planner.getAttribute('role')).toBe('tab');
  expect(planner.getAttribute('aria-selected')).toBe('true');
  expect($('#chatpane-code')!.hidden).toBe(true);
  /* a half-typed planner message */
  await act(async () => { setValue($<HTMLInputElement>('#msgInput')!, 'half a thought'); });
  await click(code);
  expect(getState().ui.chatSide).toBe('code');
  expect($('#chatpane-planner')!.hidden).toBe(true);
  expect($('#chatpane-code')!.hidden).toBe(false);
  await act(async () => { setValue($<HTMLTextAreaElement>('#codeInput')!, 'draft for claude'); });
  await key('ArrowLeft', false, code);
  expect(getState().ui.chatSide).toBe('planner');
  expect($<HTMLInputElement>('#msgInput')!.value).toBe('half a thought');
  await key('End', false, planner);
  expect(getState().ui.chatSide).toBe('code');
  expect($<HTMLTextAreaElement>('#codeInput')!.value).toBe('draft for claude');
  expect(sent.filter(m => m.type === 'user_message' || m.type === 'chat_message')).toHaveLength(0);   // flipping sends nothing
});

it('CLI side: starts a chat on first send, streams, answers a permission card with a Deny note; the switch shows it waiting', async () => {
  await act(async () => { actions.setChatSide('code'); });
  expect($('#codeEmpty')!.hidden).toBe(false);
  expect($('#codeModel')!.textContent).toBe('no chat yet');

  const input = $<HTMLTextAreaElement>('#codeInput')!;
  await act(async () => { setValue(input, 'fix the loader'); });
  await act(async () => { $<HTMLFormElement>('#codeComposer')!.requestSubmit(); });
  expect(sent.at(-1)).toEqual({ type: 'chat_new' });
  expect(input.value).toBe('');
  await step(1000);
  expect($('#codeEmpty')!.hidden).toBe(true);
  expect($('#codeModel')!.textContent).toBe('Sonnet');
  expect(sent.some(m => m.type === 'chat_message' && m.text === 'fix the loader')).toBe(true);
  expect($('#codeStop')!.hidden).toBe(false);

  await step(8000);
  expect(host.querySelectorAll('.toolrow').length).toBeGreaterThanOrEqual(2);
  const card = $('.ccard.permission')!;
  expect(card).toBeTruthy();
  /* waiting on the user: a coral count on the CLI tab, seen from the Planner side */
  await act(async () => { actions.setChatSide('planner'); });
  expect($('#chatsw-code .sw-badge')!.textContent).toBe('1');
  expect($('#chatsw-code')!.getAttribute('aria-label')).toContain('1 waiting on you');
  await act(async () => { actions.setChatSide('code'); });
  expect(card.querySelector('pre.cmd')!.textContent).toContain('incurred_month');
  expect(btn('Yes, allow all edits during this session', card)).toBeTruthy();
  await act(async () => { setValue(card.querySelector('input')!, 'leave it'); });
  await click(btn('Deny', card));
  const resp = sent.find(m => m.type === 'queue_response') as Extract<UiMessage, { type: 'queue_response' }>;
  expect(resp).toMatchObject({ decision: 'deny', message: 'leave it' });
  expect($('.ccard.permission.settled .settle')!.textContent).toBe('Denied · “leave it”');
  expect($('#chatsw-code .sw-badge')).toBeNull();
  await step(5000);
  expect(host.querySelector('.bubble.bot.md')).toBeTruthy();
  expect($('#codeStop')!.hidden).toBe(true);
});

it('Shift+Tab cycles the three modes, Esc interrupts; both only while the CLI side shows', async () => {
  await act(async () => { actions.setChatSide('code'); });
  await act(async () => { actions.sendChat('hello'); });
  await step(1000);
  const cid = getState().currentChat!;
  expect($('#modePill')!.textContent).toBe('Ask before edits');
  await key('Tab', true);
  expect(sent.at(-1)).toEqual({ type: 'chat_set_mode', chat_id: cid, mode: 'accept_edits' });
  expect($('#modePill')!.textContent).toBe('Auto-accept edits');
  await key('Tab', true);
  expect($('#modePill')!.textContent).toBe('Plan');
  expect($<HTMLTextAreaElement>('#codeInput')!.placeholder).toContain('nothing will be changed');
  await click($('#modePill')!);
  expect(getState().chats[cid].mode).toBe('default');

  /* on the Planner side neither key touches the chat */
  await act(async () => { actions.sendChat('another one'); actions.setChatSide('planner'); });
  const before = sent.length;
  await key('Tab', true); await key('Escape');
  expect(sent.length).toBe(before);
  await act(async () => { actions.setChatSide('code'); });
  expect(getState().chats[cid].busy).toBe(true);
  await key('Escape');
  expect(sent.at(-1)).toEqual({ type: 'chat_stop', chat_id: cid });
  await step(1000);
  expect(host.textContent).toContain('Interrupted.');
});

it('New chat sends chat_new and shows the CLI side', async () => {
  await act(async () => { dispatch({ type: 'settings', directories: [{ dir_id: 'd1', path: 'C:/p', name: 'p', exists: true, is_default: true, busy: false }], values: {}, can_pick_directory: false }); });
  await act(async () => { actions.setChatSide('code'); });
  await click($('#newChat')!);
  expect(sent.at(-1)).toEqual({ type: 'chat_new', dir_id: 'd1' });
  expect($('#newChat')!.textContent).toBe('Starting…');
  await step(600);
  expect(getState().currentChat).toBeTruthy();
  expect(getState().ui.chatSide).toBe('code');
});

it('visuals panel: cards, sandboxed frames, pick, tweak, retry', async () => {
  await act(async () => {
    dispatch({ type: 'session_started', session_id: 'S1' } as never);
    dispatch({ type: 'visual_set', session_id: 'S1', set_id: 'vs', brief: 'Pick a chart', picked_id: null, options: [
      { id: 'a', label: 'Bar', status: 'ready', html: '<p>bar</p>' },
      { id: 'b', label: 'Line', status: 'failed', error: 'boom' },
      { id: 'c', label: 'Tile', status: 'rendering' }] });
  });
  expect($('#visPanel')!.hidden).toBe(false);
  /* the panel belongs to the Planner side */
  await act(async () => { actions.setChatSide('code'); });
  expect($('#visPanel')!.hidden).toBe(true);
  await act(async () => { actions.setChatSide('planner'); });
  expect($('#visPanel')!.hidden).toBe(false);
  expect($('#visBrief')!.textContent).toBe('Pick a chart');
  const frame = $<HTMLIFrameElement>('.vopt[data-oid="a"] iframe')!;
  expect(frame.getAttribute('sandbox')).toBe('allow-scripts');
  expect($('.vopt[data-oid="b"] .vo-ph.failed')!.textContent).toContain('boom');
  expect($('.vopt[data-oid="c"] .vo-ph')!.textContent).toContain('drawing');

  await click($('.vopt[data-oid="a"] .vo-pick')!);
  expect(sent.at(-1)).toEqual({ type: 'visual_pick', session_id: 'S1', set_id: 'vs', option_id: 'a' });
  expect($('.vopt[data-oid="a"]')!.className).toContain('picked');

  await click($('.vopt[data-oid="b"] .vo-retry')!);
  expect(sent.at(-1)).toEqual({ type: 'visual_retry', session_id: 'S1', set_id: 'vs', option_id: 'b' });

  const tw = $<HTMLInputElement>('.vopt[data-oid="a"] .vo-tweak input')!;
  await act(async () => { setValue(tw, 'horizontal'); });
  await act(async () => { tw.closest('form')!.requestSubmit(); });
  expect(sent.at(-1)).toEqual({ type: 'visual_tweak', session_id: 'S1', set_id: 'vs', option_id: 'a', text: 'horizontal' });

  await click($('#visClose')!);
  expect($('#visPanel')!.hidden).toBe(true);
});
