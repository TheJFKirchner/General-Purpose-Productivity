/* Settings > Connections: the CLI tools the server lists (id + display name), each with a Test button and an inline
   result. This is the one place that names the real tools ("Claude Code", "Cursor"); the rest of the app says "CLI".
   Nothing runs until the user clicks Test (test_connection {id} -> connection_test). */
import { actions, useLaunchpad } from '../../store';
import type { ConnTest } from '../../store';
import { Loading } from '../../components';
import { AlertTriangle, CircleCheck, CircleX, Info, Plug } from '../../components/icons';

/** The one line that sums a test up, with its tone: ok | warn | mut. Covers every state. */
export function connResult(t: ConnTest | undefined): { tone: 'ok' | 'warn' | 'mut'; text: string; detail?: string } {
  if (!t) return { tone: 'mut', text: 'Not tested yet' };
  if (t.status === 'testing') return { tone: 'mut', text: 'Testing…' };
  const r = t.result, ver = r.version ? ` (version ${r.version})` : '';
  if (!r.installed) return { tone: 'warn', text: 'Not installed', detail: r.detail || undefined };
  if (r.reachable === false) return { tone: 'warn', text: `Installed${ver}, but not reachable`, detail: r.detail || undefined };
  if (r.usable === false) return { tone: 'warn', text: `Installed${ver}, but Launchpad cannot use it yet`, detail: r.detail || undefined };
  if (r.reachable) return { tone: 'ok', text: `Installed${ver} and reachable`, detail: r.detail || undefined };
  return { tone: 'mut', text: `Installed${ver}`, detail: r.detail || undefined };
}

export function Connections() {
  const loaded = useLaunchpad(st => st.mcp.loaded);
  const items = useLaunchpad(st => st.mcp.connections);
  const tests = useLaunchpad(st => st.connTests);
  return (
    <section className="set-sec" aria-labelledby="setConnH" id="setConnections">
      <h3 id="setConnH"><Plug />Connections</h3>
      <p className="mut set-hint">The command-line tools Launchpad can work with. Test checks that the tool is installed and that Launchpad can reach it. Nothing runs until you press Test.</p>
      {!loaded ? <Loading /> : !items.length ? <p className="mut">The server listed no connections.</p> : (
        <div className="conn-list">
          {items.map(it => {
            const t = tests[it.id], r = connResult(t), busy = t?.status === 'testing';
            return (
              <div key={it.id} className="set-card conn-row" data-conn={it.id}>
                <div className="dr-main"><b>{it.name}</b></div>
                <div className="conn-side">
                  <span className={`conn-res ${r.tone === 'warn' ? 'bad' : r.tone}`} role="status" aria-live="polite">
                    {r.tone === 'ok' ? <CircleCheck /> : r.tone === 'warn' ? <CircleX /> : busy ? null : <Info />}
                    <span>{r.text}</span>
                  </span>
                  <button type="button" className="pill xs" disabled={busy} aria-label={`Test ${it.name}`} onClick={() => actions.testConnection(it.id)}>{busy ? 'Testing…' : 'Test'}</button>
                </div>
                {r.detail ? <p className={`conn-detail ${r.tone === 'warn' ? 'bad' : r.tone}`}>{r.tone === 'warn' ? <AlertTriangle /> : null}<span>{r.detail}</span></p> : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
