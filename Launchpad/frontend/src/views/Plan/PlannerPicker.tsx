/* The planner's control row under its chat box: one compact picker button showing the harness and model ("Claude ·
   Sonnet"), styled like the model picker under the chat box in VS Code's chat panel; its menu opens upward.
   Menu: the harness-and-model options from the server (planner_choice; unavailable ones disabled with the server's
   note), a divider, "Auto-promote to <top model>" with a Rules link (the criteria, read-only), then "New plan".
   What a pick means is the server's call (planner_choose): an unstarted plan takes it at once, the top model on a
   running plan is promotion by hand, anything else applies to the next new plan (the row then says so).
   Keyboard: Enter / Space / Up / Down on the button open the menu on the current choice; Up / Down / Home / End and
   Tab / Shift+Tab move through every item; Esc or a click outside closes it and focus returns to the button. */
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent as RKeyboardEvent } from 'react';
import { actions, sel, useComputed, useCurrentSession } from '../../store';
import { Markdown, openModal } from '../../components';
import { Check, ChevronDown, Plus } from '../../components/icons';

const ITEM_SEL = '[role="menuitemradio"],[role="menuitemcheckbox"],[role="menuitem"]';

export function PlannerPicker() {
  const v = useComputed(st => sel.plannerPickerView(st));
  const s = useCurrentSession();
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  /* "New plan" with an unlaunched plan in this session: the first click asks "Set this plan aside?" (4 s) */
  const [npConfirm, setNpConfirm] = useState(false);
  const npTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearNp = () => { if (npTimer.current) { clearTimeout(npTimer.current); npTimer.current = null; } };
  useEffect(() => () => clearNp(), []);
  const sid = s ? s.id : null;
  useEffect(() => { setNpConfirm(false); clearNp(); setOpen(false); }, [sid]);

  const close = (focusButton = true) => { setOpen(false); setNpConfirm(false); clearNp(); if (focusButton) btnRef.current?.focus(); };

  /* on open: focus the current choice (else the first item) */
  useLayoutEffect(() => {
    if (!open || !menuRef.current) return;
    const m = menuRef.current;
    (m.querySelector<HTMLElement>('[aria-checked="true"][role="menuitemradio"]') || m.querySelector<HTMLElement>(ITEM_SEL))?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (menuRef.current && !menuRef.current.contains(t) && btnRef.current && !btnRef.current.contains(t)) close(false);
    };
    document.addEventListener('pointerdown', down, true);
    return () => document.removeEventListener('pointerdown', down, true);
  }, [open]);

  if (!v) return null;

  const onMenuKey = (e: RKeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return; }
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
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); }
  };

  const pick = (id: string, disabled: boolean) => {
    if (disabled) return;
    actions.choosePlanner(id);
    close();
  };
  const showRules = () => {
    close();
    openModal({
      title: 'Promotion rules', meta: `${v.rules.path || 'promotion criteria'} · read-only here; edit it in Files or Crew`, wide: true,
      body: <Markdown doc text={v.rules.markdown || '_No promotion criteria found._'} label="Promotion rules" />,
    });
  };
  const onNewPlan = () => {
    const unlaunched = !!s && !s.run && s.log.some(e => (e.kind === 'bubble' && e.who === 'me') || e.kind === 'plancard');
    if (unlaunched && !npConfirm) {
      setNpConfirm(true); clearNp();
      npTimer.current = setTimeout(() => { npTimer.current = null; setNpConfirm(false); }, 4000);
      return;
    }
    close();
    actions.chooseDir(btnRef.current, dirId => actions.newPlan(dirId));
  };

  const busy = v.choosing != null;
  return (
    <div className="pk-row" id="plannerControls">
      <div className="pk">
        <button type="button" ref={btnRef} id="pkBtn" className={`pk-btn${v.promoted ? ' promoted' : ''}`} aria-haspopup="menu" aria-expanded={open}
          aria-controls={open ? 'pkMenu' : undefined} aria-label={`Planner: ${v.label}${v.promoted ? ', promoted' : ''}. Change harness or model`}
          title={v.title} disabled={busy} onClick={() => (open ? close() : setOpen(true))} onKeyDown={onButtonKey}>
          <span className="pk-lab">{busy ? 'Switching…' : v.label}</span>
          {v.promoted && !busy ? <span className="pk-tag">promoted</span> : null}
          <ChevronDown />
        </button>
        {open ? (
          <div className="pk-menu" id="pkMenu" role="menu" aria-label="Planner harness and model" ref={menuRef} onKeyDown={onMenuKey}>
            <div className="pk-h" aria-hidden="true">Harness and model</div>
            {v.items.map(o => (
              <button key={o.id} type="button" role="menuitemradio" aria-checked={o.current} aria-disabled={o.disabled || undefined}
                className={`pk-item${o.current ? ' on' : ''}`} data-option={o.id} tabIndex={-1} onClick={() => pick(o.id, o.disabled)}>
                <span className="pk-mark">{o.current ? <Check /> : null}</span>
                <span className="pk-name">{o.label}</span>
                {o.next ? <span className="chip">next plan</span> : null}
                {o.hint ? <small>{o.hint}</small> : null}
              </button>
            ))}
            <div className="pk-sep" role="separator" />
            <div className="pk-auto">
              <button type="button" role="menuitemcheckbox" aria-checked={v.auto} aria-disabled={v.promotionOff || undefined} id="pkAuto"
                className="pk-item" tabIndex={-1} onClick={() => { if (!v.promotionOff) actions.setAutoPromote(!v.auto); }}>
                <span className={`pk-switch${v.auto ? ' on' : ''}`} aria-hidden="true" />
                <span className="pk-name">Auto-promote to {v.topLabel}</span>
                <small>{v.promotionOff ? `new plans already start on ${v.topLabel}` : v.auto ? 'the planner moves up itself when the rules say so' : 'only when you pick it'}</small>
              </button>
              <button type="button" role="menuitem" id="pkRules" className="pk-link" tabIndex={-1} onClick={showRules}>Rules</button>
            </div>
            <div className="pk-sep" role="separator" />
            <button type="button" role="menuitem" id="pkNewPlan" className={`pk-item${npConfirm ? ' danger' : ''}`} tabIndex={-1} onClick={onNewPlan}>
              <span className="pk-mark"><Plus /></span>
              <span className="pk-name">{npConfirm ? 'Set this plan aside?' : 'New plan'}</span>
              <small>{npConfirm ? 'Click again to start a new plan; this one stays in Missions' : 'Start a new session; runs already in flight keep going'}</small>
            </button>
          </div>
        ) : null}
      </div>
      {v.note ? <p className="pk-note" role="status" id="pkNote">{v.note}</p> : null}
    </div>
  );
}
