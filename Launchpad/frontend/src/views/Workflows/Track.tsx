/* The stage track: a workflow's stages left to right, drawn from its definition. Agent stages are solid boxes with the
   agent's name; review stages are dashed boxes with a person icon and the word "Review", so the two differ by shape,
   icon and word, not colour alone. With a run, each stage also shows its state (waiting, running, done, failed,
   awaiting review) as an icon plus a word. No drag and drop, no branching: a straight line. */
import { Fragment, useEffect, useRef } from 'react';
import type { Workflow, WorkflowRun, WorkflowStageStatus } from '../../contract';
import { AlertTriangle, Bot, ChevronRight, CircleCheck, CircleDashed, CircleX, Loader2, UserCheck } from '../../components/icons';

export const STAGE_STATUS_LABEL: Record<WorkflowStageStatus, string> = {
  waiting: 'Waiting', running: 'Running', done: 'Done', failed: 'Failed', awaiting_review: 'Awaiting review',
};

function StatusMark({ status }: { status: WorkflowStageStatus }) {
  const icon = status === 'running' ? <Loader2 className="spin" /> : status === 'done' ? <CircleCheck /> : status === 'failed' ? <CircleX />
    : status === 'awaiting_review' ? <UserCheck /> : <CircleDashed />;
  return <span className="wf-st">{icon}{STAGE_STATUS_LABEL[status]}</span>;
}

/** The stage a run is at (running, waiting for review, or the one that failed), or -1. */
export const currentStage = (run?: WorkflowRun | null): number => (run ? run.stages.findIndex(s => s.status === 'running' || s.status === 'awaiting_review' || s.status === 'failed') : -1);

export function Track({ w, run }: { w: Workflow; run?: WorkflowRun | null }) {
  const ref = useRef<HTMLOListElement>(null);
  const cur = currentStage(run);
  /* when the line is wider than the card (many stages) it scrolls: bring the current stage into view */
  useEffect(() => {
    const ol = ref.current, el = cur >= 0 ? ol?.querySelector<HTMLElement>(`[data-i="${cur}"]`) : null;
    if (!ol || !el || ol.scrollWidth <= ol.clientWidth) return;
    ol.scrollLeft = Math.max(0, el.offsetLeft - (ol.clientWidth - el.offsetWidth) / 2);
  }, [cur, run?.id, w.stages.length]);
  return (
    <ol className="wf-track" aria-label={`Stages of ${w.name}`} ref={ref}>
      {w.stages.map((s, i) => {
        const rs = run && run.stages[i] ? run.stages[i].status : null;
        const warned = w.warnings.some(x => x.level === 'error' && x.stage === i);
        return (
          <Fragment key={i}>
            {i > 0 ? <li className="wf-link" aria-hidden="true"><ChevronRight /></li> : null}
            <li className="wf-stage" data-i={i} title={`${s.title}${s.kind === 'agent' && (s.agent_display || s.agent) ? ' · ' + (s.agent_display || s.agent) : ''}`} data-kind={s.kind} data-status={rs || 'idle'} data-warn={warned ? 'true' : undefined} aria-label={`Stage ${i + 1}, ${s.kind === 'review' ? 'review' : 'agent'}: ${s.title}${rs ? ', ' + STAGE_STATUS_LABEL[rs] : ''}`}>
              <span className="wf-kind">{s.kind === 'review' ? <><UserCheck />Review</> : <><Bot />Agent</>}</span>
              <b className="wf-title">{s.title || 'Untitled stage'}</b>
              <span className="wf-sub">{s.kind === 'agent' ? s.agent_display || s.agent || 'No agent chosen' : s.checklist.length ? `${s.checklist.length} check${s.checklist.length === 1 ? '' : 's'}` : 'Sign-off only'}</span>
              {warned ? <span className="wf-st wf-warnmark"><AlertTriangle />Needs a fix</span> : null}
              {rs ? <StatusMark status={rs} /> : null}
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
