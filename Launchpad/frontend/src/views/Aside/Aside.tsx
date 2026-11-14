/* The right-hand side panel on every tab: the Activity feed (Missions tab only; CSS swaps it for the orbit via
   body.v-missions), "In orbit" (SVG + run list) and Incoming (the request queue).
   Ported from prototype/launchpad-orbit.html HTML 738-763; JS: Incoming 1700-1878, orbit 1880-1985, live values
   1988-2006, activity feed 2321-2404. Tooltips are the shared TipHost (data-tip on the elements). */
import './Aside.css';
import { sel, useComputed } from '../../store';
import { Feed } from './Feed';
import { Orbit, RunList } from './Orbit';
import { IncomingHead, Queue } from './Incoming';

export default function Aside() {
  return (
    <aside aria-label="Flights and incoming requests">
      <Feed />
      <div className="flight card">
        <div className="fl-head"><h2>In orbit</h2><FlightSummary /></div>
        <Orbit />
        <RunList />
      </div>
      <IncomingHead />
      <Queue />
    </aside>
  );
}

function FlightSummary() {
  const t = useComputed(st => {
    const runs = sel.inFlight(st).length, working = sel.workingCount(st), waiting = sel.openCount(st);
    return `${runs} in flight · ${working} working${waiting ? ` · ${waiting} waiting` : ''}`;
  });
  return <span className="fl-sum" id="flSum" title={t}>{t}</span>;
}
