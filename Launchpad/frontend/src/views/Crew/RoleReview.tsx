/* Crew: one role's review screen (opens in the Crew tab's detail area, like an agent's definition). While the
   Role Reviewer reads: progress lines. Then the case: one block per test in the fixed order (finding, evidence,
   strength), the reviewer's verdict and reason, the skill notes for "keep", the review's tokens and cost (the one
   usd() helper). The reviewer's question cards for this review sit inside the screen and are answered in place
   (the Incoming card component; the same cards are in Incoming, labelled with the role). The decision is the user's:
   three buttons, the reviewer's verdict marked as its recommendation, none pre-pressed. The define path hands over
   to the Add an agent form (AgentForm.tsx), then says where the case was saved. All figures and text are the server's. */
import { useEffect, useRef } from 'react';
import { actions, sel, useComputed, type CrewForm } from '../../store';
import type { ReviewSection, RoleDecision } from '../../contract';
import { Loading, Markdown, Pill } from '../../components';
import { AlertTriangle, ArrowLeft, Check, ListChecks, Sparkles, UserCog, WandSparkles } from '../../components/icons';
import { QueueCard } from '../Aside/Incoming';
import { DECISION_HINT, DECISION_LABEL, REVIEW_TESTS, STRENGTH_LABEL } from '../../lib/labels';
import { tokShort, tparts, usd } from '../../lib/format';

const DECISIONS: RoleDecision[] = ['define', 'keep', 'not_yet'];

export default function RoleReview({ role }: { role: string }) {
  const v = useComputed(st => ({
    r: st.reviews[role] || null, entry: st.roles.entries.find(e => e.name === role) || null, resurface: st.roles.resurface,
    cards: sel.reviewQueue(st, role),
  }));
  const head = useRef<HTMLHeadingElement>(null);
  useEffect(() => { head.current?.focus(); }, [role]);
  const { r, entry } = v;
  const running = !!r && (r.status === 'running' || r.status === 'starting');
  return (
    <div className="crew-detail role-review" id="roleDetail" data-role={role}>
      <div className="cd-bar">
        <Pill size="sm" variant="ghost" icon={<ArrowLeft />} id="roleBack" onClick={() => actions.closeRole()}>All agents</Pill>
      </div>
      <div className="cd-head">
        <span className="hero-ic lg" aria-hidden="true"><UserCog /></span>
        <div className="cd-title">
          <h2 tabIndex={-1} ref={head}>Review: {role}</h2>
          <p>
            <span>A role used but not defined</span>
            {entry ? <span className="cd-uses"><b>{entry.uses_total.toLocaleString()}</b> {entry.uses_total === 1 ? 'use' : 'uses'}</span> : null}
            {r && r.model ? <span>reviewer model <b>{r.model}</b></span> : null}
          </p>
        </div>
      </div>

      {!r ? (
        <section className="cd-sec">
          <p className="none">This role has not been reviewed yet. The reviewer reads its recorded uses and writes a case for or against giving it its own agent; the decision stays yours.</p>
          <div className="row"><Pill variant="primary" icon={<ListChecks />} id="roleStart" onClick={() => actions.roleReview(role)}>Start the review</Pill></div>
        </section>
      ) : null}

      {running ? (
        <section className="cd-sec" aria-labelledby="rvProgressH">
          <h3 id="rvProgressH">The reviewer is working <span>{r!.phase === 'asking' ? 'asking you something' : r!.phase === 'finalising' ? 'writing the case' : 'reading the history'}</span></h3>
          <div role="status" aria-live="polite" className="rv-progress">
            <Loading>{r!.progress.length ? r!.progress[r!.progress.length - 1] : 'Starting the review…'}</Loading>
            {r!.progress.length > 1 ? <ul className="rv-lines">{r!.progress.slice(0, -1).map((t, i) => <li key={i}>{t}</li>)}</ul> : null}
          </div>
        </section>
      ) : null}

      {r && (r.status === 'failed' || r.status === 'refused') ? (
        <section className="cd-sec">
          <div className="warn" role="alert"><b className="warn-h"><AlertTriangle />{r.status === 'failed' ? 'The review could not finish' : 'This role cannot be reviewed now'}</b>{r.error}</div>
          <p className="none rv-after">The role is still in the list and can be reviewed again.</p>
          <div className="row"><Pill variant="primary" icon={<ListChecks />} id="roleRetry" onClick={() => actions.roleReview(role)}>Review again</Pill></div>
        </section>
      ) : null}

      {v.cards.length ? (
        <section className="cd-sec rv-cards" aria-labelledby="rvQuestionsH">
          <h3 id="rvQuestionsH">The reviewer's questions <span>answer here or in Incoming; what the evidence cannot show</span></h3>
          <div className="queue">
            {v.cards.map(i => <QueueCard key={i.id} scope="review" c={{ i, s: null, hidden: false, total: 0, pc: 0 }} />)}
          </div>
        </section>
      ) : null}

      {r && r.status === 'case' && r.case ? <Case role={role} /> : null}
    </div>
  );
}

function Case({ role }: { role: string }) {
  const v = useComputed(st => ({ r: st.reviews[role]!, resurface: st.roles.resurface, form: st.crewForm, hasDir: !!sel.crewDir(st) }));
  const { r, form } = v;
  const c = r.case!;
  const byTest = new Map<string, ReviewSection>(c.sections.map(s => [s.test, s]));
  const decided = r.decided;
  const rec = c.verdict;
  return (
    <>
      <section className="cd-sec rv-verdict" aria-labelledby="rvVerdictH" data-verdict={rec}>
        <h3 id="rvVerdictH">The reviewer's verdict <span>a recommendation: the decision is yours</span></h3>
        <p className="rv-vline"><b>{DECISION_LABEL[rec]}</b></p>
        <p className="rv-reason">{c.reason}</p>
        {c.history_thin ? <p className="none">The reviewer found the history thin, so it leans to waiting.</p> : null}
        <p className="none">Read {c.opened.length} of the {c.uses_recorded} recorded uses in full ({c.uses_total} in all){c.missing.length ? `; the session records of ${c.missing.join(', ')} are gone, so it worked from the tally lines` : ''}.</p>
      </section>

      <section className="cd-sec" aria-labelledby="rvTestsH">
        <h3 id="rvTestsH">The five tests</h3>
        <ol className="rv-tests">
          {REVIEW_TESTS.map(t => {
            const s = byTest.get(t.test);
            return (
              <li key={t.test} className="rv-test" data-test={t.test}>
                <div className="rv-test-h">
                  <h4>{s?.title || t.title}</h4>
                  {s ? <span className={`chip rv-strength ${s.strength}`}>{STRENGTH_LABEL[s.strength] || s.strength}</span> : null}
                </div>
                {s ? (
                  <>
                    <p className="rv-finding">{s.finding}</p>
                    {s.evidence.length ? (
                      <ul className="rv-evidence" aria-label={`Evidence for ${s.title || t.title}`}>
                        {s.evidence.map((e, i) => <li key={i}><q>{e.quote}</q><small>{e.source}</small></li>)}
                      </ul>
                    ) : <p className="none">No evidence quoted.</p>}
                  </>
                ) : <p className="none">The reviewer did not address this test.</p>}
              </li>
            );
          })}
        </ol>
      </section>

      {c.verdict === 'keep' && c.skill_notes ? (
        <section className="cd-sec" aria-labelledby="rvSkillH">
          <h3 id="rvSkillH">What the skill should cover <span>for keeping this as a skill plus the Builder</span></h3>
          <div className="prompt"><Markdown text={c.skill_notes} /></div>
        </section>
      ) : null}

      {c.verdict === 'define' && c.proposal && c.proposal.name ? (
        <section className="cd-sec" aria-labelledby="rvPropH">
          <h3 id="rvPropH">What the reviewer would define <span>the drafter starts from this</span></h3>
          <dl className="kv">
            <dt>Name</dt><dd><code>{c.proposal.name}</code></dd>
            <dt>Description</dt><dd>{c.proposal.description}</dd>
          </dl>
        </section>
      ) : null}

      <section className="cd-sec" aria-labelledby="rvCostH">
        <h3 id="rvCostH">Cost of this review</h3>
        <p className="rv-cost" title="Counted in the app-wide total, not in any session">
          <b>{usd(c.usage.cost)}</b> · {tokShort(tparts(c.usage))} · {c.reviewer.label || c.reviewer.model}
        </p>
      </section>

      <section className="cd-sec rv-decide" aria-labelledby="rvDecideH">
        <h3 id="rvDecideH">Your decision</h3>
        {!decided ? (
          <>
            <div className="rv-buttons" role="group" aria-label="Decide what to do with this role">
              {DECISIONS.map(d => (
                <span key={d} className="rv-choice">
                  <Pill id={`decide-${d}`} disabled={!!r.deciding}
                    aria-label={`${DECISION_LABEL[d]}${d === rec ? ' (the reviewer\'s recommendation)' : ''}`}
                    title={DECISION_HINT[d]} onClick={() => actions.roleDecide(role, d)}>
                    {DECISION_LABEL[d]}
                  </Pill>
                  {d === rec ? <span className="rv-rec-tag"><Sparkles />Reviewer's recommendation</span> : null}
                </span>
              ))}
            </div>
            <p className="none">{r.deciding ? 'Sending your decision…' : 'Nothing is pre-selected. Define an agent drafts one for you to edit; the other two leave the role as a skill plus the Builder, or keep counting.'}</p>
          </>
        ) : decided.decision === 'define' ? (
          <DefinePanel role={role} saved={r.saved} form={form} hasDir={v.hasDir} />
        ) : (
          <div className="rv-decided" role="status">
            <p><b className="af-ok"><Check />Decision: {DECISION_LABEL[decided.decision]}</b>{decided.reviewerVerdict && decided.reviewerVerdict !== decided.decision ? <span className="none"> (the reviewer recommended {DECISION_LABEL[decided.reviewerVerdict]})</span> : null}</p>
            <p className="rv-rest">{sel.roleRestNote(decided.decision, v.resurface)}</p>
            <div className="row"><Pill size="sm" variant="ghost" icon={<ArrowLeft />} onClick={() => actions.closeRole()}>Back to Crew</Pill></div>
          </div>
        )}
      </section>
    </>
  );
}

function DefinePanel({ role, saved, form, hasDir }: { role: string; saved: { agent: string; casePath: string | null } | null; form: CrewForm; hasDir: boolean }) {
  if (saved) {
    return (
      <div className="rv-decided" role="status">
        <p><b className="af-ok"><Check />Agent <code>{saved.agent}</code> saved</b></p>
        <p className="rv-rest">The role is no longer listed; the agent is in its purpose section of the Crew tab, and the planner can name it in new plans.
          {saved.casePath ? <> The case is saved beside it at <code>{sel.relPath(saved.casePath)}</code>.</> : <> No case file was kept for it (the review was not made in this launch).</>}</p>
        <div className="row"><Pill size="sm" variant="ghost" icon={<ArrowLeft />} onClick={() => actions.closeRole()}>Back to Crew</Pill></div>
      </div>
    );
  }
  const mine = form.role === role;
  const cost = mine ? form.cost : null;
  return (
    <div className="rv-decided" role="status">
      <p><b className="af-ok"><Check />Decision: {DECISION_LABEL.define}</b></p>
      {mine && form.drafting ? <Loading>The drafter is writing a first version from the case…</Loading> : null}
      {mine && form.draftError ? <div className="warn" role="alert">{form.draftError}</div> : null}
      {mine && form.drafted ? <p className="rv-rest">Drafted. Check every field in the form, then save.{cost ? <> Drafting cost <b>{usd(cost.cost)}</b> · {tokShort(tparts(cost))}.</> : null}</p> : null}
      {!hasDir ? <p className="none">Connect a folder in Settings first: the agent is saved in a project folder.</p> : null}
      <div className="row">
        {mine && form.drafted ? <Pill variant="primary" id="roleOpenForm" onClick={() => actions.roleOpenForm(role)}>{form.open ? 'Form is open' : 'Open the form'}</Pill> : null}
        {!(mine && form.drafting) ? <Pill size={mine && form.drafted ? 'sm' : 'md'} variant={mine && form.drafted ? 'ghost' : 'primary'} icon={<WandSparkles />} id="roleDraft" onClick={() => actions.roleDraft(role)}>{mine && form.drafted ? 'Draft again' : 'Draft the agent'}</Pill> : null}
        {!(mine && form.drafting) && !(mine && form.drafted) ? <Pill size="sm" variant="ghost" onClick={() => actions.roleOpenForm(role)}>Fill the form myself</Pill> : null}
      </div>
    </div>
  );
}
