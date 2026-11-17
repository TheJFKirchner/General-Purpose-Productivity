/* The Repos panel: the right-hand panel while the Files tab is open. One collapsible card per git repo found in the
   connected folders (grouped under the folder), with its branch, status chips, changed files (tick boxes), a commit
   message box and Commit / Commit and push. Display + input only: git runs on the server (app/gitrepos.py), the
   messages are git_scan / git_refresh / git_fetch / git_commit / git_push (header of app/server.py). */
import { actions, sel, useComputed, useLaunchpad } from '../../store';
import type { GitRepo } from '../../contract';
import { Chip, Empty, Loading, Pill } from '../../components';
import { AlertTriangle, ChevronDown, ChevronRight, CloudDownload, GitBranch, Inbox, RotateCw, Send } from '../../components/icons';

const OP_TEXT = { refresh: 'Refreshing…', fetch: 'Checking the remote…', commit: 'Committing…', push: 'Pushing…' } as const;
const STATUS_TITLE: Record<string, string> = { M: 'Modified', A: 'Added', D: 'Deleted', U: 'Conflict (unmerged)', '?': 'New file (not tracked yet)' };
const TONE = { ok: 'ok', warn: 'warnc', info: 'rev', err: 'warnc' } as const;

/** The "N waiting" line: queue cards keep their timers while the Files tab is open, so they are never hidden silently. */
export function WaitingLine() {
  const n = useComputed(st => sel.openCount(st));
  if (!n) return null;
  return (
    <button type="button" className="waitline" id="repoWaiting" onClick={() => { actions.openVis(false); actions.setView('plan'); }} aria-label={`${n} waiting in Incoming. Open the Plan tab to answer.`}>
      <Inbox /><b>{n} waiting</b><span>Open Incoming</span><ChevronRight />
    </button>
  );
}

export function Repos() {
  const loaded = useLaunchpad(st => st.git.loaded);
  const scanning = useLaunchpad(st => st.git.scanning);
  const available = useLaunchpad(st => st.git.available);
  const groups = useComputed(st => sel.gitGroups(st));
  return (
    <section className="repos" id="repos" aria-label="Git repos">
      <div className="inc-head">
        <h2>Repos</h2>
        <Pill size="sm" variant="ghost" icon={<RotateCw />} disabled={scanning} onClick={() => actions.gitScan()} data-tip="text:Look for repos again">Rescan</Pill>
      </div>
      {!loaded ? <div className="card repo-note"><Loading>Looking for repos…</Loading></div>
        : available === false ? (
          <Empty card icon={<AlertTriangle />} title="Git is not installed">Install Git (and restart Launchpad) to see and commit your repos here.</Empty>
        ) : !groups.length ? (
          <Empty card icon={<GitBranch />} title="No repos found">None of your connected folders is a git repo or holds one (two levels down is searched).</Empty>
        ) : groups.map(g => (
          <div key={g.dirId} className="repo-group">
            <div className="overline">{g.name}</div>
            {g.repos.map(r => <RepoCard key={r.repo_id} repo={r} />)}
          </div>
        ))}
    </section>
  );
}

function RepoCard({ repo }: { repo: GitRepo }) {
  const id = repo.repo_id;
  const open = useLaunchpad(st => sel.gitIsOpen(st, repo));
  const busy = useLaunchpad(st => st.git.busy[id] || null);
  const error = useLaunchpad(st => st.git.error[id] || null);
  const note = useLaunchpad(st => st.git.note[id] || null);
  const message = useLaunchpad(st => st.git.message[id] || '');
  const unticked = useLaunchpad(st => st.git.unticked[id]);
  const ticked = repo.files.filter(f => !(unticked || []).includes(f.path)).map(f => f.path);
  const chips = sel.gitChips(repo);
  const canCommit = !busy && !!message.trim() && ticked.length > 0;
  const shown = repo.files.length, total = shown + repo.more;
  const where = repo.rel && repo.rel !== '.' ? repo.rel : '';
  const remote = repo.remote ? [repo.remote.host, repo.remote.owner, repo.remote.repo].filter(Boolean).join('/') : '';

  return (
    <article className="card repo" aria-label={`Repo ${repo.name}`} data-repo={repo.name}>
      <div className="repo-head">
        <button type="button" className="repo-toggle" aria-expanded={open} aria-label={`${open ? 'Collapse' : 'Expand'} repo ${repo.name}`} onClick={() => actions.gitToggleOpen(id, !open)}>
          {open ? <ChevronDown /> : <ChevronRight />}
          <span className="repo-nm" title={where ? `${repo.name} (${where})` : repo.name}>{repo.name}</span>
          <span className="repo-br"><GitBranch />{repo.detached ? 'detached HEAD' : repo.branch || 'no branch'}</span>
        </button>
        <div className="repo-chips">
          {chips.map(c => <Chip key={c.text} variant={TONE[c.tone]}>{c.text}</Chip>)}
          <span className="repo-tools">
            <Pill size="xs" variant="ghost" icon={<RotateCw />} disabled={!!busy} onClick={() => actions.gitRefresh(id)} data-tip="text:Read the status again">Refresh</Pill>
            {repo.linked ? <Pill size="xs" variant="ghost" icon={<CloudDownload />} disabled={!!busy} onClick={() => actions.gitFetch(id)} data-tip="text:Fetch from the remote (no pull)">Check remote</Pill> : null}
          </span>
        </div>
      </div>
      {open ? (
        <div className="repo-body">
          <p className="repo-meta">
            {repo.linked && remote ? <>Remote <b>{repo.remote?.name}</b> · {remote} · tracks {repo.upstream}</>
              : repo.remote ? <>Remote <b>{repo.remote.name}</b>{remote ? ` · ${remote}` : ''} · this branch has no upstream yet</>
              : <>No remote</>}
            {where ? <> · in <code>{where}</code></> : null}
          </p>
          {!repo.linked && !repo.error ? <p className="repo-hint">Not linked to GitHub, so only Commit is offered.</p> : null}
          {repo.behind ? <p className="repo-hint">{repo.behind} behind the remote. Launchpad never pulls; update it in your own tools.</p> : null}
          {repo.error ? <div className="warn" role="alert"><span><AlertTriangle /> {repo.error}</span></div> : null}
          {busy ? <div className="repo-busy"><Loading>{OP_TEXT[busy]}</Loading></div> : null}
          {error ? <div className="warn" role="alert"><span><AlertTriangle /> {error}</span></div> : null}
          {note && !busy && !error ? <p className="repo-ok" role="status">{note}</p> : null}
          {repo.clean && !repo.error ? <p className="repo-clean">No changes. Everything is committed.</p> : null}
          {!repo.clean ? (
            <>
              <label className="repo-all">
                <input type="checkbox" aria-label={`Include all changed files in ${repo.name}`}
                  aria-checked={ticked.length === shown ? 'true' : ticked.length > 0 ? 'mixed' : 'false'}
                  checked={ticked.length === shown} ref={el => { if (el) el.indeterminate = ticked.length > 0 && ticked.length < shown; }}
                  onChange={e => actions.gitTickAll(id, e.target.checked)} />
                <span>{ticked.length === shown ? 'All files ticked' : `${ticked.length} of ${shown} ticked`}</span>
              </label>
              <ul className="repo-files">
                {repo.files.map(f => (
                  <li key={f.path}>
                    <input type="checkbox" aria-label={`Include ${f.path}`} checked={ticked.includes(f.path)} onChange={() => actions.gitToggleFile(id, f.path)} />
                    <span className={`repo-st st-${f.status === '?' ? 'new' : f.status}`} title={STATUS_TITLE[f.status] || f.status}>{f.status}</span>
                    {f.status === 'D'
                      ? <span className="repo-fp" title={f.path}>{f.path}</span>
                      : <button type="button" className="repo-fp link" title={`Open ${f.path} in Files`} onClick={() => actions.gitOpenFile(id, f.path)}>{f.path}</button>}
                    <span className="repo-cnt">{f.binary ? 'binary' : <><b className="repo-add">+{f.added}</b> <b className="repo-rem">-{f.removed}</b></>}</span>
                  </li>
                ))}
              </ul>
              {repo.more ? <p className="repo-hint">…and {repo.more} more changed files not shown.</p> : null}
              <p className="repo-tot">{total} changed {total === 1 ? 'file' : 'files'} · <b className="repo-add">+{repo.added}</b> <b className="repo-rem">-{repo.removed}</b></p>
              <label className="sr" htmlFor={`msg-${id}`}>Commit message</label>
              <textarea id={`msg-${id}`} className="field repo-msg" rows={2} placeholder="Commit message" value={message} disabled={!!busy}
                onChange={e => actions.gitSetMessage(id, e.target.value)} />
              <div className="row">
                <Pill size="sm" variant="soft" disabled={!canCommit} onClick={() => actions.gitCommit(id, false)}>Commit</Pill>
                {repo.linked ? <Pill size="sm" variant="primary" icon={<Send />} disabled={!canCommit} onClick={() => actions.gitCommit(id, true)}>Commit and push</Pill> : null}
              </div>
            </>
          ) : null}
          {repo.linked && repo.ahead ? (
            <div className="row">
              <Pill size="sm" variant={repo.clean ? 'primary' : 'soft'} icon={<Send />} disabled={!!busy} onClick={() => actions.gitPush(id)}>Push {repo.ahead} {repo.ahead === 1 ? 'commit' : 'commits'}</Pill>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
