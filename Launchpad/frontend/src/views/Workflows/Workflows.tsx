/* Workflows: a workflow is a study or report you run more than once, written down once as a straight line of stages
   (an agent doing one job, or a person reviewing). Each is a wide, flat card: name, description, folder, the stages
   left to right (Track.tsx), warnings (which also disable Run), and Run with a "Test run" tick box and an "Unattended"
   tick that starts from the workflow's own default. Run asks for the workflow's named inputs first. During a run the
   card shows each stage's state, the run folder, Stop, and a Review button when a person is wanted; the review itself
   is Review.tsx. Add / Edit is WorkflowForm.tsx. Messages: workflows_get, workflow_save, workflow_remove, workflow_run,
   workflow_stop, workflow_review (see the app/server.py header); state lives in `st.wf`. */
import './Workflows.css';
import { useEffect, useRef, useState } from 'react';
import { actions, sel, useLaunchpad } from '../../store';
import type { Workflow, WorkflowRun } from '../../contract';
import { Dialog, DialogTitle, DialogX, DirChip, Empty, Loading, Pill, ViewFrame } from '../../components';
import { AlertTriangle, FlaskConical, FolderOpen, Pencil, Play, Plus, RotateCw, Square, Trash, UserCheck, Workflow as WorkflowIcon } from '../../components/icons';
import { Track } from './Track';
import { ReviewScreen } from './Review';
import WorkflowForm from './WorkflowForm';

export const RUN_LABEL: Record<WorkflowRun['status'], string> = {
  running: 'Running', awaiting_review: 'Waiting for your review', done: 'Finished', failed: 'Failed', stopped: 'Stopped',
};

export default function Workflows() {
  const wf = useLaunchpad(st => st.wf);
  const runs = useLaunchpad(st => st.wf.runs);
  const [editing, setEditing] = useState<Workflow | 'new' | null>(null);
  const [review, setReview] = useState<string | null>(null);   // run id on the review screen
  const live = useRef(false);                                   // the screen was opened on a review that was waiting
  const openReview = useLaunchpad(st => st.wf.openReview);
  const canAdd = useLaunchpad(st => st.wf.folders.length > 0);
  const waiting = useLaunchpad(st => sel.wfWaiting(st));

  const rv = review ? runs[review] : null;
  const rvStage = rv ? (rv.stages.findIndex(s => s.status === 'awaiting_review') >= 0 ? rv.stages.findIndex(s => s.status === 'awaiting_review') : rv.stages.findLastIndex(s => s.kind === 'review' && !!s.review)) : -1;
  /* the run went away: back to the cards */
  useEffect(() => { if (review && !runs[review]) setReview(null); }, [runs, review]);
  /* an Incoming review card asked for this run's review */
  useEffect(() => { if (openReview) { live.current = true; setReview(openReview); actions.clearOpenReview(); } }, [openReview]);
  /* the review we were signing is no longer waiting (signed, sent back, run stopped): back to the cards, where the run shows its new state */
  useEffect(() => { if (review && live.current && rv && sel.wfReviewStage(rv) < 0) { live.current = false; setReview(null); } }, [rv, review]);

  const sub = wf.list.length
    ? `${wf.list.length} workflow${wf.list.length === 1 ? '' : 's'}${waiting ? ` · ${waiting} review${waiting === 1 ? '' : 's'} waiting for you` : ''}. A workflow is a study or report you run again and again.`
    : 'Studies and reports you run more than once, written down once.';

  return (
    <ViewFrame id="viewWorkflows" label="Workflows" title="Workflows" sub={<span id="wfSum">{sub}</span>} bodyClass={null}
      tools={<div className="wf-tools">
        <Pill size="sm" variant="primary" id="wfAdd" icon={<Plus />} disabled={!canAdd}
          title={canAdd ? 'Write a new workflow: its stages, inputs and where it saves its results' : 'Connect a folder in Settings first: a workflow is saved in a connected folder'}
          onClick={() => setEditing('new')}>Add workflow</Pill>
        <Pill size="sm" id="wfRefresh" icon={<RotateCw />} onClick={() => actions.workflowsGet()}>Refresh</Pill>
      </div>}>
      <div className="wf-body">
        {rv && rvStage >= 0 ? <ReviewScreen key={`${rv.id}:${rvStage}`} run={rv} stage={rvStage} onBack={() => setReview(null)} />
          : !wf.loaded ? <div className="wf-note"><Loading>Loading workflows…</Loading></div>
          : !wf.list.length ? (
            <Empty icon={<WorkflowIcon />} title="No workflows yet">
              A workflow is a study or report you run more than once, written down as a short line of stages: an agent does each job, and a person reviews and signs off where it matters. Add one and it appears here as a card you can run.
              <Pill size="sm" variant="primary" icon={<Plus />} disabled={!canAdd} onClick={() => setEditing('new')} className="wf-empty-add">Add workflow</Pill>
            </Empty>
          ) : (
            <>
              {wf.error ? <div className="warn" role="alert"><AlertTriangle />{wf.error}</div> : null}
              <div className="wf-list">{wf.list.map(w => <WorkflowCard key={w.id} w={w} onEdit={() => setEditing(w)} onReview={id => { live.current = sel.wfActive(runs[id]); setReview(id); }} />)}</div>
            </>
          )}
      </div>
      <WorkflowForm editing={editing} onClose={() => setEditing(null)} />
    </ViewFrame>
  );
}

/* ---------------- one card ---------------- */
function WorkflowCard({ w, onEdit, onReview }: { w: Workflow; onEdit: () => void; onReview: (runId: string) => void }) {
  const run = useLaunchpad(st => sel.wfRunOf(st, w.id));
  const refused = useLaunchpad(st => sel.wfRunError(st, w.id));
  const [test, setTest] = useState(false);
  const [unattended, setUnattended] = useState(w.unattended_default);
  const [asking, setAsking] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [stopping, setStopping] = useState(false);
  const active = sel.wfActive(run) || (!run && !!w.running_run_id);
  const blocked = !w.can_run;
  const reviewWaiting = !!run && run.status === 'awaiting_review';
  useEffect(() => { setUnattended(w.unattended_default); }, [w.unattended_default]);
  useEffect(() => { if (!active) setStopping(false); }, [active]);

  const start = () => { if (blocked || active) return; if (w.inputs.length) setAsking(true); else actions.runWorkflow(w.id, {}, test, unattended); };
  const why = blocked ? 'This workflow has a problem to fix first (see the warnings).' : active ? 'This workflow is already running.' : '';

  return (
    <article className={`wf-card${reviewWaiting ? ' wait' : ''}${blocked ? ' warned' : ''}`} data-wf={w.id} aria-label={`Workflow ${w.name}`}>
      <div className="wf-head">
        <div className="wf-name">
          <h2>{w.name}</h2>
          <DirChip label={w.folder_name} path={w.output_path || w.output_folder} />
          {reviewWaiting ? <span className="chip warnc wf-flag"><UserCheck />Review waiting for you</span> : null}
          {run && run.test && active ? <span className="chip warnc wf-flag"><FlaskConical />Test run</span> : null}
        </div>
        <div className="wf-ctl">
          {removing ? (
            <span className="wf-confirm" role="alertdialog" aria-label={`Remove ${w.name}`}>
              Remove <b>{w.name}</b>? Its file is deleted; the output folder is left alone.
              <Pill size="xs" variant="danger" onClick={() => { setRemoving(false); actions.removeWorkflow(w.id); }}>Confirm remove</Pill>
              <Pill size="xs" variant="ghost" onClick={() => setRemoving(false)}>Cancel</Pill>
            </span>
          ) : (
            <>
              <Pill size="xs" icon={<Pencil />} aria-label={`Edit ${w.name}`} onClick={onEdit}>Edit</Pill>
              <Pill size="xs" variant="ghost" icon={<Trash />} aria-label={`Remove ${w.name}`} disabled={active} title={active ? 'Stop the run first' : undefined} onClick={() => setRemoving(true)}>Remove</Pill>
            </>
          )}
        </div>
      </div>
      {w.description ? <p className="wf-desc">{w.description}</p> : null}
      <Track w={w} run={run} />
      {w.warnings.length ? (
        <ul className="wf-warns" role="alert" aria-label="Warnings">
          {w.warnings.map((m, i) => <li key={i} className={m.level === 'warning' ? 'soft' : ''}><AlertTriangle /><span><span className="wf-lvl">{m.level === 'error' ? 'Fix' : 'Note'}</span>{m.stage != null && w.stages[m.stage] ? `Stage ${m.stage + 1}: ` : ''}{m.message}</span></li>)}
        </ul>
      ) : null}
      {refused ? <div className="wf-failmsg" role="alert"><AlertTriangle />{refused}</div> : null}
      {run ? <RunStrip run={run} active={active} stopping={stopping} setStopping={setStopping} onReview={() => onReview(run.id)} /> : null}
      <div className="wf-foot">
        <Pill variant="primary" size="sm" icon={<Play />} id={`wfRun-${w.id}`} disabled={blocked || active} title={why || undefined} onClick={start}>Run</Pill>
        <label className="wf-tick"><input type="checkbox" checked={test} disabled={active} onChange={e => setTest(e.target.checked)} />Test run</label>
        <label className="wf-tick" title="Agents' questions are answered with their own recommendation and their permission requests are approved. Review stops always wait for a person."><input type="checkbox" checked={unattended} disabled={active} onChange={e => setUnattended(e.target.checked)} />Unattended</label>
        {test ? <span className="wf-hint">Saves into one <code>test</code> folder that is cleared first.</span> : null}
        {w.inputs.length ? <span className="wf-hint">Asks for {w.inputs.map(i => i.label || i.name).join(', ')}.</span> : null}
        {run?.finished_at && !active ? <span className="wf-hint">Last run ended {new Date(run.finished_at).toLocaleString()}.</span> : null}
      </div>
      <RunDialog w={w} open={asking} test={test} unattended={unattended} onClose={() => setAsking(false)} />
    </article>
  );
}

/* the run line: state, folder, Stop, Review */
function RunStrip({ run, active, stopping, setStopping, onReview }: { run: WorkflowRun; active: boolean; stopping: boolean; setStopping: (b: boolean) => void; onReview: () => void }) {
  const failed = run.stages.find(s => s.status === 'failed');
  return (
    <div className={`wf-run ${run.status}`} role="status" data-run={run.id}>
      <div className="wf-run-main">
        <span className={`status ${run.status === 'awaiting_review' ? 'waiting' : run.status}`}>{RUN_LABEL[run.status]}</span>
        {run.test ? <span className="chip warnc"><FlaskConical />Test run</span> : null}
        {run.unattended ? <span className="chip">Unattended</span> : null}
        <span className="wf-runfolder" title={run.folder}><FolderOpen /><code>{run.folder}</code></span>
      </div>
      {Object.keys(run.inputs || {}).length ? <div className="wf-inputs">{Object.entries(run.inputs).map(([k, v]) => <span key={k}><b>{k}:</b> {v}</span>)}</div> : null}
      {failed ? <div className="wf-failmsg"><AlertTriangle />{failed.title} failed{failed.error ? `: ${failed.error}` : '.'}</div> : null}
      {run.error ? <div className="wf-failmsg"><AlertTriangle />{run.error}</div> : null}
      <div className="wf-run-act">
        {run.status === 'awaiting_review' ? <Pill size="sm" variant="primary" icon={<UserCheck />} onClick={onReview}>Review now</Pill> : null}
        {run.status !== 'running' && run.status !== 'awaiting_review' && run.stages.some(s => s.kind === 'review' && s.review) ? <Pill size="xs" variant="ghost" icon={<UserCheck />} onClick={onReview}>See the review</Pill> : null}
        {active ? (stopping ? (
          <span className="wf-confirm">Stop this run?
            <Pill size="xs" variant="danger" icon={<Square />} onClick={() => { setStopping(false); actions.stopWorkflow(run.id); }}>Yes, stop</Pill>
            <Pill size="xs" variant="ghost" onClick={() => setStopping(false)}>Keep going</Pill>
          </span>
        ) : <Pill size="xs" icon={<Square />} onClick={() => setStopping(true)}>Stop</Pill>) : null}
      </div>
    </div>
  );
}

/* Run asks for the workflow's named inputs before starting (text, date, number, file path or a choice; required unless the file says not) */
function RunDialog({ w, open, test, unattended, onClose }: { w: Workflow; open: boolean; test: boolean; unattended: boolean; onClose: () => void }) {
  const [vals, setVals] = useState<Record<string, string>>({});
  useEffect(() => { if (open) setVals(Object.fromEntries(w.inputs.map(i => [i.name, i.default || (i.kind === 'choice' && i.required ? i.options[0] || '' : '')]))); }, [open]);   // eslint-disable-line react-hooks/exhaustive-deps
  const missing = w.inputs.filter(i => i.required && !(vals[i.name] || '').trim());
  const go = () => { if (missing.length) return; onClose(); actions.runWorkflow(w.id, Object.fromEntries(w.inputs.map(i => [i.name, (vals[i.name] || '').trim()])), test, unattended); };
  return (
    <Dialog open={open} onRequestClose={onClose} className="wf-rundlg" scrimId="wfRunScrim">
      <div className="modal-head">
        <div>
          <DialogTitle>Run {w.name}</DialogTitle>
          <div className="modal-meta">{test ? 'Test run: saves into the test folder, which is cleared first. ' : ''}{unattended ? 'Unattended: agents are not stopped by questions; reviews still wait for you.' : 'Agents may ask you questions while it runs.'}</div>
        </div>
        <DialogX onClick={onClose} />
      </div>
      <form className="modal-body wf-fbody" onSubmit={e => { e.preventDefault(); go(); }} id="wfRunForm" noValidate>
        <p className="mut">These go to every stage and are saved in the run record.</p>
        {w.inputs.map((i, k) => (
          <div className="wf-fld" key={i.name}><label htmlFor={`wfIn${k}`}>{i.label || i.name}{i.required ? '' : ' (optional)'}</label>
            {i.kind === 'choice' ? (
              <select id={`wfIn${k}`} className="field" value={vals[i.name] || ''} onChange={e => setVals({ ...vals, [i.name]: e.target.value })}>
                {!i.required ? <option value="">None</option> : null}{i.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input id={`wfIn${k}`} className="field" type={i.kind === 'date' ? 'date' : i.kind === 'number' ? 'number' : 'text'} step={i.kind === 'number' ? 'any' : undefined} value={vals[i.name] || ''} autoComplete="off"
                placeholder={i.kind === 'file' ? 'Path to the file' : undefined} onChange={e => setVals({ ...vals, [i.name]: e.target.value })} />
            )}
            {i.help ? <small className="mut">{i.help}</small> : null}</div>
        ))}
      </form>
      <div className="modal-foot">
        {missing.length ? <span className="wf-hint">Fill in {missing.map(m => m.label || m.name).join(', ')} to start.</span> : null}
        <Pill variant="ghost" onClick={onClose}>Cancel</Pill>
        <Pill variant="primary" icon={<Play />} type="submit" form="wfRunForm" disabled={!!missing.length}>{test ? 'Start test run' : 'Start run'}</Pill>
      </div>
    </Dialog>
  );
}
