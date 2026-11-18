/* Add / Edit workflow: a dialog that writes the workflow's JSON for the user (workflow_save). Name, description, which
   connected folder to save into (workflows_list folders), the output folder, named inputs, workflow-level attached
   markdown files, and stages added one at a time and reorderable: an agent stage (an agent the server lists for that
   folder, its instruction, attached files) or a review stage (checklist items, each a tick or a written answer).
   The server answers with workflows_list (error = a refusal, shown here). */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { actions, useLaunchpad } from '../../store';
import type { Workflow, WorkflowDraft, WorkflowInputKind } from '../../contract';
import { Dialog, DialogTitle, DialogX, Pill } from '../../components';
import { ArrowDown, ArrowUp, Bot, FolderOpen, Plus, Trash, UserCheck, X } from '../../components/icons';

interface FInput { name: string; label: string; kind: WorkflowInputKind; required: boolean; default: string; options: string }
interface FItem { text: string; kind: 'tick' | 'answer' }
interface FStage { kind: 'agent' | 'review'; title: string; agent: string; instruction: string; files: string; checklist: FItem[] }
export interface FForm {
  name: string; description: string; folder: string; output_folder: string; inputs: FInput[]; files: string; unattended: boolean; stages: FStage[];
}
const INPUT_KINDS: { value: WorkflowInputKind; label: string }[] = [
  { value: 'text', label: 'Text' }, { value: 'date', label: 'Date' }, { value: 'number', label: 'Number' }, { value: 'file', label: 'File path' }, { value: 'choice', label: 'Choice' },
];
const lines = (t: string) => t.split('\n').map(x => x.trim()).filter(Boolean);
const fstage = (kind: 'agent' | 'review', o: Partial<FStage> = {}): FStage => ({ kind, title: '', agent: '', instruction: '', files: '', checklist: [], ...o });
const blank = (folder: string): FForm => ({ name: '', description: '', folder, output_folder: '', inputs: [], files: '', unattended: false, stages: [] });
export const fromWorkflow = (w: Workflow): FForm => ({
  name: w.name, description: w.description, folder: w.folder, output_folder: w.output_folder, files: w.files.map(f => f.path).join('\n'), unattended: w.unattended_default,
  inputs: w.inputs.map(i => ({ name: i.name, label: i.label === i.name ? '' : i.label, kind: i.kind, required: i.required, default: i.default, options: i.options.join(', ') })),
  stages: w.stages.map(s => (s.kind === 'agent'
    ? fstage('agent', { title: s.title, agent: s.agent, instruction: s.instruction, files: s.files.map(f => f.path).join('\n') })
    : fstage('review', { title: s.title, checklist: s.checklist.map(c => ({ ...c })) }))),
});
/** The JSON the server stores (the file's content). */
export function toDraft(f: FForm): WorkflowDraft {
  return {
    name: f.name.trim(), description: f.description.trim(), output_folder: f.output_folder.trim(), unattended_default: f.unattended, files: lines(f.files),
    inputs: f.inputs.filter(i => i.name.trim()).map(i => ({
      name: i.name.trim(), ...(i.label.trim() ? { label: i.label.trim() } : {}), kind: i.kind, required: i.required, ...(i.default.trim() ? { default: i.default.trim() } : {}),
      ...(i.kind === 'choice' ? { options: i.options.split(',').map(o => o.trim()).filter(Boolean) } : {}),
    })),
    stages: f.stages.map(s => (s.kind === 'agent'
      ? { kind: 'agent' as const, title: s.title.trim(), agent: s.agent, instruction: s.instruction.trim(), files: lines(s.files) }
      : { kind: 'review' as const, title: s.title.trim(), checklist: s.checklist.filter(c => c.text.trim()).map(c => ({ text: c.text.trim(), kind: c.kind })) })),
  };
}
export function formProblems(f: FForm): string[] {
  const p: string[] = [];
  if (!f.name.trim()) p.push('Give the workflow a name.');
  if (!f.folder) p.push('Choose which connected folder to save it into.');
  if (!f.output_folder.trim()) p.push('Enter the output folder, where each run saves its files.');
  const seen = new Set<string>();
  f.inputs.forEach((i, k) => {
    const n = i.name.trim(); if (!n) return;
    if (!/^[a-z][a-z0-9_]*$/.test(n)) p.push(`Input ${k + 1}: the name must be lower case letters, digits and underscores, starting with a letter (for example valuation_date).`);
    if (seen.has(n)) p.push(`Input ${k + 1}: ${n} is used twice.`);
    seen.add(n);
    if (i.kind === 'choice' && !i.options.split(',').some(o => o.trim())) p.push(`Input ${k + 1}: a choice needs its options, separated by commas.`);
  });
  if (!f.stages.length) p.push('Add at least one stage.');
  f.stages.forEach((s, i) => {
    const n = `Stage ${i + 1}`;
    if (!s.title.trim()) p.push(`${n} needs a title.`);
    if (s.kind === 'agent' && !s.agent) p.push(`${n} needs an agent.`);
    if (s.kind === 'agent' && !s.instruction.trim()) p.push(`${n} needs an instruction.`);
  });
  return p;
}

export default function WorkflowForm({ editing, onClose }: { editing: Workflow | 'new' | null; onClose: () => void }) {
  const folders = useLaunchpad(st => st.wf.folders);
  const agents = useLaunchpad(st => st.wf.agents);
  const err = useLaunchpad(st => st.wf.error);
  const list = useLaunchpad(st => st.wf.list);
  const picked = useLaunchpad(st => st.ui.pickedOutput);
  const canPick = useLaunchpad(st => !!(st.settings && st.settings.can_pick));
  const picking = useLaunchpad(st => st.ui.picking && st.ui.pickFor === 'output');
  const [f, setF] = useState<FForm>(() => blank(''));
  const [tried, setTried] = useState(false);
  const [saving, setSaving] = useState(false);
  const bodyRef = useRef<HTMLFormElement>(null);

  /* fill the form whenever it opens */
  useEffect(() => {
    if (!editing) return;
    setTried(false); setSaving(false);
    setF(editing === 'new' ? blank((folders.find(x => x.is_primary) || folders[0])?.dir_id || '') : fromWorkflow(editing));
  }, [editing]);   // eslint-disable-line react-hooks/exhaustive-deps
  /* the list answers a save: close (an error keeps the form open) */
  useEffect(() => { if (saving) { setSaving(false); if (!err) onClose(); } }, [list]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (saving && err) setSaving(false); }, [err, saving]);

  /* a folder picked with Browse only fills the output field (it is never connected as a working directory) */
  useEffect(() => { if (picked && editing) { setF(x => ({ ...x, output_folder: picked })); actions.clearPickedOutput(); } }, [picked]);   // eslint-disable-line react-hooks/exhaustive-deps
  const problems = formProblems(f);
  const set = (patch: Partial<FForm>) => setF({ ...f, ...patch });
  const setStage = (i: number, patch: Partial<FStage>) => set({ stages: f.stages.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  const move = (i: number, d: number) => { const j = i + d; if (j < 0 || j >= f.stages.length) return; const a = [...f.stages];[a[i], a[j]] = [a[j], a[i]]; set({ stages: a }); };
  const setInput = (i: number, patch: Partial<FInput>) => set({ inputs: f.inputs.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const setItem = (i: number, k: number, patch: Partial<FItem>) => setStage(i, { checklist: f.stages[i].checklist.map((c, j) => (j === k ? { ...c, ...patch } : c)) });

  const submit = (e?: FormEvent) => {
    e?.preventDefault(); setTried(true);
    if (problems.length) { requestAnimationFrame(() => bodyRef.current?.querySelector<HTMLElement>('.wf-problems')?.focus()); return; }
    setSaving(true);
    actions.saveWorkflow(f.folder, toDraft(f), editing && editing !== 'new' ? editing.id : undefined);
  };
  const isNew = editing === 'new';
  /* the agents a stage may name in the chosen folder; one that is not listed any more stays selectable, so editing does not silently change it */
  const choices = agents[f.folder] || [];
  const agentOptions = (cur: string) => (cur && !choices.some(a => a.name === cur) ? [{ name: cur, display_name: cur }, ...choices] : choices);

  return (
    <Dialog open={!!editing} onRequestClose={onClose} className="wide wf-form" scrimId="wfScrim">
      <div className="modal-head">
        <div>
          <DialogTitle>{isNew ? 'Add a workflow' : `Edit ${f.name || 'workflow'}`}</DialogTitle>
          <div className="modal-meta">Saved as a JSON file in the <code>workflows</code> folder of the connected folder you choose. You can also edit that file directly.</div>
        </div>
        <DialogX onClick={onClose} />
      </div>
      <form className="modal-body wf-fbody" ref={bodyRef} onSubmit={submit} noValidate id="wfForm">
        {tried && problems.length ? <div className="warn wf-problems" role="alert" tabIndex={-1}><b>Not saved yet.</b><ul>{problems.map((p, i) => <li key={i}>{p}</li>)}</ul></div> : null}
        {err ? <div className="warn" role="alert">{err}</div> : null}
        <div className="wf-row2">
          <div className="wf-fld"><label htmlFor="wfName">Name</label><input id="wfName" className="field" value={f.name} autoComplete="off" onChange={e => set({ name: e.target.value })} placeholder="Quarterly reserve study" /></div>
          <div className="wf-fld"><label htmlFor="wfFolder">Save into</label>
            <select id="wfFolder" className="field" value={f.folder} onChange={e => set({ folder: e.target.value })}>
              {!f.folder ? <option value="">Choose a connected folder</option> : null}
              {folders.map(d => <option key={d.dir_id} value={d.dir_id}>{d.name || d.path}</option>)}
            </select></div>
        </div>
        <div className="wf-fld"><label htmlFor="wfDesc">Description</label><textarea id="wfDesc" className="field" rows={2} value={f.description} onChange={e => set({ description: e.target.value })} placeholder="What this workflow is for, in a sentence or two." /></div>
        <div className="wf-fld"><label htmlFor="wfOut">Output folder</label><div className="wf-pickrow"><input id="wfOut" className="field" value={f.output_folder} autoComplete="off" onChange={e => set({ output_folder: e.target.value })} placeholder="C:/shared/studies/reserves" />
            {canPick ? <Pill size="sm" id="wfBrowse" icon={<FolderOpen />} disabled={picking} onClick={() => actions.pickOutputFolder()}>{picking ? 'Choosing…' : 'Browse…'}</Pill> : null}</div>
          <small className="mut">Where each run saves its result files, review records and summary, in a dated folder. It can be anywhere, such as a shared drive. A test run reuses one folder called test.</small></div>

        <fieldset className="wf-fld wf-inputs"><legend>Inputs asked at Run (optional)</legend>
          {f.inputs.map((i, k) => (
            <div className="wf-inrow" key={k}>
              <div className="wf-pair">
                <input className="field" aria-label={`Input ${k + 1} name`} placeholder="Name, e.g. valuation_date" value={i.name} spellCheck={false} onChange={e => setInput(k, { name: e.target.value })} />
                <input className="field" aria-label={`Input ${k + 1} label`} placeholder="Label shown at Run (optional)" value={i.label} onChange={e => setInput(k, { label: e.target.value })} />
                <button type="button" className="pill xs ghost icon" aria-label={`Remove input ${k + 1}`} onClick={() => set({ inputs: f.inputs.filter((_, j) => j !== k) })}><X /></button>
              </div>
              <div className="wf-opts">
                <select className="field" aria-label={`Input ${k + 1} type`} value={i.kind} onChange={e => setInput(k, { kind: e.target.value as WorkflowInputKind })}>{INPUT_KINDS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
                <input className="field" aria-label={`Input ${k + 1} suggested value`} placeholder="Suggested value" value={i.default} onChange={e => setInput(k, { default: e.target.value })} />
                {i.kind === 'choice' ? <input className="field" aria-label={`Input ${k + 1} options`} placeholder="Options, separated by commas" value={i.options} onChange={e => setInput(k, { options: e.target.value })} /> : null}
                <label className="wf-tick"><input type="checkbox" checked={i.required} onChange={e => setInput(k, { required: e.target.checked })} />Required</label>
              </div>
            </div>
          ))}
          <div><Pill size="xs" icon={<Plus />} id="wfAddInput" onClick={() => set({ inputs: [...f.inputs, { name: '', label: '', kind: 'text', required: true, default: '', options: '' }] })}>Add input</Pill></div>
        </fieldset>

        <div className="wf-fld"><label htmlFor="wfFiles">Attached markdown files for every agent stage (one path per line)</label>
          <textarea id="wfFiles" className="field mono" rows={2} value={f.files} onChange={e => set({ files: e.target.value })} placeholder="methodology/house-style.md" />
          <small className="mut">Links, read at the start of each run, relative to the folder above or absolute. A file that is missing stops the run.</small></div>
        <label className="wf-tick"><input type="checkbox" checked={f.unattended} onChange={e => set({ unattended: e.target.checked })} />Unattended by default (agents' questions are answered with their own recommendation and permission requests approved; reviews always stop)</label>

        <div className="wf-stages-h"><h3>Stages</h3><span className="mut">Run in this order.</span></div>
        {!f.stages.length ? <p className="mut wf-nostage">No stages yet. Add an agent stage for each job, and a review stage wherever a person must sign off.</p> : null}
        <ol className="wf-fstages">
          {f.stages.map((s, i) => (
            <li key={i} className="wf-fstage" data-kind={s.kind}>
              <div className="wf-fstage-h">
                <span className="wf-kind">{s.kind === 'review' ? <><UserCheck />Review</> : <><Bot />Agent</>}</span>
                <b>Stage {i + 1}</b>
                <span className="wf-fstage-tools">
                  <button type="button" className="pill xs ghost icon" aria-label={`Move stage ${i + 1} up`} disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp /></button>
                  <button type="button" className="pill xs ghost icon" aria-label={`Move stage ${i + 1} down`} disabled={i === f.stages.length - 1} onClick={() => move(i, 1)}><ArrowDown /></button>
                  <button type="button" className="pill xs ghost icon" aria-label={`Remove stage ${i + 1}`} onClick={() => set({ stages: f.stages.filter((_, j) => j !== i) })}><Trash /></button>
                </span>
              </div>
              <div className="wf-fld"><label htmlFor={`wfT${i}`}>Title</label><input id={`wfT${i}`} className="field" value={s.title} onChange={e => setStage(i, { title: e.target.value })} placeholder={s.kind === 'review' ? 'Methodology review' : 'Load the data'} /></div>
              {s.kind === 'agent' ? (
                <>
                  <div className="wf-fld"><label htmlFor={`wfA${i}`}>Agent (from Crew)</label>
                    <select id={`wfA${i}`} className="field" value={s.agent} onChange={e => setStage(i, { agent: e.target.value })}>
                      <option value="">{choices.length ? 'Choose an agent' : 'Choose a folder first'}</option>
                      {agentOptions(s.agent).map(a => <option key={a.name} value={a.name}>{a.display_name || a.name}</option>)}
                    </select></div>
                  <div className="wf-fld"><label htmlFor={`wfI${i}`}>Instruction</label><textarea id={`wfI${i}`} className="field" rows={3} value={s.instruction} onChange={e => setStage(i, { instruction: e.target.value })} placeholder="What this agent does in this stage. It writes one result file." /></div>
                  <div className="wf-fld"><label htmlFor={`wfF${i}`}>Attached markdown files for this stage (one path per line)</label><textarea id={`wfF${i}`} className="field mono" rows={2} value={s.files} onChange={e => setStage(i, { files: e.target.value })} /></div>
                </>
              ) : (
                <div className="wf-fld"><span className="wf-lab">Checklist</span>
                  {s.checklist.map((c, k) => (
                    <div className="wf-citem" key={k}>
                      <input className="field" aria-label={`Stage ${i + 1} checklist item ${k + 1}`} value={c.text} onChange={e => setItem(i, k, { text: e.target.value })} placeholder="Totals agree with the control sheet" />
                      <select className="field" aria-label={`Stage ${i + 1} item ${k + 1} type`} value={c.kind} onChange={e => setItem(i, k, { kind: e.target.value as 'tick' | 'answer' })}>
                        <option value="tick">Tick</option><option value="answer">Written answer</option>
                      </select>
                      <button type="button" className="pill xs ghost icon" aria-label={`Remove stage ${i + 1} checklist item ${k + 1}`} onClick={() => setStage(i, { checklist: s.checklist.filter((_, j) => j !== k) })}><X /></button>
                    </div>
                  ))}
                  <div><Pill size="xs" icon={<Plus />} onClick={() => setStage(i, { checklist: [...s.checklist, { text: '', kind: 'tick' }] })}>Add checklist item</Pill></div>
                  <small className="mut">The reviewer must tick each tick item and answer each written one before signing off. No items = a plain stop and sign-off.</small></div>
              )}
            </li>
          ))}
        </ol>
        <div className="wf-addrow">
          <Pill size="sm" icon={<Bot />} id="wfAddAgent" onClick={() => set({ stages: [...f.stages, fstage('agent')] })}>Add agent stage</Pill>
          <Pill size="sm" icon={<UserCheck />} id="wfAddReview" onClick={() => set({ stages: [...f.stages, fstage('review')] })}>Add review stage</Pill>
        </div>
      </form>
      <div className="modal-foot">
        <Pill variant="ghost" onClick={onClose}>Cancel</Pill>
        <Pill variant="primary" type="submit" form="wfForm" id="wfSave" disabled={saving}>{saving ? 'Saving…' : isNew ? 'Add workflow' : 'Save changes'}</Pill>
      </div>
    </Dialog>
  );
}
