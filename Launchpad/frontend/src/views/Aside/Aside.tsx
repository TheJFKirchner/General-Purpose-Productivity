/* The right-hand side panel: on the Files tab the Repos panel (Repos.tsx); on every other tab the Activity feed
   (Missions tab only; CSS swaps it for the orbit via body.v-missions), "In orbit" (SVG + run list) and Incoming (the request queue).
   The panel can be closed with the slim handle on its boundary with the view (AsideToggle.tsx): it then shrinks to a slim
   strip with the reopen arrow and the waiting count at the same mid-height, and the view takes the width. Ported from prototype/launchpad-orbit.html HTML 738-763; JS: Incoming 1700-1878, orbit
   1880-1985, live values 1988-2006, activity feed 2321-2404. Tooltips are the shared TipHost (data-tip on the elements). */
import './Aside.css';
import { useRef } from 'react';
import { sel, useComputed, useLaunchpad } from '../../store';
import { Feed } from './Feed';
import { Orbit, RunList } from './Orbit';
import { IncomingHead, Queue } from './Incoming';
import { Repos, WaitingLine } from './Repos';
import { AsideClose, AsideStrip } from './AsideToggle';

export default function Aside() {
  const view = useLaunchpad(st => st.ui.view);
  const closed = useLaunchpad(st => st.ui.asideClosed);
  /* a short slide-in only when the user reopens it (not on load or on a tab switch): the class stays until the next toggle */
  const was = useRef(closed), opened = useRef(false);
  if (was.current !== closed) { opened.current = !closed; was.current = closed; }
  if (closed) return <AsideStrip />;
  const cls = opened.current ? 'aside-in' : undefined;
  /* Files tab: the Repos panel (with a compact "N waiting" line for the queue) instead of In orbit and Incoming */
  if (view === 'files') {
    return (
      <aside aria-label="Git repos" className={cls}>
        <AsideClose />
        <WaitingLine />
        <Repos />
      </aside>
    );
  }
  return (
    <aside aria-label="Flights and incoming requests" className={cls}>
      <AsideClose />
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
