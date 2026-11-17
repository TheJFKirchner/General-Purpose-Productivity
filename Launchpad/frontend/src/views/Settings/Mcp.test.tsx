// @vitest-environment happy-dom
/* Settings view: section order, Connections (every Test state), the MCP library (list, add, edit with masked secrets,
   test, remove with confirm, import) and the Crew MCP picker, all against the in-page demo (no back end). */
import { it, expect } from 'vitest';
import { act } from 'react';
import { actions, dispatch, getState } from '../../store';
import { useDemoApp, step, q, qa, click, byText, sentOf, typeInto } from '../../test/demoApp';

useDemoApp();
const MASK = '••••••••';
const open = async () => { await act(async () => { actions.openSettings(); }); await step(1500); };
const conn = (id: string) => q(`[data-conn="${id}"]`)!;
const res = (id: string) => conn(id).querySelector('.conn-res')!.textContent;

it('Settings is a view with its sections in order, names the tools, and has no dialog', async () => {
  await open();
  expect(q('[role=dialog]')).toBeNull();
  expect(getState().ui.view).toBe('settings');
  expect(qa('#setBody > section h3').map(h => h.textContent)).toEqual(['Connections', 'MCP library', 'Working directories', 'Settings']);
  expect(qa('.conn-row b').map(b => b.textContent)).toEqual(['Claude Code', 'Cursor']);
  expect(q('#tab-settings')?.getAttribute('aria-pressed')).toBe('true');
  expect(sentOf('get_mcp').length).toBeGreaterThan(0);
});

it('Connections: Test shows every state', async () => {
  await open();
  expect(res('claude_code')).toBe('Not tested yet');
  await click(conn('claude_code').querySelector('button'));
  expect(sentOf('test_connection').at(-1)).toEqual({ type: 'test_connection', id: 'claude_code' });
  expect(res('claude_code')).toBe('Testing…');
  await step(1500);
  expect(res('claude_code')).toBe('Installed (version 2.1.0) and reachable');
  await click(conn('cursor').querySelector('button'));
  await step(1500);
  expect(res('cursor')).toBe('Installed (version 1.4.2), but Launchpad cannot use it yet');
  await act(async () => { dispatch({ type: 'connection_test', id: 'claude_code', installed: false, version: null, reachable: null, usable: null, detail: 'claude was not found on the PATH' }); });
  expect(res('claude_code')).toBe('Not installed');
  expect(conn('claude_code').textContent).toContain('claude was not found');
  await act(async () => { dispatch({ type: 'connection_test', id: 'claude_code', installed: true, version: '2.0.9', reachable: false, usable: false, detail: 'Not signed in' }); });
  expect(res('claude_code')).toBe('Installed (version 2.0.9), but not reachable');
  expect(conn('claude_code').textContent).toContain('Not signed in');
});

it('MCP library: statuses, test, edit keeps masked secrets, remove asks first', async () => {
  await open();
  const row = (n: string) => q(`[data-mcp="${n}"]`)!;
  expect(row('filesystem').textContent).toContain('Connected · 11 tools');
  expect(row('notes-db').textContent).toContain('Failed');
  expect(row('notes-db').textContent).toContain('program not found');
  expect(row('sandbox').textContent).toContain('Not tested');
  await click(row('sandbox').querySelector('button[aria-label="Test sandbox"]'));
  expect(sentOf('test_mcp_server').at(-1)).toEqual({ type: 'test_mcp_server', name: 'sandbox' });
  expect(row('sandbox').textContent).toContain('Testing…');
  await step(2000);
  expect(row('sandbox').textContent).toContain('Connected · 5 tools');
  /* edit: the masked secret goes back unchanged */
  await click(row('web-fetch').querySelector('button[aria-label="Edit web-fetch"]'));
  expect(q<HTMLInputElement>('#mcpUrl')!.value).toBe('https://mcp.example.com/fetch');
  expect(qa<HTMLInputElement>('#mcpHdr input').map(i => i.value)).toContain(MASK);
  expect(q('#mcpHdr input[type=password]')).toBeTruthy();
  await act(async () => { q<HTMLFormElement>('#mcpForm')!.requestSubmit(); });
  const sent = sentOf('save_mcp_server').at(-1) as unknown as { server: { config: { headers: Record<string, string> } }; original_name?: string };
  expect(sent.original_name).toBe('web-fetch');
  expect(sent.server.config.headers.Authorization).toBe(MASK);
  await step(2000);
  expect(q('#mcpForm')).toBeNull();
  expect(row('web-fetch').textContent).toContain('Connected');
  /* remove: a confirm that says assignments are cleared */
  await click(row('filesystem').querySelector('button[aria-label="Remove filesystem"]'));
  expect(sentOf('remove_mcp_server')).toHaveLength(0);
  expect(row('filesystem').textContent).toContain('cleared from 1 agent');
  await click(byText('[data-mcp="filesystem"] button', 'Confirm remove'));
  expect(sentOf('remove_mcp_server').at(-1)).toEqual({ type: 'remove_mcp_server', name: 'filesystem' });
  await step(500);
  expect(q('[data-mcp="filesystem"]')).toBeNull();
  expect(getState().mcp.assignments['launchpad-astronaut']).toBeUndefined();
});

it('MCP library: add by command, validation, a failing test shows its detail', async () => {
  await open();
  await click(q('#mcpAdd'));
  await act(async () => { q<HTMLFormElement>('#mcpForm')!.requestSubmit(); });
  expect(q('#mcpForm .warn')?.textContent).toContain('name');
  expect(sentOf('save_mcp_server')).toHaveLength(0);
  await typeInto(q<HTMLInputElement>('#mcpName')!, 'broken-one');
  await typeInto(q<HTMLInputElement>('#mcpCmd')!, 'node');
  await typeInto(q<HTMLTextAreaElement>('#mcpArgs')!, 'server.js\n--port=1');
  await click(byText('#mcpEnv button', 'Add variable'));
  await typeInto(qa<HTMLInputElement>('#mcpEnv input')[0], 'API_TOKEN');
  await typeInto(qa<HTMLInputElement>('#mcpEnv input')[1], 'abc');
  await act(async () => { q<HTMLFormElement>('#mcpForm')!.requestSubmit(); });
  expect(sentOf('save_mcp_server').at(-1)).toEqual({ type: 'save_mcp_server', server: { name: 'broken-one', kind: 'command', config: { command: 'node', args: ['server.js', '--port=1'], env: { API_TOKEN: 'abc' } } } });
  await step(2000);
  expect(q('[data-mcp="broken-one"]')!.textContent).toContain('Failed');
  expect(q('[data-mcp="broken-one"]')!.textContent).toContain('exited before');
  expect(getState().mcp.servers.find(x => x.name === 'broken-one')!.config.env!.API_TOKEN).toBe(MASK);
});

it('MCP library: import marks what is already present; empty state', async () => {
  await open();
  await click(byText('#setMcp button', 'Import from Claude Code'));
  expect(sentOf('list_mcp_imports').at(-1)).toEqual({ type: 'list_mcp_imports', source: 'claude_code' });
  await step(1000);
  const items = qa('.mcp-import li');
  expect(items).toHaveLength(3);
  expect(items[0].textContent).toContain('Already in the library');
  expect(items[0].querySelector<HTMLInputElement>('input')!.disabled).toBe(true);
  await click(items[1].querySelector('input'));
  await click(byText('.mcp-import button', 'Import 1 selected'));
  expect(sentOf('import_mcp_servers').at(-1)).toEqual({ type: 'import_mcp_servers', source: 'claude_code', names: ['github'] });
  await step(2000);
  expect(q('[data-mcp="github"]')!.textContent).toContain('Connected');
  await act(async () => { dispatch({ type: 'mcp_library', servers: [], assignments: {} }); });
  expect(q('#setMcp .empty')?.textContent).toContain('No MCP servers yet');
});

const openAgent = async (name: string) => {
  await act(async () => { actions.setView('crew'); });
  await step(1500);
  await click(q(`.hero[data-name="${name}"]`));
};

it('Crew: the picker offers only connected servers, none ticked by default; ticking sends set_agent_mcp', async () => {
  await openAgent('launchpad-planner');
  expect(qa('#crewMcp .skl code').map(c => c.textContent).sort()).toEqual(['filesystem', 'web-fetch']);   // notes-db failed, sandbox untested
  expect(qa<HTMLInputElement>('#crewMcp input').every(i => !i.checked)).toBe(true);
  expect(q('#crewMcp')!.textContent).toContain('none assigned');
  await click(qa('#crewMcp input')[0]);
  expect(sentOf('set_agent_mcp').at(-1)).toEqual({ type: 'set_agent_mcp', agent: 'launchpad-planner', servers: ['filesystem'] });
  await step(300);
  expect(qa<HTMLInputElement>('#crewMcp input').filter(i => i.checked)).toHaveLength(1);
});

it('Crew: an assigned server that failed stays listed with a warning, also on the card', async () => {
  await act(async () => { actions.setView('crew'); });
  await step(1500);
  expect(q('.hero[data-name="launchpad-builder"] .mcp-warn')?.textContent).toBe('MCP 1');
  expect(q('.hero[data-name="launchpad-planner"] .mcp-warn')).toBeNull();
  await click(q('.hero[data-name="launchpad-builder"]'));
  const li = q('#crewMcp li.gone')!;
  expect(li.textContent).toContain('notes-db');
  expect(li.textContent).toContain('Failed its last test');
  expect(q<HTMLInputElement>('#crewMcp li.gone input')!.checked).toBe(true);
  expect(q('#crewMcp .warn[role=alert]')?.textContent).toContain('not connected');
  /* removed from the library: still shown, as gone */
  await act(async () => { dispatch({ type: 'mcp_library', servers: [], assignments: { 'launchpad-builder': ['notes-db'] } }); });
  expect(q('#crewMcp li.gone')!.textContent).toContain('No longer in the library');
});

it('Crew: an agent whose engine cannot take MCP servers says so plainly', async () => {
  await openAgent('launchpad-builder');
  expect(q('#crewMcp [role=note]')).toBeNull();
  await act(async () => {
    const defs = getState().crewDefs!.map(a => (a.name === 'launchpad-builder' ? { ...a, mcp_supported: false, engine_label: 'Cursor' } : a));
    dispatch({ type: 'crew_list', agents: defs });
  });
  expect(q('#crewMcp [role=note]')?.textContent).toContain('Cursor cannot take MCP servers');
});

it('Crew: ticking a server keeps the list order; the file section is labelled and the CLI says it reads its own setup', async () => {
  await openAgent('launchpad-planner');
  const order = () => qa('#crewMcp .skl code').map(c => c.textContent);
  const before = order();
  await click(qa('#crewMcp input')[1]);
  await step(300);
  expect(order()).toEqual(before);
  expect(qa('#crewDetail h3').map(h => h.textContent).some(t => t!.startsWith("MCP servers from the agent's file"))).toBe(true);
  expect(qa('#crewDetail h3').some(h => h.textContent === 'MCP servers 0')).toBe(false);
  await click(byText('#crewBack', 'All agents'));
  await click(q('.hero[data-name="launchpad-pilot"]'));
  expect(q('#crewDetail')!.textContent).toContain('The CLI reads its own MCP setup');
});

it('Settings: warning results and failed-server details are not the stacked .warn box', async () => {
  await open();
  expect(q('.conn-res.warn, .conn-detail.warn')).toBeNull();
  expect(q('[data-mcp="notes-db"] .conn-detail.bad')).toBeTruthy();
});
