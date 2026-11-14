/* The shared modal (#scrim .modal): title, optional meta line, any body, action buttons + Close.
   openModal({...}) from anywhere; closeModal() closes it. Backdrop click and Esc close it too (Radix Dialog, see
   Dialog.tsx: focus is trapped inside and returns to where it was on close).
   `actions` may be a function: it is re-evaluated on every store change, so labels / disabled stay live.
   (The pen editor and Settings have their own dialogs in views/Files and views/Settings.) */
import { useEffect, useRef, type ReactNode } from 'react';
import { create } from 'zustand';
import { useLaunchpad } from '../store';
import { Dialog, DialogTitle, DialogX } from './Dialog';

export interface ModalAction { label: string; primary?: boolean; danger?: boolean; disabled?: boolean; icon?: ReactNode; onClick: () => void }
export interface ModalSpec {
  title: string;
  meta?: string;
  wide?: boolean;
  body: ReactNode;
  actions?: ModalAction[] | (() => ModalAction[]);
}

const useModal = create<{ spec: ModalSpec | null; n: number }>(() => ({ spec: null, n: 0 }));
export const openModal = (spec: ModalSpec): void => useModal.setState(s => ({ spec, n: s.n + 1 }));
export const closeModal = (): void => useModal.setState({ spec: null });
export const isModalOpen = (): boolean => !!useModal.getState().spec;

export function ModalHost() {
  const { spec, n } = useModal();
  useLaunchpad();                              // re-render on store changes (live action labels)
  const actsRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const focusFirst = () => {
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
    const f = actsRef.current;
    (f?.querySelector<HTMLButtonElement>('button.primary:not(:disabled)') || f?.querySelector<HTMLButtonElement>('button:not(:disabled)'))?.focus();
  };
  /* a new modal replacing an open one: back to the top, focus its first action */
  const firstN = useRef(n);
  useEffect(() => {
    if (spec && n !== firstN.current) focusFirst();
    firstN.current = n;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n]);
  const acts = spec ? (typeof spec.actions === 'function' ? spec.actions() : spec.actions || []) : [];
  return (
    <Dialog open={!!spec} onRequestClose={closeModal} scrimId="scrim" className={spec && spec.wide ? 'wide' : ''} initialFocus={focusFirst}>
      {spec ? <>
        <div className="modal-head">
          <div>
            <DialogTitle asChild><h2 id="modalTitle">{spec.title}</h2></DialogTitle>
            {spec.meta ? <div className="modal-meta">{spec.meta}</div> : null}
          </div>
          <DialogX onClick={closeModal} />
        </div>
        <div className="modal-body" ref={bodyRef}>{spec.body}</div>
        <div className="modal-foot" ref={actsRef}>
          <button type="button" className="pill ghost" onClick={closeModal}>Close</button>
          {acts.map((a, k) => (
            <button key={k} type="button" className={`pill${a.primary ? ' primary' : ''}${a.danger ? ' danger' : ''}`} disabled={!!a.disabled} onClick={a.onClick}>{a.icon}{a.label}</button>
          ))}
        </div>
      </> : null}
    </Dialog>
  );
}
