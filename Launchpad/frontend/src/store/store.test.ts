/* Store tests (zero back end): every contract event is handled, key behaviours match the vanilla page, and the
   in-page demo drives the store. Run: npm test */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SERVER_EVENT_TYPES, type UiMessage } from '../contract';
import { actions, dispatch, getState, sel, useLaunchpad } from './index';
import { setTransport } from './core';
import { initialState } from './initial';
import { Demo } from '../demo/Demo';

const sent: UiMessage[] = [];
beforeEach(() => {
  vi.useFakeTimers();
  useLaunchpad.setState(initialState(), true);
  sent.length = 0;
  setTransport(m => { sent.push(m); return true; });
});
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

const SAMPLES: Record<string, Record<string, unknown>> = {
  snapshot: { current_session_id: 'S1', sessions: [{ session_id: 'S1', folder: 'f', dir_id: 'd1', cwd: 'C:/p', chat: [{ role: 'user', text: 'hi' }, { role: 'assistant', text: 'yo' }], report_sent: false, model: 'sonnet', promoted: false, visual_sets: [] }], chats: [{ id: 'c0', mode: 'default', model: 'sonnet', cwd: 'C:/p', history: [{ role: 'user', markdown: 'q' }] }] },
  planner_message: { text: 'Hello **there**', session_id: 'S1' },
  user_message: { text: 'me', session_id: 'S1' },
  typing: { on: true, session_id: 'S1' },
  question_round: { id: 'r1', round: 1, questions: [{ id: 'a', title: 'Q?', rec: 'Yes' }], session_id: 'S1' },
  usage: { scope: 'app', tokens: 10, cost: 0.5, input_tokens: 1, output_tokens: 2, cache_read_tokens: 3, cache_write_tokens: 4 },
  crew: { agents: [{ name: 'Planner', role: 'planner', status: 'waiting', session_id: 'S1' }] },
  plan_meta: { name: 'My plan', mode: 'Plan', status: 'Draft', session_id: 'S1' },
  system: { text: 'note', session_id: 'S1' },
  session_started: { session_id: 'S1', folder: 'f', dir_id: 'd1', cwd: 'C:/p' },
  settings: { directories: [{ dir_id: 'd1', path: 'C:/p', name: 'p', exists: true, is_default: true, busy: false }], values: { question_timeout_s: { value: 180, applies: 'now', overridden_by_launch: false } }, can_pick_directory: false },
  directory_picked: { path: null },
  dir_listing: { root: 'd1', path: '', entries: [{ name: 'b.md', type: 'file', kind: 'markdown', editable: true }, { name: 'a', type: 'dir' }] },
  file_content: { root: 'd1', path: 'b.md', kind: 'markdown', text: '# B', size: 3, mtime: 1, version: 1, editable: true, applies: 'now', validates_as: null },
  file_saved: { root: 'd1', path: 'b.md', version: 2, backup_id: 'k1', applies: 'now' },
  file_error: { root: 'd1', path: 'zz.md', code: 'not_found', message: 'nope' },
  backups: { root: 'd1', path: 'b.md', items: [] },
  plan_draft: { session_id: 'S1', path: 'plan.md', markdown: '# Plan X', steps: [{ n: 1, title: 'One', agent: null, agent_display: 'Builder' }], revision: 1, previous_runs: 0 },
  run_started: { session_id: 'S1', name: 'Plan X', steps: [{ n: 1, title: 'One', status: 'todo', agent: 'copy-reviewer', agent_display: 'Copy reviewer' }], run: 1, revision: 1, autopilot: false },
  planner_model: { session_id: 'S1', model: 'opus', promoted: true, reason: 'big', by: 'criteria' },
  autopilot: { session_id: 'S1', on: true },
  step_update: { session_id: 'S1', n: 1, status: 'done', built: ['x.txt'], report_path: 'step-1.md', agent: 'copy-reviewer', agent_display: 'Builder', agent_fallback: true },
  queue_item: { id: 'q1', session_id: 'S1', chat_id: null, kind: 'question', agent: 'Builder', agent_id: 'b1', step: 1, title: 'Which?', body: 'b', rec: 'A', options: ['A', 'B'], blocking: false, timeout_s: 180, expires_at: null },
  queue_resolved: { id: 'q1', answer: 'A', by: 'timer' },
  agent_usage: { session_id: 'S1', chat_id: null, agent_id: 'b1', role: 'builder', name: 'Builder', step: 1, status: 'working', input_tokens: 1, output_tokens: 2, cache_read_tokens: 3, cache_write_tokens: 4, cost_usd: 0.25, tool_calls: 3 },
  activity: { id: 'a1', session_id: 'S1', chat_id: null, agent_id: 'b1', role: 'builder', name: 'Builder', step: 1, tool: 'Read', summary: 'x.txt', status: 'started', ts: '2026-11-13T10:00:00Z' },
  run_finished: { session_id: 'S1', status: 'done', report_path: 'report.md', markdown: '# Report', total_cost_usd: 0.25, planner_cost_usd: 0.1 },
  crew_list: { dir_id: 'd1', tool_choices: ['Read', 'Write'], agents: [
    { name: 'launchpad-pilot', display_name: 'Claude Code', role: 'pilot', purpose: 'building', uses: 4, builtin: true },
    { name: 'copy-reviewer', display_name: 'Copy reviewer', role: null, purpose: 'reviewing', uses: 1, builtin: false, step_worker: true, root: 'd1', path: '.claude/agents/copy-reviewer.md' }] },
  agent_uses: { name: 'copy-reviewer', uses: 2 },
  agent_drafted: { ok: false, dir_id: 'd1', error: 'nope' },
  agent_saved: { ok: false, dir_id: 'd1', error: 'Not saved', problems: ['name: lowercase letters, digits and dashes only'] },
  agent_removed: { ok: false, dir_id: 'd1', name: 'copy-reviewer', error: 'locked' },
  chat_started: { chat_id: 'c1', mode: 'default', model: 'sonnet', cwd: 'C:/p', dir_id: 'd1' },
  chat_typing: { chat_id: 'c1', on: true },
  chat_delta: { chat_id: 'c1', text: 'Hel' },
  chat_message: { chat_id: 'c1', role: 'assistant', markdown: 'Hello' },
  chat_mode: { chat_id: 'c1', mode: 'plan' },
  chat_done: { chat_id: 'c1', status: 'failed', error: 'boom' },
  visual_set: { session_id: 'S1', set_id: 'v1', brief: 'Look?', options: [{ id: 'o1', label: 'Bar', status: 'rendering' }], picked_id: null },
};

describe('reducer', () => {
  it('has a sample for, and handles, every server event in the contract', () => {
    for (const t of SERVER_EVENT_TYPES) {
      expect(SAMPLES[t], `sample for ${t}`).toBeTruthy();
      expect(() => dispatch({ type: t, ...SAMPLES[t] })).not.toThrow();
    }
    const st = getState();
    expect(st.current).toBe('S1');
    const s = st.sessions.S1;
    expect(s.status).toBe('done');
    expect(s.report?.markdown).toBe('# Report');
    expect(s.autopilot).toBe(true);
    expect(s.promoted).toBe(true);
    expect(s.log.some(e => e.kind === 'sys' && e.cls === 'promo')).toBe(true);
    expect(s.log.some(e => e.kind === 'plancard' && e.state === 'approved')).toBe(true);
    expect(st.queue.find(i => i.id === 'report:S1')).toBeTruthy();
    expect(st.queue.find(i => i.id === 'q1')?.ui).toBe('auto');
    expect(st.agents.b1.cost_usd).toBe(0.25);
    expect(st.acts).toHaveLength(1);
    expect(st.chats.c1.mode).toBe('plan');
    expect(st.chats.c1.log.some(e => e.kind === 'sys' && e.cls === 'err')).toBe(true);
    expect(st.crewDefs).toHaveLength(2);
    expect(st.crewDirId).toBe('d1');
    expect(st.toolChoices).toEqual(['Read', 'Write']);
    expect(st.crewUses['copy-reviewer']).toBe(2);                         // agent_uses after crew_list
    expect(st.crewUses['launchpad-pilot']).toBe(4);
    expect(st.crewError).toBe('locked');
    expect(s.run!.steps[0]).toMatchObject({ agent: 'copy-reviewer', agent_display: 'Builder', agent_fallback: true });
    expect(sel.stepAgent(st.crewDefs, s.run!.steps[0])).toMatchObject({ fallback: true, label: 'Builder', name: 'copy-reviewer' });
    expect(st.fx.cache['d1|'].map(e => e.name)).toEqual(['a', 'b.md']);   // folders first
    expect(st.files['d1|b.md']).toBeTruthy();
    expect(s.visualSets).toHaveLength(1);
    expect(sel.sessionTotal(st, 'S1')).toBeCloseTo(0.25);
  });

  it('a snapshot replays quietly and ends the replay on usage', () => {
    dispatch({ type: 'snapshot', ...SAMPLES.snapshot });
    expect(getState().replaying).toBe(true);
    dispatch({ type: 'run_started', ...SAMPLES.run_started });
    expect(getState().ui.toasts).toHaveLength(0);
    dispatch({ type: 'usage', ...SAMPLES.usage });
    expect(getState().replaying).toBe(false);
    const log = getState().sessions.S1.log;
    expect(log.filter(e => e.kind === 'bubble').map(e => (e as { text: string }).text)).toEqual(['hi', 'yo']);
    expect(getState().chats.c0.log).toHaveLength(1);
  });

  it('a newer draft supersedes the open card; approving sends plan_approve', () => {
    dispatch({ type: 'session_started', session_id: 'S1' });
    dispatch({ type: 'plan_draft', ...SAMPLES.plan_draft });
    dispatch({ type: 'plan_draft', ...SAMPLES.plan_draft, revision: 2, markdown: '# Plan Y' });
    const cards = getState().sessions.S1.log.filter(e => e.kind === 'plancard') as { state: string }[];
    expect(cards.map(c => c.state)).toEqual(['superseded', 'open']);
    actions.approve('S1');
    expect(sent.at(-1)).toEqual({ type: 'plan_approve', session_id: 'S1' });
    expect(getState().sessions.S1.approving).toBe(true);
  });

  it('round answers go out once every question is answered', () => {
    dispatch({ type: 'session_started', session_id: 'S1' });
    dispatch({ type: 'question_round', id: 'r1', round: 1, questions: [{ id: 'a', title: 'A?', rec: 'Y' }, { id: 'b', title: 'B?' }], session_id: 'S1' });
    actions.answerQuestion('r1', 'a', { accepted: true });
    expect(sent.find(m => m.type === 'round_answer')).toBeUndefined();
    actions.answerQuestion('r1', 'b', { accepted: false, text: 'no' });
    expect(sent.find(m => m.type === 'round_answer')).toEqual({ type: 'round_answer', roundId: 'r1', answers: { a: { accepted: true }, b: { accepted: false, text: 'no' } } });
  });

  it('Claude Code: first message starts a chat and is sent once chat_started arrives', () => {
    actions.sendChat('do it');
    expect(sent.at(-1)).toEqual({ type: 'chat_new' });
    dispatch({ type: 'chat_started', chat_id: 'c9', mode: 'default', model: 'sonnet', cwd: 'C:/p' });
    expect(sent.at(-1)).toEqual({ type: 'chat_message', chat_id: 'c9', text: 'do it' });
    expect(getState().chats.c9.busy).toBe(true);
  });

  it('purposes, step agents and form problems', () => {
    dispatch({ type: 'crew_list', ...SAMPLES.crew_list });
    const st = getState(), defs = st.crewDefs!;
    expect(defs.map(sel.purposeOf)).toEqual(['building', 'reviewing']);
    expect(sel.purposeOf({ name: 'x', builtin: false })).toBe('building');                  // folder agent with no purpose
    expect(sel.purposeOf({ name: 'launchpad-astronaut', role: 'astronaut', builtin: true })).toBe('exploring');
    expect(sel.stepAgent(defs, { agent: null, agent_display: 'Builder' })).toBeNull();
    expect(sel.stepAgent(defs, { agent: 'copy-reviewer', agent_display: 'Copy reviewer' })).toMatchObject({ purpose: 'reviewing', label: 'Copy reviewer', fallback: false });
    /* the step's own agent_purpose wins over whatever folder Crew is showing */
    expect(sel.stepAgent(null, { agent: 'copy-reviewer', agent_display: 'Copy reviewer', agent_purpose: 'reviewing' })!.purpose).toBe('reviewing');
    expect(sel.stepAgent(defs, { agent: 'copy-reviewer', agent_display: 'Copy reviewer', agent_purpose: 'exploring' })!.purpose).toBe('exploring');
    dispatch({ type: 'session_started', session_id: 'S9', dir_id: 'd2' });
    expect(sel.defsForSession(getState(), getState().sessions.S9)).toBeNull();          // Crew shows d1, the session is in d2
    dispatch({ type: 'run_finished', session_id: 'S9', status: 'done', report_path: 'r.md', markdown: '# R' });
    expect(getState().queue.find(i => i.id === 'report:S9')?.agent).toBe('Orchestrator');
    expect(sel.problemField('name: lowercase letters, digits and dashes only')).toBe('name');
    expect(sel.problemField("front matter: 'description' missing")).toBe('description');
    expect(sel.problemField('tools: not a tool name: Foo')).toBe('tools');
    expect(sel.problemField('the file needs a front matter block')).toBeNull();
    expect(sel.problemText({ field: 'model', message: 'bad' })).toBe('model: bad');
    const probs = sel.agentFormProblems(st, { name: 'Copy reviewer', description: '', purpose: 'reviewing', model: 'haiku', tools: ['Write'], instructions: '' });
    expect(probs.map(p => p.field).sort()).toEqual(['description', 'instructions', 'name', 'tools']);
    expect(sel.agentFormProblems(st, { name: 'copy-reviewer', description: 'd', purpose: 'building', model: 'haiku', tools: [], instructions: 'i' })[0].message).toContain('already exists');
  });

  it('chat switch: what is waiting on each side; New chat and Send plan flip to Claude Code', () => {
    dispatch({ type: 'session_started', session_id: 'S1', dir_id: 'd1' });
    dispatch({ type: 'question_round', id: 'r1', round: 1, questions: [{ id: 'a', title: 'A?' }], session_id: 'S1' });
    expect(sel.plannerWaiting(getState())).toBe(1);
    dispatch({ type: 'plan_draft', ...SAMPLES.plan_draft });
    expect(sel.plannerWaiting(getState())).toBe(2);                       // open round + a draft to approve
    dispatch({ type: 'chat_started', chat_id: 'c1', mode: 'default' });
    dispatch({ type: 'queue_item', id: 'p1', chat_id: 'c1', session_id: null, kind: 'permission', tool: 'Edit' });
    expect(sel.codeWaiting(getState())).toBe(1);

    actions.sendPlanToCode('S1');
    expect(sent.at(-1)).toEqual({ type: 'chat_from_plan', session_id: 'S1' });
    let st = getState();
    expect(st.ui.chatSide).toBe('code');
    expect(st.sessions.S1.codeSending).toBe(true);
    actions.setChatSide('planner');
    dispatch({ type: 'chat_started', chat_id: 'c2', mode: 'plan', from_session_id: 'S1' });
    dispatch({ type: 'chat_message', chat_id: 'c2', role: 'user', markdown: '# Plan X' });
    st = getState();
    expect(st.ui.chatSide).toBe('code');
    expect(st.currentChat).toBe('c2');
    expect(st.chats.c2.mode).toBe('plan');                                // the user's mode preference does not override it
    expect(st.sessions.S1.codeSending).toBe(false);
    expect(st.sessions.S1.codeSentV).toBe(st.sessions.S1.draftV);
    const mine = st.chats.c2.log.filter(e => e.kind === 'bubble' && e.who === 'me');
    expect(mine).toHaveLength(1);                                         // the plan, once, as a folded plan entry
    expect(mine[0]).toMatchObject({ text: '# Plan X', plan: 'Plan from Session A · Plan X' });
    expect(st.chats.c2.log.filter(e => e.kind === 'sys').length).toBeLessThanOrEqual(2);
    expect(sent.filter(m => m.type === 'chat_set_mode')).toHaveLength(0);

    actions.setChatSide('planner');
    actions.newChat(null);
    expect(sent.at(-1)).toEqual({ type: 'chat_new' });
    expect(getState().ui.chatSide).toBe('code');
  });

  it('Crew: draft fills the form, create sends the fields and shows problems, remove asks the server', () => {
    dispatch({ type: 'crew_list', ...SAMPLES.crew_list });
    actions.crewOpenForm();
    actions.crewSetDraftText('checks copy for tone');
    actions.crewDraft();
    expect(sent.at(-1)).toEqual({ type: 'agent_draft', dir_id: 'd1', text: 'checks copy for tone' });
    dispatch({ type: 'agent_drafted', ok: true, dir_id: 'd1', fields: { name: 'tone-reviewer', description: 'Checks tone.', purpose: 'reviewing', model: 'haiku', tools: ['Read', 'Write'], instructions: '# Tone' } });
    let f = getState().crewForm;
    expect(f.fields).toMatchObject({ name: 'tone-reviewer', purpose: 'reviewing', tools: ['Read'] });   // Write dropped: read-only
    expect(f.drafted).toBe(true);

    expect(actions.crewCreate()).toBe(true);
    expect(sent.at(-1)).toEqual({ type: 'agent_create', dir_id: 'd1', fields: { name: 'tone-reviewer', description: 'Checks tone.', purpose: 'reviewing', model: 'haiku', tools: ['Read'], instructions: '# Tone' } });
    dispatch({ type: 'agent_saved', ok: false, dir_id: 'd1', error: 'Not saved', problems: ['model: bad', { field: 'name', message: 'taken' }, 'something else'] });
    f = getState().crewForm;
    expect(f.saving).toBe(false);
    expect(f.problems).toEqual(['model: bad', 'name: taken', 'something else']);
    actions.crewSetFields({ name: 'tone-reviewer-2' });
    expect(getState().crewForm.problems).toEqual(['model: bad', 'something else']);   // the name problem went with the edit

    actions.crewCreate();
    dispatch({ type: 'agent_saved', ok: true, dir_id: 'd1', name: 'tone-reviewer-2' });
    expect(getState().crewForm.open).toBe(false);
    expect(getState().crewForm.fields.name).toBe('');
    expect(getState().crewFlash).toBe('tone-reviewer-2');

    actions.crewRemove('launchpad-pilot');                                // built-ins cannot be removed
    expect(sent.some(m => m.type === 'agent_remove')).toBe(false);
    actions.crewRemove('copy-reviewer');
    expect(sent.at(-1)).toEqual({ type: 'agent_remove', dir_id: 'd1', name: 'copy-reviewer' });
    expect(getState().crewRemoving).toBe('copy-reviewer');
    dispatch({ type: 'agent_removed', ok: true, dir_id: 'd1', name: 'copy-reviewer' });
    expect(getState().crewRemoving).toBeNull();

    actions.crewPickDir('d2');
    expect(sent.at(-1)).toEqual({ type: 'get_crew', dir_id: 'd2' });
  });

  it('two-click confirms: autopilot on and stop run', () => {
    dispatch({ type: 'run_started', ...SAMPLES.run_started });
    actions.toggleAutopilot('S1');
    expect(sent.find(m => m.type === 'set_autopilot')).toBeUndefined();
    actions.toggleAutopilot('S1');
    expect(sent.at(-1)).toEqual({ type: 'set_autopilot', session_id: 'S1', on: true });
    actions.stopRun('S1'); actions.stopRun('S1');
    expect(sent.at(-1)).toEqual({ type: 'run_stop', session_id: 'S1' });
  });

  it('a name or round before any session is kept as header text; the round tag moves to the first session', () => {
    dispatch({ type: 'plan_meta', name: 'Early name' });
    dispatch({ type: 'question_round', id: 'r0', round: 1, questions: [{ id: 'a', title: 'A?' }] });
    expect(getState().preName).toBe('Early name');
    expect(getState().preRoundTag).toBe('Round 1');
    expect(getState().preLog.some(e => e.kind === 'round')).toBe(true);
    dispatch({ type: 'session_started', session_id: 'S1' });
    const st = getState();
    expect(st.sessions.S1.roundTag).toBe('Round 1');
    expect(st.sessions.S1.log.some(e => e.kind === 'round')).toBe(true);
    expect(st.preName).toBe('');
  });

  it('a dismissed card hidden by a filter goes at once; a visible one fades first', () => {
    dispatch({ type: 'run_finished', ...SAMPLES.run_finished });
    dispatch({ type: 'queue_item', ...SAMPLES.queue_item, id: 'i1', kind: 'info', title: 'FYI' });
    actions.setQueueFilter('question');
    actions.dismissItem('i1');
    expect(getState().queue.find(i => i.id === 'i1')).toBeUndefined();
    actions.setQueueFilter('all');
    actions.dismissItem('report:S1');
    expect(getState().queue.find(i => i.id === 'report:S1')?.leaving).toBe(true);
    vi.advanceTimersByTime(300);
    expect(getState().queue.find(i => i.id === 'report:S1')).toBeUndefined();
  });
});

describe('demo', () => {
  it('drives the store: runs, chat, cards, activity, and answers UI messages', () => {
    const demo = new Demo(dispatch, 1);
    setTransport(m => { sent.push(m); demo.receive(m); return true; });
    demo.start();
    vi.advanceTimersByTime(10_000);
    let st = getState();
    expect(st.order).toEqual(['S-A', 'S-B', 'S-C']);
    expect(st.current).toBe('S-C');
    expect(sel.inFlight(st).map(s => s.letter)).toEqual(['A', 'B']);
    expect(st.sessions['S-C'].log.some(e => e.kind === 'round')).toBe(true);
    expect(st.queue.length).toBeGreaterThanOrEqual(4);
    expect(st.acts.length).toBeGreaterThan(5);
    expect(st.settings?.directories).toHaveLength(2);

    // answer round 1 -> planner replies, promotes itself, opens visuals, asks round 2
    actions.acceptAllPicks('r1');
    vi.advanceTimersByTime(6_000);
    st = getState();
    expect(st.sessions['S-C'].promoted).toBe(true);
    const vs = st.sessions['S-C'].visualSets;                       // ECharts, Chart.js, D3, matplotlib fallback, design
    expect(vs.map(v => v.drawn_with)).toEqual(['echarts', 'chartjs', 'd3', 'echarts', 'echarts']);
    expect(vs.map(v => v.library)).toEqual([null, 'chartjs', 'd3', 'matplotlib', null]);
    expect(vs[3].library_note).toBe('drawn in ECharts, styled like matplotlib');
    expect(vs[0].libraries).toEqual(['echarts', 'chartjs', 'd3']);
    expect(vs[4].options.map(o => o.label)).toEqual(['Colour palette', 'Hero card']);
    expect(vs.flatMap(v => v.options).filter(o => o.status === 'ready').length).toBe(11);   // all but the failing line
    expect(vs[1].options.every(o => o.drawn_with === 'chartjs' && (o.html || '').includes('new Chart('))).toBe(true);
    expect(st.rounds.r2).toBeTruthy();

    // answer round 2 -> plan draft -> approve -> run C launches
    actions.acceptAllPicks('r2');
    vi.advanceTimersByTime(5_000);
    expect(getState().sessions['S-C'].draft).toBeTruthy();
    actions.approve('S-C');
    vi.advanceTimersByTime(3_000);
    expect(getState().sessions['S-C'].status).toBe('running');

    // Claude Code chat
    actions.sendChat('fix the loader');
    vi.advanceTimersByTime(8_000);
    st = getState();
    const chat = sel.curChat(st);
    expect(chat).toBeTruthy();
    expect(chat!.log.some(e => e.kind === 'tool')).toBe(true);
    expect(Object.values(st.chatItems).some(i => i.kind === 'permission')).toBe(true);

    // crew list on request: built-ins + the folder's agents, use counts ticking up as agents start
    actions.setView('crew');
    vi.advanceTimersByTime(1_000);
    st = getState();
    expect(st.crewDefs?.length).toBe(8);
    expect(st.crewDefs!.filter(a => a.builtin === false).map(a => a.name)).toEqual(['sql-builder', 'sql-reviewer']);
    expect(st.crewUses['launchpad-builder']).toBeGreaterThan(41);
    // run C's plan names folder agents for steps 3 and 4
    expect(st.sessions['S-C'].run!.steps.map(x => x.agent ?? null)).toEqual([null, null, 'sql-builder', 'sql-reviewer', null]);
    demo.stop();
  });
});
