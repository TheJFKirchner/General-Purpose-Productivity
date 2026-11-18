/* The MCP picker on an agent's detail, beside the Skills section: tick the library servers this agent gets
   (set_agent_mcp {agent, servers}). Only servers whose last test passed are offered; nothing is ticked by default; an
   assigned server that is no longer connected stays listed, unticked-able, with a warning (the agent then runs without
   it). Same control for every agent, the planner and the CLI included. When the agent's engine cannot take MCP
   servers (CrewAgentDef.mcp_supported === false) the section says so. */
import { actions, sel, useComputed } from '../../store';
import type { CrewAgentDef } from '../../contract';
import { AlertTriangle } from '../../components/icons';

export function McpPicker({ a }: { a: CrewAgentDef }) {
  const v = useComputed(st => ({ loaded: st.mcp.loaded, assigned: sel.mcpAssigned(st, a.name), servers: st.mcp.servers }));
  const unsupported = a.mcp_supported === false;
  const picked = v.assigned.map(x => x.name);
  const bad = v.assigned.filter(x => !x.ok && x.server?.status !== 'testing');
  const toggle = (name: string, on: boolean) => actions.setAgentMcp(a.name, on ? [...picked, name] : picked.filter(n => n !== name));
  /* a stable order that ticking does not change: library order for servers that are offered or assigned, then any
     assigned name no longer in the library (alphabetical) */
  const rows = [
    ...v.servers.filter(s => s.status === 'connected' || picked.includes(s.name)).map(s => ({ name: s.name, x: v.assigned.find(y => y.name === s.name) || null, s })),
    ...v.assigned.filter(x => !x.server).sort((p, q) => p.name.localeCompare(q.name)).map(x => ({ name: x.name, x, s: null })),
  ];
  const total = picked.length;
  const reason = (x: (typeof v.assigned)[number]) =>
    !x.server ? 'No longer in the library.' : x.server.status === 'failed' ? `Failed its last test${x.server.detail ? ': ' + x.server.detail : '.'}`
      : x.server.status === 'testing' ? 'Being tested.' : 'Not tested since it changed.';
  return (
    <section className="cd-sec" aria-labelledby="cdMcp" id="crewMcp">
      <h3 id="cdMcp">Library MCP servers <span>{total ? `${total} assigned` : 'none assigned'}</span></h3>
      <p className="none skl-note">MCP servers from the library in Settings. This agent gets only the ones ticked here; none by default. Only servers whose last test passed are offered. If an assigned server stops working, the agent runs without it and the run shows a warning.</p>
      {unsupported ? (
        <div className="warn" role="note"><b className="warn-h"><AlertTriangle />Not used by this agent</b>
          {a.engine_label ? `${a.engine_label} cannot` : 'This agent\'s engine cannot'} take MCP servers for a run, so nothing ticked here is passed to it. Servers only take effect on the Claude engine.
        </div>
      ) : null}
      {bad.length ? (
        <div className="warn" role="alert"><b className="warn-h"><AlertTriangle />{bad.length} assigned server{bad.length > 1 ? 's are' : ' is'} not connected</b>
          <span>The agent goes ahead without {bad.length > 1 ? 'them' : 'it'}. Fix {bad.length > 1 ? 'them' : 'it'} in Settings, or untick below.</span>
        </div>
      ) : null}
      {!v.loaded ? <p className="none">Loading the MCP library…</p>
        : rows.length ? (
          <ul className="skl" aria-label="MCP servers for this agent">
            {rows.map(({ name, x, s: srv }) => x ? (
              <li key={name} className={x.ok ? undefined : 'gone'}>
                <label className="skl-row">
                  <input type="checkbox" checked onChange={() => toggle(name, false)} />
                  <span className="skl-t"><code>{name}</code>
                    <small>{x.ok ? `Connected${typeof x.server?.tool_count === 'number' ? ` · ${x.server.tool_count} tools` : ''}` : <><AlertTriangle className="mcp-ic" /> {reason(x)}</>}</small>
                  </span>
                  <span className="skl-src">{x.ok ? 'Assigned' : 'Warning'}</span>
                </label>
              </li>
            ) : (
              <li key={name}>
                <label className="skl-row">
                  <input type="checkbox" checked={false} onChange={() => toggle(name, true)} />
                  <span className="skl-t"><code>{name}</code><small>Connected{typeof srv?.tool_count === 'number' ? ` · ${srv.tool_count} tools` : ''}</small></span>
                </label>
              </li>
            ))}
          </ul>
        ) : (
          <p className="none">{v.servers.length ? 'No server is connected right now, so there is nothing to offer. Test them in Settings.' : 'The library is empty. Add a server in Settings first.'} <button type="button" className="pill xs" onClick={() => actions.setView('settings')}>Open Settings</button></p>
        )}
    </section>
  );
}
