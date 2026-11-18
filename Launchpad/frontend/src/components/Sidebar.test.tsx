// @vitest-environment happy-dom
/* Sidebar: every view reachable, active marked, Settings apart at the bottom, collapse persists, keys move between views. */
import { afterEach, expect, it, vi } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Sidebar } from './Sidebar';
import { getState, useLaunchpad } from '../store';
import { initialState } from '../store/initial';
import { LS_SIDEBAR } from '../lib/storage';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); });

async function mount(wide = true) {
  /* happy-dom's window is narrow; say whether the 1240 px query matches */
  vi.stubGlobal('matchMedia', () => ({ matches: !wide, addEventListener() {}, removeEventListener() {} }));
  useLaunchpad.setState(initialState(), true);
  const host = document.createElement('div'); document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<Sidebar />); });
  return { host, root };
}

it('lists the views in order with Settings apart, marks the active one and switches on click and keys', async () => {
  const { host, root } = await mount();
  const tabs = [...host.querySelectorAll('[role=tab]')].map(t => t.id);
  expect(tabs).toEqual(['tab-plan', 'tab-missions', 'tab-crew', 'tab-files', 'tab-workflows', 'tab-settings']);
  expect(host.querySelector('.side-bottom #tab-settings')).toBeTruthy();
  expect(host.querySelector('#tab-plan')!.getAttribute('aria-selected')).toBe('true');
  await act(async () => { (host.querySelector('#tab-crew') as HTMLElement).click(); });
  expect(getState().ui.view).toBe('crew');
  expect(host.querySelector('#tab-crew')!.getAttribute('aria-selected')).toBe('true');
  expect(host.querySelector('#tab-plan')!.getAttribute('aria-selected')).toBe('false');
  await act(async () => { host.querySelector('nav')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true })); });
  expect(getState().ui.view).toBe('settings');
  await act(async () => { root.unmount(); });
});

it('collapses to icons only, keeps every name, and remembers the choice', async () => {
  const a = await mount();
  expect(a.host.querySelector('.sidebar')!.classList.contains('collapsed')).toBe(false);
  await act(async () => { (a.host.querySelector('.side-toggle') as HTMLElement).click(); });
  expect(a.host.querySelector('.sidebar')!.classList.contains('collapsed')).toBe(true);
  expect(a.host.querySelector('#tab-files')!.textContent).toContain('Files');           // label stays for screen readers
  expect(a.host.querySelector('#tab-files')!.getAttribute('data-tip')).toBe('text:Files');
  expect(JSON.parse(localStorage.getItem(LS_SIDEBAR)!)).toBe(true);
  await act(async () => { a.root.unmount(); });
  const b = await mount();                                                               // "reload"
  expect(b.host.querySelector('.sidebar')!.classList.contains('collapsed')).toBe(true);
  await act(async () => { b.root.unmount(); });
});

it('is icons only at narrow widths whatever the choice, without the toggle', async () => {
  const { host, root } = await mount(false);
  expect(host.querySelector('.sidebar')!.classList.contains('collapsed')).toBe(true);
  expect(host.querySelector('.side-toggle')).toBeNull();
  await act(async () => { root.unmount(); });
});
