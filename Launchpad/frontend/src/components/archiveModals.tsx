/* Modals opened from more than one screen: a run's report, a plan, a read-only copy of a planning chat. */
import { actions, getState, sel, useLaunchpad } from '../store';
import { Markdown } from './Markdown';
import { PlanLog } from '../views/Plan/PlanLog';
import { closeModal, openModal } from './Modal';
import { usd } from '../lib/format';
import { S_LABEL } from '../lib/labels';
import { Pencil, Rocket, Send } from './icons';

/** Report of a finished run (Incoming report card, Missions). Edit report (pen) + Send to planner. */
export function openReport(sid: string): void {
  const st = getState(), s = st.sessions[sid]; if (!s || !s.report) return;
  const pc = sel.plannerCostOf(st, sid), total = sel.sessionTotal(st, sid);
  const thisRun = typeof s.report.total === 'number' && Math.abs(s.report.total - total) > 0.005 ? `this run ${usd(s.report.total)}` : '';
  const meta = [`${sel.sLabel(s)} · ${S_LABEL[s.status] || s.status}`, `session total ${usd(total)}`, thisRun, pc ? `planner ${usd(pc)} (separate)` : '', s.report.path].filter(Boolean).join(' · ');
  const rroot = s.dirId ?? sel.defaultDirId(st), path = s.report.path;
  openModal({
    title: `Report · ${sel.sName(s)}`, meta, wide: true,
    body: <Markdown doc text={s.report.markdown || '_The run sent no report text._'} />,
    actions: () => {
      const s2 = getState().sessions[sid];
      return [
        ...(path && rroot != null && !s.wf ? [{ label: 'Edit report', icon: <Pencil />, onClick: () => actions.openEditor(rroot, path) }] : []),
        ...(s2?.wf ? [] : [{ label: s2?.reportSent ? 'Sent to planner' : 'Send to planner', icon: <Send />, primary: true, disabled: !!s2?.reportSent, onClick: () => { actions.sendReport(sid); } }]),
      ];
    },
  });
}

/** A session's current plan draft (Missions "Read plan"), with Approve when it has not run yet. */
export function openPlan(sid: string): void {
  const s = getState().sessions[sid]; if (!s || !s.draft) return;
  openModal({
    title: `Plan · ${sel.sName(s)}`, meta: [sel.sLabel(s), s.draft.path].filter(Boolean).join(' · '), wide: true,
    body: <Markdown doc text={s.draft.markdown || ''} />,
    actions: () => {
      const s2 = getState().sessions[sid];
      if (!s2 || sel.draftLaunched(s2)) return [];
      return [{ label: s2.approving ? 'Launching…' : s2.status === 'running' ? 'Run in progress' : 'Approve and launch', icon: <Rocket />, primary: true, disabled: !sel.canApprove(s2), onClick: () => actions.approve(sid) }];
    },
  });
}

/** Read-only copy of a session's planning chat (Missions "Planning chat"). */
export function openArchive(sid: string): void {
  const s = getState().sessions[sid]; if (!s) return;
  openModal({ title: `Planning chat · ${sel.sName(s)}`, meta: `${sel.sLabel(s)} · read-only copy`, wide: true, body: <ArchivedLog sid={sid} /> });
}

/** The planner chat log rendered read-only: the same PlanLog the Plan tab uses (full plan, Autopilot tag, answered
    rounds), inside .msgs.archived, whose CSS hides every button, form and action row (as the vanilla DOM copy did). */
function ArchivedLog({ sid }: { sid: string }) {
  const s = useLaunchpad(st => st.sessions[sid]);
  if (!s) return null;
  return (
    <div className="msgs archived">
      <PlanLog entries={s.log} sid={sid} typing={false} />
    </div>
  );
}

export { closeModal };
