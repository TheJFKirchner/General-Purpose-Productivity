/* Connections and the MCP library: the server-event handlers (connection_test, mcp_library, mcp_imports) used by
   reducer.ts. The lists (connections, import sources, servers, assignments) are the server's; nothing is decided here. */
import type { ConnectionTestEvent, McpImportsEvent, McpLibraryEvent } from '../contract';
import type { Ctx } from './core';

export function onConnectionTest(c: Ctx, ev: ConnectionTestEvent): void {
  const { type: _t, id, ...result } = ev; void _t;
  c.st.connTests[id] = { status: 'done', result };
}

export function onMcpLibrary(c: Ctx, ev: McpLibraryEvent): void {
  const m = c.st.mcp;
  m.loaded = true;
  m.servers = Array.isArray(ev.servers) ? ev.servers : [];
  m.assignments = ev.assignments && typeof ev.assignments === 'object' ? ev.assignments : {};
  if (Array.isArray(ev.connections)) m.connections = ev.connections;
  if (Array.isArray(ev.import_sources)) m.importSources = ev.import_sources;
  m.error = ev.error || null;
  /* an import list that was open closes once the library answers an import (names now present are marked on reopen) */
}

export function onMcpImports(c: Ctx, ev: McpImportsEvent): void {
  c.st.mcpImports[ev.source] = { loading: false, servers: Array.isArray(ev.servers) ? ev.servers : [] };
}
