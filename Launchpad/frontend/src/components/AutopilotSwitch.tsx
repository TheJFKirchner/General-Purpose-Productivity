/* The per-session Autopilot switch (plan card before launch, run row in the side panel, Missions system).
   A real switch (role=switch, aria-checked). Turning it on takes a second click within 4 s (store: ui.apConfirm);
   the server's autopilot event is authoritative. */
import { actions, useLaunchpad } from '../store';
import { AP_HINT } from '../lib/labels';

export function AutopilotSwitch({ sessionId }: { sessionId: string }) {
  const on = useLaunchpad(st => !!st.sessions[sessionId]?.autopilot);
  const confirm = useLaunchpad(st => st.ui.apConfirm === sessionId);
  return (
    <button type="button" role="switch" aria-checked={on} className={`apsw${on ? ' on' : ''}${confirm ? ' confirm' : ''}`} title={AP_HINT}
      onClick={e => { e.preventDefault(); e.stopPropagation(); actions.toggleAutopilot(sessionId); }}>
      <i aria-hidden="true" />{on ? 'Autopilot ON' : confirm ? 'Click again: approve everything' : 'Autopilot off'}
    </button>
  );
}
