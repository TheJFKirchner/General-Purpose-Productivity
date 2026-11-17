/* The planner chat log entries: bubbles, system lines, visuals notes (with Show), question rounds and plan draft
   cards. Ported from prototype/launchpad-orbit.html (addBubble / addSys 1518-1532, plan cards 1405-1449, question
   rounds 1563-1615, visuals notes 2830-2837). Model text only reaches the DOM through <Markdown> (ChatBubble). */
import { memo, useState } from 'react';
import type { Question, RoundAnswer } from '../../contract';
import { actions, getState, sel, useLaunchpad, useSession, type PlannerEntry, type Round } from '../../store';
/* direct imports (not the components index, which would be a cycle): components/archiveModals.tsx renders PlanLog for the read-only archive */
import { AutopilotSwitch } from '../../components/AutopilotSwitch';
import { ChatBubble, SysLine, TypingDots } from '../../components/ChatBubble';
import { Markdown } from '../../components/Markdown';
import { PenButton } from '../../components/PenButton';
import { Pill } from '../../components/Pill';
import { StepAgent } from '../../components/Purpose';
import { AP_HINT } from '../../lib/labels';
import { ArrowRight, Check, Sparkles, Terminal } from '../../components/icons';

type PlanCardEntry = Extract<PlannerEntry, { kind: 'plancard' }>;

/** The whole log of one session (or the lines before any session when sid is null). */
export function PlanLog({ entries, sid, typing, onChanges }: {
  entries: PlannerEntry[]; sid: string | null; typing: boolean; onChanges?: () => void;
}) {
  return (
    <div className="log">
      {entries.map(e => <LogEntry key={e.id} e={e} sid={sid} onChanges={onChanges} />)}
      {typing ? <TypingDots /> : null}
    </div>
  );
}

export const LogEntry = memo(function LogEntry({ e, sid, onChanges }: { e: PlannerEntry; sid: string | null; onChanges?: () => void }) {
  switch (e.kind) {
    case 'bubble': return <ChatBubble who={e.who} text={e.text} />;
    case 'sys': return <SysLine text={e.text} cls={e.cls} />;
    case 'visnote':
      return (
        <SysLine text={e.text + ' '} cls="visnote">
          <button type="button" onClick={() => { const id = sid ?? getState().current; if (id != null) actions.visShowSet(id, e.setId); }}>Show</button>
        </SysLine>
      );
    case 'round': return <RoundView roundId={e.roundId} />;
    case 'auto': return <AutoLine e={e} />;
    case 'plancard': return sid != null ? <PlanCard e={e} sid={sid} onChanges={onChanges} /> : null;
  }
});

/* ---------------- auto-answered questions ---------------- */
/** One question the Auto answers switch answered: the question and the answer taken, marked automatic. */
function AutoLine({ e }: { e: Extract<PlannerEntry, { kind: 'auto' }> }) {
  const who = e.step ? `${e.agent}, step ${e.step}` : e.agent;
  return (
    <div className="autoline" title={`${who} asked: ${e.title}. Answered automatically with the recommended answer: ${e.answer}`}>
      <span className="autotag"><Sparkles />Auto</span>
      <span className="aa-q"><span className="sr">{who} asked: </span>{e.title}</span>
      <span className="aa-a"><span className="sr">Answered automatically: </span><ArrowRight />{e.answer}</span>
    </div>
  );
}

/* ---------------- question rounds ---------------- */
function RoundView({ roundId }: { roundId: string }) {
  const r = useLaunchpad(st => st.rounds[roundId]);
  if (!r) return null;
  return (
    <div className="round" id={`round-${r.id}`}>
      {r.questions.map((q, i) => <QuestionCard key={q.id} r={r} q={q} i={i} />)}
      {!r.actionsHidden ? (
        <div className="round-actions">
          <Pill variant="soft" size="sm" onClick={() => actions.acceptAllPicks(r.id)}>Accept all picks</Pill>
          <Pill variant="ghost" size="sm" onClick={() => actions.skipRound(r.id)}>Skip for now</Pill>
        </div>
      ) : null}
    </div>
  );
}

function QuestionCard({ r, q, i }: { r: Round; q: Question; i: number }) {
  const a = r.answers[q.id];
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const opts = (q.options || []).filter(o => o !== q.rec);
  const answer = (ans: RoundAnswer) => actions.answerQuestion(r.id, q.id, ans);
  const cid = `q-${r.id}-${q.id}`;
  return (
    <div className={`q${a ? ' done' : ''}`} id={cid}>
      <span className="lbl">Question {i + 1}</span>
      <h3>{q.title}</h3>
      {q.body ? <p className="why">{q.body}</p> : null}
      {q.rec ? <p>My pick: {q.rec}</p> : null}
      {a ? <span className="ans"><Check />{a.accepted ? 'Accepted my pick' : (a.text || a.option || '')}</span> : (
        <>
          {opts.length ? (
            <div className="row opts">
              {opts.map(o => <Pill key={o} variant="soft" size="sm" onClick={() => answer({ accepted: false, option: o, text: o })}>{o}</Pill>)}
            </div>
          ) : null}
          {editing ? (
            <>
              <label className="sr" htmlFor={`ta-${cid}`}>Your answer</label>
              <textarea id={`ta-${cid}`} autoFocus placeholder="Your answer…" value={text} onChange={ev => setText(ev.target.value)} />
              <div className="row">
                <Pill variant="primary" size="sm" onClick={() => { const v = text.trim(); if (v) answer({ accepted: false, text: v }); }}>Save</Pill>
                <Pill variant="ghost" size="sm" onClick={() => { setEditing(false); setText(''); }}>Cancel</Pill>
              </div>
            </>
          ) : (
            <div className="row">
              {q.rec ? <Pill variant="primary" size="sm" onClick={() => answer({ accepted: true })}>Yes</Pill> : null}
              <Pill size="sm" onClick={() => setEditing(true)}>{q.rec ? 'Change' : 'Answer'}</Pill>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ---------------- plan draft cards ---------------- */
/** The skills a plan step names (its worker gets them); ones not found in the session's folders are greyed. */
function StepSkills({ step }: { step: { n: number; skills?: string[]; skills_unknown?: string[] } }) {
  const list = step.skills || [];
  if (!list.length) return null;
  const gone = new Set(step.skills_unknown || []);
  return (
    <span className="st-skills" aria-label={`Step ${step.n} skills: ${list.join(', ')}`}>
      {list.map(n => (
        <span key={n} className={`chip skill${gone.has(n) ? ' gone' : ''}`}
          data-tip={`text:${gone.has(n) ? 'Not found in this session\'s folders: ignored when the step runs' : 'This step\'s worker gets this skill'}`}>
          <Sparkles />{n}
        </span>
      ))}
    </span>
  );
}


function PlanCard({ e, sid, onChanges }: { e: PlanCardEntry; sid: string; onChanges?: () => void }) {
  const s = useSession(sid);
  const defDir = useLaunchpad(st => sel.defaultDirId(st));
  /* the agent per step when it is not the Builder (purpose colours come from the crew list) */
  const crewDefs = useLaunchpad(st => sel.defsForSession(st, st.sessions[sid]));
  if (!s) return null;
  const v = sel.planCardView(s, e);
  const d = e.draft;
  const agentOf = (st: { agent?: string | null; agent_display?: string | null; agent_fallback?: boolean; agent_purpose?: string | null }) => sel.stepAgent(crewDefs, st);
  const codeSent = s.codeSentV === e.draftV;
  return (
    <div className={`plancard${v.approved ? ' approved' : v.superseded ? ' superseded' : ''}`}>
      <div className="top">
        <span className="tag ques">Plan draft</span>
        <span className="chip">Session {s.letter}</span>
        {e.rev ? <span className="chip rev">Revision {e.rev}</span> : null}
      </div>
      <h3>{d.title || sel.sName(s)}</h3>
      {d.path ? <div className="path">{d.path} <PenButton root={s.dirId ?? defDir} path={d.path} label="Edit plan" /></div> : null}
      {d.steps && d.steps.length ? (
        <ol className="steps">{d.steps.map((st, k) => {
          const ag = agentOf(st);
          return <li key={`${st.n}-${k}`}><span className="n">{st.n}</span><span className="st-t">{st.title}</span>{ag ? <StepAgent a={ag} step={`Step ${st.n}`} /> : null}<StepSkills step={st} /></li>;
        })}</ol>
      ) : null}
      <details className="full">
        <summary>Read the full plan</summary>
        <Markdown doc className="mdbox" text={d.markdown} />
      </details>
      <div className="pc-ap">
        {v.showApSwitch ? <><AutopilotSwitch sessionId={s.id} /><p className="ap-hint">{AP_HINT}</p></>
          : v.apTag ? <span className="aptag">Autopilot on for this run</span> : null}
      </div>
      {v.live ? (
        <div className="row pc-actions">
          <Pill variant="primary" disabled={v.approveDisabled} onClick={() => actions.approve(s.id)}>{v.approveLabel}</Pill>
          <Pill variant="soft" icon={s.codeSending ? undefined : <Terminal />} disabled={s.codeSending} data-sendcode="1"
            title="Open a CLI chat in this folder with the plan as its first message (Plan mode). An alternative to launching the run."
            onClick={() => actions.sendPlanToCode(s.id)}>{s.codeSending ? 'Opening the CLI…' : codeSent ? 'Send to CLI again' : 'Send plan to CLI'}</Pill>
          <Pill variant="ghost" onClick={() => onChanges && onChanges()}>Ask for changes</Pill>
        </div>
      ) : null}
      {v.status ? <p className="pc-status">{v.status}</p> : null}
      {v.live && codeSent && !s.codeSending ? <p className="pc-sent">Sent to the CLI. <button type="button" onClick={() => actions.setChatSide('code')}>Show the chat</button></p> : null}
    </div>
  );
}
