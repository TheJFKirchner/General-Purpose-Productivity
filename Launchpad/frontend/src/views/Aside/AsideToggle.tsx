/* Closing and reopening the right-hand panel. `AsideClose` is a slim handle centred on the boundary between the view and
   the panel, at the panel's mid-height (it sits in the gap between them, positioned on the aside, which never scrolls
   itself, so it stays put while the panel's lists scroll). `AsideStrip` stands in the panel's place while it is closed: a
   slim strip at the right edge with the reopen arrow at that same mid-height and, just above it, a coral count of the
   Incoming items waiting on the user (sel.openCount, the same count as the Incoming badge and the page title).
   At narrow widths (980 px and below, where the panel stacks under the views) the handle is centred horizontally on the
   boundary above the panel and points down; the closed strip is a slim row under the view with the arrow pointing up.
   The choice is kept in localStorage (lp.asideClosed) through actions.setAsideClosed. */
import { actions, sel, useComputed, useLaunchpad } from '../../store';
import { ChevronsLeft, ChevronsRight } from '../../components/icons';

/** What the panel holds on the current view (for labels and tooltips). */
function usePanelName(): string {
  const view = useLaunchpad(st => st.ui.view);
  return view === 'files' ? 'Repos' : view === 'missions' ? 'Activity and Incoming' : 'In orbit and Incoming';
}

/* the button pressed goes away with the panel or the strip, so focus moves to its counterpart */
const focusSoon = (id: string) => { setTimeout(() => document.getElementById(id)?.focus(), 0); };

export function AsideClose() {
  const name = usePanelName();
  return (
    <button type="button" className="aside-x" id="asideClose" aria-label={`Close the side panel (${name})`} aria-expanded={true}
      data-tip="text:Close the panel" onClick={() => { actions.setAsideClosed(true); focusSoon('asideOpen'); }}>
      <ChevronsRight />
    </button>
  );
}

export function AsideStrip() {
  const n = useComputed(st => sel.openCount(st));
  const name = usePanelName();
  const label = `Open the side panel (${name})${n ? `, ${n} waiting` : ''}`;
  return (
    <aside className="aside-strip" aria-label="Side panel (closed)">
      <div className="aside-mid">
        {/* the live region stays mounted so a change is announced; empty (and invisible) at zero */}
        <span className="aside-count-slot" role="status" aria-live="polite">
          {n ? <span className="aside-count" id="asideCount"><span aria-hidden="true">{n > 99 ? '99+' : n}</span><span className="sr">{n} waiting</span></span> : null}
        </span>
        <button type="button" className="aside-open" id="asideOpen" aria-label={label} aria-expanded={false}
          data-tip={`text:Show ${name}`} onClick={() => { actions.setAsideClosed(false); focusSoon('asideClose'); }}>
          <ChevronsLeft /><span className="aside-open-txt">Show {name}</span>
        </button>
      </div>
    </aside>
  );
}
