/* The CLI-then-model picker under a chat box (the planner's and the CLI chat's; views/Plan/PlannerPicker.tsx and
   views/Code/Code.tsx): one compact button showing "CLI · Model" ("Claude · Sonnet"), styled like the model picker
   under VS Code's chat box; its menu opens upward.
   Menu: a "CLI" dropdown (a menuitem that opens a small nested menu of the CLIs; unavailable ones listed with the
   server's note, not selectable), then only the shown CLI's models as radio items, then the caller's own items after a
   separator (the planner: auto-promote + Rules, New plan). Changing the CLI picks that CLI's first model and keeps the
   menu open on its models; picking a model closes it. What a pick means is the server's call (the view's hints and
   note say it). Everything shown comes from a selector (sel.plannerPickerView / sel.cliPickerView).
   Keyboard: Enter / Space / Up / Down on the button open the menu on the current choice; Up / Down / Home / End and
   Tab / Shift+Tab move through every item; Enter / Space / Right on "CLI" open its list, Left or Esc close it again;
   Esc (or a click outside) closes the menu and focus returns to the button. */
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent as RKeyboardEvent, type ReactNode } from 'react';
import type { ModelPickerView, PickerHarness } from '../store';
import { Check, ChevronDown } from './icons';

const ITEM_SEL = '[role="menuitemradio"],[role="menuitemcheckbox"],[role="menuitem"]';

export interface ModelPickerProps {
  /** id prefix: <id>Btn, <id>Menu, <id>Cli, <id>CliList, <id>Note ('pk' = the planner, 'cpk' = the CLI chat) */
  id: string;
  /** id of the row (for tests and anchors) */
  rowId?: string;
  view: ModelPickerView;
  /** whose picker, for the button's accessible name ("Planner", "CLI chat") */
  who: string;
  /** a small tag on the button (the planner: "promoted") */
  tag?: string | null;
  onPick: (optionId: string) => void;
  /** extra menu items after a separator; close() closes the menu (focus back on the button unless false); button = the
      picker's button (an anchor for a follow-up menu) */
  extra?: (close: (focusButton?: boolean) => void, button: HTMLButtonElement | null) => ReactNode;
  /** called whenever the menu closes (local confirms reset) */
  onClose?: () => void;
  /** the menu closes when this changes (the planner: the session shown) */
  resetKey?: string | null;
  /** something that sits in the row beside the picker button (the planner: the Auto answers switch) */
  trailing?: ReactNode;
}

export function ModelPicker({ id, rowId, view: v, who, tag, onPick, extra, onClose, resetKey, trailing }: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const [cliOpen, setCliOpen] = useState(false);
  /** the CLI whose models are listed (starts on the current one each time the menu opens) */
  const [shown, setShown] = useState(v.harness);
  const focusNext = useRef<'model' | 'cli' | 'harness' | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose); onCloseRef.current = onClose;

  const close = (focusButton = true) => {
    setOpen(false); setCliOpen(false); onCloseRef.current?.();
    if (focusButton) btnRef.current?.focus();
  };
  const openMenu = () => { setShown(v.harness); setCliOpen(false); setOpen(true); };

  useEffect(() => { setOpen(false); setCliOpen(false); onCloseRef.current?.(); }, [resetKey]);

  /* on open: focus the current choice (else the first item) */
  useLayoutEffect(() => {
    if (!open || !menuRef.current) return;
    const m = menuRef.current;
    (m.querySelector<HTMLElement>('[role="menuitemradio"][data-option][aria-checked="true"]') || m.querySelector<HTMLElement>(ITEM_SEL))?.focus();
  }, [open]);

  /* after the CLI list opens / closes or another CLI is shown: move focus where the keyboard user expects it */
  useLayoutEffect(() => {
    const m = menuRef.current, f = focusNext.current; focusNext.current = null;
    if (!m || !f) return;
    if (f === 'harness') (m.querySelector<HTMLElement>('[data-harness][aria-checked="true"]') || m.querySelector<HTMLElement>('[data-harness]'))?.focus();
    else if (f === 'cli') m.querySelector<HTMLElement>(`#${id}Cli`)?.focus();
    else (m.querySelector<HTMLElement>('[data-option][aria-checked="true"]') || m.querySelector<HTMLElement>('[data-option]'))?.focus();
  }, [cliOpen, shown, id]);

  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (menuRef.current && !menuRef.current.contains(t) && btnRef.current && !btnRef.current.contains(t)) close(false);
    };
    document.addEventListener('pointerdown', down, true);
    return () => document.removeEventListener('pointerdown', down, true);
  }, [open]);

  const shownH = v.harnesses.find(h => h.harness === shown) || v.harnesses.find(h => h.harness === v.harness) || v.harnesses[0];
  const models = v.items.filter(o => o.harness === (shownH ? shownH.harness : v.harness));

  const toggleCli = (on = !cliOpen) => { focusNext.current = on ? 'harness' : 'cli'; setCliOpen(on); };
  const pickCli = (h: PickerHarness) => {
    if (h.disabled) return;
    if (h.harness === shown) { toggleCli(false); return; }
    focusNext.current = 'model';
    setShown(h.harness); setCliOpen(false);
    if (h.first) onPick(h.first);                     // changing the CLI picks its first model; the menu stays open
  };
  const pick = (optionId: string, disabled: boolean) => {
    if (disabled) return;
    onPick(optionId);
    close();
  };

  const onMenuKey = (e: RKeyboardEvent<HTMLDivElement>) => {
    const t = e.target as HTMLElement;
    const inList = !!t.closest?.(`#${id}CliList`);
    if (e.key === 'Escape') {
      e.preventDefault(); e.stopPropagation();
      if (cliOpen) toggleCli(false); else close();
      return;
    }
    if (t.id === `${id}Cli` && e.key === 'ArrowRight') { e.preventDefault(); toggleCli(true); return; }
    if (inList && e.key === 'ArrowLeft') { e.preventDefault(); toggleCli(false); return; }
    const items = [...(menuRef.current?.querySelectorAll<HTMLElement>(ITEM_SEL) || [])];
    if (!items.length) return;
    const k = items.indexOf(document.activeElement as HTMLElement);
    let next = -1;
    if (e.key === 'ArrowDown' || (e.key === 'Tab' && !e.shiftKey)) next = (k + 1) % items.length;
    else if (e.key === 'ArrowUp' || (e.key === 'Tab' && e.shiftKey)) next = (k - 1 + items.length) % items.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = items.length - 1;
    if (next >= 0) { e.preventDefault(); items[next].focus(); }
  };
  const onButtonKey = (e: RKeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); openMenu(); }
  };

  const busy = v.choosing != null;
  return (
    <div className="pk-row" id={rowId}>
      <div className="pk">
        <button type="button" ref={btnRef} id={`${id}Btn`} className={`pk-btn${tag ? ' promoted' : ''}`} aria-haspopup="menu" aria-expanded={open}
          aria-controls={open ? `${id}Menu` : undefined} aria-label={`${who}: ${v.label}${tag ? ', ' + tag : ''}. Change CLI or model`}
          title={v.title} disabled={busy} onClick={() => (open ? close() : openMenu())} onKeyDown={onButtonKey}>
          <span className="pk-lab">{busy ? 'Switching…' : v.label}</span>
          {tag && !busy ? <span className="pk-tag">{tag}</span> : null}
          <ChevronDown />
        </button>
        {open ? (
          <div className="pk-menu" id={`${id}Menu`} role="menu" aria-label={`${who}: CLI and model`} ref={menuRef} onKeyDown={onMenuKey}>
            <div className="pk-h" aria-hidden="true">CLI</div>
            <button type="button" role="menuitem" id={`${id}Cli`} className="pk-item pk-cli" aria-haspopup="menu" aria-expanded={cliOpen}
              aria-controls={cliOpen ? `${id}CliList` : undefined} aria-label={`CLI: ${shownH ? shownH.label : ''}. Change CLI`} tabIndex={-1}
              onClick={() => toggleCli()}>
              <span className="pk-name">{shownH ? shownH.label : ''}</span>
              <ChevronDown />
            </button>
            {cliOpen ? (
              <div className="pk-clilist" role="menu" id={`${id}CliList`} aria-label="CLI">
                {v.harnesses.map(h => (
                  <button key={h.harness} type="button" role="menuitemradio" aria-checked={h.harness === shown} aria-disabled={h.disabled || undefined}
                    className={`pk-item${h.harness === shown ? ' on' : ''}`} data-harness={h.harness} tabIndex={-1} onClick={() => pickCli(h)}>
                    <span className="pk-mark">{h.harness === shown ? <Check /> : null}</span>
                    <span className="pk-name">{h.label}</span>
                    {h.note ? <small>{h.note}</small> : null}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="pk-h" aria-hidden="true">Model</div>
            {models.map(o => (
              <button key={o.id} type="button" role="menuitemradio" aria-checked={o.current} aria-disabled={o.disabled || undefined}
                aria-label={`${o.full}${o.hint ? ', ' + o.hint : ''}`}
                className={`pk-item${o.current ? ' on' : ''}`} data-option={o.id} tabIndex={-1} onClick={() => pick(o.id, o.disabled)}>
                <span className="pk-mark">{o.current ? <Check /> : null}</span>
                <span className="pk-name">{o.label}</span>
                {o.next ? <span className="chip">{v.nextLabel}</span> : null}
                {o.hint ? <small>{o.hint}</small> : null}
              </button>
            ))}
            {extra ? <><div className="pk-sep" role="separator" />{extra(close, btnRef.current)}</> : null}
          </div>
        ) : null}
      </div>
      {trailing}
      {v.note ? <p className="pk-note" role="status" id={`${id}Note`} title={v.note}>{v.note}</p> : null}
    </div>
  );
}
