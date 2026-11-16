// @vitest-environment happy-dom
/* Files against the in-page demo: tree, pane, Raw, layout saved, and the pen editor (conflict, Esc / Ctrl+S, checks). */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions } from '../../store';
import { useDemoApp, step, q, qa, click, byText, sentOf, typeInto, key } from '../../test/demoApp';

useDemoApp();

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
