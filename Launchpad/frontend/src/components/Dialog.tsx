/* The dialog primitive every modal uses: Radix Dialog (focus trap, focus return, Esc, outside click, aria-modal,
   scroll lock, the rest of the page hidden from assistive tech), styled only by theme.css (.scrim, .modal).
   Radix brings no look of its own. Esc and outside clicks call onRequestClose; the caller decides whether the dialog
   really closes (the editor asks once when there are unsaved changes). Every dialog needs a <DialogTitle>. */
import * as D from '@radix-ui/react-dialog';
import { useRef, type ReactNode } from 'react';
import { X } from './icons';

export function Dialog({ open, onRequestClose, scrimId, className = '', initialFocus, onEscape, children }: {
  open: boolean;
  onRequestClose: () => void;
  scrimId?: string;
  className?: string;
  /** focus this instead of the first focusable element when the dialog opens */
  initialFocus?: () => void;
  /** own Esc handling (call e.preventDefault() to keep the dialog open) */
  onEscape?: (e: KeyboardEvent) => void;
  children: ReactNode;
}) {
  /* no Radix Trigger here (dialogs open from many places), so remember the opener and give focus back on close */
  const opener = useRef<HTMLElement | null>(null);
  return (
    <D.Root open={open} onOpenChange={o => { if (!o) onRequestClose(); }}>
      <D.Portal>
        <D.Overlay className="scrim open" id={scrimId}>
          <D.Content className={`modal card${className ? ' ' + className : ''}`} aria-describedby={undefined}
            onOpenAutoFocus={e => {
              const a = document.activeElement;
              opener.current = a instanceof HTMLElement && a !== document.body ? a : null;
              if (initialFocus) { e.preventDefault(); initialFocus(); }
            }}
            onCloseAutoFocus={e => { e.preventDefault(); const o = opener.current; opener.current = null; if (o && o.isConnected) o.focus(); }}
            onEscapeKeyDown={onEscape}>
            {children}
          </D.Content>
        </D.Overlay>
      </D.Portal>
    </D.Root>
  );
}

export const DialogTitle = D.Title;

/** The round X in a dialog's top-right corner. */
export function DialogX({ onClick, label = 'Close' }: { onClick: () => void; label?: string }) {
  return <button type="button" className="pill ghost sm icon" aria-label={label} data-tip={`text:${label}`} onClick={onClick}><X /></button>;
}
