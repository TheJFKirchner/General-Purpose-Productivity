// @vitest-environment happy-dom
/* The Auto answers switch in the planner's control row (separate from Autopilot) and the compact auto-answered line in
   the planner chat, against the in-page demo. */
import { expect, it } from 'vitest';
import { act } from 'react';
import { dispatch, getState } from '../../store';
import { click, q, qa, sentOf, step, useDemoApp } from '../../test/demoApp';

useDemoApp();

const sw = () => q<HTMLButtonElement>('#autoAnswers')!;

it('has an accessible name and a tooltip, is off by default, sits in the control row and is not the Autopilot switch', () => {
  expect(sw()).toBeTruthy();
  expect(sw().getAttribute('role')).toBe('switch');
  expect(sw().getAttribute('aria-checked')).toBe('false');
  expect(sw().getAttribute('aria-label')).toBe('Auto answers');
  expect(sw().title).toMatch(/recommended answer/);
  expect(sw().title).toMatch(/Permission requests are not affected/);
  expect(sw().closest('#plannerControls')).toBeTruthy();
  expect(sw().textContent).toBe('Auto answers off');
});

it('turning it on sends set_auto_answers for the current plan and follows the server, off again the same way', async () => {
  const sid = getState().current!;
  await click(sw());
  expect(sentOf('set_auto_answers').at(-1)).toEqual({ type: 'set_auto_answers', session_id: sid, on: true });
  await step(500);
  expect(sw().getAttribute('aria-checked')).toBe('true');
  expect(sw().textContent).toBe('Auto answers ON');
  expect(getState().sessions[sid].autoAnswers).toBe(true);
  expect(sentOf('set_autopilot')).toHaveLength(0);                          // Autopilot is a different switch
  await click(sw());
  expect(sentOf('set_auto_answers').at(-1)).toMatchObject({ on: false });
  await step(500);
  expect(sw().getAttribute('aria-checked')).toBe('false');
});

it('an auto-answered question is a compact line in the chat, marked automatic; a waiting round card is closed', async () => {
  const sid = getState().current!;
  await act(async () => {
    dispatch({ type: 'question_round', session_id: sid, id: 'rz', round: 9, questions: [
      { id: 'a', title: 'Which audience?', body: 'why', rec: 'Managers', options: [] }, { id: 'b', title: 'Which library?', body: 'why', rec: 'ECharts', options: [] }] } as never);
  });
  expect(q('#round-rz .round-actions')).toBeTruthy();
  await act(async () => {
    dispatch({ type: 'auto_answer', session_id: sid, id: 'a', agent: 'Planner', step: null, title: 'Which audience?', answer: 'Managers', round_id: 'rz' } as never);
    dispatch({ type: 'auto_answer', session_id: sid, id: 'b', agent: 'Planner', step: null, title: 'Which library?', answer: 'ECharts', round_id: 'rz' } as never);
  });
  const lines = qa('.autoline');
  expect(lines).toHaveLength(2);
  expect(lines[0].querySelector('.autotag')?.textContent).toBe('Auto');
  expect(lines[0].textContent).toContain('Which audience?');
  expect(lines[0].textContent).toContain('Managers');
  expect(lines[0].textContent).toContain('Answered automatically');
  expect(q('#round-rz .round-actions')).toBeNull();                         // the card no longer asks
  expect(getState().rounds.rz.sent).toBe(true);
});

it('a builder question answered automatically shows its step in the line', async () => {
  const sid = getState().current!;
  await act(async () => {
    dispatch({ type: 'auto_answer', session_id: sid, id: 'q7', agent: 'Builder', step: 2, title: 'Colour?', answer: 'Blue', round_id: null } as never);
  });
  const line = qa('.autoline').at(-1)!;
  expect(line.textContent).toContain('Builder, step 2 asked');
  expect(line.textContent).toContain('Blue');
});

it('the CLI chat card in Crew shows the CLI and model actually chosen', async () => {
  await act(async () => {
    dispatch({ type: 'cli_choice', options: [], choice: { option_id: 'claude:opus', harness: 'claude', model: 'opus', label: 'Claude · Opus' }, overridden: [] } as never);
  });
  const { sel } = await import('../../store');
  const pilot = { name: 'launchpad-pilot', role: 'pilot', model: 'sonnet', builtin: true };
  expect(sel.crewModel(getState(), pilot as never)).toBe('New chats: Claude · Opus');       // saved choice, labelled as such
  await act(async () => {
    dispatch({ type: 'chat_started', chat_id: 'cx', mode: 'default', model: 'sonnet', harness: 'claude', label: 'Claude · Sonnet', option_id: 'claude:sonnet', started: true, cwd: 'C:/p', dir_id: 'd1' } as never);
  });
  expect(sel.crewModel(getState(), pilot as never)).toBe('This chat: Claude · Sonnet');   // a running chat's own choice
  expect(sel.crewModel(getState(), { name: 'launchpad-builder', role: 'builder', model: 'sonnet' } as never)).toBe('Sonnet');
});
