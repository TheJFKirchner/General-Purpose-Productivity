/* The review screen of a workflow run: the results so far (each earlier stage's result file, readable in place), the
   author's checklist (a tick item must be ticked, an answer item answered, before sign-off), a name (the server remembers
   it: workflows_list reviewer_name) and an optional note, Approve, and Send back (asks for an earlier agent stage to
   return to and a note; the checklist may be incomplete then). An empty checklist is a plain stop and sign-off. Nothing is decided here: the page sends workflow_review and the run's next state arrives. */
import { useEffect, useId, useState } from 'react';
import { actions, sel, useLaunchpad } from '../../store';
import type { ReviewAnswerOut, WorkflowRun } from '../../contract';
import { Markdown, Pill } from '../../components';
import { ArrowLeft, Check, FileText, FlaskConical, ListChecks, Undo2, UserCheck } from '../../components/icons';

interface Item { ticked: boolean; text: string }

export function ReviewScreen({ run, stage, onBack }: { run: WorkflowRun; stage: number; onBack: () => void }) {
  const st = run.stages[stage];
  const w = useLaunchpad(s => s.wf.list.find(x => x.id === run.workflow_id) || null);
  const checklist = st?.checklist || [];
  const earlier = run.stages.slice(0, stage).map((s, k) => ({ s, k })).filter(({ s }) => s.kind === 'agent');
  const refused = useLaunchpad(s => sel.wfRunError(s, run.workflow_id));
  const reviewer = useLaunchpad(s => s.wf.reviewerName);
  const [items, setItems] = useState<Item[]>(() => checklist.map(() => ({ ticked: false, text: '' })));
  const [name, setName] = useState<string>(reviewer);
  const [note, setNote] = useState('');
  const [backing, setBacking] = useState(false);
  const [backTo, setBackTo] = useState<number>(earlier[0]?.k ?? 0);
  const [backNote, setBackNote] = useState('');
  const [sent, setSent] = useState(false);
  const id = useId();
  /* the run's state changed (carried on, or refused and unchanged): nothing is pending any more */
  useEffect(() => { setSent(false); }, [run]);

  if (!st) return <div className="wf-review"><button type="button" className="pill sm" onClick={onBack}><ArrowLeft />All workflows</button><p className="mut">This run has no such stage.</p></div>;
  const waiting = st.status === 'awaiting_review' && !sent;
  const open = checklist.filter((c, k) => (c.kind === 'answer' ? !items[k]?.text.trim() : !items[k]?.ticked)).length;
  const answers: ReviewAnswerOut[] = checklist.map((c, k) => (c.kind === 'answer' ? { answer: (items[k]?.text || '').trim() } : { ticked: items[k]?.ticked || false }));
  const results = earlier.filter(({ s }) => s.result_file || s.result_markdown);
  const why = !name.trim() ? 'Type your name to sign off.' : open ? `${open} checklist item${open === 1 ? ' is' : 's are'} still open: tick it or write the answer.` : '';
  const backWhy = !name.trim() ? 'Type your name first.' : !backNote.trim() ? 'Write a note for the stage you send it back to.' : '';
  const setItem = (k: number, patch: Partial<Item>) => setItems(items.map((x, j) => (j === k ? { ...x, ...patch } : x)));

  const approve = () => { if (why) return; setSent(true); actions.reviewWorkflow({ runId: run.id, stage, answers, name, note, decision: 'approve' }); };
  const sendBack = () => { if (backWhy || !earlier.length) return; setSent(true); actions.reviewWorkflow({ runId: run.id, stage, answers, name, note: backNote, decision: 'send_back', backTo }); };

  return (
    <div className="wf-review" aria-label={`Review: ${st.title}`}>
      <div className="wf-rhead">
        <button type="button" className="pill sm" onClick={onBack}><ArrowLeft />All workflows</button>
        <h2><UserCheck />{st.title}</h2>
        <span className="wf-sub2">{w?.name || run.workflow_id}</span>
        {run.test ? <span className="chip warnc" title="A test run: its records are labelled as a test"><FlaskConical />Test run</span> : null}
      </div>
      {refused ? <div className="warn" role="alert">{refused}</div> : null}
      {!waiting ? (
        <div className="wf-note" role="status">{sent ? 'Sent. Waiting for the run to carry on…' : 'This review is no longer waiting for you.'}{st.review ? ` Signed by ${st.review.name} (${st.review.decision === 'approve' ? 'approved' : 'sent back'}${st.review.note ? ': ' + st.review.note : ''}).` : ''}</div>
      ) : null}

      <section className="wf-rsec" aria-labelledby={`${id}-res`}>
        <h3 id={`${id}-res`}><FileText />Results so far</h3>
        {results.length ? results.map(({ s, k }, n) => (
          <details key={k} className="wf-result" open={n === results.length - 1}>
            <summary><b>{s.title}</b>{s.attempts.length > 1 ? <span className="chip">Attempt {s.attempts.length}</span> : null}<code>{s.result_file || ''}</code></summary>
            {s.result_markdown ? <Markdown text={s.result_markdown} className="wf-md" label={`Result of ${s.title}`} /> : <p className="mut">The text of this file did not come with the run. Open it from the run folder.</p>}
            {s.attempts.some(a => a.rejected) ? (
              <ul className="wf-attempts" aria-label="Rejected attempts, kept">
                {s.attempts.filter(a => a.rejected).map(a => <li key={a.attempt}>Attempt {a.attempt} was sent back and is kept: <code>{a.result_file || ''}</code>{a.note ? ` (${a.note})` : ''}</li>)}
              </ul>
            ) : null}
          </details>
        )) : <p className="mut">No stage has written a result file yet.</p>}
        <p className="mut wf-folder">Run folder: <code>{run.folder}</code></p>
      </section>

      <section className="wf-rsec" aria-labelledby={`${id}-chk`}>
        <h3 id={`${id}-chk`}><ListChecks />Checklist</h3>
        {checklist.length ? (
          <>
            <p className="mut">Tick each tick item and write an answer for each answer item. Sign-off stays off until every item is done.</p>
            <ul className="wf-checks">
              {checklist.map((c, k) => {
                const done = c.kind === 'answer' ? !!items[k]?.text.trim() : !!items[k]?.ticked;
                return (
                  <li key={k} className={done ? 'done' : ''} data-kind={c.kind}>
                    {c.kind === 'answer' ? (
                      <>
                        <label className="wf-check" htmlFor={`${id}-a${k}`}><span>{c.text} <small className="mut">(write an answer)</small></span></label>
                        <input id={`${id}-a${k}`} className="field" aria-label={`Answer for: ${c.text}`} placeholder="Your answer" value={items[k]?.text || ''} disabled={!waiting} onChange={e => setItem(k, { text: e.target.value })} />
                      </>
                    ) : (
                      <label className="wf-check wf-check-wide"><input type="checkbox" checked={items[k]?.ticked || false} disabled={!waiting} onChange={e => setItem(k, { ticked: e.target.checked })} /><span>{c.text}</span></label>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        ) : <p className="mut">This review has no checklist: it is a plain stop and sign-off.</p>}
      </section>

      <section className="wf-rsec wf-sign" aria-labelledby={`${id}-sign`}>
        <h3 id={`${id}-sign`}><Check />Sign-off</h3>
        <div className="wf-fld"><label htmlFor={`${id}-name`}>Your name</label>
          <input id={`${id}-name`} className="field" value={name} autoComplete="name" disabled={!waiting} onChange={e => setName(e.target.value)} placeholder="Typed once, remembered next time" /></div>
        <div className="wf-fld"><label htmlFor={`${id}-note`}>Note (optional)</label>
          <textarea id={`${id}-note`} className="field" rows={2} value={note} disabled={!waiting} onChange={e => setNote(e.target.value)} /></div>
        {waiting && why ? <p className="wf-why" role="status">{why}</p> : null}
        <div className="wf-actions">
          <Pill variant="primary" icon={<Check />} disabled={!waiting || !!why} id="wfApprove" onClick={approve}>Approve</Pill>
          <Pill icon={<Undo2 />} disabled={!waiting} aria-expanded={backing} id="wfSendBack" onClick={() => setBacking(!backing)}>Send back</Pill>
        </div>
        {backing && waiting ? (
          <div className="wf-back" role="group" aria-label="Send back">
            <div className="wf-fld"><label htmlFor={`${id}-to`}>Return to stage</label>
              {!earlier.length ? <p className="mut">There is no earlier agent stage to send this back to.</p> : null}
              <select id={`${id}-to`} className="field" value={backTo} onChange={e => setBackTo(+e.target.value)}>
                {earlier.map(({ s, k }) => <option key={k} value={k}>{k + 1}. {s.title}</option>)}
              </select>
              <small className="mut">That stage and every later one run again, given your note. The rejected results are kept, not overwritten.</small></div>
            <div className="wf-fld"><label htmlFor={`${id}-bn`}>Note for that stage</label>
              <textarea id={`${id}-bn`} className="field" rows={2} value={backNote} onChange={e => setBackNote(e.target.value)} placeholder="What needs to change?" /></div>
            {backWhy ? <p className="wf-why" role="status">{backWhy}</p> : null}
            <Pill variant="danger" icon={<Undo2 />} disabled={!!backWhy || !earlier.length} id="wfSendBackGo" onClick={sendBack}>Send back to stage {earlier.length ? backTo + 1 : ''}</Pill>
          </div>
        ) : null}
      </section>
    </div>
  );
}
