/* Incoming: the request queue (questions, permissions, updates, run reports) with filters, timers and ages.
   Ported from prototype/launchpad-orbit.html 1700-1878 (renderQueue, itemEl, answerItem, decide, tickTimers,
   filters, report cards). Card order: open cards that need you (blocking first), then other open, then settled.
   Model text (question / update bodies) only reaches the DOM through <Markdown>. */
import { useState } from 'react';
import { actions, sel, useComputed, useLaunchpad, type QueueItem, type Session } from '../../store';
import { Badge, Empty, Markdown, Pill, Tag, openReport } from '../../components';
import { useNow } from '../../lib/hooks';
import { ago, cleanName, mmss, usd } from '../../lib/format';
import { REVIEW_TESTS, S_LABEL, agentLabel } from '../../lib/labels';
import { CircleHelp, FileText, Inbox, Send, UserCheck, Users } from '../../components/icons';

const FILTERS: { f: 'all' | 'permission' | 'question'; label: string }[] = [
  { f: 'all', label: 'All' }, { f: 'permission', label: 'Permissions' }, { f: 'question', label: 'Questions' },
];

export function IncomingHead() {
  const waiting = useComputed(st => sel.openCount(st));
  const filter = useLaunchpad(st => st.ui.queueFilter);
  return (
    <div className="inc-head">
      <h2>Incoming<Badge n={waiting} /></h2>
      <div className="filters seg" role="group" aria-label="Filter requests">
        {FILTERS.map(x => (
          <button key={x.f} type="button" aria-pressed={filter === x.f} onClick={() => actions.setQueueFilter(x.f)}>{x.label}</button>
        ))}
      </div>
    </div>
  );
}

export interface CardView { i: QueueItem; s: Session | null; hidden: boolean; total: number; pc: number }

export function Queue() {
  const v = useComputed(st => {
    const cards: CardView[] = sel.orderedQueue(st).map(i => {
      const s = i.session_id != null ? st.sessions[i.session_id] || null : null;
      return { i, s, hidden: !sel.queueVisible(st, i), total: s ? sel.sessionTotal(st, s.id) : 0, pc: s ? sel.plannerCostOf(st, s.id) : 0 };
    });
    return { cards, shown: cards.some(c => !c.hidden) };
  });
  return (
    <div className="queue" id="queue" aria-live="polite">
      {v.cards.map(c => <QueueCard key={c.i.id} c={c} />)}
      {!v.shown ? <Empty card icon={<Inbox />} title="All clear">Nothing needs you right now. The crew will ping here.</Empty> : null}
    </div>
  );
}

function Age({ at }: { at: number }) {
  useNow(5000);
  return <span className="age">{ago(at)}</span>;
}

function Timer({ i }: { i: QueueItem }) {
  const now = useNow(1000);
  const left = sel.deadline(i) - now;
  if (isNaN(left)) return null;
  const perm = i.kind === 'permission', up = left <= 0;
  const total = (+(i.timeout_s ?? 0) || Math.max(left / 1000, 1)) * 1000;
  const width = up ? 0 : Math.max(0, Math.min(100, left / total * 100));
  const rv = i.review_id != null;
  const text = rv
    ? (up ? 'Time is up. The reviewer carries on without your answer…' : <>The reviewer carries on without an answer in <b className="tleft">{mmss(left)}</b></>)
    : up
    ? (perm ? 'Time is up. The request is being denied…' : 'Time is up. Auto-answering with the recommendation…')
    : perm ? <>Denied automatically in <b className="tleft">{mmss(left)}</b> unless you answer</>
    : <>{i.rec ? 'Auto-answers with the recommendation' : 'Auto-answers'} in <b className="tleft">{mmss(left)}</b></>;
  return (
    <div className={`timer${perm ? ' deny' : ''}${up || left < 10000 ? ' soon' : ''}`}>
      <span>{text}</span>
      <div className="bar"><i style={{ width: width + '%' }} /></div>
    </div>
  );
}

function Dismiss({ id }: { id: string }) {
  return <div className="row"><Pill variant="ghost" size="sm" onClick={() => actions.dismissItem(id)}>Dismiss</Pill></div>;
}

/** One Incoming card. scope "review" = the same card shown inside a role's review screen (own ids, no "Open review" button). */
export function QueueCard({ c, scope }: { c: CardView; scope?: 'review' }) {
  const { i, s, hidden } = c;
  const open = i.ui === 'open';
  const needsYou = i.kind === 'question' || i.kind === 'permission' || i.kind === 'review';
  const testTitle = i.test ? REVIEW_TESTS.find(t => t.test === i.test)?.title : '';
  const who = [agentLabel(cleanName(i.agent)), i.step != null ? `step ${i.step}` : '', testTitle || ''].filter(Boolean).join(' · ');
  const runTxt = s ? sel.sLabel(s) : 'The run';
  const cls = `item card${open && i.blocking && needsYou ? ' blocking' : ''}${open ? '' : ' settled'}${i.leaving ? ' leaving' : ''}`;
  return (
    <article className={cls} id={`${scope ? 'rv-' : ''}item-${i.id}`} hidden={hidden}>
      <div className="top">
        <Tag kind={i.kind} />
        {i.review_id != null && i.role ? <span className="chip role-chip" title={`A question from the Role Reviewer about the role ${i.role}`}><Users />{i.role}</span> : null}
        {s ? <span className={`chip${s.wf ? ' wfchip' : ''}`} title={sel.sName(s)}>{sel.sLabel(s)}</span> : null}
        <span className="who">{who}</span>
        <Age at={i.at} />
      </div>
      <CardBody c={c} runTxt={runTxt} scope={scope} />
    </article>
  );
}

function CardBody({ c, runTxt, scope }: { c: CardView; runTxt: string; scope?: 'review' }) {
  const { i, s } = c;
  const open = i.ui === 'open';

  if (i.kind === 'report') {
    return (
      <>
        <h3>{s ? `${sel.sLabel(s)} finished · ${S_LABEL[s.status] || s.status}` : 'Run finished'}</h3>
        <p className="why">{s ? (s.wf ? (s.wf.test ? 'Test run of a workflow' : 'Workflow run') : sel.sName(s)) : ''}{s ? ` · ${s.wf ? 'cost' : 'session total'} ${usd(c.total)}` : ''}{c.pc ? ` · planner ${usd(c.pc)} (separate)` : ''}</p>
        <div className="row">
          <Pill variant="soft" size="sm" icon={<FileText />} onClick={() => { if (i.session_id != null) openReport(i.session_id); }}>Read report</Pill>
          {s && s.wf ? null : (
            <Pill size="sm" icon={s && s.reportSent ? undefined : <Send />} disabled={!!s && s.reportSent} onClick={() => { if (i.session_id != null) actions.sendReport(i.session_id); }}>
              {s && s.reportSent ? 'Sent to planner' : 'Send to planner'}
            </Pill>
          )}
          <Pill variant="ghost" size="sm" onClick={() => actions.dismissItem(i.id)}>Dismiss</Pill>
        </div>
      </>
    );
  }
  if (i.kind === 'review' && open) {
    const wfName = i.workflow ? `${i.workflow.name}${i.workflow.test ? ' (test run)' : ''}` : runTxt;
    return (
      <>
        <h3>{i.title || 'Sign-off needed'}</h3>
        {i.body ? <Markdown className="qbody" text={i.body} /> : null}
        <div className="blockline"><span className="dot" />Needs you · {wfName} is waiting for your sign-off</div>
        <div className="row"><Pill variant="primary" size="sm" icon={<UserCheck />} onClick={() => { if (i.run_id) actions.openWorkflowReview(i.run_id); }}>Open the review</Pill></div>
      </>
    );
  }
  if (i.kind === 'info') {
    return <><h3>{i.title || 'Update'}</h3>{i.body ? <Markdown className="qbody" text={i.body} /> : null}<Dismiss id={i.id} /></>;
  }
  if (!open) {
    const head = <h3>{i.title}</h3>;
    if (i.ui === 'sent') return <>{head}<p className="settle"><b>Sent: “{i.answer}”.</b> Waiting for the agent to pick it up…</p></>;
    if (i.ui === 'timedout') return <>{head}<p className="settle denied"><b>Denied by timeout.</b> No answer came before the timer ran out, so the request was refused and the builder carried on without it.</p><Dismiss id={i.id} /></>;
    if (i.ui === 'decided') return <>{head}<p className="settle decided"><span className="aatag"><CircleHelp />Auto</span><b>Decided by the {agentLabel(cleanName(i.agent)) || 'builder'} (Auto answers on): “{i.answer}”.</b> Its own recommendation was taken, so the run did not wait for you.</p><Dismiss id={i.id} /></>;
    if (i.ui === 'autopilot') return <>{head}<p className="settle auto"><b>Approved by Autopilot.</b> Autopilot is on for {runTxt}, so this request went through without an answer from you.</p><Dismiss id={i.id} /></>;
    if (i.ui === 'auto' && i.review_id != null) return <>{head}<p className="settle auto"><b>No answer in time.</b> The reviewer carried on without one, and its case says so.</p><Dismiss id={i.id} /></>;
    if (i.ui === 'auto') return <>{head}<p className="settle auto"><b>Auto-answered with the recommendation: “{i.answer}”.</b> No reply came before the timer ran out, so the agent carried on with it.</p><Dismiss id={i.id} /></>;
    return <>{head}<p className="settle">{runTxt} ended before this was answered.</p><Dismiss id={i.id} /></>;
  }
  if (i.kind === 'permission') {
    /* permissions: neutral buttons, never a recommendation (the user decides) */
    return (
      <>
        <h3>{i.title || 'Permission needed'}</h3>
        {i.body ? <pre className="cmd">{i.body}</pre> : null}
        {sel.hasTimer(i) ? <Timer i={i} />
          : i.blocking ? <div className="blockline"><span className="dot" />Waiting on you · {agentLabel(cleanName(i.agent)) || 'the agent'} is paused</div> : null}
        <div className="row">
          <Pill onClick={() => actions.decide(i.id, 'allow')}>Allow</Pill>
          <Pill onClick={() => actions.decide(i.id, 'deny')}>Deny</Pill>
          <Pill onClick={() => actions.decide(i.id, 'always')}>Always allow this</Pill>
        </div>
      </>
    );
  }
  return <QuestionBody i={i} runTxt={runTxt} scope={scope} />;
}

function QuestionBody({ i, runTxt, scope }: { i: QueueItem; runTxt: string; scope?: 'review' }) {
  const [other, setOther] = useState('');
  const opts = Array.isArray(i.options) ? i.options : [];
  const recIn = i.rec != null && i.rec !== '' && opts.includes(i.rec);
  return (
    <>
      <h3>{i.title}</h3>
      {i.body ? <Markdown className="qbody" text={i.body} /> : null}
      {i.blocking ? <div className="blockline"><span className="dot" />Waiting on you · {i.review_id != null ? 'the review' : runTxt} is paused until you answer</div>
        : sel.hasTimer(i) ? <Timer i={i} /> : null}
      {i.rec && !recIn ? (
        <div className="recbox"><span>Recommended</span><p>{i.rec}</p><Pill variant="primary" size="sm" onClick={() => actions.answerItem(i.id, i.rec || '')}>Use this</Pill></div>
      ) : null}
      {opts.length ? (
        <div className="row">
          {opts.map((o, k) => (
            <Pill key={k} variant={o === i.rec ? 'sugg' : 'default'} onClick={() => actions.answerItem(i.id, o)}>
              {o}{o === i.rec ? <small>Recommended</small> : null}
            </Pill>
          ))}
        </div>
      ) : null}
      <form className="other" onSubmit={e => { e.preventDefault(); const t = other.trim(); if (t) actions.answerItem(i.id, t); }}>
        <label className="sr" htmlFor={`${scope ? 'rv-' : ''}o-${i.id}`}>Your own answer</label>
        <input id={`${scope ? 'rv-' : ''}o-${i.id}`} placeholder="Or type your own answer…" value={other} onChange={e => setOther(e.target.value)} />
        <Pill size="sm" type="submit" icon={<Send />} aria-label="Send your answer" data-tip="text:Send your answer" />
      </form>
      {i.review_id != null && i.role && !scope ? (
        <div className="row"><Pill variant="soft" size="sm" icon={<Users />} onClick={() => actions.openRole(i.role!)}>Open review of {i.role}</Pill></div>
      ) : null}
    </>
  );
}
