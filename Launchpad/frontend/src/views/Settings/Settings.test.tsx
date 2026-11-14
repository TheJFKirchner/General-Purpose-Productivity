// @vitest-environment happy-dom
/* Settings against the in-page demo: folders, add, two-click remove, settings sent on change. */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, getState } from '../../store';
import { useDemoApp, step, q, qa, click, byText, sentOf, typeInto, key } from '../../test/demoApp';

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
  await key('Escape');
  expect(getState().ui.settingsOpen).toBe(false);
});
