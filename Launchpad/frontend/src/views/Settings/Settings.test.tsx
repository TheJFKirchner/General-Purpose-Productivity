// @vitest-environment happy-dom
/* Settings against the in-page demo: folders, add, two-click remove, settings sent on change. */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, getState } from '../../store';
import { useDemoApp, step, q, qa, click, byText, sentOf, typeInto } from '../../test/demoApp';

useDemoApp();

it('Settings: folders, add, two-click remove, a setting sent on change', async () => {
  await act(async () => { actions.openSettings(); });
  await step(400);
  expect(qa('.dirrow').length).toBe(2);
  expect(qa('.dirrow button').filter(b => b.textContent === 'Remove').every(b => (b as HTMLButtonElement).disabled)).toBe(true);   // both busy
  await typeInto(q<HTMLInputElement>('#setAddPath')!, 'C:/work/extra');
  await act(async () => { q<HTMLFormElement>('#setAdd')!.requestSubmit(); });
  await step(400);
  expect(sentOf('add_directory')).toHaveLength(1);
  expect(qa('.dirrow').length).toBe(3);
  expect(q<HTMLInputElement>('#setAddPath')!.value).toBe('');
  const rm = qa<HTMLButtonElement>('.dirrow button').filter(b => b.textContent === 'Remove' && !b.disabled);
  expect(rm).toHaveLength(1);
  await click(rm[0]);
  expect(sentOf('remove_directory')).toHaveLength(0);
  await click(byText('.dirrow button', 'Confirm remove'));
  expect(sentOf('remove_directory')).toHaveLength(1);
  await step(400);
  expect(qa('.dirrow').length).toBe(2);

  const num = q<HTMLInputElement>('#set-question_timeout_s')!;
  await act(async () => { num.value = '240'; num.dispatchEvent(new Event('change', { bubbles: true })); });
  expect(sentOf('set_settings').at(-1)).toEqual({ type: 'set_settings', patch: { question_timeout_s: 240 } });
  expect(q<HTMLInputElement>('#set-pilot_model')!.disabled).toBe(true);      // set by a launch option
  expect(getState().ui.view).toBe('settings');
  expect(q('#viewSettings')).toBeTruthy();                                     // a view now, not a dialog
  expect(q('[role=dialog]')).toBeNull();
});

it('Settings: the primary folder is marked; another folder can be ticked as additional', async () => {
  await act(async () => { actions.openSettings(); });
  await step(400);
  const rows = qa('.dirrow');
  expect(rows[0].querySelector('.chip.ok')?.textContent).toBe('Primary');
  expect(rows[0].querySelector('.dr-add')).toBeNull();                          // the primary has no tick box
  const tick = rows[1].querySelector<HTMLInputElement>('.dr-add input')!;
  expect(tick.checked).toBe(false);
  await click(tick);
  expect(sentOf('set_settings').at(-1)).toEqual({ type: 'set_settings', patch: { additional_dir_ids: ['d2'] } });
  await step(400);
  expect(qa('.dirrow')[1].querySelector<HTMLInputElement>('.dr-add input')!.checked).toBe(true);
  expect(getState().settings!.directories.find(d => d.dir_id === 'd2')!.is_additional).toBe(true);
});
