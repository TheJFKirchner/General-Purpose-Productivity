// Shared harness for the view tests: renders <App /> against the in-page demo (no back end), records the
// messages that go out and fails the test on any console.error. Call useDemoApp() once at the top of a test file.
import { afterEach, beforeEach, expect, vi } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import App from '../App';
import { dispatch, useLaunchpad } from '../store';
import { setTransport } from '../store/core';
import { initialState } from '../store/initial';
import { Demo } from '../demo/Demo';
import type { UiMessage } from '../contract';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root, demo: Demo, sent: UiMessage[], errors: unknown[];
export const step = async (ms: number) => { await act(async () => { vi.advanceTimersByTime(ms); }); };
export const doc = () => host.ownerDocument;
export const q = <T extends Element = HTMLElement>(sel: string) => doc().querySelector<T>(sel);
export const qa = <T extends Element = HTMLElement>(sel: string) => [...doc().querySelectorAll<T>(sel)];
export const click = async (el: Element | null | undefined) => { expect(el).toBeTruthy(); await act(async () => { (el as HTMLElement).click(); }); };
export const byText = (sel: string, text: string) => qa(sel).find(el => el.textContent?.trim() === text) || null;
export const sentOf = (type: string) => sent.filter(m => m.type === type);
export async function typeInto(el: HTMLTextAreaElement | HTMLInputElement, value: string) {
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value); el.dispatchEvent(new Event('input', { bubbles: true })); });
}
export const key = async (k: string, ctrl = false) => { await act(async () => { doc().body.dispatchEvent(new KeyboardEvent('keydown', { key: k, ctrlKey: ctrl, bubbles: true, cancelable: true })); }); };

export function useDemoApp() {

  beforeEach(async () => {
    vi.useFakeTimers();
    localStorage.clear();
    useLaunchpad.setState(initialState(), true);
    demo = new Demo(dispatch, 1);
    sent = [];
    setTransport(m => { sent.push(m); demo.receive(m); return true; });
    errors = [];
    vi.spyOn(console, 'error').mockImplementation((...a) => { errors.push(a); });
    host = document.createElement('div'); document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => { root.render(<App />); });
    await act(async () => { demo.start(); });
    await step(10_000);
  });
  afterEach(async () => {
    await act(async () => { root.unmount(); });
    demo.stop(); host.remove();
    vi.restoreAllMocks(); vi.clearAllTimers(); vi.useRealTimers();
    expect(errors, JSON.stringify(errors).slice(0, 600)).toHaveLength(0);
  });
}
