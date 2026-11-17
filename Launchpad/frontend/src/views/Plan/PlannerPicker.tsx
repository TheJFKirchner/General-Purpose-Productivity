/* The planner's control row under its chat box: the shared CLI-then-model picker (components/ModelPicker.tsx) with
   the planner's own items after the models: "Auto-promote to <top model>" with a Rules link (the criteria,
   read-only), then "New plan". (The Auto answers switch is not here: it sits beside Autopilot.)
   What a pick means is the server's call (planner_choose): an unstarted plan takes it at once, the top model on a
   running plan is promotion by hand, anything else applies to the next new plan (the row then says so). The server
   sends a flat list of harness-and-model options (planner_choice); sel.plannerPickerView groups it by CLI. */
import { useEffect, useRef, useState } from 'react';
import { actions, sel, useComputed, useCurrentSession } from '../../store';
import { Markdown, ModelPicker, openModal } from '../../components';
import { Plus } from '../../components/icons';

export function PlannerPicker() {
  const v = useComputed(st => sel.plannerPickerView(st));
  const s = useCurrentSession();

  /* "New plan" with an unlaunched plan in this session: the first click asks "Set this plan aside?" (4 s) */
  const [npConfirm, setNpConfirm] = useState(false);
  const npTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearNp = () => { if (npTimer.current) { clearTimeout(npTimer.current); npTimer.current = null; } };
  useEffect(() => () => clearNp(), []);
  const sid = s ? s.id : null;

  if (!v) return null;

  const resetNp = () => { setNpConfirm(false); clearNp(); };
  const showRules = (close: () => void) => {
    close();
    openModal({
      title: 'Promotion rules', meta: `${v.rules.path || 'promotion criteria'} · read-only here; edit it in Files or Crew`, wide: true,
      body: <Markdown doc text={v.rules.markdown || '_No promotion criteria found._'} label="Promotion rules" />,
    });
  };
  const onNewPlan = (close: () => void, button: HTMLElement | null) => {
    const unlaunched = !!s && !s.run && s.log.some(e => (e.kind === 'bubble' && e.who === 'me') || e.kind === 'plancard');
    if (unlaunched && !npConfirm) {
      setNpConfirm(true); clearNp();
      npTimer.current = setTimeout(() => { npTimer.current = null; setNpConfirm(false); }, 4000);
      return;
    }
    close();
    actions.chooseDir(button, dirId => actions.newPlan(dirId));
  };

  return (
    <ModelPicker id="pk" rowId="plannerControls" view={v} who="Planner" tag={v.promoted ? 'promoted' : null} resetKey={sid}
        onPick={id => actions.choosePlanner(id)} onClose={resetNp}
        extra={(close, button) => <>
          <div className="pk-auto">
            <button type="button" role="menuitemcheckbox" aria-checked={v.auto} aria-disabled={v.promotionOff || undefined} id="pkAuto"
              aria-label={`Auto-promote to ${v.topLabel}, ${v.auto ? 'on' : 'off'}${v.promotionOff ? ', not needed: new plans already start there' : ''}`}
              className="pk-item" tabIndex={-1} onClick={() => { if (!v.promotionOff) actions.setAutoPromote(!v.auto); }}>
              <span className={`pk-switch${v.auto ? ' on' : ''}`} aria-hidden="true" />
              <span className="pk-name">Auto-promote to {v.topLabel}</span>
              <small>{v.promotionOff ? `new plans already start on ${v.topLabel}` : v.auto ? 'the planner moves up itself when the rules say so' : 'only when you pick it'}</small>
            </button>
            <button type="button" role="menuitem" id="pkRules" className="pk-link" tabIndex={-1} onClick={() => showRules(() => close())}>Rules</button>
          </div>
          <div className="pk-sep" role="separator" />
          <button type="button" role="menuitem" id="pkNewPlan" aria-label={npConfirm ? 'Set this plan aside and start a new plan. Click again to confirm' : 'New plan'} className={`pk-item${npConfirm ? ' danger' : ''}`} tabIndex={-1} onClick={() => onNewPlan(() => close(), button)}>
            <span className="pk-mark"><Plus /></span>
            <span className="pk-name">{npConfirm ? 'Set this plan aside?' : 'New plan'}</span>
            <small>{npConfirm ? 'Click again to start a new plan; this one stays in Missions' : 'Start a new session; runs already in flight keep going'}</small>
          </button>
        </>} />
  );
}
