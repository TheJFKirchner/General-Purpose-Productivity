/* "Add an agent": a dialog with a "Draft for me" box (a sentence or two -> agent_draft -> the form filled for
   editing) and the form itself (name, description, purpose, model, tools as tick boxes from crew_list.tool_choices,
   instructions). The page's own checks show inline once Save was tried; the server's problems (agent_saved) show
   under the field they are about, anything else in the banner on top. Everything typed lives in the store
   (crewForm), so closing the dialog keeps it until the agent is saved or "Start over" is pressed. */
import { useRef, useState, type FormEvent, type ReactNode } from 'react';
import { actions, sel, useComputed, useLaunchpad, type FormField } from '../../store';
import type { Purpose } from '../../contract';
import { Dialog, DialogTitle, DialogX, Loading, PURPOSE_ICON, Pill } from '../../components';
import { Check, WandSparkles } from '../../components/icons';
import { tokShort, tparts, usd } from '../../lib/format';
import { ADDABLE_PURPOSES, AGENT_MODELS, PURPOSE_HINT, PURPOSE_LABEL, WRITE_TOOLS } from '../../lib/labels';

const DEFAULT_TOOLS = ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash', 'WebFetch', 'WebSearch'];

export default function AgentForm() {
  const f = useLaunchpad(st => st.crewForm);
  const v = useComputed(st => ({
    choices: st.toolChoices.length ? st.toolChoices : DEFAULT_TOOLS,
    dir: sel.dirLabelOf(st, sel.crewDir(st)) || 'the project folder',
    client: sel.agentFormProblems(st, st.crewForm.fields),
  }));
  const [tried, setTried] = useState(false);
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const fields = f.fields;

  /* problems per field: the page's checks (after a Save attempt) first, then the server's */
  const byField: Partial<Record<FormField, string[]>> = {};
  const other: string[] = [];
  if (tried) for (const p of v.client) (byField[p.field] ||= []).push(p.message);
  for (const p of f.problems) { const k = sel.problemField(p); if (k) (byField[k] ||= []).push(p.replace(/^\s*[\w ]+:\s*/, '')); else other.push(p); }

  const close = () => { setTried(false); actions.crewCloseForm(); };
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    setTried(true);
    if (!actions.crewCreate()) {
      /* focus the first field with a problem */
      requestAnimationFrame(() => formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
    }
  };
  const draft = (e?: FormEvent) => { e?.preventDefault(); actions.crewDraft(); };
  const set = (patch: Parameters<typeof actions.crewSetFields>[0]) => actions.crewSetFields(patch);
  const toggleTool = (t: string, on: boolean) => set({ tools: on ? [...fields.tools.filter(x => x !== t), t] : fields.tools.filter(x => x !== t) });
  const readOnly = fields.purpose === 'exploring' || fields.purpose === 'reviewing';
  const choices = [...v.choices, ...fields.tools.filter(t => !v.choices.includes(t))];
  const fileName = fields.name.trim() && /^[a-z0-9][a-z0-9-]*$/.test(fields.name.trim()) ? fields.name.trim() : '<name>';

  const err = (k: FormField) => (byField[k] && byField[k]!.length ? `af-err-${k}` : undefined);
  const problems = (k: FormField): ReactNode => byField[k] && byField[k]!.length
    ? <p className="af-err" id={`af-err-${k}`}>{byField[k]!.join(' ')}</p> : null;

  return (
    <Dialog open={f.open} onRequestClose={close} className="wide agent-form" scrimId="agentScrim"
      initialFocus={() => draftRef.current?.focus()}>
      <div className="modal-head">
        <div>
          <DialogTitle asChild><h2>{f.role ? 'Define an agent' : 'Add an agent'}</h2></DialogTitle>
          {f.role ? <div className="modal-meta af-role">For the role <code>{f.role}</code>. Saving removes it from "Used but not defined" and keeps the review's case beside the agent.</div> : null}
          <div className="modal-meta">Saved as <code>.claude/agents/{fileName}.md</code> in {v.dir}. The planner can then name it for a step in new plans; the Orchestrator starts it.</div>
        </div>
        <DialogX onClick={close} />
      </div>
      <div className="modal-body af-body">
        <form className="af-draft" onSubmit={draft} aria-labelledby="afDraftH">
          <div className="af-draft-h">
            <span className="af-draft-ic" aria-hidden="true"><WandSparkles /></span>
            <div><h3 id="afDraftH">{f.role ? 'Drafted from the review' : 'Draft for me'}</h3><p>{f.role ? 'A quick, cheap model wrote a first version from the case the reviewer wrote. Edit every field you like before saving. Add a note below and draft again if you want a different take.' : 'Say in a sentence or two what the agent should do. A quick, cheap model fills the form below; you check and edit it before saving.'}</p></div>
          </div>
          <label className="sr" htmlFor="afDraftText">What should the agent do?</label>
          <textarea id="afDraftText" ref={draftRef} className="field" rows={2} value={f.draftText} disabled={f.drafting}
            placeholder={f.role ? 'Optional: anything the drafter should know' : 'For example: checks new SQL for NULL handling and join fan-out before a step is marked done'}
            onChange={e => actions.crewSetDraftText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) draft(); }} />
          <div className="af-draft-row">
            <Pill type="submit" size="sm" icon={f.drafting ? undefined : <WandSparkles />} disabled={f.drafting || (!f.draftText.trim() && !f.role)} id="afDraft">
              {f.drafting ? 'Drafting…' : f.role ? 'Draft again' : 'Draft for me'}
            </Pill>
            <span className="af-draft-status" role="status">
              {f.drafting ? <Loading>Writing a first version…</Loading>
                : f.drafted ? <span className="af-ok"><Check />Drafted. Check every field below, then save.</span> : null}
              {f.cost && !f.drafting ? <span className="af-cost" id="afDraftCost" title="Counted in the app-wide total, not in any session">Drafting cost <b>{usd(f.cost.cost)}</b> · {tokShort(tparts(f.cost))}</span> : null}
            </span>
          </div>
          {f.draftError ? <div className="warn" role="alert">{f.draftError}</div> : null}
        </form>

        <form className="af-form" id="agentForm" ref={formRef} onSubmit={submit} noValidate>
          {f.error ? (
            <div className="warn" role="alert"><b>{f.error}</b>{other.length ? <ul>{other.map((p, i) => <li key={i}>{p}</li>)}</ul> : null}</div>
          ) : null}
          <div className="af-row2">
            <Field label="Name" htmlFor="afName" hint="Lowercase letters, digits and dashes; it is also the file name." problems={problems('name')}>
              <input id="afName" className="field" value={fields.name} autoComplete="off" spellCheck={false} placeholder="sql-reviewer"
                aria-invalid={!!err('name')} aria-describedby={err('name')} onChange={e => set({ name: e.target.value })} />
            </Field>
            <Field label="Model" htmlFor="afModel" hint="Haiku is cheapest; Opus is strongest." problems={problems('model')}>
              <select id="afModel" className="field" value={fields.model} aria-invalid={!!err('model')} aria-describedby={err('model')} onChange={e => set({ model: e.target.value })}>
                {AGENT_MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                {!AGENT_MODELS.some(m => m.value === fields.model) && fields.model ? <option value={fields.model}>{fields.model}</option> : null}
              </select>
            </Field>
          </div>
          <Field label="Description" htmlFor="afDesc" hint="One or two sentences. The planner reads this to decide when to give it a step." problems={problems('description')}>
            <textarea id="afDesc" className="field" rows={2} value={fields.description} placeholder="Reviews new SQL for NULL handling, join fan-out and row-count drift."
              aria-invalid={!!err('description')} aria-describedby={err('description')} onChange={e => set({ description: e.target.value })} />
          </Field>
          <fieldset className="af-field af-purpose" aria-describedby={err('purpose')}>
            <legend>Purpose</legend>
            <div className="af-purposes">
              {ADDABLE_PURPOSES.map(p => (
                <label key={p} className={`af-pcard${fields.purpose === p ? ' on' : ''}`} data-purpose={p}>
                  <input type="radio" name="afPurpose" value={p} checked={fields.purpose === p} onChange={() => set({ purpose: p as Purpose })} aria-invalid={!!err('purpose')} />
                  <span className="hero-ic" aria-hidden="true">{PURPOSE_ICON[p]}</span>
                  <span className="af-pt"><b>{PURPOSE_LABEL[p]}</b><small>{PURPOSE_HINT[p]}</small></span>
                </label>
              ))}
            </div>
            <p className="af-hint">Planning agents cannot be added yet.</p>
            {problems('purpose')}
          </fieldset>
          <fieldset className="af-field af-tools" aria-describedby={err('tools')}>
            <legend>Tools</legend>
            <div className="af-toolgrid">
              {choices.map(t => {
                const blocked = readOnly && WRITE_TOOLS.includes(t);
                return (
                  <label key={t} className={`af-tool${blocked ? ' blocked' : ''}`} title={blocked ? 'Not for a read-only agent' : undefined}>
                    <input type="checkbox" checked={!blocked && fields.tools.includes(t)} disabled={blocked} onChange={e => toggleTool(t, e.target.checked)} />
                    <code>{t}</code>
                  </label>
                );
              })}
            </div>
            <p className="af-hint">
              {readOnly ? `${PURPOSE_LABEL[fields.purpose]} agents are read-only, so write, edit and shell tools are not offered.` : fields.purpose === 'building' ? 'Building agents get the Builder\'s permission cards, guards and shell deny list.' : ''}
              {' '}Tick none to give it the usual set for its purpose.
            </p>
            {problems('tools')}
          </fieldset>
          <Field label="Instructions" htmlFor="afInstr" hint="How it should work, in plain words or markdown. This becomes its prompt." problems={problems('instructions')}>
            <textarea id="afInstr" className="field mono" rows={9} value={fields.instructions} spellCheck={false}
              placeholder={'# SQL reviewer\n\nRead the step\'s SQL and its brief. Check NULL handling, joins that multiply rows, and row counts before and after each join.\nReport what you found; never change files.'}
              aria-invalid={!!err('instructions')} aria-describedby={err('instructions')} onChange={e => set({ instructions: e.target.value })} />
          </Field>
        </form>
      </div>
      <div className="modal-foot">
        <button type="button" className="pill ghost af-reset" onClick={() => { setTried(false); actions.crewResetForm(); }} disabled={f.saving}>Start over</button>
        <button type="button" className="pill ghost" onClick={close}>Cancel</button>
        <button type="submit" form="agentForm" className="pill primary" id="afSave" disabled={f.saving}>{f.saving ? 'Saving…' : 'Save agent'}</button>
      </div>
    </Dialog>
  );
}

function Field({ label, htmlFor, hint, problems, children }: { label: string; htmlFor: string; hint: string; problems: ReactNode; children: ReactNode }) {
  return (
    <div className="af-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      <p className="af-hint">{hint}</p>
      {problems}
    </div>
  );
}
