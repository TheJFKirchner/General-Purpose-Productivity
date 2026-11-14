// @vitest-environment happy-dom
/* Task 2c views against the in-page demo (no back end): Missions systems and their buttons, Crew reader, File
   Explorer (tree, pane, Raw, layout saved), the pen editor (conflict, Esc / Ctrl+S, discard ask) and Settings
   (two-click remove, settings sent on change). Checks the messages that go out. */
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import App from '../../App';
import { actions, dispatch, getState, useLaunchpad } from '../../store';
import { setTransport } from '../../store/core';
import { initialState } from '../../store/initial';
import { Demo } from '../../demo/Demo';
import type { UiMessage } from '../../contract';
import { closeModal, openArchive } from '../../components';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement, root: Root, demo: Demo, sent: UiMessage[], errors: unknown[];
const step = async (ms: number) => { await act(async () => { vi.advanceTimersByTime(ms); }); };
const doc = () => host.ownerDocument;
const q = <T extends Element = HTMLElement>(sel: string) => doc().querySelector<T>(sel);
const qa = <T extends Element = HTMLElement>(sel: string) => [...doc().querySelectorAll<T>(sel)];
const click = async (el: Element | null | undefined) => { expect(el).toBeTruthy(); await act(async () => { (el as HTMLElement).click(); }); };
const byText = (sel: string, text: string) => qa(sel).find(el => el.textContent?.trim() === text) || null;
const sentOf = (type: string) => sent.filter(m => m.type === type);
async function typeInto(el: HTMLTextAreaElement | HTMLInputElement, value: string) {
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value); el.dispatchEvent(new Event('input', { bubbles: true })); });
}
const key = async (k: string, ctrl = false) => { await act(async () => { doc().body.dispatchEvent(new KeyboardEvent('keydown', { key: k, ctrlKey: ctrl, bubbles: true, cancelable: true })); }); };

beforeEach(async () => {
  vi.useFakeTimers();
  localStorage.clear();
  useLaunchpad.setState(initialState(), true);
  demo = new Demo(dispatch, 1);
  sent = [];
  setTransport(m => { sent.push(m); demo.receive(m); return true; });
  errors = [];
  vi.spyOn(console, 'error').mockImplementation((...a) => { errors.push(a); });
  host = document.createElement('div'); document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(<App />); });
  await act(async () => { demo.start(); });
  await step(10_000);
});
afterEach(async () => {
  await act(async () => { root.unmount(); });
  demo.stop(); host.remove();
  vi.restoreAllMocks(); vi.clearAllTimers(); vi.useRealTimers();
  expect(errors, JSON.stringify(errors).slice(0, 600)).toHaveLength(0);
});

it('Missions: a system per run with its steps; Stop run takes two clicks; Move to Landed', async () => {
  await act(async () => { actions.setView('missions'); });
  await step(300);
  const cells = qa('#missionList .sys-cell');
  expect(cells.length).toBeGreaterThanOrEqual(2);
  const a = cells.find(c => c.querySelector('svg[data-sys="S-A"]'))!;
  expect(a.querySelectorAll('.st-planet').length).toBe(getState().sessions['S-A'].run!.steps.length);
  expect(a.querySelector('.star-g')?.getAttribute('data-tip')).toBe('run:S-A');
  expect(a.querySelector('g.dyn')).toBeTruthy();
  expect(q('#missionSum')?.textContent).toMatch(/in flight · \d+ on the pad · \d+ finished/);

  await click(byText('#missionList .sys-cell button', 'Stop run'));
  expect(sentOf('run_stop')).toHaveLength(0);
  expect(byText('#missionList button', 'Confirm stop')).toBeTruthy();
  await click(byText('#missionList button', 'Confirm stop'));
  expect(sentOf('run_stop')).toHaveLength(1);
  await step(3_000);
  const stopped = qa('#missionList .sys-cell.fin');
  expect(stopped.length).toBeGreaterThanOrEqual(1);
  await click(byText('#missionList .sys-cell.fin button', 'Move to Landed'));
  expect(byText('#missionList .pad h3', 'Landed')).toBeTruthy();
});

it('Missions: clicking a star pins its agent and scrolls that agent\'s feed row into view', async () => {
  await act(async () => { actions.setView('missions'); });
  await step(300);
  const star = q('#missionList svg[data-sys="S-A"] .star-g')!;
  const id = star.getAttribute('data-agent')!;
  expect(id).toBeTruthy();
  const rows = qa(`#feedList [data-hover-agent="${id}"]`);
  expect(rows.length).toBeGreaterThan(0);                    // both sides use the same attribute
  const spy = vi.fn();
  for (const r of rows) { r.scrollIntoView = spy; Object.defineProperty(r, 'offsetParent', { configurable: true, get: () => doc().body }); }
  await act(async () => { star.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
  expect(getState().ui.sel).toBe(id);
  expect(spy).toHaveBeenCalledTimes(1);
});

it('Planning chat archive: the full plan section and the Autopilot tag, no buttons', async () => {
  await act(async () => {
    dispatch({ type: 'session_started', session_id: 'S-Z' } as never);
    dispatch({ type: 'plan_draft', session_id: 'S-Z', path: 'plan.md', markdown: '# Zed plan\n\nBody text here', steps: [{ n: 1, title: 'One' }], revision: 1, previous_runs: 0 } as never);
    dispatch({ type: 'run_started', session_id: 'S-Z', name: 'Zed plan', steps: [{ n: 1, title: 'One', status: 'todo' }], run: 1, revision: 1, autopilot: true } as never);
    openArchive('S-Z');
  });
  const box = q('.msgs.archived')!;
  expect(box).toBeTruthy();
  expect(box.querySelector('.plancard details.full summary')?.textContent).toBe('Read the full plan');
  expect(box.querySelector('.plancard .mdbox')?.textContent).toContain('Body text here');
  expect(box.querySelector('.plancard .aptag')?.textContent).toBe('Autopilot on for this run');
  await act(async () => { closeModal(); });                     // close it while the app is mounted (Radix focus scope)
});

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

it('Missions: steps with their own agent show it under the system', async () => {
  await act(async () => { actions.setView('missions'); });
  await step(300);
  const b = qa('#missionList .sys-cell').find(c => c.querySelector('svg[data-sys="S-B"]'))!;
  expect(b.querySelector('.sys-agents')?.textContent).toContain('Step 3');
  expect(b.querySelector('.sys-agents .stepagent')?.textContent).toBe('Sql reviewer');
  expect(b.querySelector('.st-agent[data-purpose="reviewing"]')).toBeTruthy();
});

it('Files: tree, file pane, Raw toggle and layout saved to localStorage', async () => {
  await act(async () => { actions.setView('files'); });
  await step(500);
  const rootBtn = qa('#fxTree .fx-root').find(b => b.textContent?.includes('claims-project'))!;
  await click(rootBtn);
  await step(200);
  expect(sentOf('list_dir').some(m => m.type === 'list_dir' && m.root === 'd1' && m.path === '')).toBe(true);
  await click(qa('#fxTree .fx-node.file').find(b => b.textContent?.includes('README.md')));
  await step(200);
  expect(q('#fxFile h2')?.textContent).toBe('README.md');
  expect(q('#fxFile .md')?.textContent).toContain('Claims project');
  await click(byText('#fxFile .seg button', 'Raw'));
  expect(q('#fxFile pre.raw')?.textContent).toContain('# Claims project');
  await click(q('#fxToggle'));
  expect(q('#fxWrap')?.classList.contains('collapsed')).toBe(true);
  const saved = JSON.parse(localStorage.getItem('lp.files') || '{}');
  expect(saved).toMatchObject({ raw: true, collapsed: true, sel: { root: 'd1', path: 'README.md' } });
  expect(saved.open).toContain('d1|');
});

it('Editor: conflict banner, overwrite, Esc asks once when dirty, Ctrl+S saves', async () => {
  await act(async () => { actions.openEditor('d1', 'notes/team-notes.md'); });
  await step(300);
  const ta = q<HTMLTextAreaElement>('#edScrim textarea')!;
  expect(ta.value).toContain('# Team notes');
  await step(2_000);                                         // a teammate saves it meanwhile (demo)
  await typeInto(ta, ta.value + '\n- mine');
  expect(q('#edStatus')?.textContent).toBe('Unsaved changes');
  await key('s', true);                                      // Ctrl+S
  await step(400);
  expect(sentOf('save_file')).toHaveLength(1);
  expect(q('#edBanner.conflict')?.textContent).toContain('changed on disk');
  expect(q('#edBanner details pre')?.textContent).toContain('added by a teammate');
  await click(byText('#edBanner button', 'Overwrite it with mine'));
  await step(400);
  expect(sentOf('save_file')).toHaveLength(2);
  expect(q('#edScrim.open')).toBeNull();                      // saved and closed

  await act(async () => { actions.openEditor('d1', 'README.md'); });
  await step(300);
  await typeInto(q<HTMLTextAreaElement>('#edScrim textarea')!, '# changed');
  await key('Escape');
  expect(q('#edCancel')?.textContent).toBe('Discard changes?');
  expect(q('#edScrim.open')).toBeTruthy();
  await key('Escape');
  expect(q('#edScrim.open')).toBeNull();
});

it('Editor: invalid save shows the check message; previous versions list', async () => {
  await act(async () => { actions.openEditor('d1', '.launchpad/S-A/plan.md'); });
  await step(300);
  expect(q('#edNotes')?.textContent).toContain('Checked as a plan file');
  expect(q('#edPrev')?.getAttribute('aria-label')).toBe('Preview');
  await typeInto(q<HTMLTextAreaElement>('#edScrim textarea')!, 'not a plan');
  await click(q('#edSave'));
  await step(400);
  expect(q('#edBanner.invalid')?.textContent).toContain('did not pass the check');
  await click(q('#edVersions'));
  await step(400);
  expect(sentOf('list_backups')).toHaveLength(1);
  expect(q('#edBackups')).toBeTruthy();
  await click(byText('#edPrevSeg button', 'Text only'));
  expect(q('#edPanes')?.className).toContain('edit');
  expect(localStorage.getItem('lp.editorView')).toBe('"edit"');
});

it('Settings: folders, add, two-click remove, a setting sent on change', async () => {
  await act(async () => { actions.openSettings(); });
  await step(400);
  expect(qa('.dirrow').length).toBe(2);
  expect(qa('.dirrow button').filter(b => b.textContent === 'Remove').every(b => (b as HTMLButtonElement).disabled)).toBe(true);   // both busy
  await typeInto(q<HTMLInputElement>('#setAddPath')!, 'C:/work/extra');
  await act(async () => { q<HTMLFormElement>('#setAdd')!.requestSubmit(); });
  await step(400);
  expect(sentOf('add_directory')).toHaveLength(1);
  expect(qa('.dirrow').length).toBe(3);
  expect(q<HTMLInputElement>('#setAddPath')!.value).toBe('');
  const rm = qa<HTMLButtonElement>('.dirrow button').filter(b => b.textContent === 'Remove' && !b.disabled);
  expect(rm).toHaveLength(1);
  await click(rm[0]);
  expect(sentOf('remove_directory')).toHaveLength(0);
  await click(byText('.dirrow button', 'Confirm remove'));
  expect(sentOf('remove_directory')).toHaveLength(1);
  await step(400);
  expect(qa('.dirrow').length).toBe(2);

  const num = q<HTMLInputElement>('#set-question_timeout_s')!;
  await act(async () => { num.value = '240'; num.dispatchEvent(new Event('change', { bubbles: true })); });
  expect(sentOf('set_settings').at(-1)).toEqual({ type: 'set_settings', patch: { question_timeout_s: 240 } });
  expect(q<HTMLInputElement>('#set-pilot_model')!.disabled).toBe(true);      // set by a launch option
  await key('Escape');
  expect(getState().ui.settingsOpen).toBe(false);
});
