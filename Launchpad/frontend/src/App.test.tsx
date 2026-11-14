// @vitest-environment happy-dom
/* Render smoke test (DOM, no browser): the shell, every view, the overlays and every tooltip key render against
   demo-driven state without errors. */
import { afterEach, expect, it, vi } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { renderToString } from 'react-dom/server';
import App from './App';
import { actions, dispatch, getState, useLaunchpad, type View } from './store';
import { setTransport } from './store/core';
import { initialState } from './store/initial';
import { tipContent } from './components/Tooltip';
import { Demo } from './demo/Demo';
import { visLib } from './views/Visuals/frames';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('renders the shell, each view and each tooltip with live demo state', async () => {
  /* no server here: the visual frames use the ECharts stand-in, loaded before any frame exists (quiet output) */
  vi.stubGlobal('fetch', () => Promise.reject(new Error('no server in tests')));
  await visLib();
  vi.useFakeTimers();
  useLaunchpad.setState(initialState(), true);
  const demo = new Demo(dispatch, 1);
  setTransport(m => { demo.receive(m); return true; });
  const errors: unknown[] = [];
  const onErr = vi.spyOn(console, 'error').mockImplementation((...a) => { errors.push(a); });

  const host = document.createElement('div'); document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<App />); });
  const step = async (ms: number) => { await act(async () => { vi.advanceTimersByTime(ms); }); };

  await act(async () => { demo.start(); });
  await step(10_000);
  expect(host.querySelector('#viewPlan h1')?.textContent).toBe('Q3 inpatient trend refresh');
  expect(host.querySelectorAll('aside .queue .item').length).toBeGreaterThanOrEqual(4);

  await act(async () => { actions.acceptAllPicks('r1'); });
  await step(6_000);
  expect(host.querySelector('.vis-panel')).toBeTruthy();         // visuals slot opens after round 1
  expect(document.body.classList.contains('vis-open')).toBe(true);

  await act(async () => { actions.sendChat('fix the loader'); });
  await step(6_000);
  await act(async () => { actions.openSettings(); actions.openEditor('d1', 'README.md'); });
  await step(1_000);
  expect(host.parentElement!.querySelector('#edScrim.open textarea')).toBeTruthy();
  expect((host.parentElement!.querySelector('#edScrim textarea') as HTMLTextAreaElement).value).toContain('# Claims project');

  for (const v of ['plan', 'missions', 'crew', 'files'] as View[]) {
    await act(async () => { actions.setView(v); });
    await step(500);
    const visible = [...host.querySelectorAll('.view-slot')].filter(el => !(el as HTMLElement).hidden);
    expect(visible).toHaveLength(1);
    expect(document.body.classList.contains('v-missions')).toBe(v === 'missions');
  }
  await act(async () => { actions.setChatSide('code'); });
  expect(host.querySelector('#codeName')?.textContent).toBe('Claude Code');
  expect(host.querySelector('#tab-flight')).toBeNull();                 // the Free Flight tab is gone
  expect(host.querySelector('#chatsw-planner')?.textContent).toMatch(/^Planner/);

  const st = getState();
  const keys = ['planner', 'cursession', 'allagents', 'chat', 'run:S-A', 'run:S-B', 'step:2:S-A', ...Object.keys(st.agents).map(id => 'agent:' + id)];
  for (const k of keys) expect(() => renderToString(<div>{tipContent(st, k)}</div>), k).not.toThrow();
  expect(renderToString(<div>{tipContent(st, 'run:S-A')}</div>)).toContain('Claims loader rebuild');

  await act(async () => { root.unmount(); });
  demo.stop();
  onErr.mockRestore();
  expect(errors, JSON.stringify(errors).slice(0, 600)).toHaveLength(0);
});
