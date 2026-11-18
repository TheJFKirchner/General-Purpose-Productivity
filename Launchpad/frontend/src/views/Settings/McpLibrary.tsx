/* Settings > MCP library: the user's MCP servers with their test status, an add / edit form (command + arguments +
   environment variables, or URL + headers), Test, Remove (with a confirm that says assignments are cleared) and
   "Import from <source>" (the sources and the candidates come from the server). Secret values arrive masked and are
   sent back unchanged to keep them. Messages: save_mcp_server, remove_mcp_server, test_mcp_server, list_mcp_imports,
   import_mcp_servers; every one is answered by mcp_library. */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { actions, useLaunchpad } from '../../store';
import type { McpConfig, McpKind, McpServer } from '../../contract';
import { Empty, Loading } from '../../components';
import { AlertTriangle, CircleCheck, CircleX, Download, Loader2, Pencil, Plus, Server, Trash, X } from '../../components/icons';

/* ---------------- form model ---------------- */
interface Pair { k: string; v: string }
interface Form { original?: string; name: string; kind: McpKind; command: string; args: string; env: Pair[]; url: string; headers: Pair[] }
const pairs = (o?: Record<string, string>): Pair[] => Object.entries(o || {}).map(([k, v]) => ({ k, v: String(v) }));
const blank = (): Form => ({ name: '', kind: 'command', command: '', args: '', env: [], url: '', headers: [] });
const fromServer = (s: McpServer): Form => ({
  original: s.name, name: s.name, kind: s.kind, command: s.config.command || '', args: (s.config.args || []).join('\n'),
  env: pairs(s.config.env), url: s.config.url || '', headers: pairs(s.config.headers),
});
const toObj = (ps: Pair[]) => { const o: Record<string, string> = {}; for (const p of ps) if (p.k.trim()) o[p.k.trim()] = p.v; return o; };
/** The config to send: only the fields of the chosen kind, empty ones left out. */
export function formConfig(f: Form): McpConfig {
  if (f.kind === 'url') { const h = toObj(f.headers); return { url: f.url.trim(), ...(Object.keys(h).length ? { headers: h } : {}) }; }
  const args = f.args.split('\n').map(a => a.trim()).filter(Boolean), env = toObj(f.env);
  return { command: f.command.trim(), ...(args.length ? { args } : {}), ...(Object.keys(env).length ? { env } : {}) };
}
const looksSecret = (k: string, v: string) => /key|token|secret|password|auth|bearer/i.test(k) || /^[•*]{3,}$/.test(v);
/** A masked value reads as a placeholder: it is kept unless the user types a new one. */
const isMasked = (v: string) => /^[•*]{3,}$/.test(v);

export function summary(s: McpServer): string {
  return s.kind === 'url' ? (s.config.url || '') : [s.config.command, ...(s.config.args || [])].filter(Boolean).join(' ');
}

export function McpLibrary() {
  const m = useLaunchpad(st => st.mcp);
  const [form, setForm] = useState<Form | null>(null);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState('');
  const [removing, setRemoving] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  /* the library answers a save: close the form (an error from the server keeps it open) */
  useEffect(() => { if (saving) { setSaving(false); if (!m.error) setForm(null); } }, [m.servers]);          // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (saving && m.error) setSaving(false); }, [m.error, saving]);
  useEffect(() => { if (form) formRef.current?.querySelector<HTMLInputElement>('input')?.focus(); }, [form?.original, form === null]);   // eslint-disable-line react-hooks/exhaustive-deps

  const assignedCount = (name: string) => Object.values(m.assignments).filter(l => l.includes(name)).length;
  const submit = (e: FormEvent) => {
    e.preventDefault(); if (!form) return;
    const name = form.name.trim();
    if (!name) return setProblem('Give the server a name.');
    if (m.servers.some(s => s.name === name && s.name !== form.original)) return setProblem(`A server called ${name} is already in the library.`);
    if (form.kind === 'command' && !form.command.trim()) return setProblem('Enter the command to start the server.');
    if (form.kind === 'url' && !form.url.trim()) return setProblem('Enter the server URL.');
    setProblem(''); setSaving(true);
    actions.saveMcpServer({ name, kind: form.kind, config: formConfig(form) }, form.original);
  };

  return (
    <section className="set-sec" aria-labelledby="setMcpH" id="setMcp">
      <div className="set-sec-head">
        <h3 id="setMcpH"><Server />MCP library</h3>
        <div className="row">
          {m.importSources.map(src => <ImportButton key={src.id} id={src.id} name={src.name} />)}
          <button type="button" className="pill sm primary" id="mcpAdd" onClick={() => { setProblem(''); setForm(blank()); }}><Plus />Add server</button>
        </div>
      </div>
      <p className="mut set-hint">MCP servers give an agent extra tools. Add them here, then choose which agents get which servers in Crew; no agent has any by default. Each server is tested when you save it, when you press Test and when Launchpad starts. A test starts the server, reads its tool list and stops it, so it costs nothing.</p>
      {m.error && !form ? <div className="warn setmsg" role="alert"><AlertTriangle />{m.error}</div> : null}
      {m.importSources.map(src => <ImportPanel key={src.id} id={src.id} name={src.name} />)}
      {form ? (
        <form className="mcp-form card" ref={formRef} onSubmit={submit} aria-label={form.original ? `Edit ${form.original}` : 'Add an MCP server'} id="mcpForm">
          <h4>{form.original ? `Edit ${form.original}` : 'Add an MCP server'}</h4>
          <div className="mcp-fld"><label htmlFor="mcpName">Name</label><input className="field" id="mcpName" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. filesystem" autoComplete="off" /></div>
          <div className="mcp-fld"><span id="mcpKindL">Type</span>
            <div className="seg" role="group" aria-labelledby="mcpKindL">
              <button type="button" aria-pressed={form.kind === 'command'} onClick={() => setForm({ ...form, kind: 'command' })}>Command</button>
              <button type="button" aria-pressed={form.kind === 'url'} onClick={() => setForm({ ...form, kind: 'url' })}>URL</button>
            </div>
          </div>
          {form.kind === 'command' ? <>
            <div className="mcp-fld"><label htmlFor="mcpCmd">Command</label><input className="field" id="mcpCmd" value={form.command} onChange={e => setForm({ ...form, command: e.target.value })} placeholder="e.g. npx" autoComplete="off" /></div>
            <div className="mcp-fld"><label htmlFor="mcpArgs">Arguments, one per line</label><textarea className="field" id="mcpArgs" rows={3} value={form.args} onChange={e => setForm({ ...form, args: e.target.value })} placeholder={'-y\n@modelcontextprotocol/server-filesystem'} /></div>
            <PairEditor label="Environment variables" kName="Variable" vName="Value" rows={form.env} onChange={env => setForm({ ...form, env })} id="mcpEnv" />
          </> : <>
            <div className="mcp-fld"><label htmlFor="mcpUrl">URL</label><input className="field" id="mcpUrl" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} placeholder="https://example.com/mcp" autoComplete="off" /></div>
            <PairEditor label="Headers" kName="Header" vName="Value" rows={form.headers} onChange={headers => setForm({ ...form, headers })} id="mcpHdr" />
          </>}
          {problem ? <div className="warn" role="alert">{problem}</div> : null}
          {m.error ? <div className="warn" role="alert">{m.error}</div> : null}
          <div className="row">
            <button type="submit" className="pill sm primary" disabled={saving}>{saving ? 'Saving and testing…' : form.original ? 'Save changes' : 'Save and test'}</button>
            <button type="button" className="pill sm ghost" onClick={() => { setForm(null); setProblem(''); }}>Cancel</button>
          </div>
        </form>
      ) : null}
      {!m.loaded ? <Loading /> : !m.servers.length ? (
        <Empty icon={<Server />} title="No MCP servers yet">Add one with Add server{m.importSources.length ? ', or import the ones you already use' : ''}. Servers you add can then be given to any agent in Crew.</Empty>
      ) : (
        <ul className="mcp-list" id="mcpList">
          {m.servers.map(s => (
            <li key={s.name} className="set-card mcp-row" data-mcp={s.name}>
              <div className="mcp-main">
                <div className="dr-main"><b>{s.name}</b><span className="chip">{s.kind === 'url' ? 'URL' : 'Command'}</span><McpStatusChip s={s} /></div>
                <code className="mcp-sum">{summary(s)}</code>
                {s.status === 'failed' && s.detail ? <p className="conn-detail bad"><AlertTriangle /><span>{s.detail}</span></p> : null}
              </div>
              {removing === s.name ? (
                <div className="mcp-confirm" role="alertdialog" aria-label={`Remove ${s.name}`}>
                  <span>Remove <b>{s.name}</b>? {assignedCount(s.name) ? `It will be cleared from ${assignedCount(s.name)} agent${assignedCount(s.name) === 1 ? '' : 's'}.` : 'No agent has it.'} Assignments to it are cleared.</span>
                  <button type="button" className="pill xs danger" onClick={() => { setRemoving(null); actions.removeMcpServer(s.name); }}>Confirm remove</button>
                  <button type="button" className="pill xs ghost" onClick={() => setRemoving(null)}>Cancel</button>
                </div>
              ) : (
                <div className="row">
                  <button type="button" className="pill xs" disabled={s.status === 'testing'} aria-label={`Test ${s.name}`} onClick={() => actions.testMcpServer(s.name)}>Test</button>
                  <button type="button" className="pill xs" aria-label={`Edit ${s.name}`} onClick={() => { setProblem(''); setForm(fromServer(s)); }}><Pencil />Edit</button>
                  <button type="button" className="pill xs ghost" aria-label={`Remove ${s.name}`} onClick={() => setRemoving(s.name)}><Trash />Remove</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function McpStatusChip({ s }: { s: Pick<McpServer, 'status' | 'tool_count'> }) {
  if (s.status === 'connected') return <span className="chip ok"><CircleCheck />Connected{typeof s.tool_count === 'number' ? ` · ${s.tool_count} tool${s.tool_count === 1 ? '' : 's'}` : ''}</span>;
  if (s.status === 'failed') return <span className="chip warnc"><CircleX />Failed</span>;
  if (s.status === 'testing') return <span className="chip"><Loader2 className="spin" />Testing…</span>;
  return <span className="chip">Not tested</span>;
}

/** Name / value rows (environment variables, headers). Secret-looking values show as dots; masked ones are kept unless retyped. */
function PairEditor({ label, kName, vName, rows, onChange, id }: { label: string; kName: string; vName: string; rows: Pair[]; onChange: (r: Pair[]) => void; id: string }) {
  const set = (i: number, patch: Partial<Pair>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <fieldset className="mcp-pairs" id={id}>
      <legend>{label}</legend>
      {rows.map((r, i) => (
        <div className="mcp-pair" key={i}>
          <input className="field" aria-label={`${kName} ${i + 1} name`} placeholder={kName} value={r.k} onChange={e => set(i, { k: e.target.value })} autoComplete="off" />
          <input className="field" aria-label={`${kName} ${i + 1} value`} placeholder={vName} type={looksSecret(r.k, r.v) ? 'password' : 'text'} value={r.v} onChange={e => set(i, { v: e.target.value })} autoComplete="off"
            title={isMasked(r.v) ? 'Saved secret, hidden. Leave it as it is to keep it, or type a new value.' : undefined} />
          <button type="button" className="pill xs ghost icon" aria-label={`Remove ${kName.toLowerCase()} ${i + 1}`} onClick={() => onChange(rows.filter((_, j) => j !== i))}><X /></button>
        </div>
      ))}
      <button type="button" className="pill xs" onClick={() => onChange([...rows, { k: '', v: '' }])}><Plus />Add {kName.toLowerCase()}</button>
    </fieldset>
  );
}

/* ---------------- import ---------------- */
function ImportButton({ id, name }: { id: string; name: string }) {
  const open = useLaunchpad(st => !!st.mcpImports[id]);
  return <button type="button" className="pill sm" aria-expanded={open} onClick={() => (open ? actions.closeMcpImports(id) : actions.listMcpImports(id))}><Download />Import from {name}</button>;
}

function ImportPanel({ id, name }: { id: string; name: string }) {
  const list = useLaunchpad(st => st.mcpImports[id]);
  const [ticked, setTicked] = useState<string[]>([]);
  if (!list) return null;
  const toggle = (n: string, on: boolean) => setTicked(t => (on ? [...t, n] : t.filter(x => x !== n)));
  return (
    <div className="mcp-import card" role="group" aria-label={`Import from ${name}`}>
      <h4>Import from {name}</h4>
      {list.loading ? <Loading>Reading the {name} setup…</Loading> : !list.servers.length ? <p className="mut">{name} has no MCP servers to import.</p> : (
        <ul className="skl">
          {list.servers.map(c => (
            <li key={c.name} className={c.exists ? 'gone' : undefined}>
              <label className="skl-row">
                <input type="checkbox" disabled={c.exists} checked={!c.exists && ticked.includes(c.name)} onChange={e => toggle(c.name, e.target.checked)} />
                <span className="skl-t"><code>{c.name}</code><small>{c.summary}</small></span>
                <span className="skl-src">{c.exists ? 'Already in the library' : c.kind === 'url' ? 'URL' : 'Command'}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <div className="row">
        <button type="button" className="pill sm primary" disabled={list.loading || !ticked.length} onClick={() => { actions.importMcpServers(id, ticked); setTicked([]); actions.closeMcpImports(id); }}>Import {ticked.length ? `${ticked.length} selected` : 'selected'}</button>
        <button type="button" className="pill sm ghost" onClick={() => { setTicked([]); actions.closeMcpImports(id); }}>Cancel</button>
      </div>
    </div>
  );
}
