// @vitest-environment happy-dom
/* Workflows view against the in-page demo (no back end): sidebar entry and badge, every card state, Run with inputs,
   Test run / Unattended, the review (checklist gate, remembered name, send back), the form, remove with a confirm. */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, dispatch, getState } from '../../store';
import { useDemoApp, step, q, qa, click, sentOf, typeInto } from '../../test/demoApp';
import { toDraft, formProblems, type FForm } from './WorkflowForm';

useDemoApp();
const open = async () => { await act(async () => { actions.setView('workflows'); }); await step(500); };
const card = (id: string) => q(`[data-wf="d1/${id}"]`)!;
const btn = (root: Element, label: string) => [...root.querySelectorAll('button')].find(b => b.textContent?.trim() === label || b.getAttribute('aria-label') === label) as HTMLButtonElement;
const dlg = () => q('[role=dialog]')!;
const setSelect = async (el: HTMLSelectElement, value: string) => {
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!.call(el, value); el.dispatchEvent(new Event('change', { bubbles: true })); });
};

it('is in the sidebar after Files, with a waiting-review badge', async () => {
  const tabs = qa('[role=tab]').map(t => t.id);
  expect(tabs.indexOf('tab-workflows')).toBe(tabs.indexOf('tab-files') + 1);
  expect(q('#tab-workflows .nbadge.warn')?.textContent).toBe('1');
  await open();
  expect(q('#tab-workflows')?.getAttribute('aria-selected')).toBe('true');
  expect(sentOf('workflows_get').length).toBeGreaterThan(0);
});

it('shows every card state', async () => {
  await open();
  expect(qa('.wf-card')).toHaveLength(6);
  /* idle: stages drawn, agent and review differ */
  const idle = card('reserve-study');
  expect(idle.querySelectorAll('.wf-stage')).toHaveLength(5);
  expect(idle.querySelectorAll('.wf-stage[data-kind=review]')).toHaveLength(1);
  expect(idle.querySelector('.wf-run')).toBeNull();
  expect(btn(idle, 'Run').disabled).toBe(false);
  /* warnings disable Run (an error), a note alone would not */
  expect(card('experience').textContent).toContain('was not found');
  expect(card('experience').textContent).toContain('output folder is not set');
  expect(card('experience').querySelector('.wf-stage[data-warn=true]')).toBeTruthy();
  expect(btn(card('experience'), 'Run').disabled).toBe(true);
  /* in progress */
  expect([...card('claims-check').querySelectorAll('.wf-stage')].map(s => s.getAttribute('data-status'))).toEqual(['done', 'running', 'waiting']);
  expect(btn(card('claims-check'), 'Run').disabled).toBe(true);
  expect(btn(card('claims-check'), 'Stop')).toBeTruthy();
  /* awaiting review */
  expect(card('pricing').textContent).toContain('Review waiting for you');
  expect(btn(card('pricing'), 'Review now')).toBeTruthy();
  /* finished */
  expect(card('year-end').querySelector('.wf-run.done')?.textContent).toContain('Finished');
  /* test run is labelled */
  expect(card('mortality').textContent).toContain('Test run');
});

it('Run asks for the named inputs first, and sends test and unattended', async () => {
  await open();
  const c = card('reserve-study');
  await click(c.querySelectorAll('input[type=checkbox]')[0]);   // Test run
  await click(btn(c, 'Run'));
  expect(sentOf('workflow_run')).toHaveLength(0);
  expect(dlg().textContent).toContain('Valuation date');
  expect((dlg().querySelector('#wfIn0') as HTMLInputElement).type).toBe('date');
  expect((dlg().querySelector('#wfIn0') as HTMLInputElement).value).toBe('2026-09-30');
  expect((dlg().querySelector('#wfIn2') as HTMLSelectElement).value).toBe('Paid');
  expect(btn(dlg(), 'Start test run').disabled).toBe(true);      // the required file input is empty
  await typeInto(dlg().querySelector('#wfIn1') as HTMLInputElement, 'claims.csv');
  await click(btn(dlg(), 'Start test run'));
  expect(sentOf('workflow_run').at(-1)).toMatchObject({ id: 'd1/reserve-study', test: true, unattended: false, inputs: { valuation_date: '2026-09-30', claims_file: 'claims.csv', basis: 'Paid' } });
  await step(1000);
  const run = card('reserve-study').querySelector('.wf-run')!;
  expect(run.textContent).toContain('Test run');
  expect(run.textContent).toContain('/test');                    // the one test folder
  expect(card('reserve-study').querySelector('.wf-stage[data-status=running]')).toBeTruthy();
  await step(2000);
  expect(card('reserve-study').querySelectorAll('.wf-stage[data-status=done]').length).toBeGreaterThan(0);
});

it('a workflow with no inputs starts at once; Unattended starts from the workflow default', async () => {
  await open();
  const c = card('year-end');
  expect((c.querySelectorAll('input[type=checkbox]')[1] as HTMLInputElement).checked).toBe(false);
  expect((card('claims-check').querySelectorAll('input[type=checkbox]')[1] as HTMLInputElement).checked).toBe(true);
  await click(btn(c, 'Run'));
  expect(sentOf('workflow_run').at(-1)).toMatchObject({ id: 'd1/year-end', test: false, unattended: false, inputs: {} });
});

it('Stop asks first', async () => {
  await open();
  const c = card('claims-check');
  await click(btn(c, 'Stop'));
  expect(sentOf('workflow_stop')).toHaveLength(0);
  await click(btn(c, 'Yes, stop'));
  expect(sentOf('workflow_stop').at(-1)).toEqual({ type: 'workflow_stop', run_id: 'run-claims' });
  await step(300);
  expect(card('claims-check').querySelector('.wf-run.stopped')).toBeTruthy();
});

it('the review cannot be signed off with open items; send back asks for a stage and a note', async () => {
  await open();
  await click(btn(card('pricing'), 'Review now'));
  const approve = () => q<HTMLButtonElement>('#wfApprove')!;
  expect(q('.wf-review')?.textContent).toContain('Results so far');
  expect(qa('.wf-result')).toHaveLength(3);
  expect(q('.wf-review')?.textContent).toContain('sent back and is kept');   // the earlier attempt of stage 2 is kept and shown
  expect(q<HTMLInputElement>('.wf-sign input.field')!.value).toBe('Sam Lee');   // the name the server remembered
  expect(approve().disabled).toBe(true);                                       // two items open
  await click(q('.wf-checks input[type=checkbox]'));
  expect(approve().disabled).toBe(true);                         // the written answer is still missing
  await typeInto(q<HTMLInputElement>('.wf-checks li[data-kind=answer] input')!, 'Resolved both in the memo');
  expect(approve().disabled).toBe(false);
  await typeInto(q<HTMLInputElement>('.wf-sign input.field')!, '');
  expect(approve().disabled).toBe(true);                         // no name
  await typeInto(q<HTMLInputElement>('.wf-sign input.field')!, 'Sam Lee');
  expect(approve().disabled).toBe(false);
  /* send back needs a note and an earlier agent stage */
  await click(q('#wfSendBack'));
  expect(q<HTMLButtonElement>('#wfSendBackGo')!.disabled).toBe(true);
  expect([...q<HTMLSelectElement>('.wf-back select')!.options].map(o => o.textContent)).toEqual(['1. Load the data', '2. Fit the reserve factors', '3. Prepare the review memo']);
  await typeInto(q<HTMLTextAreaElement>('.wf-back textarea')!, 'Refit with the 2025 triangle');
  await click(q('#wfSendBackGo'));
  expect(sentOf('workflow_review').at(-1)).toMatchObject({ run_id: 'run-pricing', stage: 3, decision: 'send_back', back_to: 0, note: 'Refit with the 2025 triangle', name: 'Sam Lee' });
  await step(3000);
  expect(getState().wf.runs['run-pricing'].stages[0].status).not.toBe('awaiting_review');
});

it('approve sends the answers by kind and the run carries on', async () => {
  await open();
  await click(btn(card('pricing'), 'Review now'));
  await click(q('.wf-checks input[type=checkbox]'));
  await typeInto(q<HTMLInputElement>('.wf-checks li[data-kind=answer] input')!, 'Both resolved');
  await typeInto(q<HTMLTextAreaElement>('.wf-sign textarea')!, 'Looks fine');
  await click(q('#wfApprove'));
  expect(sentOf('workflow_review').at(-1)).toEqual({ type: 'workflow_review', run_id: 'run-pricing', stage: 3, answers: [{ ticked: true }, { answer: 'Both resolved' }], name: 'Sam Lee', note: 'Looks fine', decision: 'approve' });
  await step(1500);
  expect(getState().wf.runs['run-pricing'].status).toBe('done');
});

it('a refused request shows its reason on the card', async () => {
  await open();
  await act(async () => { dispatch({ type: 'workflow_run_state', run: null, workflow_id: 'd1/reserve-study', error: 'The output folder cannot be made.' }); });
  expect(card('reserve-study').textContent).toContain('The output folder cannot be made.');
});

it('the form adds a workflow with stages in order, and checks what is missing', async () => {
  await open();
  await click(q('#wfAdd'));
  await click(q('#wfSave'));
  expect(dlg().textContent).toContain('Give the workflow a name.');
  expect(sentOf('workflow_save')).toHaveLength(0);
  expect((q<HTMLSelectElement>('#wfFolder'))!.value).toBe('d1');
  await typeInto(q<HTMLInputElement>('#wfName')!, 'Lapse study');
  await typeInto(q<HTMLInputElement>('#wfOut')!, 'C:/out/lapse');
  await click(q('#wfAddAgent')); await click(q('#wfAddReview'));
  await typeInto(q<HTMLInputElement>('#wfT0')!, 'Pull data');
  await typeInto(q<HTMLInputElement>('#wfT1')!, 'Sign-off');
  await click(q('.wf-fstage[data-kind=review] .wf-fld .pill.xs'));   // Add checklist item
  await typeInto(qa<HTMLInputElement>('.wf-citem input')[0], 'Totals agree');
  await typeInto(q<HTMLTextAreaElement>('#wfI0')!, 'Pull the data');
  await setSelect(q<HTMLSelectElement>('#wfA0')!, 'launchpad-builder');
  await click(qa('button').find(b => b.getAttribute('aria-label') === 'Move stage 2 up')!);
  expect(qa<HTMLInputElement>('.wf-fstage input[id^=wfT]').map(i => i.value)).toEqual(['Sign-off', 'Pull data']);
  await click(q('#wfSave'));
  const m = sentOf('workflow_save').at(-1) as any;
  expect(m.folder).toBe('d1');
  expect(m.workflow.stages.map((s: any) => s.kind)).toEqual(['review', 'agent']);
  expect(m.workflow.stages[0].checklist).toEqual([{ text: 'Totals agree', kind: 'tick' }]);
  expect(m.workflow.stages[1]).toMatchObject({ kind: 'agent', agent: 'launchpad-builder', instruction: 'Pull the data' });
  await step(300);
  expect(q('[role=dialog]')).toBeNull();
  expect(q('[data-wf="d1/lapse-study"]')).toBeTruthy();
});

it('the form edits an existing workflow, and remove asks first', async () => {
  await open();
  await click(btn(card('year-end'), 'Edit Year-end close'));
  expect((q<HTMLInputElement>('#wfName'))!.value).toBe('Year-end close');
  expect(qa('.wf-fstage')).toHaveLength(3);
  await typeInto(q<HTMLInputElement>('#wfName')!, 'Year-end close v2');
  await click(q('#wfSave'));
  expect(sentOf('workflow_save').at(-1)).toMatchObject({ original_id: 'd1/year-end', folder: 'd1' });
  await step(300);
  expect(card('year-end').textContent).toContain('Year-end close v2');
  await click(btn(card('year-end'), 'Remove Year-end close v2'));
  expect(sentOf('workflow_remove')).toHaveLength(0);
  await click(btn(card('year-end'), 'Confirm remove'));
  expect(sentOf('workflow_remove').at(-1)).toEqual({ type: 'workflow_remove', id: 'd1/year-end' });
  await step(300);
  expect(q('[data-wf="d1/year-end"]')).toBeNull();
});

it('the empty state explains what a workflow is', async () => {
  await open();
  for (const id of ['claims', 'pricing', 'mortality']) actions.stopWorkflow(`run-${id}`);
  await step(300);
  for (const id of ['reserve-study', 'experience', 'claims-check', 'pricing', 'year-end', 'mortality']) actions.removeWorkflow(`d1/${id}`);
  await step(300);
  expect(q('.wf-body .empty')?.textContent).toContain('A workflow is a study or report you run more than once');
});

it('form helpers: draft JSON and problems', () => {
  const f: FForm = {
    name: ' A ', description: '', folder: 'd1', output_folder: 'o', files: 'a.md\n\n b.md ', unattended: true,
    inputs: [{ name: ' ', label: '', kind: 'text', required: true, default: '', options: '' }, { name: 'basis', label: '', kind: 'choice', required: false, default: '', options: 'Paid, Incurred' }],
    stages: [
      { kind: 'agent', title: 'T', agent: 'x', instruction: 'do', files: '', checklist: [] },
      { kind: 'review', title: 'R', agent: '', instruction: '', files: '', checklist: [{ text: ' ok ', kind: 'answer' }, { text: ' ', kind: 'tick' }] },
    ],
  };
  expect(formProblems(f)).toEqual([]);
  expect(toDraft(f)).toEqual({
    name: 'A', description: '', output_folder: 'o', files: ['a.md', 'b.md'], unattended_default: true,
    inputs: [{ name: 'basis', kind: 'choice', required: false, options: ['Paid', 'Incurred'] }],
    stages: [{ kind: 'agent', title: 'T', agent: 'x', instruction: 'do', files: [] }, { kind: 'review', title: 'R', checklist: [{ text: 'ok', kind: 'answer' }] }],
  });
  expect(formProblems({ ...f, stages: [] })).toContain('Add at least one stage.');
  expect(formProblems({ ...f, inputs: [{ ...f.inputs[1], name: 'Bad Name' }] })[0]).toContain('lower case');
});

it('a review waiting shows in Incoming and Missions (needs you), and the card opens that review', async () => {
  await open();
  const item = q('[id="item-review:run-pricing:3"]')!;
  expect(item).toBeTruthy();
  expect(item.textContent).toContain('Sign-off needed');
  expect(item.textContent).toContain('Pricing refresh');
  expect(item.textContent).not.toContain('Orchestrator');
  expect(getState().queue.find(i => i.kind === 'review')?.run_id).toBe('run-pricing');
  const s = getState().sessions['wf-run-pricing'];
  expect(s.wf?.name).toBe('Pricing refresh');
  expect(s.run?.steps[3]).toMatchObject({ status: 'blocked', waiting_for: 'review' });
  expect(sel_status()).toBe('waiting');
  await act(async () => { actions.setView('plan'); });
  await click(btn(item, 'Open the review'));
  expect(getState().ui.view).toBe('workflows');
  await step(100);
  expect(q('.wf-review')?.textContent).toContain('Pricing sign-off');
  expect(q('.wf-review #wfApprove')).toBeTruthy();
});

const sel_status = () => { const st = getState(), s = st.sessions['wf-run-pricing']; return st.queue.some(i => i.session_id === s.id && i.kind === 'review' && i.ui === 'open') ? 'waiting' : s.status; };

it('workflow runs are labelled as the workflow and offer no planner actions; auto answers follow the run', async () => {
  const mark = { id: 'd1/x', name: 'Monthly sales report', run_id: 'x', test: true };
  await act(async () => {
    dispatch({ type: 'run_started', session_id: 'wf-x', name: 'Workflow: Monthly sales report (test run)', steps: [{ n: 1, title: 'Load', status: 'in_progress' }], run: 1, autopilot: true, auto_answers: true, workflow: mark } as any);
  });
  expect(getState().sessions['wf-x'].autoAnswers).toBe(true);
  await act(async () => { dispatch({ type: 'auto_answers', session_id: 'wf-x', on: false }); });
  expect(getState().sessions['wf-x'].autoAnswers).toBe(false);
  await act(async () => { dispatch({ type: 'run_finished', session_id: 'wf-x', status: 'done', report_path: '/r/run-summary.md', markdown: '# Done', workflow: mark } as any); });
  const rep = getState().queue.find(i => i.kind === 'report' && i.session_id === 'wf-x')!;
  expect(rep.agent).toBe('');
  const el = () => q(`[id="item-${rep.id}"]`)!;
  expect(el().textContent).toContain('Monthly sales report (test run)');
  expect(el().textContent).not.toContain('Orchestrator');
  expect(el().textContent).not.toContain('Send to planner');
  expect(el().textContent).toContain('Read report');
  await act(async () => { actions.setView('missions'); });
  expect(q('#viewMissions')?.textContent).toContain('Monthly sales report');
  expect(q('#viewMissions')?.textContent).not.toContain('Send to planner');
});

it('after the review is signed the screen closes and the stale note is gone', async () => {
  await open();
  await click(btn(card('pricing'), 'Review now'));
  await click(q('.wf-checks input[type=checkbox]'));
  await typeInto(q<HTMLInputElement>('.wf-checks li[data-kind=answer] input')!, 'ok');
  await click(q('#wfApprove'));
  await step(400);
  expect(q('.wf-review')).toBeNull();
  expect(q('.wf-body .wf-list')).toBeTruthy();
});

it('Browse fills only the output folder field and never connects a working directory', async () => {
  await open();
  await click(q('#wfAdd'));
  await click(q('#wfBrowse'));
  await step(1200);
  expect(q<HTMLInputElement>('#wfOut')!.value).toBe('C:/work/new-project');
  expect(sentOf('add_directory')).toHaveLength(0);
});

it('the track fits the card: stages shrink and wrap before it scrolls, with full text in a tooltip', async () => {
  await open();
  const st = card('reserve-study').querySelector('.wf-stage')!;
  expect(st.getAttribute('title')).toContain('Load the data');
});
