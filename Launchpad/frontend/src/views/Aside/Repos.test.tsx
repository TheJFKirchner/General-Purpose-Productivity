// @vitest-environment happy-dom
/* The Repos panel against the in-page demo: it replaces In orbit / Incoming on the Files tab only, shows the demo
   repos, commits only the ticked files, and keeps an "N waiting" line for the queue. */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, dispatch, getState } from '../../store';
import { useDemoApp, step, q, qa, click, byText, sentOf, typeInto } from '../../test/demoApp';

useDemoApp();

const openFiles = async () => { await act(async () => { actions.setView('files'); }); await step(1_500); };

it('Aside: Repos on the Files tab, In orbit and Incoming on every other tab', async () => {
  expect(q('.flight')).toBeTruthy();
  expect(q('#repos')).toBeNull();
  await openFiles();
  expect(sentOf('git_scan').length).toBeGreaterThan(0);
  expect(q('#repos h2')?.textContent).toBe('Repos');
  expect(q('.flight')).toBeNull();
  expect(q('#queue')).toBeNull();
  await act(async () => { actions.setView('missions'); });
  expect(q('#repos')).toBeNull();
  expect(q('.flight')).toBeTruthy();
  expect(q('#queue')).toBeTruthy();
});

it('Repos: cards grouped by folder with branch and status chips; clean and not linked repo', async () => {
  await openFiles();
  const groups = qa('.repo-group .overline').map(e => e.textContent);
  expect(groups).toEqual(['claims-project', 'readmissions']);
  const loader = q('[data-repo="claims-loader"]')!;
  expect(loader.querySelector('.repo-br')?.textContent).toBe('main');
  const chips = [...loader.querySelectorAll('.repo-chips .chip')].map(c => c.textContent);
  expect(chips).toEqual(['1 ahead', 'Changes']);
  const rm = q('[data-repo="readmissions"]')!;
  expect([...rm.querySelectorAll('.repo-chips .chip')].map(c => c.textContent)).toEqual(['Not linked']);
  expect(rm.querySelector('.repo-body')).toBeNull();                      // a clean repo starts collapsed
  await click(rm.querySelector('.repo-toggle'));
  expect(rm.textContent).toContain('No changes');
  expect(rm.textContent).toContain('only Commit is offered');
  expect(byText('[data-repo="readmissions"] button', 'Check remote')).toBeNull();
});

it('Repos: files ticked by default, Commit needs a message and a tick, sends only the ticked paths', async () => {
  await openFiles();
  const loader = () => q('[data-repo="claims-loader"]')!;
  const boxes = () => [...loader().querySelectorAll<HTMLInputElement>('.repo-files input[type=checkbox]')];
  expect(boxes()).toHaveLength(4);
  expect(boxes().every(b => b.checked)).toBe(true);
  expect(loader().querySelector('.repo-tot')?.textContent).toContain('4 changed files');
  const commit = () => byText('[data-repo="claims-loader"] button', 'Commit') as HTMLButtonElement;
  expect(commit().disabled).toBe(true);                                   // no message yet
  await typeInto(loader().querySelector<HTMLTextAreaElement>('textarea')!, '  Fix the loader  ');
  expect(commit().disabled).toBe(false);
  await click(boxes()[2]);                                                // untick qa/reconcile.py
  await click(boxes()[3]);                                                // untick old_notes.txt
  expect(loader().querySelector('.repo-all')?.textContent).toBe('2 of 4 ticked');
  await click(commit());
  const sent = sentOf('git_commit')[0];
  expect(sent).toMatchObject({ type: 'git_commit', message: 'Fix the loader', paths: ['load_claims.py', 'schema.sql'], push: false });
  await step(1_500);
  expect([...loader().querySelectorAll('.repo-fp')].map(e => e.textContent)).toEqual(['qa/reconcile.py', 'old_notes.txt']);
  expect(loader().textContent).toContain('Committed.');
  expect(loader().querySelector<HTMLTextAreaElement>('textarea')?.value).toBe('');
  expect(loader().querySelector('.repo-chips')?.textContent).toContain('2 ahead');
  await click(byText('[data-repo="claims-loader"] button', 'Push 2 commits'));
  await step(1_500);
  expect(sentOf('git_push')).toHaveLength(1);
  expect(loader().querySelector('.repo-chips')?.textContent).not.toContain('ahead');
});

it('Repos: untick all disables Commit; Commit and push sends push; Check remote shows behind; errors show in the card', async () => {
  await openFiles();
  const loader = () => q('[data-repo="claims-loader"]')!;
  await typeInto(loader().querySelector<HTMLTextAreaElement>('textarea')!, 'msg');
  await click(loader().querySelector('.repo-all input'));
  expect(loader().querySelectorAll('.repo-files input:checked')).toHaveLength(0);
  expect((byText('[data-repo="claims-loader"] button', 'Commit and push') as HTMLButtonElement).disabled).toBe(true);
  await click(loader().querySelector('.repo-all input'));
  await click(byText('[data-repo="claims-loader"] button', 'Commit and push'));
  expect(sentOf('git_commit')[0]).toMatchObject({ push: true });
  await step(1_500);
  await click(byText('[data-repo="claims-loader"] button', 'Check remote'));
  await step(1_500);
  expect(loader().querySelector('.repo-chips')?.textContent).toContain('1 behind');
  await act(async () => { dispatch({ type: 'git_result', repo_id: 'gdemo1', op: 'push', ok: false, committed: false, message: 'rejected: fetch first', repo: null }); });
  expect(loader().querySelector('.warn')?.textContent).toContain('rejected: fetch first');
});

it('Repos: clicking a changed file opens it in the Files view; a deleted file is not a link', async () => {
  await openFiles();
  await click(byText('[data-repo="claims-loader"] button.repo-fp', 'load_claims.py'));
  await step(500);
  expect(sentOf('read_file').some(m => m.type === 'read_file' && m.root === 'd1' && m.path === 'loader/load_claims.py')).toBe(true);
  expect(byText('[data-repo="claims-loader"] button.repo-fp', 'old_notes.txt')).toBeNull();
});

it('Files tab: a "N waiting" line shows when the queue has items and leads back to Incoming', async () => {
  await act(async () => { dispatch({ type: 'queue_item', id: 'p1', session_id: null, kind: 'permission', agent: 'Builder', title: 'Run a command', body: 'ls', blocking: false, timeout_s: 180 }); });
  await openFiles();
  await act(async () => { actions.openVis(true); });                      // the Visuals panel was left open
  const w = q('#repoWaiting')!;
  expect(w.textContent).toContain('waiting');
  await click(w);
  expect(q('#repos')).toBeNull();
  expect(q('#queue')).toBeTruthy();
  expect(getState().ui.vis.open).toBe(false);                             // so the Incoming list is visible
});

it('Repos: accessible names for tick-all and the expand / collapse buttons; Files labels Primary / Additional', async () => {
  await openFiles();
  const loader = q('[data-repo="claims-loader"]')!;
  expect(loader.querySelector('.repo-all input')?.getAttribute('aria-label')).toBe('Include all changed files in claims-loader');
  expect(loader.querySelector('.repo-all input')?.getAttribute('aria-checked')).toBe('true');
  await click(loader.querySelector('.repo-files input'));
  expect(loader.querySelector('.repo-all input')?.getAttribute('aria-checked')).toBe('mixed');
  expect(loader.querySelector('.repo-toggle')?.getAttribute('aria-label')).toBe('Collapse repo claims-loader');
  expect(q('[data-repo="readmissions"] .repo-toggle')?.getAttribute('aria-label')).toBe('Expand repo readmissions');
  const tags = qa('.fx-root .k').map(e => e.textContent);
  expect(tags).toContain('Primary');
  expect(tags).not.toContain('default');
});

it('Repos: git not installed, and no repos found', async () => {
  await openFiles();
  await act(async () => { dispatch({ type: 'git_repos', available: false, repos: [] }); });
  expect(q('#repos')?.textContent).toContain('Git is not installed');
  await act(async () => { dispatch({ type: 'git_repos', available: true, repos: [] }); });
  expect(q('#repos')?.textContent).toContain('No repos found');
});
