// @vitest-environment happy-dom
/* Crew against the in-page demo: hero cards, definition reader, Add an agent dialog (draft, checks, save, remove). */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, dispatch } from '../../store';
import { useDemoApp, step, q, qa, doc, click, byText, sentOf, typeInto } from '../../test/demoApp';

useDemoApp();

it('Crew: hero cards grouped by purpose, live use counts, filter, detail with promotion criteria and back', async () => {
  await act(async () => { actions.setView('crew'); });
  await step(1_000);
  expect(sentOf('get_crew').length).toBeGreaterThanOrEqual(1);
  const cards = qa('#crewAgents .hero:not(.add)');
  expect(cards).toHaveLength(8);
  expect(q('#crewSum')?.textContent).toMatch(/6 built in, 2 from claims-project/);
  expect(qa('.pgroup').map(g => g.getAttribute('data-purpose'))).toEqual(['planning', 'exploring', 'building', 'reviewing']);
  /* built-ins and folder agents look different; each card says its purpose in words */
  const rev = q('.hero[data-name="sql-reviewer"]')!;
  expect(rev.classList.contains('folder')).toBe(true);
  expect(rev.querySelector('.ptag')?.textContent).toBe('Reviewing');
  expect(rev.querySelector('.src')?.textContent).toBe('claims-project');
  expect(q('.hero[data-name="launchpad-builder"] .src')?.textContent).toBe('Built in');
  expect(q('.hero[data-name="sql-builder"] .chip.warnc')).toBeTruthy();
  /* live counts */
  const before = Number(q('.hero[data-name="launchpad-builder"] .hero-uses b')!.textContent!.replace(/,/g, ''));
  await act(async () => { dispatch({ type: 'agent_uses', name: 'launchpad-builder', uses: before + 5 } as never); });
  expect(q('.hero[data-name="launchpad-builder"] .hero-uses b')!.textContent).toBe(String(before + 5));
  /* purpose filter */
  await click(byText('.crew-filter button', 'Reviewing1'));
  expect(qa('#crewAgents .hero:not(.add)').map(c => c.getAttribute('data-name'))).toEqual(['sql-reviewer']);
  await click(byText('.crew-filter button', `All8`));
  /* detail and back (focus returns to the card) */
  await click(q('.hero[data-name="launchpad-planner"]'));
  expect(q('#crewDetail')?.textContent).toContain('Promotion');
  expect(doc().activeElement?.tagName).toBe('H2');
  expect(q('#crewRemove')).toBeNull();                                      // built-ins cannot be removed
  await click(q('#crewBack'));
  expect(doc().activeElement?.getAttribute('data-name')).toBe('launchpad-planner');
  await typeInto(q<HTMLInputElement>('#crewSearch')!, 'zzz-nothing');
  expect(q('#crewAgents')?.textContent).toContain('No agent matches');
});

it('Crew: Draft for me fills the form; page checks and server problems show inline; save adds a card; remove takes two clicks', async () => {
  await act(async () => { actions.setView('crew'); });
  await step(1_000);
  await click(q('#crewAdd'));
  const dlg = q('.agent-form')!;
  expect(dlg).toBeTruthy();
  /* Save with nothing: the page's own checks, inline */
  await click(q('#afSave'));
  expect(sentOf('agent_create')).toHaveLength(0);
  expect(q('#af-err-name')?.textContent).toContain('Give the agent a name');
  expect(q('#afName')?.getAttribute('aria-invalid')).toBe('true');
  /* Draft for me */
  await typeInto(q<HTMLTextAreaElement>('#afDraftText')!, 'checks new SQL for NULL handling before a step is done');
  await click(q('#afDraft'));
  expect(sentOf('agent_draft').at(-1)).toEqual({ type: 'agent_draft', dir_id: 'd1', text: 'checks new SQL for NULL handling before a step is done' });
  expect(q('#afDraft')?.textContent).toBe('Drafting…');
  await step(2_000);
  const name = q<HTMLInputElement>('#afName')!.value;
  expect(name).toMatch(/reviewer$/);
  expect(q<HTMLInputElement>('input[name="afPurpose"][value="reviewing"]')!.checked).toBe(true);
  expect(q<HTMLTextAreaElement>('#afInstr')!.value).toContain('#');
  /* read-only purpose: write tools are not offered */
  expect(qa<HTMLLabelElement>('.af-tool').find(l => l.textContent === 'Write')!.querySelector('input')!.disabled).toBe(true);
  /* a server problem (reserved name) lands under the name field */
  await typeInto(q<HTMLInputElement>('#afName')!, 'launchpad-helper');
  await click(q('#afSave'));
  await step(1_000);
  expect(sentOf('agent_create')).toHaveLength(1);
  expect(q('.agent-form .warn')?.textContent).toContain('Not saved');
  expect(q('#af-err-name')?.textContent).toContain('kept for Launchpad');
  /* fix it and save: the dialog closes, the new card is there */
  await typeInto(q<HTMLInputElement>('#afName')!, 'null-reviewer');
  expect(q('#af-err-name')).toBeNull();
  await click(q('#afSave'));
  await step(1_500);
  expect(sentOf('agent_create').at(-1)).toMatchObject({ type: 'agent_create', dir_id: 'd1', fields: { name: 'null-reviewer', purpose: 'reviewing' } });
  expect(q('.agent-form')).toBeNull();
  expect(q('.hero[data-name="null-reviewer"]')).toBeTruthy();
  /* remove it: two clicks, then agent_remove, then the card is gone */
  await click(q('.hero[data-name="null-reviewer"]'));
  await click(q('#crewRemove'));
  expect(sentOf('agent_remove')).toHaveLength(0);
  expect(q('#crewRemove')?.textContent).toBe('Confirm remove');
  await click(q('#crewRemove'));
  expect(sentOf('agent_remove').at(-1)).toEqual({ type: 'agent_remove', dir_id: 'd1', name: 'null-reviewer' });
  await step(1_000);
  expect(q('#crewDetail')).toBeNull();
  expect(q('.hero[data-name="null-reviewer"]')).toBeNull();
});

it('Crew: Skills section per agent (Planner all, others a checklist, the CLI chat handled by the harness)', async () => {
  await act(async () => { actions.setView('crew'); });
  await step(1_000);
  /* Planner: all skills */
  await click(q('.hero[data-name="launchpad-planner"]'));
  expect(byText('#crewDetail .seg button', 'All skills')!.getAttribute('aria-pressed')).toBe('true');
  expect(qa('#crewDetail .skl li:not(.gone)').map(li => li.querySelector('code')!.textContent)).toEqual(['claims-glossary', 'sql-style']);
  await click(q('#crewBack'));
  /* Builder: none ticked; ticking one sends set_agent_skills */
  await click(q('.hero[data-name="launchpad-builder"]'));
  expect(byText('#crewDetail .seg button', 'Choose')!.getAttribute('aria-pressed')).toBe('true');
  const boxes = qa<HTMLInputElement>('#crewDetail .skl li:not(.gone) input');
  expect(boxes.every(b => !b.checked)).toBe(true);
  await click(boxes[1]);
  expect(sentOf('set_agent_skills').at(-1)).toEqual({ type: 'set_agent_skills', name: 'launchpad-builder', skills: ['sql-style'], dir_id: 'd1' });
  await step(500);
  expect(qa<HTMLInputElement>('#crewDetail .skl li:not(.gone) input')[1].checked).toBe(true);
  /* a stored name that no longer exists stays listed, greyed */
  await act(async () => { actions.setAgentSkills('launchpad-builder', ['sql-style', 'gone-skill']); });
  await step(500);
  expect(q('#crewDetail .skl li.gone code')?.textContent).toBe('gone-skill');
  await click(q('#crewBack'));
  /* the CLI chat: no checklist */
  await click(q('.hero[data-name="launchpad-pilot"]'));
  expect(q('#crewDetail #cdSkills')?.textContent).toContain('All (handled by the CLI)');
  expect(q('#crewDetail .skl')).toBeNull();
});
