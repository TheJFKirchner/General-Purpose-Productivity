/* Workflows demo: six made-up workflows covering every card state, and the messages answered the way the server does
   (shapes follow the Workflows section of the app/server.py header).
   - Reserve study: idle card (inputs of every kind, a review with tick and written items, Unattended off)
   - Experience analysis: warnings (a missing attached file, a mistake in the file, a note), Run disabled
   - Monthly claims check: a run in progress (stage 2 running), Unattended on
   - Pricing refresh: a run awaiting review (checklist, results to read, one earlier attempt sent back and kept)
   - Year-end close: a finished run
   - Mortality update: a test run in progress
   A run you start moves on its own (agent stages finish after a moment, a review stops and waits); Approve continues,
   Send back re-runs from the chosen stage, Stop ends it. Saves and removes change the list. */
import type { AttachedFile, ChecklistItem, Workflow, WorkflowAgentStage, WorkflowDraft, WorkflowInput, WorkflowReviewStage, WorkflowRun, WorkflowRunStage, WorkflowStage, WorkflowWarning } from '../contract';

type Ev = Record<string, any>;
export interface WfDemoState { list: Workflow[]; runs: Record<string, WorkflowRun>; n: number; reviewer: string; seen: Record<string, { started: boolean; stages: string; card: string | null; finished: boolean }> }

const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const file = (path: string, exists = true): AttachedFile => ({ path, resolved: `C:/work/claims-project/${path}`, exists, name: path.split('/').pop() });
const item = (text: string, kind: 'tick' | 'answer' = 'tick'): ChecklistItem => ({ text, kind });
const input = (name: string, o: Partial<WorkflowInput> = {}): WorkflowInput => ({ name, label: name.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()), kind: 'text', required: true, default: '', options: [], help: '', ...o });
const AGENT_DISPLAY: Record<string, string> = { 'launchpad-builder': 'Builder', 'launchpad-astronaut': 'Explorer', 'sql-builder': 'Sql builder', 'sql-reviewer': 'Sql reviewer' };
type StageDef = Omit<WorkflowAgentStage, 'index'> | Omit<WorkflowReviewStage, 'index'>;
const agent = (title: string, a: string, instruction: string, files: string[] = [], missing: string[] = []): StageDef =>
  ({ kind: 'agent', title, agent: a, agent_display: AGENT_DISPLAY[a] || a, agent_purpose: a === 'sql-reviewer' ? 'reviewing' : 'building', instruction, files: files.map(f => file(f, !missing.includes(f))) });
const review = (title: string, checklist: ChecklistItem[] = []): StageDef => ({ kind: 'review', title, checklist });

function wf(id: string, name: string, description: string, stages: StageDef[], extra: Partial<Workflow> = {}): Workflow {
  const w = {
    id: `d1/${id}`, slug: id, name, description, folder: 'd1', folder_name: 'claims-project', path: `workflows/${id}.json`, output_folder: `studies/${id}`, output_path: `C:/work/claims-project/studies/${id}`,
    unattended_default: false, inputs: [], files: [], stages: stages.map((s, index) => ({ ...s, index }) as WorkflowStage), warnings: [], can_run: true, running_run_id: null, last_run_id: null, ...extra,
  } as Workflow;
  w.can_run = !w.warnings.some(x => x.level === 'error');
  return w;
}

const RESULTS: Record<string, string> = {
  'Load the data': '# Data load\n\n- 48,210 claim lines read from `claims_2026q3.csv`\n- 112 lines dropped (blank facility id)\n- Totals agree with the control sheet to the cent',
  'Fit the reserve factors': '# Reserve factors\n\n| Lag | Factor |\n|---|---|\n| 1 | 1.482 |\n| 2 | 1.121 |\n| 3 | 1.034 |\n\nTail factor 1.012, chosen as in the methodology page.',
  'Prepare the review memo': '# Memo for the reviewer\n\n**Checked:** totals, lag triangle shape, factor selection.\n\n**Looks off:** lag 2 is higher than last quarter (1.121 against 1.098).\n\n**Questions:** is the lag 2 movement explained by the new provider contract?',
};
const resultOf = (t: string) => RESULTS[t] || `# ${t}\n\nDone. Nothing to flag.`;

const FOLDERS = [{ dir_id: 'd1', name: 'claims-project', path: 'C:/work/claims-project', is_primary: true }, { dir_id: 'd2', name: 'readmissions', path: 'C:/work/readmissions', is_primary: false }];
const AGENTS = [
  { name: 'launchpad-builder', display_name: 'Builder', purpose: 'building', builtin: true }, { name: 'launchpad-astronaut', display_name: 'Explorer', purpose: 'exploring', builtin: true },
  { name: 'sql-builder', display_name: 'Sql builder', purpose: 'building', builtin: false }, { name: 'sql-reviewer', display_name: 'Sql reviewer', purpose: 'reviewing', builtin: false },
];

export function demoWorkflows(): WfDemoState {
  const list: Workflow[] = [
    wf('reserve-study', 'Quarterly reserve study', 'Fit the claims reserve factors from the latest triangle, with a methodology check by a second person before anything goes out.', [
      agent('Load the data', 'sql-builder', "Read the quarter's claims extract and check the totals against the control sheet.", ['methodology/data-checks.md']),
      agent('Fit the reserve factors', 'launchpad-builder', 'Fit the development factors following the methodology page and write them out.', ['methodology/reserving.md']),
      agent('Prepare the review memo', 'sql-reviewer', 'Write a memo for the reviewer: what you verified, what looks off, questions.'),
      review('Methodology review', [item('Triangle totals agree with the control sheet'), item('Lag factors follow the methodology page'), item('Why is the tail factor right?', 'answer')]),
      agent('Write the summary', 'launchpad-builder', 'Write a one-page summary of the study and its sign-off.'),
    ], { inputs: [input('valuation_date', { kind: 'date', default: '2026-09-30' }), input('claims_file', { kind: 'file', help: 'The claims extract for the quarter' }), input('basis', { kind: 'choice', options: ['Paid', 'Incurred'], default: 'Paid' })], files: [file('methodology/house-style.md')], output_folder: 'studies/reserves', output_path: 'C:/work/claims-project/studies/reserves' }),
    wf('experience', 'Experience analysis', 'Actual against expected claims by cohort, for the annual experience review.', [
      agent('Pull the experience data', 'sql-builder', 'Pull the cohort data.', ['methodology/experience.md'], ['methodology/experience.md']),
      review('Sign-off'),
    ], { warnings: [
      { level: 'error', code: 'missing_file', message: 'The attached file methodology/experience.md was not found.', stage: 0, field: 'files' },
      { level: 'error', code: 'no_output_folder', message: 'The output folder is not set.', stage: null, field: 'output_folder' },
      { level: 'warning', code: 'unknown_field', message: 'The field "owner" is not used and will be dropped the next time the form saves.', stage: null, field: 'owner' },
    ] as WorkflowWarning[], output_folder: '', output_path: '' }),
    wf('claims-check', 'Monthly claims check', "Check the month's claims against the paid ledger and list anything that does not tie.", [
      agent('Load the ledger', 'sql-builder', 'Load the paid ledger.'), agent('Match the claims', 'launchpad-builder', 'Match claims to ledger lines.'),
      review('Reviewer check', [item('Unmatched lines are explained')]),
    ], { output_folder: 'studies/monthly', output_path: 'C:/work/claims-project/studies/monthly', unattended_default: true, running_run_id: 'run-claims', last_run_id: 'run-claims' }),
    wf('pricing', 'Pricing refresh', 'Refresh the price table from the latest trend and have a pricing actuary approve it.', [
      agent('Load the data', 'sql-builder', 'Load the data.'), agent('Fit the reserve factors', 'launchpad-builder', 'Fit the trend.'),
      agent('Prepare the review memo', 'sql-reviewer', 'Write a memo.'), review('Pricing sign-off', [item('Trend agrees with last quarter within tolerance'), item('Which memo questions did you resolve?', 'answer')]),
    ], { inputs: [input('effective_date', { kind: 'date' })], running_run_id: 'run-pricing', last_run_id: 'run-pricing', output_folder: 'studies/pricing', output_path: 'C:/work/claims-project/studies/pricing' }),
    wf('year-end', 'Year-end close', "Roll the year's balances forward and write the close-out note.", [
      agent('Roll the balances', 'launchpad-builder', 'Roll forward.'), review('Controller sign-off'), agent('Write the close-out note', 'launchpad-builder', 'Write the note.'),
    ], { output_folder: 'studies/year-end', output_path: 'C:/work/claims-project/studies/year-end', last_run_id: 'run-year-end' }),
    wf('mortality', 'Mortality update', 'Update the mortality table from the new experience and compare with the published one.', [
      agent('Fit the table', 'launchpad-builder', 'Fit.'), agent('Compare with the published table', 'sql-reviewer', 'Compare.'), review('Review'),
    ], { output_folder: 'studies/mortality', output_path: 'C:/work/claims-project/studies/mortality', running_run_id: 'run-mortality', last_run_id: 'run-mortality' }),
  ];
  const st = (index: number, title: string, kind: 'agent' | 'review', status: WorkflowRunStage['status'], extra: Partial<WorkflowRunStage> = {}): WorkflowRunStage => ({
    index, kind, title, status, agent: null, agent_display: kind === 'review' ? 'Review' : null, result_file: null, result_markdown: null, attempts: [], checklist: [], review: null, reviews: [], error: null, ...extra,
  });
  const done = (index: number, title: string, base: string, attempts = 1, rejectedNote = ''): WorkflowRunStage => {
    const stem = (k: number) => `${base}/${String(index + 1).padStart(2, '0')}-${slug(title)}${k ? '-' + (k + 1) : ''}.md`;
    return st(index, title, 'agent', 'done', {
      result_file: stem(attempts - 1), result_markdown: resultOf(title),
      attempts: Array.from({ length: attempts }, (_, k) => ({ attempt: k + 1, result_file: stem(k), status: 'done', rejected: k < attempts - 1, note: k < attempts - 1 ? rejectedNote : null })),
    });
  };
  const run = (id: string, w: string, name: string, o: Partial<WorkflowRun>): WorkflowRun => ({
    id, workflow_id: `d1/${w}`, workflow_name: name, test: false, folder: '', mission_id: `wf-${id}`, inputs: {}, unattended: false, status: 'running', current_stage: null,
    started_at: '2026-11-17T09:00:00', finished_at: null, summary_file: null, error: null, stages: [], ...o,
  });
  const rec = { decision: 'approve' as const, name: 'Sam Lee', note: 'Balances tie.', at: '2026-11-10T11:20:00', answers: [], back_to: null };
  const runs: Record<string, WorkflowRun> = {
    'run-claims': run('run-claims', 'claims-check', 'Monthly claims check', { unattended: true, folder: 'C:/work/claims-project/studies/monthly/2026-11-17_0900', current_stage: 1,
      stages: [done(0, 'Load the ledger', 'claims'), st(1, 'Match the claims', 'agent', 'running'), st(2, 'Reviewer check', 'review', 'waiting', { checklist: [item('Unmatched lines are explained')] })] }),
    'run-pricing': run('run-pricing', 'pricing', 'Pricing refresh', { folder: 'C:/work/claims-project/studies/pricing/2026-11-17_0830', inputs: { effective_date: '2027-01-01' }, status: 'awaiting_review', current_stage: 3, started_at: '2026-11-17T08:30:00',
      stages: [done(0, 'Load the data', 'pricing'), done(1, 'Fit the reserve factors', 'pricing', 2, 'Use the 2025 triangle'), done(2, 'Prepare the review memo', 'pricing'),
        st(3, 'Pricing sign-off', 'review', 'awaiting_review', { checklist: [item('Trend agrees with last quarter within tolerance'), item('Which memo questions did you resolve?', 'answer')] })] }),
    'run-year-end': run('run-year-end', 'year-end', 'Year-end close', { folder: 'C:/work/claims-project/studies/year-end/2026-11-10_1000', status: 'done', started_at: '2026-11-10T10:00:00', finished_at: '2026-11-10T11:45:00',
      stages: [done(0, 'Roll the balances', 'year-end'), st(1, 'Controller sign-off', 'review', 'done', { review: rec, reviews: [rec] }), done(2, 'Write the close-out note', 'year-end')] }),
    'run-mortality': run('run-mortality', 'mortality', 'Mortality update', { test: true, folder: 'C:/work/claims-project/studies/mortality/test', current_stage: 1, started_at: '2026-11-17T09:10:00',
      stages: [done(0, 'Fit the table', 'mortality'), st(1, 'Compare with the published table', 'agent', 'running'), st(2, 'Review', 'review', 'waiting')] }),
  };
  return { list, runs, n: 0, reviewer: 'Sam Lee', seen: {} };
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const stagesOf = (w: Workflow): WorkflowRunStage[] => w.stages.map(s => ({
  index: s.index, kind: s.kind, title: s.title, status: 'waiting' as const, agent: s.kind === 'agent' ? s.agent : null, agent_display: s.kind === 'agent' ? s.agent_display || s.agent : 'Review',
  result_file: null, result_markdown: null, attempts: [], checklist: s.kind === 'review' ? s.checklist : [], review: null, reviews: [], error: null,
}));
const fromDraft = (d: WorkflowDraft, folder: string, slugName: string): Workflow => wf(slugName, d.name, d.description, d.stages.map(s => (s.kind === 'agent'
  ? agent(s.title, s.agent, s.instruction, s.files)
  : review(s.title, s.checklist))), {
  folder, folder_name: folder === 'd2' ? 'readmissions' : 'claims-project', output_folder: d.output_folder, output_path: d.output_folder, unattended_default: d.unattended_default,
  id: `${folder}/${slugName}`, inputs: d.inputs.map(i => input(i.name, { label: i.label || i.name, kind: i.kind || 'text', required: i.required !== false, default: i.default || '', options: i.options || [], help: i.help || '' })),
  files: d.files.map(f => file(f)), warnings: d.stages.length ? [] : [{ level: 'error', code: 'invalid', message: 'The workflow has no stages.', stage: null, field: 'stages' }],
});

/* The Missions / Incoming side of a run (the header's "Workflows > Missions" block): run_started with the workflow marker,
   step_update per changed stage (a review stage waiting = blocked + waiting_for review), the "needs you" review card and its
   queue_resolved, run_finished. Emits only what changed since the last call for that run. */
export function demoWorkflowMission(s: WfDemoState, r: WorkflowRun, emit: (ev: Ev) => void): void {
  const w = s.list.find(x => x.id === r.workflow_id), sid = r.mission_id || `wf-${r.id}`;
  const mark = { id: r.workflow_id, name: r.workflow_name, run_id: r.id, test: r.test };
  const stat = (x: WorkflowRunStage) => (x.status === 'waiting' ? 'todo' : x.status === 'running' ? 'in_progress' : x.status === 'awaiting_review' ? 'blocked' : x.status);
  const step = (x: WorkflowRunStage) => ({ n: x.index + 1, title: x.title, status: stat(x), agent: null, agent_display: x.kind === 'review' ? 'Review' : x.agent_display, agent_purpose: x.kind === 'review' ? 'reviewing' : 'building', ...(x.status === 'awaiting_review' ? { waiting_for: 'review' } : {}) });
  let seen = s.seen[r.id];
  if (!seen) {
    seen = s.seen[r.id] = { started: true, stages: r.stages.map(x => x.status).join(','), card: null, finished: false };
    emit({ type: 'run_started', session_id: sid, name: `Workflow: ${r.workflow_name}${r.test ? ' (test run)' : ''}`, steps: r.stages.map(step), run: 1, revision: 0, autopilot: r.unattended, auto_answers: r.unattended, workflow: mark });
    emit({ type: 'autopilot', session_id: sid, on: r.unattended }); emit({ type: 'auto_answers', session_id: sid, on: r.unattended });
  } else {
    const before = seen.stages.split(',');
    r.stages.forEach((x, k) => { if (before[k] !== x.status) emit({ type: 'step_update', session_id: sid, n: x.index + 1, status: stat(x), agent_display: x.kind === 'review' ? 'Review' : x.agent_display, ...(x.status === 'awaiting_review' ? { waiting_for: 'review' } : {}) }); });
    seen.stages = r.stages.map(x => x.status).join(',');
  }
  const cur = r.status === 'awaiting_review' ? r.stages.find(x => x.status === 'awaiting_review') : null;
  const card = cur ? `review:${r.id}:${cur.index}` : null;
  if (seen.card && seen.card !== card) emit({ type: 'queue_resolved', id: seen.card, answer: r.status === 'stopped' ? null : 'approve', by: 'user' });
  if (card && card !== seen.card && cur) emit({ type: 'queue_item', id: card, session_id: sid, chat_id: null, kind: 'review', agent: 'Review', agent_id: null, step: cur.index + 1, title: `Sign-off needed: ${cur.title}`, body: `${w?.name || r.workflow_name}: ${cur.title}. Sign off in the Workflows view.`, rec: null, blocking: true, timeout_s: null, expires_at: null, workflow: mark, run_id: r.id, stage: cur.index });
  seen.card = card;
  if (!seen.finished && (r.status === 'done' || r.status === 'failed' || r.status === 'stopped')) {
    seen.finished = true;
    emit({ type: 'run_finished', session_id: sid, status: r.status, report_path: `${r.folder}/run-summary.md`, markdown: `# Run summary

${r.workflow_name}${r.test ? ' (test run)' : ''}: ${r.status}.`, total_cost_usd: 0, planner_cost_usd: 0, workflow: mark });
  }
}

export function demoWorkflowsOn(msg: Ev, s: WfDemoState, emit: (ev: Ev) => void, later: (ms: number, fn: () => void) => void): boolean {
  const list = (error?: string) => emit({ type: 'workflows_list', workflows: clone(s.list), folders: FOLDERS, agents: { d1: AGENTS, d2: AGENTS.slice(0, 2) }, reviewer_name: s.reviewer, ...(error ? { error } : {}) });
  const push = (r: WorkflowRun, error?: string, mission = true) => { emit({ type: 'workflow_run_state', run: clone(r), ...(error ? { error } : {}) }); if (mission) demoWorkflowMission(s, r, emit); };
  const mark = (r: WorkflowRun) => { const w = s.list.find(x => x.id === r.workflow_id); if (w) { w.last_run_id = r.id; w.running_run_id = r.status === 'running' || r.status === 'awaiting_review' ? r.id : null; } };
  /* move a run on: the first waiting stage runs; an agent stage finishes after a moment, a review stops and waits */
  const advance = (r: WorkflowRun) => {
    if (r.status !== 'running') return;
    const i = r.stages.findIndex(x => x.status === 'waiting' || x.status === 'running');
    if (i < 0) { r.status = 'done'; r.current_stage = null; r.finished_at = new Date().toISOString(); mark(r); push(r); list(); return; }
    const x = r.stages[i]; r.current_stage = i;
    if (x.kind === 'review') { x.status = 'awaiting_review'; r.status = 'awaiting_review'; push(r); return; }
    x.status = 'running'; push(r);
    later(1800, () => {
      if (r.status !== 'running' || x.status !== 'running') return;
      const k = x.attempts.length + 1, base = `${r.folder}/${String(i + 1).padStart(2, '0')}-${slug(x.title)}`;
      x.status = 'done'; x.result_file = `${base}${k > 1 ? '-' + k : ''}.md`; x.result_markdown = resultOf(x.title);
      x.attempts.push({ attempt: k, result_file: x.result_file, status: 'done', rejected: false, note: null });
      advance(r);
    });
  };
  switch (msg.type) {
    case 'workflows_get':
      list(); for (const r of Object.values(s.runs)) push(r, undefined, false);
      /* the first time Workflows is opened, the run waiting at its review also shows in Incoming and Missions (kept out of the
         page's first load so the plan demo's sessions stay as they were) */
      if (!msg.quiet && !s.seen['run-pricing']) demoWorkflowMission(s, s.runs['run-pricing'], emit);
      return true;
    case 'workflow_save': {
      const d = msg.workflow as WorkflowDraft, orig = msg.original_id ? s.list.find(x => x.id === msg.original_id) : null;
      if (msg.original_id && !orig) { list('That workflow no longer exists.'); return true; }
      const sl = orig ? orig.slug : slug(d.name);
      const w = fromDraft(d, msg.folder, sl);
      if (orig) { w.running_run_id = orig.running_run_id; w.last_run_id = orig.last_run_id; s.list[s.list.indexOf(orig)] = w; }
      else if (s.list.some(x => x.slug === sl)) { list(`A workflow file called ${sl}.json already exists. Choose another name.`); return true; }
      else s.list.push(w);
      list(); return true;
    }
    case 'workflow_remove': {
      const w = s.list.find(x => x.id === msg.id);
      if (w && w.running_run_id) { list('This workflow is running; stop it first.'); return true; }
      s.list = s.list.filter(x => x.id !== msg.id); list(); return true;
    }
    case 'workflow_run': {
      const w = s.list.find(x => x.id === msg.id); if (!w) return true;
      const refuse = (e: string) => emit({ type: 'workflow_run_state', run: null, workflow_id: w.id, error: e });
      if (!w.can_run) { refuse('This workflow has problems to fix first: ' + w.warnings.filter(x => x.level === 'error').map(x => x.message).join(' ')); return true; }
      if (w.running_run_id) { refuse('This workflow is already running.'); return true; }
      const miss = w.inputs.find(i => i.required && !String((msg.inputs || {})[i.name] || i.default || '').trim());
      if (miss) { refuse(`The input ${miss.label} is required.`); return true; }
      const id = `run-${++s.n}`, inputs: Record<string, string> = {};
      for (const i of w.inputs) inputs[i.name] = String((msg.inputs || {})[i.name] || i.default || '');
      const r: WorkflowRun = { id, workflow_id: w.id, workflow_name: w.name, test: !!msg.test, folder: `${w.output_path}/${msg.test ? 'test' : '2026-11-17_10' + String(s.n).padStart(2, '0')}`, mission_id: `wf-${id}`, inputs, unattended: !!msg.unattended,
        status: 'running', current_stage: 0, started_at: new Date().toISOString(), finished_at: null, summary_file: null, error: null, stages: stagesOf(w) };
      s.runs[id] = r; mark(r); push(r); list(); later(600, () => advance(r)); return true;
    }
    case 'workflow_stop': {
      const r = s.runs[msg.run_id]; if (!r) return true;
      if (r.status !== 'running' && r.status !== 'awaiting_review') { push(r, 'This run is not in progress.'); return true; }
      r.status = 'stopped'; r.error = 'Stopped'; r.finished_at = new Date().toISOString();
      for (const x of r.stages) if (x.status === 'running') { x.status = 'failed'; x.error = 'Stopped'; }
      mark(r); push(r); list(); return true;
    }
    case 'workflow_review': {
      const r = s.runs[msg.run_id]; if (!r) return true;
      const x = r.stages[msg.stage];
      if (!x || x.status !== 'awaiting_review') { push(r, 'This run is not waiting at that review.'); return true; }
      if (!String(msg.name || '').trim()) { push(r, 'Type your name to sign.'); return true; }
      const answers = x.checklist.map((c, k) => ({ text: c.text, kind: c.kind, ticked: !!msg.answers?.[k]?.ticked, answer: String(msg.answers?.[k]?.answer || '') }));
      if (msg.decision === 'approve' && answers.some(a => (a.kind === 'tick' ? !a.ticked : !a.answer.trim()))) { push(r, 'Every checklist item must be ticked or answered before you approve.'); return true; }
      if (msg.decision === 'send_back' && (!String(msg.note || '').trim() || !r.stages.slice(0, msg.stage).some((y, k) => k === msg.back_to && y.kind === 'agent'))) { push(r, 'Sending back needs a note and an earlier agent stage.'); return true; }
      s.reviewer = String(msg.name).trim();
      const record = { decision: msg.decision, name: s.reviewer, note: msg.note || '', at: new Date().toISOString(), answers, back_to: msg.back_to ?? null };
      x.review = record; x.reviews.push(record);
      if (msg.decision === 'approve') { x.status = 'done'; r.status = 'running'; push(r); later(600, () => advance(r)); list(); return true; }
      for (let i = msg.back_to; i < r.stages.length; i++) {
        const y = r.stages[i]; y.status = 'waiting';
        if (y.kind === 'agent') { const last = y.attempts[y.attempts.length - 1]; if (last) { last.rejected = true; last.note = msg.note; } y.result_file = null; y.result_markdown = null; } else y.review = null;
      }
      r.status = 'running'; push(r); later(600, () => advance(r)); list(); return true;
    }
  }
  return false;
}
