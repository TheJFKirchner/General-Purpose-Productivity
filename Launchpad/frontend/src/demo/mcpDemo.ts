/* Connections and MCP library demo: two made-up connections, four made-up MCP servers (connected, connected with a
   masked secret, failed, untested), one import source, and the messages answered the way the server does. A save
   re-tests (testing, then connected; a command named "fail" fails), a test of a server whose name contains "broken"
   fails, remove clears its assignments, and secret values go out masked (a value sent back masked keeps its secret). */
import type { McpImportCandidate, McpServer } from '../contract';

type Ev = Record<string, any>;
export const MASK = '••••••••';
const SECRET = /key|token|secret|password|auth|bearer/i;

export interface McpDemoState { servers: McpServer[]; assignments: Record<string, string[]>; secrets: Record<string, Record<string, string>> }

export function demoMcp(): McpDemoState {
  const servers: McpServer[] = [
    { name: 'filesystem', kind: 'command', config: { command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem', 'C:/work'] }, status: 'connected', detail: null, tool_count: 11, tested_at: '2026-11-17T08:00:00' },
    { name: 'web-fetch', kind: 'url', config: { url: 'https://mcp.example.com/fetch', headers: { Authorization: MASK } }, status: 'connected', detail: null, tool_count: 4, tested_at: '2026-11-17T08:00:00' },
    { name: 'notes-db', kind: 'command', config: { command: 'notes-mcp', args: ['--db', 'notes.sqlite'], env: { NOTES_API_KEY: MASK } }, status: 'failed', detail: 'Could not start "notes-mcp": program not found on the PATH.', tool_count: null, tested_at: '2026-11-17T08:00:00' },
    { name: 'sandbox', kind: 'command', config: { command: 'python', args: ['-m', 'sandbox_mcp'] }, status: 'untested', detail: null, tool_count: null, tested_at: null },
  ];
  return {
    servers,
    /* the Builder is given a server that fails (shows the warning), the Explorer one that works; nothing else has any */
    assignments: { 'launchpad-builder': ['notes-db'], 'launchpad-astronaut': ['filesystem'] },
    secrets: { 'web-fetch': { Authorization: 'Bearer demo-secret' }, 'notes-db': { NOTES_API_KEY: 'demo-key' } },
  };
}

const IMPORTS: McpImportCandidate[] = [
  { name: 'filesystem', kind: 'command', summary: 'npx -y @modelcontextprotocol/server-filesystem C:/work', exists: false },
  { name: 'github', kind: 'url', summary: 'https://api.githubcopilot.com/mcp/', exists: false },
  { name: 'postgres', kind: 'command', summary: 'npx -y @modelcontextprotocol/server-postgres', exists: false },
];

const library = (s: McpDemoState): Ev => ({
  type: 'mcp_library', servers: JSON.parse(JSON.stringify(s.servers)), assignments: JSON.parse(JSON.stringify(s.assignments)),
  connections: [{ id: 'claude_code', name: 'Claude Code' }, { id: 'cursor', name: 'Cursor' }],
  import_sources: [{ id: 'claude_code', name: 'Claude Code' }],
});

const groups = (c: any): Record<string, string>[] => [c.env, c.headers].filter(Boolean);

export function demoMcpOn(msg: Ev, s: McpDemoState, emit: (ev: Ev) => void, later: (ms: number, fn: () => void) => void): boolean {
  const out = () => emit(library(s));
  const find = (n: string) => s.servers.find(x => x.name === n);
  const finish = (name: string) => later(900, () => {
    const x = find(name); if (!x) return;
    const bad = /broken/.test(name) || x.config.command === 'fail';
    x.status = bad ? 'failed' : 'connected'; x.detail = bad ? 'The server exited before it listed its tools.' : null;
    x.tool_count = bad ? null : 5; x.tested_at = new Date().toISOString(); out();
  });
  switch (msg.type) {
    case 'test_connection': {
      const id = msg.id;
      later(900, () => emit(id === 'cursor'
        ? { type: 'connection_test', id, installed: true, version: '1.4.2', reachable: null, usable: false, detail: 'Launchpad has no Cursor engine yet.' }
        : { type: 'connection_test', id, installed: true, version: '2.1.0', reachable: true, usable: true, detail: null }));
      return true;
    }
    case 'get_mcp': out(); return true;
    case 'save_mcp_server': {
      const sv = msg.server, orig = msg.original_name || null;
      if (s.servers.some(x => x.name === sv.name && x.name !== orig)) { emit({ ...library(s), error: `A server called ${sv.name} is already in the library.` }); return true; }
      /* a value sent back masked keeps its saved secret; the page only ever gets the mask */
      const keep = s.secrets[orig || sv.name] || {}, secrets: Record<string, string> = {};
      const config = JSON.parse(JSON.stringify(sv.config));
      for (const g of groups(config)) for (const k of Object.keys(g)) {
        if (g[k] === MASK && keep[k]) g[k] = keep[k];
        if (SECRET.test(k)) secrets[k] = g[k];
      }
      s.secrets[sv.name] = secrets;
      for (const g of groups(config)) for (const k of Object.keys(g)) if (SECRET.test(k)) g[k] = MASK;
      const entry: McpServer = { name: sv.name, kind: sv.kind, config, status: 'testing', detail: null, tool_count: null, tested_at: null };
      const i = orig ? s.servers.findIndex(x => x.name === orig) : -1;
      if (i >= 0) {
        s.servers[i] = entry;
        if (orig !== sv.name) for (const a of Object.keys(s.assignments)) s.assignments[a] = s.assignments[a].map(n => (n === orig ? sv.name : n));
      } else s.servers.push(entry);
      out(); finish(sv.name); return true;
    }
    case 'remove_mcp_server':
      s.servers = s.servers.filter(x => x.name !== msg.name);
      for (const a of Object.keys(s.assignments)) { s.assignments[a] = s.assignments[a].filter(n => n !== msg.name); if (!s.assignments[a].length) delete s.assignments[a]; }
      out(); return true;
    case 'test_mcp_server': { const x = find(msg.name); if (x) { x.status = 'testing'; x.detail = null; out(); finish(msg.name); } return true; }
    case 'list_mcp_imports':
      later(500, () => emit({ type: 'mcp_imports', source: msg.source, servers: IMPORTS.map(c => ({ ...c, exists: !!find(c.name) })) }));
      return true;
    case 'import_mcp_servers':
      for (const n of msg.names || []) {
        const c = IMPORTS.find(x => x.name === n); if (!c || find(n)) continue;
        const parts = c.summary.split(' ');
        s.servers.push({ name: n, kind: c.kind, config: c.kind === 'url' ? { url: c.summary } : { command: parts[0], args: parts.slice(1) }, status: 'testing', detail: null, tool_count: null, tested_at: null });
        finish(n);
      }
      out(); return true;
    case 'set_agent_mcp':
      if ((msg.servers || []).length) s.assignments[msg.agent] = [...msg.servers]; else delete s.assignments[msg.agent];
      out(); return true;
  }
  return false;
}
