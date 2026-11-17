/* Crew: "Used but not defined". The roles plan steps ran under that no agent defines, as the server lists them
   (roles_list, visible ones): name, times used, last used, skills, folders and small markers for failed, blocked and
   sent-back uses. Each has Review (opens the review screen), Merge (fold it into another role, with a confirm) and
   Dismiss. The list is the server's: nothing is counted or hidden here. */
import { useState, type ReactNode } from 'react';
import { actions, sel, useComputed, useLaunchpad } from '../../store';
import type { RoleEntry } from '../../contract';
import { Pill } from '../../components';
import { AlertTriangle, Folder, GitMerge, History, ListChecks, ShieldAlert, Sparkles, UserCog, X } from '../../components/icons';
import { useNow } from '../../lib/hooks';
import { ago } from '../../lib/format';

const usesText = (n: number) => `${n.toLocaleString()} use${n === 1 ? '' : 's'}`;

export function UsedRoles() {
  const v = useComputed(st => ({ list: sel.visibleRoles(st), all: st.roles.entries, threshold: st.roles.threshold, loaded: st.roles.loaded }));
  return (
    <section className="roles" aria-labelledby="usedRolesH" id="usedRoles">
      <h2 className="pgroup-h roles-h" id="usedRolesH"><span className="pg-ic" aria-hidden="true"><UserCog /></span>Used but not defined<span className="cnt">{v.list.length}</span>
        <small>Roles the planner gave plan steps that no agent defines. The Builder ran them; review one to see whether it has earned its own agent.</small></h2>
      {v.list.length ? (
        <ul className="roles-list">
          {v.list.map(e => <li key={e.name}><RoleRow e={e} others={v.all.filter(o => o.name !== e.name).map(o => o.name)} /></li>)}
        </ul>
      ) : (
        <p className="roles-empty" id="usedRolesEmpty">
          {v.loaded ? `Nothing here yet. A role the planner names for a step shows up here once it has been used ${v.threshold} times and no agent defines it.`
            : 'Roles will show here once the list has loaded.'}
        </p>
      )}
    </section>
  );
}

function RoleRow({ e, others }: { e: RoleEntry; others: string[] }) {
  const mk = sel.roleMarkers(e);
  const [merging, setMerging] = useState(false);
  const [into, setInto] = useState('');
  const has = useLaunchpad(st => !!st.reviews[e.name]);
  useNow(60000);
  const last = Date.parse(e.last_used);
  const marker = (n: number, cls: string, label: string, icon: ReactNode) => n ? (
    <span className={`chip ${cls}`} title={`${n} of the listed uses ${label}`}>{icon}{n} {label}</span>
  ) : null;
  const confirm = () => { if (into) { actions.roleMerge(e.name, into); setMerging(false); setInto(''); } };
  return (
    <div className="role" data-role={e.name}>
      <div className="role-main">
        <h3 className="role-name"><code>{e.name}</code></h3>
        <div className="role-meta">
          <span className="role-uses"><b>{e.uses_total.toLocaleString()}</b> {e.uses_total === 1 ? 'use' : 'uses'}</span>
          <span title={e.last_used}>last used {isNaN(last) ? 'unknown' : ago(last) + ' ago'}</span>
          {e.state === 'defining' ? <span className="chip rev" title="You chose to define an agent for this role; the agent is not saved yet">Being defined</span> : null}
          {e.resurfaced ? <span className="chip rev" title="It rested after an earlier decision and has come back">Back after a rest</span> : null}
          {e.reviewing ? <span className="chip rev">Review running</span> : null}
        </div>
        <div className="role-tags">
          {marker(mk.failed, 'warnc', 'failed', <AlertTriangle />)}
          {marker(mk.blocked, 'warnc', 'blocked', <ShieldAlert />)}
          {marker(mk.sentBack, 'warnc', 'sent back', <History />)}
          {e.skills.map(s => <span key={s} className="chip skill" title="A skill a step under this role used"><Sparkles />{s}</span>)}
          {e.folders.map(f => <span key={f.dir_id ?? f.name} className="chip" title="A folder it was used in"><Folder />{f.name}</span>)}
        </div>
      </div>
      <div className="role-actions">
        <Pill size="sm" variant="primary" icon={<ListChecks />} aria-label={`Review the role ${e.name}`} onClick={() => actions.roleReview(e.name)}>{has && e.reviewing ? 'Open review' : 'Review'}</Pill>
        <Pill size="sm" icon={<GitMerge />} aria-label={`Merge the role ${e.name} into another role`} aria-expanded={merging} disabled={!others.length}
          title={others.length ? 'Fold this role into another one (near-duplicate names)' : 'There is no other role to merge into'} onClick={() => { setMerging(m => !m); setInto(others[0] || ''); }}>Merge</Pill>
        <Pill size="sm" variant="ghost" icon={<X />} aria-label={`Dismiss the role ${e.name}`} title="Hide it until a step uses it again" onClick={() => actions.roleDismiss(e.name)}>Dismiss</Pill>
      </div>
      {merging ? (
        <div className="role-merge" role="group" aria-label={`Merge ${e.name}`}>
          <label htmlFor={`merge-${e.name}`}>Merge <code>{e.name}</code> into</label>
          <select id={`merge-${e.name}`} aria-label={`Merge ${e.name} into`} className="field" value={into} onChange={ev => setInto(ev.target.value)}>
            {others.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
          <p className="none">Its {usesText(e.uses_total)}, skills and folders move into the other role and <code>{e.name}</code> goes away.</p>
          <div className="row">
            <Pill size="sm" variant="primary" disabled={!into} onClick={confirm}>Confirm merge</Pill>
            <Pill size="sm" variant="ghost" onClick={() => setMerging(false)}>Cancel</Pill>
          </div>
        </div>
      ) : null}
    </div>
  );
}
