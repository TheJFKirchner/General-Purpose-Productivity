// @vitest-environment happy-dom
/* The Auto answers switch (builders only) beside the Autopilot switch in the three places Autopilot appears, never under the
   planner's chat box; a builder's question decided under it is a compact marked line in Incoming; every cost shown is the
   server's total. Against the in-page demo. */
import { expect, it } from 'vitest';
import { act } from 'react';
import { actions, dispatch, getState, sel } from '../../store';
import { click, q, qa, sentOf, step, useDemoApp } from '../../test/demoApp';

useDemoApp();

const runRow = (sid: string) => qa<HTMLElement>('#runList li').find(li => li.querySelector('[data-tip="run:' + sid + '"]'))!;
const sw = (sid: string) => runRow(sid).querySelector<HTMLButtonElement>('.aasw')!;

it('is not under the planner chat box; it sits beside Autopilot on the run row, with a name, an icon and a tooltip', () => {
  expect(q('#plannerControls')).toBeTruthy();
  expect(q('#plannerControls .aasw')).toBeNull();                                    // the old place is empty
  for (const sid of ['S-A', 'S-B']) {
    const row = runRow(sid);
    expect(row.querySelector('.apline .apsw:not(.aasw)')).toBeTruthy();              // Autopilot
    expect(row.querySelector('.apline .aasw')).toBeTruthy();                         // right beside it
  }
  const s = sw('S-A');
  expect(s.getAttribute('role')).toBe('switch');
  expect(s.getAttribute('aria-checked')).toBe('false');                              // off by default
  expect(s.getAttribute('aria-label')).toContain('Auto answers');
  expect(s.getAttribute('aria-label')).toContain('builders');
  expect(s.textContent).toBe('Auto answers off');
  expect(s.querySelector('svg')).toBeTruthy();                                       // its own icon
  expect(s.title).toMatch(/builder's own recommendation/);
  expect(s.title).toMatch(/Autopilot is the switch for those/);
  expect(s.title).toMatch(/Permission requests are not affected/);
});

it('sits beside Autopilot on the plan card before launch', async () => {
  await act(async () => {
    dispatch({ type: 'plan_draft', session_id: 'S-C', path: 'plan.md', markdown: '# Trend tabs\n', steps: [{ n: 1, title: 'Pull the extract' }], revision: 1 } as never);
  });
  const pair = q('.plancard .pc-ap .swpair')!;
  expect(pair.querySelector('.apsw:not(.aasw)')).toBeTruthy();
  expect(pair.querySelector('.aasw')).toBeTruthy();
});

it('sits beside Autopilot on each running Missions system', async () => {
  await act(async () => { actions.setView('missions'); });
  const cells = qa('.sys-cell.run, .sys-cell').filter(c => c.querySelector('.apsw:not(.aasw)'));
  expect(cells.length).toBeGreaterThanOrEqual(2);
  for (const c of cells) expect(c.querySelector('.aasw')).toBeTruthy();
});

it('the toast says what the switch does now: builders only, own recommendation, planner and CLI still wait', async () => {
  await click(sw('S-B'));
  const text = JSON.stringify(getState().ui.toasts);
  expect(text).toContain("builders' questions are answered with the builder's own recommendation");
  expect(text).toContain('planner and CLI questions still wait');
  expect(text).not.toContain('with a recommended answer');
  await click(sw('S-B'));
});

it('turning it on sends set_auto_answers for that run, follows the server, and is not Autopilot', async () => {
  await click(sw('S-A'));
  expect(sentOf('set_auto_answers').at(-1)).toEqual({ type: 'set_auto_answers', session_id: 'S-A', on: true });
  await step(500);
  expect(sw('S-A').getAttribute('aria-checked')).toBe('true');
  expect(sw('S-A').textContent).toBe('Auto answers ON');
  expect(getState().sessions['S-A'].autoAnswers).toBe(true);
  expect(getState().sessions['S-B'].autoAnswers).toBe(false);                        // per session
  expect(sentOf('set_autopilot')).toHaveLength(0);
  await click(sw('S-A'));
  expect(sentOf('set_auto_answers').at(-1)).toMatchObject({ on: false });
  await step(500);
  expect(sw('S-A').getAttribute('aria-checked')).toBe('false');
});

it('turning it on settles the waiting builder question as a marked line; the orchestrator-run blocking card is untouched', async () => {
  const card = () => q('#item-A-q1')!;
  expect(card().classList.contains('settled')).toBe(false);                          // a builder's question, waiting
  await click(sw('S-A'));
  await step(500);
  expect(card().classList.contains('settled')).toBe(true);
  const line = card().querySelector('.settle.decided')!;
  expect(line.querySelector('.aatag')?.textContent).toBe('Auto');
  expect(line.textContent).toContain('Decided by the');
  expect(line.textContent).toContain('(Auto answers on)');
  expect(line.textContent).toContain('service_from_dt');
  expect(q('#item-B-q2')!.classList.contains('settled')).toBe(false);               // S-B's switch is off
});

it('a builder question decided under Auto answers shows in Incoming, never as a line in the planner chat', async () => {
  await act(async () => {
    dispatch({ type: 'auto_answer', session_id: 'S-B', id: 'q77', agent: 'Builder', step: 2, title: 'Colour?', answer: 'Blue' } as never);
  });
  const item = q('#item-q77')!;
  expect(item.classList.contains('settled')).toBe(true);
  expect(item.textContent).toContain('Colour?');
  expect(item.textContent).toContain('Decided by the Builder (Auto answers on): “Blue”');
  expect(qa('.autoline')).toHaveLength(0);
  expect(getState().sessions['S-B'].log.some(e => (e as { kind: string }).kind === 'auto')).toBe(false);
});

it('cost figures are the server\'s totals: session, planner share, whole app, chat; per-agent figures are not added up', async () => {
  await act(async () => {
    dispatch({ type: 'usage', scope: 'session', session_id: 'S-A', cost: 7.89, planner_cost: 1.25, agents: 3,
      input_tokens: 10, output_tokens: 20, cache_read_tokens: 30, cache_write_tokens: 40, steps: { '2': { cost: 2.5, tool_calls: 4, agents: 1, input_tokens: 1, output_tokens: 2 } } } as never);
    dispatch({ type: 'usage', scope: 'app', tokens: 1000, cost: 12.34, input_tokens: 100, output_tokens: 200, cache_read_tokens: 300, cache_write_tokens: 400, by_role: { builder: 9, planner: 3.34 } } as never);
  });
  expect(sel.sessionTotal(getState(), 'S-A')).toBe(7.89);
  expect(sel.plannerCostOf(getState(), 'S-A')).toBe(1.25);
  expect(sel.crewCountOf(getState(), 'S-A')).toBe(3);
  expect(sel.stepTotalsOf(getState(), 'S-A', 2)?.cost).toBe(2.5);
  expect(q('.usage .u-txt')!.textContent).toContain('~$12.34');                       // header: the server's app total
  await act(async () => { actions.setView('missions'); });
  const cell = qa('.sys-cell').find(c => c.querySelector('[data-sys="S-A"]'))!;
  expect(cell.querySelector('.m-cost b')?.textContent).toBe('$7.89');
  /* a per-agent figure changes: no total moves until the server sends one */
  await act(async () => {
    dispatch({ type: 'agent_usage', session_id: 'S-A', chat_id: null, agent_id: 'A-b2', role: 'builder', name: 'x', step: 2, status: 'working',
      input_tokens: 1, output_tokens: 1, cache_read_tokens: 1, cache_write_tokens: 1, cost_usd: 99, tool_calls: 1 } as never);
  });
  expect(sel.sessionTotal(getState(), 'S-A')).toBe(7.89);
  expect(qa('.sys-cell').find(c => c.querySelector('[data-sys="S-A"]'))!.querySelector('.m-cost b')?.textContent).toBe('$7.89');
  /* a CLI chat's totals */
  await act(async () => {
    dispatch({ type: 'chat_started', chat_id: 'cx', mode: 'default', model: 'sonnet', cwd: 'C:/p', dir_id: 'd1' } as never);
    dispatch({ type: 'usage', scope: 'chat', chat_id: 'cx', cost: 0.42, tokens: 10, tool_calls: 2, agents: 1, input_tokens: 1, output_tokens: 2, cache_read_tokens: 3, cache_write_tokens: 4 } as never);
  });
  expect(getState().chatTotals.cx).toMatchObject({ cost: 0.42, tools: 2, n: 1 });
});

it('the CLI chat card in Crew shows the CLI and model actually chosen', async () => {
  await act(async () => {
    dispatch({ type: 'cli_choice', options: [], choice: { option_id: 'claude:opus', harness: 'claude', model: 'opus', label: 'Claude · Opus' }, overridden: [] } as never);
  });
  const pilot = { name: 'launchpad-pilot', role: 'pilot', model: 'sonnet', builtin: true };
  expect(sel.crewModel(getState(), pilot as never)).toBe('New chats: Claude · Opus');       // saved choice, labelled as such
  await act(async () => {
    dispatch({ type: 'chat_started', chat_id: 'cy', mode: 'default', model: 'sonnet', harness: 'claude', label: 'Claude · Sonnet', option_id: 'claude:sonnet', started: true, cwd: 'C:/p', dir_id: 'd1' } as never);
  });
  expect(sel.crewModel(getState(), pilot as never)).toBe('This chat: Claude · Sonnet');   // a running chat's own choice
  expect(sel.crewModel(getState(), { name: 'launchpad-builder', role: 'builder', model: 'sonnet' } as never)).toBe('Sonnet');
});
