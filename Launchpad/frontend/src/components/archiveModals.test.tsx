// @vitest-environment happy-dom
/* The read-only planning chat archive (openArchive) against the in-page demo. */
import { it, expect } from 'vitest';
import { act } from 'react';
import { dispatch } from '../store';
import { closeModal, openArchive } from '.';
import { useDemoApp, q } from '../test/demoApp';

useDemoApp();

it('Planning chat archive: the full plan section and the Autopilot tag, no buttons', async () => {
  await act(async () => {
    dispatch({ type: 'session_started', session_id: 'S-Z' } as never);
    dispatch({ type: 'plan_draft', session_id: 'S-Z', path: 'plan.md', markdown: '# Zed plan\n\nBody text here', steps: [{ n: 1, title: 'One' }], revision: 1, previous_runs: 0 } as never);
    dispatch({ type: 'run_started', session_id: 'S-Z', name: 'Zed plan', steps: [{ n: 1, title: 'One', status: 'todo' }], run: 1, revision: 1, autopilot: true } as never);
    openArchive('S-Z');
  });
  const box = q('.msgs.archived')!;
  expect(box).toBeTruthy();
  expect(box.querySelector('.plancard details.full summary')?.textContent).toBe('Read the full plan');
  expect(box.querySelector('.plancard .mdbox')?.textContent).toContain('Body text here');
  expect(box.querySelector('.plancard .aptag')?.textContent).toBe('Autopilot on for this run');
  await act(async () => { closeModal(); });                     // close it while the app is mounted (Radix focus scope)
});
