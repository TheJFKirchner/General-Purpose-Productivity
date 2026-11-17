/* The per-session Auto answers switch, in the planner's control row (next to the model picker). A real switch
   (role=switch, aria-checked) with an accessible name and a short tooltip. It is NOT Autopilot (which approves
   permission requests): this one answers questions with the agent's recommended answer. One click either way; the
   server's auto_answers event is authoritative. */
import { actions, useLaunchpad } from '../store';
import { AUTO_ANSWERS_HINT } from '../lib/labels';

export function AutoAnswersSwitch({ sessionId }: { sessionId: string }) {
  const on = useLaunchpad(st => !!st.sessions[sessionId]?.autoAnswers);
  return (
    <button type="button" role="switch" aria-checked={on} id="autoAnswers" className={`apsw aasw${on ? ' on' : ''}`}
      aria-label="Auto answers" title={AUTO_ANSWERS_HINT} onClick={() => actions.toggleAutoAnswers(sessionId)}>
      <i aria-hidden="true" />{on ? 'Auto answers ON' : 'Auto answers off'}
    </button>
  );
}
