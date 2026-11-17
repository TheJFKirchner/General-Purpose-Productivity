/* The per-session Auto answers switch, beside the Autopilot switch wherever that appears (plan card before launch, the run
   row in the side panel, each running Missions system). A real switch (role=switch, aria-checked) with its own icon, an
   accessible name and a tooltip saying what it does. It is NOT Autopilot (which approves permission requests): this one
   answers the builders' questions with the builder's own recommendation. One click either way; the server's auto_answers
   event is authoritative. */
import { actions, useLaunchpad } from '../store';
import { AUTO_ANSWERS_HINT } from '../lib/labels';
import { CircleHelp } from './icons';

export function AutoAnswersSwitch({ sessionId }: { sessionId: string }) {
  const on = useLaunchpad(st => !!st.sessions[sessionId]?.autoAnswers);
  return (
    <button type="button" role="switch" aria-checked={on} className={`apsw aasw${on ? ' on' : ''}`}
      aria-label="Auto answers: answer builders' questions with their own recommendation" title={AUTO_ANSWERS_HINT}
      onClick={e => { e.preventDefault(); e.stopPropagation(); actions.toggleAutoAnswers(sessionId); }}>
      <i aria-hidden="true" /><CircleHelp />{on ? 'Auto answers ON' : 'Auto answers off'}
    </button>
  );
}
