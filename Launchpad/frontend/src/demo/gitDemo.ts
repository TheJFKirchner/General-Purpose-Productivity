/* Repos panel demo: two made-up repos (one linked to a remote with changes, one with no remote), and the git_* messages
   answered the way the server does: commit removes the ticked files, push clears "ahead", fetch finds one new commit. */
import type { GitRepo } from '../contract';

type Ev = Record<string, any>;

export function demoGitRepos(): GitRepo[] {
  const repos: GitRepo[] = [
    {
      repo_id: 'gdemo1', name: 'claims-loader', dir_id: 'd1', folder_name: 'claims-project', rel: 'loader', branch: 'main', detached: false,
      remote: { name: 'origin', host: 'github.com', owner: 'acme-data', repo: 'claims-loader' }, upstream: 'origin/main', linked: true,
      ahead: 1, behind: 0, clean: false, more: 0, added: 0, removed: 0, error: null,
      files: [
        { path: 'load_claims.py', status: 'M', added: 6, removed: 2, binary: false },
        { path: 'schema.sql', status: 'M', added: 1, removed: 1, binary: false },
        { path: 'qa/reconcile.py', status: '?', added: 24, removed: 0, binary: false },
        { path: 'old_notes.txt', status: 'D', added: 0, removed: 9, binary: false },
      ],
    },
    {
      repo_id: 'gdemo2', name: 'readmissions', dir_id: 'd2', folder_name: 'readmissions', rel: '.', branch: 'main', detached: false,
      remote: null, upstream: null, linked: false, ahead: 0, behind: 0, clean: true, files: [], more: 0, added: 0, removed: 0, error: null,
    },
  ];
  return repos.map(totals);
}

function totals(r: GitRepo): GitRepo {
  return { ...r, added: r.files.reduce((n, f) => n + f.added, 0), removed: r.files.reduce((n, f) => n + f.removed, 0) };
}

/** Handles the git_* messages; `repos` is the demo's own list (changed in place), `emit` sends a server event. */
export function demoGitOn(msg: Ev, repos: GitRepo[], emit: (ev: Ev) => void, later: (ms: number, fn: () => void) => void): void {
  if (msg.type === 'git_scan') { later(500, () => emit({ type: 'git_repos', available: true, repos: JSON.parse(JSON.stringify(repos)) })); return; }
  if (!('repo_id' in msg)) return;
  const i = repos.findIndex(r => r.repo_id === msg.repo_id), op = msg.type.slice(4) as 'refresh' | 'fetch' | 'commit' | 'push';
  const reply = (ok: boolean, message: string, committed = false) =>
    later(700, () => emit({ type: 'git_result', repo_id: msg.repo_id, op, ok, committed, message, repo: i >= 0 ? JSON.parse(JSON.stringify(repos[i])) : null }));
  if (i < 0) return reply(false, 'That repo is not in the list any more. Press Rescan.');
  const r = repos[i];
  if (msg.type === 'git_fetch') { r.behind = r.linked ? 1 : 0; return reply(true, 'Checked the remote.'); }
  if (msg.type === 'git_push') { r.ahead = 0; return reply(true, 'Pushed.'); }
  if (msg.type === 'git_commit') {
    if (!msg.message.trim() || !msg.paths.length) return reply(false, 'Type a commit message first.');
    r.files = r.files.filter(f => !msg.paths.includes(f.path));
    Object.assign(r, totals(r), { clean: !r.files.length, ahead: r.ahead + 1 });
    if (msg.push && r.linked) { r.ahead = 0; return reply(true, 'Committed. Pushed.', true); }
    return reply(true, 'Committed.', true);
  }
  reply(true, '');
}
