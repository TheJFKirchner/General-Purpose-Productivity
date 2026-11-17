// @vitest-environment happy-dom
/* The CLI chat's picker under its box, against the in-page demo: the same two-level menu as the planner's (a CLI
   dropdown, then that CLI's models) without auto-promote and New plan; before the first message a choice applies to
   the chat at once, after it the choice is for the next new chat and the row says so. */
import { expect, it } from 'vitest';
import { act } from 'react';
import { actions, getState } from '../../store';
import { click, doc, q, qa, sentOf, step, typeInto, useDemoApp } from '../../test/demoApp';

useDemoApp();

const btn = () => q<HTMLButtonElement>('#cpkBtn')!;
const menu = () => q('#cpkMenu');
const opt = (id: string) => q<HTMLButtonElement>(`#cpkMenu [data-option="${id}"]`);
const press = async (k: string) => {
  await act(async () => { (doc().activeElement as HTMLElement).dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true })); });
};
const sendCode = async (text: string) => {
  await typeInto(q<HTMLTextAreaElement>('#codeInput')!, text);
  await act(async () => { q<HTMLFormElement>('#codeComposer')!.requestSubmit(); });
};

it('sits under the CLI chat box with the CLI dropdown and models, but no auto-promote, Rules or New plan; no model chip', async () => {
  await act(async () => { actions.setChatSide('code'); });
  expect(q('#codeModel')).toBeNull();
  const row = q('#cliControls')!;
  expect(q('#codeComposer')!.nextElementSibling).toBe(row);          // right under the input box
  expect(btn().textContent).toContain('Claude · Sonnet');           // no chat yet: what the next chat starts on
  await click(btn());
  expect(menu()).toBeTruthy();
  expect(doc().activeElement).toBe(opt('claude:sonnet'));
  expect(q('#cpkCli')!.textContent).toContain('Claude');
  expect(qa('#cpkMenu [data-option]').map(e => e.getAttribute('data-option'))).toEqual(['claude:sonnet', 'claude:opus']);
  expect(q('#cpkMenu [role="menuitemcheckbox"]')).toBeNull();
  expect(menu()!.textContent).not.toContain('Auto-promote');
  expect(menu()!.textContent).not.toContain('New plan');
  expect(menu()!.textContent).not.toContain('Rules');
  /* the unavailable CLI is listed in the dropdown but cannot be chosen */
  await click(q('#cpkCli'));
  const cursor = q<HTMLButtonElement>('#cpkCliList [data-harness="cursor"]')!;
  expect(cursor.getAttribute('aria-disabled')).toBe('true');
  expect(cursor.textContent).toContain('not available yet');
  await click(cursor);
  expect(sentOf('cli_choose')).toHaveLength(0);
  await press('Escape');                                             // closes the CLI list
  await press('Escape');                                             // closes the menu
  expect(menu()).toBeNull();
  expect(doc().activeElement).toBe(btn());
  /* the planner's picker is a separate one */
  expect(q('#pkBtn')).toBeTruthy();
  expect(q('#pkBtn')).not.toBe(btn());
});

it('a chat nobody has written to takes a choice at once; after the first message it applies to the next new chat', async () => {
  await act(async () => { actions.setChatSide('code'); });
  await click(q('#newChat'));
  const dm = q('.dirmenu');
  if (dm && !dm.hidden) await click(qa('.dirmenu button[role="menuitem"]')[0]);
  await step(1_000);
  const cid = getState().currentChat!;
  expect(cid).toBeTruthy();
  expect(btn().textContent).toContain('Claude · Sonnet');

  /* before the first message: the open chat moves to Opus at once, no note */
  await click(btn());
  expect(opt('claude:opus')!.textContent).not.toContain('next new chat');
  await click(opt('claude:opus'));
  expect(sentOf('cli_choose').at(-1)).toEqual({ type: 'cli_choose', option_id: 'claude:opus' });
  await step(1_000);
  expect(btn().textContent).toContain('Claude · Opus');
  expect(getState().chats[cid].optionId).toBe('claude:opus');
  expect(q('#cpkNote')).toBeNull();
  expect(sentOf('planner_choose')).toHaveLength(0);                   // independent of the planner
  expect(q('#pkBtn')!.textContent).toContain('Claude · Sonnet');

  /* the first message fixes it; a later choice is for the next new chat, and the row says so */
  await sendCode('hello there');
  await step(500);
  await click(btn());
  expect(opt('claude:sonnet')!.textContent).toContain('from your next new chat');
  await click(opt('claude:sonnet'));
  await step(1_000);
  expect(btn().textContent).toContain('Claude · Opus');              // this chat keeps Opus
  expect(q('#cpkNote')?.textContent).toContain('Claude · Sonnet applies to your next new chat; this chat keeps Claude · Opus.');
  await click(btn());
  expect(opt('claude:sonnet')!.textContent).toContain('next chat');
  await click(btn());

  /* a new chat starts on the remembered choice */
  await click(q('#newChat'));
  const dm2 = q('.dirmenu');
  if (dm2 && !dm2.hidden) await click(qa('.dirmenu button[role="menuitem"]')[0]);
  await step(1_000);
  expect(getState().currentChat).not.toBe(cid);
  expect(btn().textContent).toContain('Claude · Sonnet');
  expect(q('#cpkNote')).toBeNull();
});
