/* Crew: every agent as a card ("hero card"), grouped and filterable by purpose (planning, exploring, building,
   reviewing; colours from the --purpose-* tokens, always with a label and an icon too). A card shows the name,
   description, model, where it comes from (built in, or a file in the connected folder) and a use count that updates
   live (agent_uses). Clicking a card opens the full definition (the reader the Crew tab always had) with the edit pen;
   folder agents can also be removed there (two-click confirm, the server keeps a backup copy). "Add agent" opens
   the form in AgentForm.tsx. Vanilla source of the reader: prototype/launchpad-orbit.html 3324-3400.
   Selection, filter text and Formatted / Raw are local to this view. Prompt and criteria text go through <Markdown>.
   The detail's Skills section sets the agent's skills ("All skills" or a checklist of the skills found in the folder
   and the additional folders; set_agent_skills); names no longer found stay listed, greyed. The CLI chat shows
   "All (handled by the CLI)" with no checklist. */
import './Crew.css';
import { Fragment, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { actions, sel, useComputed, useLaunchpad, type AppState } from '../../store';
import type { CrewAgentDef, Purpose, SkillInfo } from '../../contract';
import { Empty, Loading, Markdown, PURPOSE_ICON, PenButton, Pill, PurposeTag, ViewFrame } from '../../components';
import { AlertTriangle, ArrowLeft, Bot, Copy, FolderOpen, Plus, RotateCw, Rocket, Search, Trash, UserPlus, Users } from '../../components/icons';
import { ADDABLE_PURPOSES, PURPOSES, PURPOSE_HINT, PURPOSE_LABEL, roleLabel } from '../../lib/labels';
import { modelName } from '../../lib/format';
import AgentForm from './AgentForm';

type Filter = 'all' | Purpose;

function crewMatches(a: CrewAgentDef, q: string): boolean {
  if (!q) return true;
  const hay = [a.name, a.display_name, roleLabel(a.role), sel.purposeOf(a), a.model, a.description, ...(a.builtin_tools || []), ...(a.custom_tools || []).map(t => t.name), ...(a.mcp_servers || []).map(m => m.name)].join(' ').toLowerCase();
  return hay.includes(q);
}
/** A file path with line-break chances after each / or \ (so long paths wrap between folders, not mid-name). */
function pathBreaks(path: string) {
  return path.split(/(?<=[\\/])/).map((part, i) => <Fragment key={i}>{part}<wbr /></Fragment>);
}
const usesText = (n: number) => `${n.toLocaleString()} use${n === 1 ? '' : 's'}`;
/** Where a folder agent lives, for its badge ("Folder · claims-project"). */
const folderName = (st: AppState, a: CrewAgentDef) => sel.dirLabelOf(st, a.root && a.root !== 'app' ? a.root : sel.crewDir(st)) || 'this project';

export default function Crew() {
  const defs = useLaunchpad(st => st.crewDefs);
  const loading = useLaunchpad(st => st.crewLoading);
  const flash = useLaunchpad(st => st.crewFlash);
  const canAdd = useLaunchpad(st => !!sel.crewDir(st));
  const [selName, setSelName] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [raw, setRaw] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const backTo = useRef<string | null>(null);

  /* the open agent went away (removed, or the folder changed): back to the cards */
  useEffect(() => { if (selName && defs && !defs.some(a => a.name === selName)) { setSelName(null); backTo.current = null; } }, [defs, selName]);
  /* a card just added: show it */
  useEffect(() => {
    if (!flash) return;
    setFilter('all'); setQuery('');
    requestAnimationFrame(() => bodyRef.current?.querySelector<HTMLElement>(`.hero[data-name="${CSS.escape ? CSS.escape(flash) : flash}"]`)?.scrollIntoView?.({ block: 'nearest' }));
  }, [flash]);
  /* focus: the detail's heading when it opens, the card it came from when it closes */
  useLayoutEffect(() => {
    const body = bodyRef.current; if (!body) return;
    if (selName) { body.scrollTop = 0; body.querySelector<HTMLElement>('#crewDetail h2')?.focus(); }
    else if (backTo.current) {
      const name = backTo.current; backTo.current = null;
      body.querySelector<HTMLElement>(`.hero[data-name="${CSS.escape ? CSS.escape(name) : name}"]`)?.focus();
    }
  }, [selName]);

  const open = (name: string) => { actions.clearCrewError(); setSelName(name); };
  const back = () => { backTo.current = selName; setSelName(null); actions.clearCrewError(); };

  const counts = useComputed(st => {
    const c: Record<string, number> = { all: 0, planning: 0, exploring: 0, building: 0, reviewing: 0 }, list = st.crewDefs || [];
    for (const a of list) { c.all++; c[sel.purposeOf(a)]++; }
    return { n: c as Record<Filter, number>, folder: list.filter(a => !sel.isBuiltin(a)).length, dir: sel.dirLabelOf(st, sel.crewDir(st)) };
  });
  const sub = defs
    ? `${defs.length} agent${defs.length === 1 ? '' : 's'}: ${defs.length - counts.folder} built in${counts.folder ? `, ${counts.folder} from ${counts.dir || 'the project folder'}` : ''}${loading ? ' · refreshing…' : ''}. Open one for its full definition.`
    : 'Every agent Launchpad can use, built in and from the project folder.';
  const sel1 = selName && defs ? defs.find(a => a.name === selName) || null : null;

  return (
    <ViewFrame id="viewCrew" label="Crew" title="Crew" sub={<span id="crewSum">{sub}</span>} bodyClass={null}
      tools={<div className="crew-tools">
        <Pill size="sm" variant="primary" id="crewAdd" icon={<UserPlus />} disabled={!canAdd}
          title={canAdd ? 'Add your own agent to the project folder; the planner can then name it for a plan step' : 'Connect a folder in Settings first: added agents are saved in a project folder'}
          onClick={() => actions.crewOpenForm()}>Add agent</Pill>
        <Pill size="sm" id="crewRefresh" icon={<RotateCw className={loading ? 'spin' : undefined} />} onClick={() => actions.requestCrew()}>Refresh</Pill>
      </div>}>
      <div className="crew-body" ref={bodyRef}>
        {sel1 ? <CrewDetail a={sel1} raw={raw} setRaw={setRaw} onBack={back} /> : (
          <>
            <div className="crew-bar">
              <div className="crew-search">
                <label className="sr" htmlFor="crewSearch">Filter agents</label>
                <Search className="crew-search-ic" />
                <input type="search" id="crewSearch" className="field" placeholder="Filter agents" title="Filter by name, purpose, model or tool" autoComplete="off" value={query} onChange={e => setQuery(e.target.value)} />
              </div>
              <FolderPick />
              <div className="seg crew-filter" role="group" aria-label="Show purpose">
                {(['all', ...PURPOSES] as Filter[]).map(f => (
                  <button key={f} type="button" aria-pressed={filter === f} data-purpose={f === 'all' ? undefined : f} onClick={() => setFilter(f)}>
                    {f === 'all' ? null : <i className="pdot" aria-hidden="true" />}{f === 'all' ? 'All' : PURPOSE_LABEL[f]}<span className="cnt">{counts.n[f]}</span>
                  </button>
                ))}
              </div>
            </div>
            <div id="crewAgents"><CrewCards defs={defs} loading={loading} query={query.trim().toLowerCase()} filter={filter} canAdd={canAdd} onOpen={open} /></div>
          </>
        )}
      </div>
      <AgentForm />
    </ViewFrame>
  );
}

/** Which connected folder's agents to list (get_crew {dir_id}); only when more than one folder is connected. */
function FolderPick() {
  const v = useComputed(st => ({ dirs: sel.dirsList(st), cur: sel.crewDir(st) || '' }));
  if (v.dirs.length < 2) return null;
  return (
    <div className="crew-dir">
      <label htmlFor="crewDir"><FolderOpen />Folder agents from</label>
      <select id="crewDir" className="field" value={v.cur} onChange={e => actions.crewPickDir(e.target.value)}>
        {v.dirs.map(d => <option key={d.dir_id} value={d.dir_id} disabled={d.exists === false}>{d.name || d.path}</option>)}
      </select>
    </div>
  );
}

/* ---------------- the cards ---------------- */
function CrewCards({ defs, loading, query, filter, canAdd, onOpen }: {
  defs: CrewAgentDef[] | null; loading: boolean; query: string; filter: Filter; canAdd: boolean; onOpen: (name: string) => void;
}) {
  if (!defs) {
    return loading ? <div className="crew-note"><Loading>Loading the crew…</Loading></div>
      : <Empty icon={<Users />} title="Crew not loaded">Open this tab while connected, or press Refresh.</Empty>;
  }
  if (!defs.length) return <Empty icon={<Bot />} title="No agents found">The back end reported no agent definitions. Press Refresh, or add one.</Empty>;
  const shown = defs.filter(a => crewMatches(a, query) && (filter === 'all' || sel.purposeOf(a) === filter));
  if (query && !shown.length) return <Empty icon={<Search />} title="No matches">No agent matches “{query}”{filter !== 'all' ? ` among ${PURPOSE_LABEL[filter].toLowerCase()} agents` : ''}.</Empty>;
  const groups = (filter === 'all' ? [...PURPOSES] : [filter]) as Purpose[];
  return <>{groups.map(p => {
    const list = shown.filter(a => sel.purposeOf(a) === p).sort((x, y) => (sel.isBuiltin(x) ? 0 : 1) - (sel.isBuiltin(y) ? 0 : 1));
    const addable = (ADDABLE_PURPOSES as readonly string[]).includes(p) && !query;
    if (!list.length && !addable) return null;
    return (
      <section key={p} className="pgroup" data-purpose={p} aria-labelledby={`pg-${p}`}>
        <h2 className="pgroup-h" id={`pg-${p}`}><span className="pg-ic" aria-hidden="true">{PURPOSE_ICON[p]}</span>{PURPOSE_LABEL[p]}<span className="cnt">{list.length}</span><small>{PURPOSE_HINT[p]}</small></h2>
        <div className="hero-grid">
          {list.map(a => <HeroCard key={a.name} a={a} onOpen={onOpen} />)}
          {addable ? <AddTile purpose={p} canAdd={canAdd} first={!list.length} /> : null}
        </div>
      </section>
    );
  })}</>;
}

function HeroCard({ a, onOpen }: { a: CrewAgentDef; onOpen: (name: string) => void }) {
  const v = useComputed(st => ({ uses: sel.usesOf(st, a), folder: sel.isBuiltin(a) ? '' : folderName(st, a), flash: st.crewFlash === a.name }));
  const p = sel.purposeOf(a), builtin = sel.isBuiltin(a), w = (a.warnings || []).length;
  const name = a.display_name || a.name;
  return (
    <button type="button" className={`hero${builtin ? '' : ' folder'}${v.flash ? ' flash' : ''}`} data-purpose={p} data-name={a.name} onClick={() => onOpen(a.name)}
      aria-label={`${name}. ${PURPOSE_LABEL[p]} agent, ${builtin ? 'built in' : 'from the folder ' + v.folder}, ${modelName(a.model) || 'default model'}, ${usesText(v.uses)}. Open its definition.`}>
      <span className="hero-top">
        <span className="hero-ic" aria-hidden="true">{PURPOSE_ICON[p]}</span>
        <PurposeTag purpose={p} icon={false} />
        {!builtin && a.step_worker === false ? <span className="chip warnc" title="This file has problems (see its warnings), so plans cannot use it until it is fixed"><AlertTriangle />Not usable</span>
          : w ? <span className="chip warnc" title={`${w} warning${w > 1 ? 's' : ''} from loading this file`}><AlertTriangle />{w}</span> : null}
        <span className={`src${builtin ? '' : ' folder'}`} title={builtin ? 'One of Launchpad\'s own agents' : `.claude/agents/${a.name}.md in ${v.folder}`}>
          {builtin ? <><Rocket />Built in</> : <><FolderOpen />{v.folder}</>}
        </span>
      </span>
      <span className="hero-name">{name}</span>
      {a.display_name && a.display_name !== a.name ? <code className="hero-file">{a.name}</code> : null}
      <span className="hero-desc">{a.description || <i>No description.</i>}</span>
      <span className="hero-foot">
        <span className="hero-model">{modelName(a.model) || 'Default model'}</span>
        <span className="hero-uses" title="Times this agent was started (yours, kept across restarts)"><b key={v.uses}>{v.uses.toLocaleString()}</b> use{v.uses === 1 ? '' : 's'}</span>
      </span>
    </button>
  );
}

function AddTile({ purpose, canAdd, first }: { purpose: Purpose; canAdd: boolean; first: boolean }) {
  return (
    <button type="button" className="hero add" data-purpose={purpose} disabled={!canAdd}
      title={canAdd ? undefined : 'Connect a folder in Settings first'}
      onClick={() => { actions.crewOpenForm(); actions.crewSetFields({ purpose }); }}>
      <span className="add-ic" aria-hidden="true"><Plus /></span>
      <span className="add-t">Add {purpose === 'exploring' ? 'an' : 'a'} {PURPOSE_LABEL[purpose].toLowerCase()} agent</span>
      <span className="add-s">{first ? `None yet. ${PURPOSE_HINT[purpose]}.` : 'Saved in the project folder for the planner to use.'}</span>
    </button>
  );
}

/* ---------------- one agent's full definition ---------------- */
function CrewDetail({ a, raw, setRaw, onBack }: { a: CrewAgentDef; raw: boolean; setRaw: (v: boolean) => void; onBack: () => void }) {
  const v = useComputed(st => ({ uses: sel.usesOf(st, a), folder: sel.isBuiltin(a) ? '' : folderName(st, a), removing: st.crewRemoving === a.name, err: st.crewError }));
  const [arm, setArm] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (armTimer.current) clearTimeout(armTimer.current); }, []);
  const p = sel.purposeOf(a), builtin = sel.isBuiltin(a);
  const chips = (list: string[], cls = '') => list.map((t, i) => <span key={i} className={`tool${cls ? ' ' + cls : ''}`}>{t}</span>);
  const custom = a.custom_tools || [], mcp = a.mcp_servers || [], warns = a.warnings || [], dis = a.disallowed_tools || [];
  const cfg = (c: unknown) => typeof c === 'string' ? c : JSON.stringify(c ?? {}, null, 2);
  const instr = String(a.instructions ?? '');
  const nLines = instr ? instr.split('\n').length : 0;
  const pr = a.promotion;
  const copy = () => {
    const pth = navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(a.source_path || '') : Promise.reject(new Error('no clipboard'));
    pth.then(() => actions.toast('Path copied'), () => actions.toast('Could not copy. Select the path text instead.'));
  };
  const onRemove = () => {
    if (armTimer.current) clearTimeout(armTimer.current);
    if (!arm) { setArm(true); armTimer.current = setTimeout(() => setArm(false), 4000); return; }
    setArm(false); actions.crewRemove(a.name);
  };
  const readOnly = p === 'exploring' || p === 'reviewing';
  const tools: ReactNode = Array.isArray(a.builtin_tools)
    ? (a.builtin_tools.length ? <div className="tools">{chips(a.builtin_tools)}</div> : <p className="none">None. This agent cannot use any built-in tools (custom tools only).</p>)
    : <p className="none">Not restricted: every built-in tool is available.</p>;

  return (
    <div className="crew-detail" id="crewDetail" data-purpose={p}>
      <div className="cd-bar">
        <Pill size="sm" variant="ghost" icon={<ArrowLeft />} onClick={onBack} id="crewBack">All agents</Pill>
      </div>
      <div className="cd-head">
        <span className="hero-ic lg" aria-hidden="true">{PURPOSE_ICON[p]}</span>
        <div className="cd-title">
          <h2 tabIndex={-1}>{a.display_name || a.name}</h2>
          <p>
            <PurposeTag purpose={p} icon={false} />
            <span className={`src${builtin ? '' : ' folder'}`}>{builtin ? <><Rocket />Built in</> : <><FolderOpen />From {v.folder}</>}</span>
            <code>{a.name}</code>
            <span>model <b>{a.model || 'default'}</b></span>
            <span className="cd-uses"><b>{v.uses.toLocaleString()}</b> {v.uses === 1 ? 'use' : 'uses'}</span>
          </p>
        </div>
        <div className="cd-actions">
          {a.editable ? <PenButton root={a.root} path={a.path || a.source_path} label="Edit file" /> : null}
          {!builtin ? (
            <Pill size="sm" variant={arm ? 'danger' : 'ghost'} icon={v.removing || arm ? undefined : <Trash />} disabled={v.removing} id="crewRemove"
              title="Remove this agent's file from the project folder (a backup copy is kept)" onClick={onRemove}>
              {v.removing ? 'Removing…' : arm ? 'Confirm remove' : 'Remove'}
            </Pill>
          ) : null}
        </div>
      </div>
      {v.err ? <div className="warn" role="alert">{v.err}</div> : null}
      {!builtin && a.step_worker === false ? <div className="warn"><b className="warn-h"><AlertTriangle />Plans cannot use this agent yet</b>Its file has problems (listed below). A step that names it is run by the Builder instead. Fix the file with the pen, then it can be named again.</div> : null}
      {!builtin && arm ? <p className="none cd-armnote">Click again to remove <b>{a.name}</b>. Plans that name it fall back to the Builder; a backup copy of the file is kept.</p> : null}
      {warns.length ? <div className="warn"><b className="warn-h"><AlertTriangle />{warns.length} warning{warns.length > 1 ? 's' : ''} from loading this file</b><ul>{warns.map((w, i) => <li key={i}>{w}</li>)}</ul></div> : null}
      <dl className="kv">
        <dt>Definition file</dt>
        <dd>
          <code className="pathcode">{pathBreaks(a.source_path || a.path || 'unknown')}</code>
          {a.source_path ? <button className="pill ghost xs" type="button" onClick={copy}><Copy />Copy path</button> : null}
        </dd>
        <dt>Description</dt><dd>{a.description ? a.description : <span className="none">None</span>}</dd>
        <dt>Purpose</dt><dd>{PURPOSE_LABEL[p]}<span className="mut">({PURPOSE_HINT[p].replace(/^./, ch => ch.toLowerCase())})</span></dd>
        {a.role && builtin ? <><dt>Role</dt><dd>{roleLabel(a.role)}</dd></> : null}
        {a.setup ? <><dt>Setup</dt><dd>{a.setup}{a.setup === 'project' ? <> <span className="mut">(the CLI harness in the project folder: its own instructions file, settings and skills)</span></> : a.setup === 'lean' ? <> <span className="mut">(only the listed tools, no folder settings)</span></> : null}</dd></> : null}
      </dl>
      {pr ? (
        <section className="cd-sec">
          <h3>Promotion <span>the planner can move to a stronger model early in a session</span></h3>
          <dl className="kv">
            <dt>Start model</dt><dd>{pr.start_model || '?'}</dd>
            <dt>Target model</dt><dd>{pr.target_model || '?'}</dd>
            <dt>Checked for</dt><dd>the first {pr.window_turns ?? '?'} turn{pr.window_turns === 1 ? '' : 's'} of each session</dd>
            <dt>Criteria file</dt><dd><code className="pathcode">{pathBreaks(pr.criteria_path || 'unknown')}</code>{pr.editable ? <PenButton root={pr.root} path={pr.path || pr.criteria_path} label="Edit criteria" /> : null}</dd>
          </dl>
          {pr.criteria ? <div className="prompt cd-crit"><Markdown text={pr.criteria} /></div> : null}
          <p className="none cd-crit-note">The user can also promote by hand from the picker under the Plan chat box.</p>
        </section>
      ) : null}
      <SkillsSection a={a} />
      <section className="cd-sec">
        <h3>Built-in tools <span>{readOnly && !builtin ? 'read-only purpose: write, edit and shell tools are removed when it runs' : 'the agent is restricted to these'}</span></h3>
        {tools}
        {dis.length ? <><h4>Explicitly blocked</h4><div className="tools">{chips(dis, 'no')}</div></> : null}
      </section>
      <section className="cd-sec">
        <h3>Custom tools <span>{custom.length}</span></h3>
        {custom.length ? <ul className="ctools">{custom.map((t, i) => <li key={i}><code>{t.name}</code>{t.description ? <p>{t.description}</p> : null}</li>)}</ul> : <p className="none">None.</p>}
      </section>
      <section className="cd-sec">
        <h3>MCP servers <span>{mcp.length}</span></h3>
        {mcp.length ? <ul className="ctools">{mcp.map((m, i) => <li key={i}><code>{m.name}</code><pre>{cfg(m.config)}</pre></li>)}</ul> : <p className="none">None.</p>}
      </section>
      <section className="cd-sec">
        <div className="cd-row">
          <h3>Full prompt <span>{nLines} lines · {instr.length.toLocaleString()} characters</span></h3>
          <div className="seg" role="group" aria-label="Prompt view">
            <button type="button" aria-pressed={!raw} onClick={() => setRaw(false)}>Formatted</button>
            <button type="button" aria-pressed={raw} onClick={() => setRaw(true)}>Raw</button>
          </div>
        </div>
        <div className="prompt">
          {instr ? (raw ? <pre className="raw">{instr}</pre> : <Markdown text={instr} />)
            : a.prompt_note ? <Markdown text={a.prompt_note} /> : <p className="none">This agent has no prompt text.</p>}
        </div>
      </section>
    </div>
  );
}

/* ---------------- one agent's skills ---------------- */
const EMPTY_SKILLS: SkillInfo[] = [];
function SkillsSection({ a }: { a: CrewAgentDef }) {
  const skills = useLaunchpad(st => st.crewSkills) || EMPTY_SKILLS;
  const setting = a.skill_setting;
  if (setting === undefined) return null;                                   // an older server: no skills yet
  if (setting === 'cli') {
    return (
      <section className="cd-sec" aria-labelledby="cdSkills">
        <h3 id="cdSkills">Skills <span>All (handled by the CLI)</span></h3>
        <p className="none">The CLI harness finds and picks skills itself, as it does in this folder; Launchpad does not limit them.</p>
      </section>
    );
  }
  const active = skills.filter(s => !s.shadowed), shadowed = skills.filter(s => s.shadowed);
  const all = setting === 'all';
  const picked = all ? active.map(s => s.name) : setting;
  const unknown = all ? [] : setting.filter(n => !active.some(s => s.name === n));
  const toggle = (name: string, on: boolean) => actions.setAgentSkills(a.name, on ? [...picked, name] : picked.filter(n => n !== name));
  const where = (s: SkillInfo) => `${s.folder_name || 'folder'} · .${s.source || 'claude'}/skills`;
  return (
    <section className="cd-sec" aria-labelledby="cdSkills">
      <div className="cd-row">
        <h3 id="cdSkills">Skills <span>{all ? `all ${active.length} found` : `${picked.length - unknown.length} of ${active.length} ticked`}</span></h3>
        <div className="seg" role="group" aria-label="Which skills this agent gets">
          <button type="button" aria-pressed={all} onClick={() => { if (!all) actions.setAgentSkills(a.name, 'all'); }}>All skills</button>
          <button type="button" aria-pressed={!all} onClick={() => { if (all) actions.setAgentSkills(a.name, active.map(s => s.name)); }}>Choose</button>
        </div>
      </div>
      <p className="none skl-note">Skills come from the folder and the folders ticked as additional (.claude/skills, or .agents/skills when a folder has no .claude folder). The agent sees each name and description and reads a skill when a task matches. A plan step can add skills for its own worker. Changes apply to new sessions and steps.</p>
      {active.length || unknown.length ? (
        <ul className="skl">
          {active.map(s => (
            <li key={s.name}>
              <label className="skl-row">
                <input type="checkbox" checked={picked.includes(s.name)} disabled={all} onChange={e => toggle(s.name, e.target.checked)} />
                <span className="skl-t"><code>{s.name}</code><small>{s.description || 'No description.'}</small></span>
                <span className="skl-src">{where(s)}</span>
              </label>
            </li>
          ))}
          {unknown.map(n => (
            <li key={'u:' + n} className="gone">
              <label className="skl-row" title="Not found in these folders: ignored when the agent runs">
                <input type="checkbox" checked onChange={() => toggle(n, false)} />
                <span className="skl-t"><code>{n}</code><small>Not found in these folders (ignored when it runs). Untick to forget it.</small></span>
              </label>
            </li>
          ))}
          {shadowed.map((s, i) => (
            <li key={'s:' + s.name + i} className="gone">
              <span className="skl-row" title="Another folder earlier in the list has a skill with this name, so that one is used">
                <input type="checkbox" disabled checked={false} aria-label={`${s.name} (shadowed)`} />
                <span className="skl-t"><code>{s.name}</code><small>Shadowed: the primary or an earlier folder has a skill with this name.</small></span>
                <span className="skl-src">{where(s)}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="none">No skills found. A skill is a folder holding a SKILL.md (name and description at the top).</p>}
    </section>
  );
}

