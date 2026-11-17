/* Public face of the store. Views import from here only:
     import { useLaunchpad, useComputed, actions, send, sel } from '../../store';
   - read:  useLaunchpad(st => st.ui.view)  (one value)  ·  useLaunchpad()  (whole state)  ·  useComputed(fn)
   - derive: the pure functions in `sel` (selectors.ts), called with the state
   - act:   actions.* for anything that changes state; send(msg) for a plain message with no local change */
import { useMemo } from 'react';
import { getState, onActivityPing, send, useLaunchpad } from './core';
import type { AppState, Session } from './types';
import * as sel from './selectors';

export { useLaunchpad, getState, send, onActivityPing, sel };
export { dispatch } from './reducer';
export { actions } from './actions';
export type * from './types';
export type { FormField, ModelPickerView, PickerHarness, PickerItem } from './selectors';

/** Derived value from the whole state, recomputed only when the state changes. */
export function useComputed<T>(fn: (st: AppState) => T): T {
  const st = useLaunchpad();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => fn(st), [st]);
}

/** The session shown in the Plan tab (null before the first session_started). */
export function useCurrentSession(): Session | null {
  return useLaunchpad(st => (st.current != null && st.sessions[st.current]) || null);
}

/** One session by id. */
export function useSession(id: string | null | undefined): Session | null {
  return useLaunchpad(st => (id != null && st.sessions[id]) || null);
}
