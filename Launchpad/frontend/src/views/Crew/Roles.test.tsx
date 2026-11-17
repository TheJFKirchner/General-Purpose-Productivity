// @vitest-environment happy-dom
/* Crew: "Used but not defined" and the Role Review screen, against the in-page demo (four made-up roles). */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, dispatch } from '../../store';
import { useDemoApp, step, q, qa, click, byText, sentOf } from '../../test/demoApp';

useDemoApp();

const row = (role: string) => q(`.role[data-role="${role}"]`)!;
const rowBtn = (role: string, label: string) => [...row(role).querySelectorAll('button')].find(b => b.textContent?.trim() === label)!;
const openCrew = async () => { await act(async () => { actions.setView('crew'); }); await step(1_000); };

it('the section lists the roles the server shows, with uses, last used, skills, folders and markers; one-use roles are not listed', async () => {
  await openCrew();
  expect(qa('.role').map(r => r.getAttribute('data-role'))).toEqual(['data-migrator', 'frontend-dev', 'copy-editor']);
  const fd = row('frontend-dev');
  expect(fd.querySelector('.role-uses')?.textContent).toBe('4 uses');
  expect(fd.querySelector('.role-meta')?.textContent).toMatch(/last used \d+[smh] ago/);
  expect(fd.querySelector('.chip.skill')?.textContent).toBe('claims-glossary');
  expect(fd.textContent).toContain('claims-project');
  expect(fd.textContent).toContain('1 sent back');
  expect(row('data-migrator').textContent).toContain('1 failed');
  expect(row('copy-editor').textContent).toContain('1 blocked');
  expect(q('#usedRoles .cnt')?.textContent).toBe('3');
  expect(rowBtn('frontend-dev', 'Review').getAttribute('aria-label')).toBe('Review the role frontend-dev');
});

it('the empty state says what will appear; the list refreshes when roles_list changes', async () => {
  await openCrew();
  await act(async () => { dispatch({ type: 'roles_list', threshold: 2, resurface_uses: 5, entries: [] } as never); });
  expect(qa('.role')).toHaveLength(0);
  expect(q('#usedRolesEmpty')?.textContent).toMatch(/shows up here once it has been used 2 times and no agent defines it/);
});

it('dismiss and merge send their messages; merge needs a confirm and folds one role into another', async () => {
  await openCrew();
  await click(rowBtn('copy-editor', 'Dismiss'));
  expect(sentOf('role_dismiss')).toEqual([{ type: 'role_dismiss', role: 'copy-editor' }]);
  await step(500);
  expect(qa('.role').map(r => r.getAttribute('data-role'))).toEqual(['data-migrator', 'frontend-dev']);
  await click(rowBtn('data-migrator', 'Merge'));
  expect(sentOf('role_merge')).toHaveLength(0);                                   // opening the merge asks first
  const pick = q<HTMLSelectElement>('#merge-data-migrator')!;
  expect(pick.value).toBe('frontend-dev');
  expect(pick.labels?.[0]?.textContent).toContain('into');                         // the drop-down has its label
  expect(pick.getAttribute('aria-label')).toBe('Merge data-migrator into');
  await click(byText('.role-merge button', 'Confirm merge'));
  expect(sentOf('role_merge')).toEqual([{ type: 'role_merge', role: 'data-migrator', into: 'frontend-dev' }]);
  await step(500);
  expect(qa('.role').map(r => r.getAttribute('data-role'))).toEqual(['frontend-dev']);
  expect(row('frontend-dev').querySelector('.role-uses')?.textContent).toBe('7 uses');
});

it('Review shows progress, then the five tests in order with the verdict, cost and three unmarked decision buttons; Keep sends review_decide and the role leaves', async () => {
  await openCrew();
  await click(rowBtn('frontend-dev', 'Review'));
  expect(sentOf('review_start')).toEqual([{ type: 'review_start', role: 'frontend-dev' }]);
  await step(1_000);
  expect(q('#roleDetail h2')?.textContent).toBe('Review: frontend-dev');
  expect(q('.rv-progress')?.textContent).toMatch(/Reading the tally: 4 recorded uses/);
  expect(qa('.rv-test')).toHaveLength(0);
  await step(3_000);
  expect(qa('.rv-test').map(t => t.getAttribute('data-test'))).toEqual(['value', 'logic', 'history', 'fixes', 'independent']);
  expect(qa('.rv-test h4').map(h => h.textContent)).toEqual(['Clear value', 'Logic beyond the skill', 'Clear usage history', 'Mistakes or issues it would fix', 'Independent view: is a subagent the right fix?']);
  expect(q('.rv-test[data-test="history"]')?.textContent).toContain('Moderate evidence');
  expect(q('.rv-test[data-test="history"] .rv-evidence')?.textContent).toContain('sent back after run 1');
  expect(q('.rv-verdict')?.textContent).toContain('Keep as skill + Builder');
  expect(q('#rvSkillH')?.textContent).toContain('What the skill should cover');
  expect(q('.rv-cost')?.textContent).toContain('$0.05');                          // usd() of 0.0487
  /* three decisions, the reviewer's marked as a recommendation, none pressed */
  const buttons = qa<HTMLButtonElement>('.rv-buttons button');
  expect(buttons.map(b => b.id)).toEqual(['decide-define', 'decide-keep', 'decide-not_yet']);
  expect(buttons.some(b => b.hasAttribute('aria-pressed'))).toBe(false);
  expect(buttons.every(b => b.className === buttons[0].className)).toBe(true);     // all three in the same unpressed style
  expect(buttons[1].getAttribute('aria-label')).toBe("Keep as skill + Builder (the reviewer's recommendation)");
  expect(qa('.rv-rec-tag').map(t => t.textContent)).toEqual(["Reviewer's recommendation"]);
  expect(buttons[1].closest('.rv-choice')?.querySelector('.rv-rec-tag')).toBeTruthy();
  await click(q('#decide-keep'));
  expect(sentOf('review_decide')).toEqual([{ type: 'review_decide', role: 'frontend-dev', decision: 'keep' }]);
  await step(500);
  expect(q('.rv-decided')?.textContent).toContain('Decision: Keep as skill + Builder');
  expect(q('.rv-decided')?.textContent).toMatch(/comes back after 5 more uses, or sooner if a step under it fails, is blocked or is sent back/);
  await click(q('#roleBack'));
  expect(qa('.role').map(r => r.getAttribute('data-role'))).toEqual(['data-migrator', 'copy-editor']);
});

it('Not yet: the role leaves with the note, no agent is drafted', async () => {
  await openCrew();
  await click(rowBtn('copy-editor', 'Review'));
  await step(4_500);
  expect(q('.rv-verdict')?.textContent).toContain('Not yet');
  expect(q('.rv-reason')?.textContent).toMatch(/thin/);
  await click(q('#decide-not_yet'));
  await step(500);
  expect(sentOf('review_decide')[0]).toMatchObject({ role: 'copy-editor', decision: 'not_yet' });
  expect(sentOf('agent_draft')).toHaveLength(0);
  expect(q('.rv-decided')?.textContent).toContain('Not yet');
  expect(qa('.role').map(r => r.getAttribute('data-role'))).not.toContain('copy-editor');
});

it('a reviewer question shows inside the review and in Incoming (labelled with the role), answers in place, then define drafts, edits and saves with the role', async () => {
  await openCrew();
  await click(rowBtn('data-migrator', 'Review'));
  await step(3_000);
  const inReview = q('.rv-cards .item')!;
  expect(inReview).toBeTruthy();
  expect(inReview.querySelector('.chip.role-chip')?.textContent).toBe('data-migrator');
  expect(inReview.textContent).toContain('row-count check');
  expect(q('.rv-progress')?.textContent).toMatch(/question card is waiting/);
  const inIncoming = q('#queue .item .chip.role-chip');                                // reachable from Incoming too, with the role
  expect(inIncoming?.textContent).toBe('data-migrator');
  expect(inIncoming?.closest('.item')?.textContent).toContain('Open review of data-migrator');
  /* answer in place */
  await click(qa('.rv-cards .pill').find(b => b.textContent?.startsWith('Yes')));
  expect(sentOf('queue_response').at(-1)).toMatchObject({ answer: 'Yes' });
  await step(3_000);
  expect(q('.rv-test[data-test="logic"]')?.textContent).toContain('you said: Yes');
  expect(q('.rv-verdict')?.textContent).toContain('Define an agent');
  /* define: decision first, then the draft with the role */
  await click(q('#decide-define'));
  expect(sentOf('review_decide').at(-1)).toMatchObject({ role: 'data-migrator', decision: 'define' });
  await step(300);
  expect(sentOf('agent_draft').at(-1)).toMatchObject({ type: 'agent_draft', text: '', role: 'data-migrator' });
  await step(2_000);
  const form = q('.agent-form')!;
  expect(form).toBeTruthy();
  expect(form.querySelector('h2')?.textContent).toBe('Define an agent');
  expect(q<HTMLInputElement>('#afName')!.value).toBe('data-migrator');
  expect(q<HTMLTextAreaElement>('#afInstr')!.value).toContain('Count rows before and after');
  expect(q('#afDraftCost')?.textContent).toMatch(/Drafting cost <\$0\.01/);
  await click(q('#afSave'));
  expect(sentOf('agent_create').at(-1)).toMatchObject({ type: 'agent_create', role: 'data-migrator', fields: { name: 'data-migrator', purpose: 'building' } });
  await step(2_000);
  expect(q('.agent-form')).toBeNull();
  expect(q('.rv-decided')?.textContent).toContain('Agent data-migrator saved');
  expect(q('.rv-decided')?.textContent).toContain('.claude/agent-cases/data-migrator.md');
  expect(q('.rv-decided')?.textContent).not.toMatch(/[A-Za-z]:[\\/]/);              // a relative path, never a machine path
  await click(q('#roleBack'));
  expect(qa('.role').map(r => r.getAttribute('data-role'))).not.toContain('data-migrator');
  expect(q('.hero[data-name="data-migrator"]')?.getAttribute('data-purpose')).toBe('building');   // in its purpose section
});

it('a review that fails shows a plain message and the role can be reviewed again', async () => {
  await openCrew();
  await click(rowBtn('frontend-dev', 'Review'));
  await step(500);
  await act(async () => { dispatch({ type: 'review_failed', review_id: 'x', role: 'frontend-dev', error: 'The engine stopped.' } as never); });
  expect(q('#roleDetail .warn')?.textContent).toContain('The engine stopped.');
  expect(q('#roleDetail')?.textContent).toContain('still in the list');
  await act(async () => { dispatch({ type: 'review_refused', role: 'frontend-dev', review_id: null, error: 'There is no role called frontend-dev in the tally.' } as never); });
  expect(q('#roleDetail .warn')?.textContent).toContain('no role called');
  await click(q('#roleRetry'));
  expect(sentOf('review_start')).toHaveLength(2);
});

it('the plan card shows a role chip on the step that carries one, with a tooltip saying it runs on the Builder', async () => {
  await act(async () => {
    dispatch({ type: 'plan_draft', session_id: 'S-C', path: 'plans/x/plan.md', markdown: '# X', revision: 9, previous_runs: 0,
      steps: [{ n: 1, title: 'Plain', agent: null, agent_display: 'Builder' }, { n: 2, title: 'Tabs', agent: null, agent_display: 'Builder', role: 'frontend-dev' }] } as never);
  });
  const chips = qa('.plancard .steps .chip.role-chip');
  expect(chips).toHaveLength(1);
  expect(chips[0].textContent).toBe('Role: frontend-dev');
  expect(chips[0].getAttribute('data-tip')).toBe('text:This step runs on the Builder under the role name frontend-dev');
  expect(chips[0].closest('li')?.querySelector('.n')?.textContent).toBe('2');
});

it('Settings lists the reviewer model beside the other model settings', async () => {
  await act(async () => { actions.openSettings(); });
  await step(500);
  expect(q('label[for="set-reviewer_model"]')?.textContent).toBe('Role Reviewer model');
  expect(q<HTMLInputElement>('#set-reviewer_model')?.value).toBe('sonnet');
});

it('Settings shows the CLI settings with the app wording and the CLI display label, never the raw id', async () => {
  await act(async () => { actions.openSettings(); });
  await step(500);
  expect(q('label[for="set-planner_harness"]')?.textContent).toBe('Planner CLI (new plans)');
  const sel = q<HTMLSelectElement>('#set-planner_harness');
  expect(sel?.value).toBe('claude');
  expect(sel?.selectedOptions[0]?.textContent).toBe('Claude');                     // the CLI's display label, not the raw id
  expect(q('#setVals')?.textContent).not.toMatch(/harness/i);
  expect(q('#setVals')?.textContent).not.toContain('Pilot harness');
});
