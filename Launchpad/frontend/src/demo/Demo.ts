/* DEMO: scripted fake back end, ported from the vanilla page (two runs in flight, timed + blocking questions,
   permissions, an info card, costs, reports, the crew list with use counts and folder agents, agent draft / create /
   remove, new sessions, Claude Code chats (also from a plan), plans with an agent per step, visuals, files).
   Talks to the UI only through emit(ev) -> the store's dispatch, and receive(msg) for UI messages, exactly like the
   websocket would. Used when the page URL has no ?port=&code= (also `npm run dev`). ?speed=N runs it N times faster.
   Loosely typed on purpose: it is a script, the store's reducer is the typed side. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import type { UiMessage } from '../contract';
import { actions, getState, sel } from '../store';
import { baseName } from '../lib/format';
import { esc } from '../lib/markdown';
import { visExtra, visJs } from './visuals';
import { agentPath, crewBase, demoFiles, DRAFT_C_MARKDOWN, FILES, folderAgentsBase, fsDirs, fsVals, PLANNER_OLD_BACKUP, PRICE, PROMOTION_PATH, START_USES, TOOL_CHOICES, type DemoFile } from './data';

type Ev = Record<string, any>;
/** The agent file behind each built-in role (use counts are keyed by agent name). */
const ROLE_FILE: Record<string, string> = {
  planner: 'launchpad-planner', astronaut: 'launchpad-astronaut', orchestrator: 'launchpad-orchestrator', builder: 'launchpad-builder',
  pilot: 'launchpad-pilot', visual: 'launchpad-visual',
};
/** Plan steps always carry agent (null = the Builder), agent_display and agent_purpose. */
const withAgents = (steps: Ev[]): Ev[] => steps.map(s => ({ agent: null, agent_display: 'Builder', agent_purpose: 'building', ...s }));
type Agent = Ev & { agent_id: string; session_id: string | null; role: string; name: string; step: number | null; status: string; model: string };

export class Demo {
  private emitFn: (ev: Ev) => void;
  speed: number;
  vistest: boolean;
  agents: Record<string, Agent> = {};
  flags: Record<string, boolean> = {};
  stopped: Record<string, boolean> = {};
  answered: Record<string, any> = {};
  pending: Record<string, (msg: Ev, v?: any) => void> = {};
  folders: Record<string, string> = {};
  names: Record<string, string> = {};
  drafts: Record<string, { steps: { n: number; title: string; agent?: string | null; agent_display?: string | null; agent_purpose?: string }[]; markdown: string; name: string }> = {};
  first: Record<string, string> = {};
  current = 'S-C';
  pid = 'P-C';
  roundNo = 0;
  n = 0;
  actN = 0;
  astroSince: Record<string, number> = {};
  autopilot: Record<string, boolean> = {};
  openPerms: Record<string, string> = {};
  fsDirs = fsDirs();
  fsVals = fsVals();
  sdir: Record<string, string> = { 'S-A': 'd1', 'S-B': 'd2', 'S-C': 'd1' };
  fsN = 0;
  bkN = 0;
  fs: Map<string, DemoFile> | null = null;
  rev: Record<string, number> = {};
  runs: Record<string, number> = { 'S-A': 1, 'S-B': 1 };            // the two seeded runs count as run 1
  running: Record<string, boolean> = { 'S-A': true, 'S-B': true };
  launchedRev: Record<string, number> = {};
  chatN = 0; chatTurns: Record<string, number> = {}; chatMode: Record<string, string> = {}; chatCount: Record<string, number> = {};
  chatAlways: Record<string, boolean> = {}; chatOpen: Record<string, string> = {}; chatCalls: Record<string, Ev[]> = {}; cqN = 0;
  /** the visual sets of the demo, by set id (vs-1 ECharts, vs-2 Chart.js, vs-3 D3, vs-4 matplotlib fallback, vs-5 design) */
  vsets: Record<string, Ev> = {};
  /* Crew: use counts per agent name (agent_uses), the connected folder's own agents */
  uses: Record<string, number> = { ...START_USES };
  folderAgents = folderAgentsBase();
  visPicked: string | null = null;
  visMonths = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];
  private intervals: ReturnType<typeof setInterval>[] = [];

  constructor(emit: (ev: Ev) => void, speed = 1, vistest = false) {
    this.emitFn = emit; this.speed = Math.max(0.1, speed || 1); this.vistest = vistest;
  }

  emit(ev: Ev): void { this.emitFn(ev); }
  later(ms: number, fn: () => void): ReturnType<typeof setTimeout> { return setTimeout(fn, ms / this.speed); }
  every(ms: number, fn: () => void): void { this.intervals.push(setInterval(fn, ms / this.speed)); }
  /** Stop every repeating timer (tests). */
  stop(): void { this.intervals.forEach(clearInterval); this.intervals = []; }

  /* builder permission card with a timer: unanswered = DENIED; skipped entirely (approved) when autopilot is on */
  timedPerm(o: Ev, secs: number, onDone: (v: string, msg?: Ev) => void): void {
    const sid = o.session_id;
    if (this.autopilot[sid]) { onDone('allow', { auto: true }); return; }
    const ms = secs * 1000 / this.speed;
    this.openPerms[o.id] = sid; this.pending[o.id] = (msg, v) => { delete this.openPerms[o.id]; onDone(v, msg); };
    this.item({ kind: 'permission', ...o, rec: null, blocking: false, timeout_s: Math.round(ms / 1000), expires_at: new Date(Date.now() + ms).toISOString() });
    setTimeout(() => {
      if (this.answered[o.id] != null || this.stopped[sid]) return;
      this.answered[o.id] = 'deny'; delete this.openPerms[o.id];
      this.emit({ type: 'queue_resolved', id: o.id, answer: 'deny', by: 'timer' });
      const f = this.pending[o.id]; delete this.pending[o.id]; if (f) f({ timer: true }, 'deny');
    }, ms);
  }
  setAutopilot(sid: string, on: boolean): void {
    this.autopilot[sid] = on;
    this.emit({ type: 'autopilot', session_id: sid, on });
    if (!on) return;
    for (const [id, s] of Object.entries(this.openPerms)) if (s === sid && this.answered[id] == null) {
      this.answered[id] = 'allow'; delete this.openPerms[id];
      this.emit({ type: 'queue_resolved', id, answer: 'allow', by: 'autopilot' });
      const f = this.pending[id]; delete this.pending[id]; if (f) f({ auto: true }, 'allow');
    }
  }
  /* one tool call: "started" now, the final status later (same id) */
  call(agentId: string, tool: string, summary: string, final: string | null = 'done', dur = 900, id?: string): Ev | null {
    const a = this.agents[agentId]; if (!a) return null;
    const ev = { type: 'activity', id: id || 'act-' + (++this.actN), session_id: a.session_id, ...(a.chat_id != null ? { chat_id: a.chat_id } : {}), agent_id: agentId, role: a.role, name: a.name, step: a.step, tool, summary };
    this.emit({ ...ev, status: 'started', ts: new Date().toISOString() });
    if (final) this.later(dur, () => this.emit({ ...ev, status: final, ts: new Date().toISOString() }));
    return ev;
  }
  actTick(): void {
    const pick = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
    for (const a of Object.values(this.agents)) {
      if (a.status !== 'working' || a.paused || a.role === 'planner' || a.role === 'pilot' || (a.session_id && this.stopped[a.session_id])) continue;
      if (Math.random() > (a.role === 'orchestrator' ? .1 : a.role === 'astronaut' ? .5 : .33)) continue;
      const files = FILES[a.session_id || ''] || FILES.other, f = pick(files);
      const tool = a.role === 'astronaut' ? pick(['Read', 'Grep', 'Glob', 'Read'])
        : a.role === 'orchestrator' ? pick(['Read', 'mcp__agentlib__update_step', 'mcp__agentlib__run_builder'])
        : pick(['Read', 'Read', 'Grep', 'Glob', 'Edit', 'Edit', 'Write', 'Bash', 'Bash', a.name === 'sql-builder' ? 'mcp__agentlib__run_sql' : 'mcp__agentlib__report_step']);
      const summary = ({
        Read: f, Edit: f, Write: f,
        Grep: pick([`"incurred_month" in ${f.split('/')[0]}/`, '"facility_id" in sql/', '"TODO" in .']),
        Glob: pick(['**/*.sql', 'loader/**/*.py', 'qa/*.md', 'packages/2026Q2/*']),
        Bash: pick(['python -m pytest qa/ -q', 'python loader/load_claims.py --dry-run', 'duckdb -c "select count(*) from claims_q3"', 'git diff --stat']),
        mcp__agentlib__update_step: `step ${a.step} → in_progress`, mcp__agentlib__run_builder: `brief for step ${a.step}`,
        mcp__agentlib__run_sql: 'select facility_id, count(*) from readmits group by 1', mcp__agentlib__report_step: `step-${a.step}.md`,
      } as Record<string, string>)[tool];
      this.call(a.agent_id, tool, summary, tool === 'Bash' && Math.random() < .08 ? 'failed' : 'done', 500 + Math.random() * 2200);
    }
  }
  /* astronaut lookups: short trips out to the files and back */
  astroTick(): void {
    const now = Date.now();
    for (const a of Object.values(this.agents)) {
      if (a.role !== 'astronaut' || a.status === 'done' || (a.session_id && this.stopped[a.session_id]) || !(a.session_id && getState().sessions[a.session_id]?.run)) continue;
      this.astroSince[a.agent_id] ||= now;
      const held = (now - this.astroSince[a.agent_id]) * this.speed;
      if (a.status === 'idle' && held > 2500 && Math.random() < .45) { this.agent(a.agent_id, { status: 'working' }); this.astroSince[a.agent_id] = now; this.bump('launchpad-astronaut'); }
      else if (a.status === 'working' && held > 4200) { this.agent(a.agent_id, { status: 'idle' }); this.astroSince[a.agent_id] = now; }
    }
  }
  agent(id: string, o: Ev): Agent {
    const fresh = !this.agents[id];
    const a = this.agents[id] || (this.agents[id] = { agent_id: id, session_id: null, role: 'builder', name: id, step: null, status: 'idle', model: 'sonnet',
      input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, cost_usd: 0, tool_calls: 0 });
    Object.assign(a, o); this.push(a);
    if (fresh && a.role !== 'visual') this.bump(a.useName || ROLE_FILE[a.role]);   // one use each time an agent is started (the Visualizer: one per visual drawn)
    return a;
  }
  push(a: Agent): void { const { model: _m, paused: _p, promotedDemo: _d, useName: _u, ...pub } = a; this.emit({ type: 'agent_usage', ...pub, by_model: pub.by_model ? JSON.parse(JSON.stringify(pub.by_model)) : undefined }); }
  /** One more use of an agent (agent_uses). */
  bump(name: string | undefined): void { if (!name) return; this.uses[name] = (this.uses[name] || 0) + 1; this.emit({ type: 'agent_uses', name, uses: this.uses[name] }); }
  burn(id: string, n: number, tools = 1): void {
    const a = this.agents[id]; if (!a) return;
    const i = Math.round(n * .15), o = Math.round(n * .25), r = Math.round(n * 2.6), w = Math.round(n * .35), p = PRICE[a.model] || PRICE.sonnet;
    a.input_tokens += i; a.output_tokens += o; a.cache_read_tokens += r; a.cache_write_tokens += w;
    const dc = (i * p[0] + o * p[1] + r * p[2] + w * p[3]) / 1e6;
    a.cost_usd += dc; a.tool_calls += tools;
    if (a.role === 'planner') {                               // per-model split, like the server's by_model
      a.by_model = a.by_model || [];
      let b = a.by_model.find((x: Ev) => x.model === a.model);
      if (!b) a.by_model.push(b = { model: a.model, cost_usd: 0, input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0 });
      b.cost_usd += dc; b.input_tokens += i; b.output_tokens += o; b.cache_read_tokens += r; b.cache_write_tokens += w;
    }
    this.push(a);
  }
  total(): void {
    let t = 0, c = 0; for (const a of Object.values(this.agents)) { t += a.input_tokens + a.output_tokens + a.cache_read_tokens + a.cache_write_tokens; c += a.cost_usd; }
    this.emit({ type: 'usage', tokens: t, cost: c });
  }
  tick(): void {
    for (const a of Object.values(this.agents)) if (a.status === 'working' && a.role !== 'planner' && !a.paused) this.burn(a.agent_id, 300 + Math.random() * 1500, Math.random() < .6 ? 1 : 0);
    this.total();
  }
  step(sid: string, n: number, status: string, extra: Ev = {}): void { if (!this.stopped[sid]) this.emit({ type: 'step_update', session_id: sid, n, status, ...extra }); }
  item(o: Ev): void { this.emit({ type: 'queue_item', session_id: null, step: null, body: '', rec: null, blocking: false, timeout_s: null, expires_at: null, ...o }); }
  timed(o: Ev, secs: number): void {
    const ms = secs * 1000 / this.speed;
    this.item({ kind: 'question', ...o, blocking: false, timeout_s: Math.round(ms / 1000), expires_at: new Date(Date.now() + ms).toISOString() });
    setTimeout(() => {
      if (this.answered[o.id] || this.stopped[o.session_id]) return;
      this.answered[o.id] = o.rec;
      this.emit({ type: 'queue_resolved', id: o.id, answer: o.rec, by: 'timer' });
      this.onAnswer(o.id, o.rec);
    }, ms);
  }
  finish(sid: string, status: string, markdown: string): void {
    this.running[sid] = false;
    this.fsWrite(this.sdir[sid] || 'd1', `${this.folders[sid]}/report.md`, markdown);
    const total = Object.values(this.agents).filter(a => a.session_id === sid).reduce((t, a) => t + a.cost_usd, 0);
    for (const a of Object.values(this.agents)) if (a.session_id === sid && a.role !== 'planner' && a.status !== 'done') this.agent(a.agent_id, { status: 'done' });
    this.emit({ type: 'run_finished', session_id: sid, status, report_path: `${this.folders[sid]}/report.md`, markdown: markdown.replace('{COST}', '$' + total.toFixed(2)), total_cost_usd: total });
  }
  session(sid: string, folder: string, name: string | null, dirId?: string): void {
    this.folders[sid] = folder; if (name) this.names[sid] = name;
    const d = dirId || this.sdir[sid] || 'd1'; this.sdir[sid] = d;
    const dd = this.fsDirs.find(x => x.dir_id === d);
    this.emit({ type: 'session_started', session_id: sid, folder, dir_id: d, cwd: dd ? dd.path : '' });
  }

  /* ---- Files demo: two connected folders + the app's own files, editable markdown, a conflict, an invalid save, backups ---- */
  fsInit(): void {
    if (this.fs) return;
    this.fs = new Map(Object.entries(demoFiles()).map(([k, f]) => [k, { size: (f.text || '').length, mtime: Date.now() - 3600e3, version: 1, backups: [], ...f } as DemoFile]));
    const pl = this.fs.get(`app|${agentPath('planner')}`)!;
    pl.backups.push({ backup_id: 'b0', saved_at: new Date(Date.now() - 86400e3).toISOString(), size: 120, text: PLANNER_OLD_BACKUP });
  }
  fsWrite(root: string, path: string, text: string, o: Partial<DemoFile> = {}): void {
    this.fsInit(); const k = `${root}|${path}`, f = this.fs!.get(k);
    if (f) Object.assign(f, { text, size: text.length, mtime: Date.now(), version: f.version + 1 });
    else this.fs!.set(k, { kind: 'markdown', text, size: text.length, mtime: Date.now(), version: 1, editable: true, applies: 'now', validates_as: null, backups: [], ...o });
  }
  fsSettings(): void { this.emit({ type: 'settings', directories: JSON.parse(JSON.stringify(this.fsDirs)), values: JSON.parse(JSON.stringify(this.fsVals)), can_pick_directory: true }); }
  fsList(root: string, path: string): Ev[] {
    this.fsInit();
    const pre = path ? path + '/' : '', seen = new Map<string, Ev>();
    for (const [k, f] of this.fs!) {
      const i = k.indexOf('|'); if (k.slice(0, i) !== root) continue;
      const p = k.slice(i + 1); if (!p.startsWith(pre)) continue;
      const rest = p.slice(pre.length), j = rest.indexOf('/');
      if (j >= 0) { const name = rest.slice(0, j); if (!seen.has(name)) seen.set(name, { name, type: 'dir', size: 0, mtime: f.mtime }); }
      else seen.set(rest, { name: rest, type: 'file', size: f.size, mtime: f.mtime, kind: f.kind, editable: !!f.editable });
    }
    return [...seen.values()];
  }
  fsCheck(f: DemoFile, text: string): string | null {
    if (f.validates_as === 'agent') {
      const m = text.match(/^---\n([\s\S]*?)\n---/);
      const miss = !m ? ['the front matter block'] : ['name', 'description'].filter(k => !new RegExp(`^${k}:\\s*\\S`, 'm').test(m[1]));
      if (miss.length) return `The agent file needs a front matter block with name and description (missing: ${miss.join(', ')}).`;
    }
    if (f.validates_as === 'plan' && !/^---\n[\s\S]*?steps:[\s\S]*?\n---/.test(text)) return 'A plan file must start with its header block, including steps.';
    return null;
  }
  fsOn(msg: Ev): void {
    this.fsInit();
    const k = `${msg.root}|${msg.path}`, f = this.fs!.get(k), err = (code: string, message: string, extra: Ev = {}) => this.emit({ type: 'file_error', root: msg.root, path: msg.path, code, message, ...extra });
    switch (msg.type) {
      case 'get_settings': this.fsSettings(); break;
      case 'set_settings': {
        for (const [key, v] of Object.entries(msg.patch || {})) {
          if (key === 'default_dir_id') this.fsDirs.forEach(d => { d.is_default = d.dir_id === v; });
          else if (this.fsVals[key] && !this.fsVals[key].overridden_by_launch) this.fsVals[key].value = v;
        }
        this.fsSettings(); break;
      }
      case 'add_directory': {
        const p = String(msg.path || '').trim();
        if (this.fsDirs.some(d => d.path === p)) { this.emit({ type: 'system', text: `That folder is already connected: ${p}` }); break; }
        const id = 'd' + (3 + this.fsN++);
        this.fsDirs.push({ dir_id: id, path: p, name: baseName(p), exists: !/missing/i.test(p), is_default: false, busy: false });
        if (!/missing/i.test(p)) this.fsWrite(id, 'README.md', `# ${baseName(p)}\n\nA folder added from Settings.`);
        this.fsSettings(); break;
      }
      case 'remove_directory': this.fsDirs = this.fsDirs.filter(d => d.dir_id !== msg.dir_id); this.fsSettings(); break;
      case 'pick_directory': this.later(800, () => this.emit({ type: 'directory_picked', path: 'C:/work/new-project' })); break;
      case 'list_dir': {
        const entries = this.fsList(msg.root, msg.path || '');
        if (!entries.length && (msg.path || '') !== '' && !sel.dirById(getState(), msg.root) && msg.root !== 'app') { err('not_found', 'No such folder'); break; }
        this.emit({ type: 'dir_listing', root: msg.root, path: msg.path || '', entries }); break;
      }
      case 'read_file': {
        if (!f) { err('not_found', `No such file: ${msg.path}`); break; }
        this.emit({ type: 'file_content', root: msg.root, path: msg.path, kind: f.kind, ...(f.kind === 'markdown' || f.kind === 'text' ? { text: f.text } : {}),
          size: f.size, mtime: f.mtime, version: f.version, editable: !!f.editable, applies: f.applies || null, validates_as: f.validates_as || null });
        if (k === 'd1|notes/team-notes.md' && !f.touched) {            // someone else edits it a moment later: a save will conflict
          f.touched = true;
          this.later(1500, () => this.fsWrite('d1', 'notes/team-notes.md', f.text + '\n- (added by a teammate while you were editing)'));
        }
        break;
      }
      case 'save_file': {
        if (!f || !f.editable || f.kind !== 'markdown') { err('not_allowed', 'Only markdown files Launchpad allows can be edited.'); break; }
        if (msg.base_version !== f.version) { err('conflict', 'Someone or something saved it after you opened it.', { current: { text: f.text, version: f.version } }); break; }
        const bad = this.fsCheck(f, String(msg.text || ''));
        if (bad) { err('invalid', bad); break; }
        const backup_id = 'b' + (++this.bkN);
        f.backups.unshift({ backup_id, saved_at: new Date().toISOString(), size: f.size, text: f.text || '' });
        this.fsWrite(msg.root, msg.path, String(msg.text));
        this.emit({ type: 'file_saved', root: msg.root, path: msg.path, version: f.version, backup_id });
        if (msg.root === 'app' || String(msg.path).startsWith('.claude/agents/')) this.later(200, () => this.emit(this.crewList()));
        break;
      }
      case 'list_backups': this.emit({ type: 'backups', root: msg.root, path: msg.path, items: (f ? f.backups : []).map(b => ({ backup_id: b.backup_id, saved_at: b.saved_at, size: b.size })) }); break;
      case 'restore_backup': {
        const b = f && f.backups.find(x => x.backup_id === msg.backup_id); if (!f || !b) { err('not_found', 'That version is gone.'); break; }
        const backup_id = 'b' + (++this.bkN);
        f.backups.unshift({ backup_id, saved_at: new Date().toISOString(), size: f.size, text: f.text || '' });
        this.fsWrite(msg.root, msg.path, b.text);
        this.emit({ type: 'file_saved', root: msg.root, path: msg.path, version: f.version, backup_id });
        if (msg.root === 'app' || String(msg.path).startsWith('.claude/agents/')) this.later(200, () => this.emit(this.crewList()));
        break;
      }
    }
  }
  fsBody(key: string): string { this.fsInit(); const f = this.fs!.get(key); return f ? String(f.text || '').replace(/^---\n[\s\S]*?\n---\n?/, '') : ''; }

  start(): void {
    this.fsSettings();
    actions.setQuiet(true);
    /* Run A: claims loader, on step 2 */
    this.session('S-A', 'runs/2026-11-12-claims-loader', 'Claims loader rebuild');
    this.emit({ type: 'run_started', session_id: 'S-A', name: 'Claims loader rebuild', steps: [
      { n: 1, title: 'Profile the source extract', status: 'done' }, { n: 2, title: 'Build the loader', status: 'in_progress' },
      { n: 3, title: 'Reconcile row counts', status: 'todo' }, { n: 4, title: 'Write the hand-off note', status: 'todo' }] });
    this.step('S-A', 1, 'done', { built: ['profile/claims_extract_profile.md'], report_path: 'runs/2026-11-12-claims-loader/step-1.md' });
    this.agent('A-o', { session_id: 'S-A', role: 'orchestrator', name: 'Orchestrator', step: 2, status: 'working' }); this.burn('A-o', 14000, 9);
    this.agent('A-b1', { session_id: 'S-A', role: 'builder', name: 'profiler', step: 1, status: 'done' }); this.burn('A-b1', 26000, 31);
    this.agent('A-b2', { session_id: 'S-A', role: 'builder', name: 'loader-builder', step: 2, status: 'working' }); this.burn('A-b2', 18000, 17);
    this.agent('A-ast', { session_id: 'S-A', role: 'astronaut', name: 'Explorer', model: 'haiku', step: 2, status: 'working' }); this.burn('A-ast', 6000, 8);
    /* Run B: readmissions SQL, on step 1 */
    this.session('S-B', 'runs/2026-11-12-readmissions', 'Readmissions tab');
    this.emit({ type: 'run_started', session_id: 'S-B', name: 'Readmissions tab', steps: [
      { n: 1, title: 'Write the 30-day readmission SQL', status: 'in_progress' }, { n: 2, title: 'Build the workbook tab', status: 'todo' }, { n: 3, title: 'QA against last quarter', status: 'todo', agent: 'sql-reviewer', agent_display: 'Sql reviewer', agent_purpose: 'reviewing' }] });
    this.agent('B-o', { session_id: 'S-B', role: 'orchestrator', name: 'Orchestrator', step: 1, status: 'working' }); this.burn('B-o', 8000, 5);
    this.agent('B-b1', { session_id: 'S-B', role: 'builder', name: 'sql-builder', step: 1, status: 'working' }); this.burn('B-b1', 12000, 11);
    /* Session C: the plan being written in the chat */
    this.session('S-C', 'plans/q3-inpatient-refresh', 'Q3 inpatient trend refresh');
    this.emit({ type: 'plan_meta', session_id: 'S-C', name: 'Q3 inpatient trend refresh', mode: 'Plan', status: 'Draft' });
    this.agent('P-C', { session_id: 'S-C', role: 'planner', name: 'Planner', model: 'sonnet', status: 'idle' });
    this.emit({ type: 'planner_model', session_id: 'S-C', model: 'sonnet', promoted: false, reason: null, by: null });
    this.total();
    actions.setQuiet(false);

    actions.addLocalPlannerBubble('me', "Let's plan the Q3 inpatient trend refresh. Same package as last quarter, plus a new readmissions tab.");
    this.think(1800);
    this.later(1100, () => {
      this.say("Love it. I've sent the Explorer to grab last quarter's package. While it's out, two quick ones:");
      this.nextRound();
    });
    this.later(1300, () => this.agent('P-ast', { session_id: 'S-C', role: 'astronaut', name: 'Explorer', model: 'haiku', status: 'working' }));
    this.later(8000, () => { this.agent('P-ast', { status: 'done' }); this.emit({ type: 'system', session_id: 'S-C', text: "Explorer is back: last quarter's package has four tabs and no readmissions logic yet." }); });
    this.later(7000, () => this.agent('A-ast', { status: 'idle' }));

    /* some history so the feed has rows, then live activity */
    ([['A-b1', 'Read', 'data/claims_q3_sample.csv'], ['A-b1', 'Bash', 'python profile/profile_extract.py --rows 50000'], ['A-b1', 'Write', 'profile/claims_extract_profile.md'],
      ['A-o', 'mcp__agentlib__update_step', 'step 1 → done'], ['A-o', 'mcp__agentlib__run_builder', 'brief for step 2'], ['B-o', 'mcp__agentlib__run_builder', 'brief for step 1'],
      ['B-b1', 'Glob', 'sql/**/*.sql'], ['A-b2', 'Read', 'loader/loader_v3.py']] as [string, string, string][]).forEach(([id, t, s], k) => this.later(k * 120, () => { this.call(id, t, s, 'done', 300); }));
    this.later(1200, () => { const ev = this.call('P-C', 'mcp__agentlib__explore', "last quarter's inpatient package", null); this.later(6800, () => { if (ev) this.emit({ ...ev, status: 'done', ts: new Date().toISOString() }); }); });
    this.every(700, () => this.actTick());
    this.every(1500, () => this.astroTick());

    /* incoming cards */
    this.later(2000, () => {
      this.call('B-b1', 'Bash', 'python scripts/pull_claims.py --period 2026Q3 --out data/claims_q3.parquet', null, 0, 'act-perm-B');
      this.agent('B-b1', { paused: true });
      this.timedPerm({ id: 'B-p1', session_id: 'S-B', agent: 'sql-builder', agent_id: 'B-b1', tool: 'Bash', step: 1, title: 'Run a shell command (Bash)',
        body: 'python scripts/pull_claims.py --period 2026Q3 --out data/claims_q3.parquet' }, 90, (v, m) => this.onAnswer('B-p1', v, m || {}));
    });
    this.later(3500, () => { this.agent('A-b2', { paused: true }); this.timed({ id: 'A-q1', session_id: 'S-A', agent: 'loader-builder', agent_id: 'A-b2', step: 2,
      title: 'Which date field defines the incurred month?', body: "The extract has three candidate dates. Last quarter's package used **service dates**.",
      rec: 'service_from_dt', options: ['service_from_dt', 'admit_dt', 'paid_dt'] }, 45); });
    this.later(6000, () => {
      this.step('S-B', 1, 'blocked');
      this.item({ id: 'B-q2', session_id: 'S-B', kind: 'question', agent: 'Orchestrator', agent_id: 'B-o', step: 1, blocking: true,
        title: 'Two facility ID formats found. Which one is the source of truth?',
        body: 'The claims table uses `facility_id` (NPI based); the census feed uses the legacy `site_code`. Mapping between them drops 3% of rows.',
        rec: 'Use NPI-based facility_id', options: ['Use legacy site_code', 'Keep both, flag mismatches'] });
    });
    this.later(4500, () => {
      const ev = this.call('A-b2', 'Bash', 'git push origin feature/claims-loader', null, 0, 'act-perm-A');
      this.timedPerm({ id: 'A-p2', session_id: 'S-A', agent: 'loader-builder', agent_id: 'A-b2', tool: 'Bash', step: 2, title: 'Push the branch (git push)',
        body: 'git push origin feature/claims-loader' }, 25, (v, m) => { if (ev) this.emit({ ...ev, status: v === 'deny' ? 'denied' : 'done', ...(m && m.auto ? { auto: true } : {}), ts: new Date().toISOString() }); });
    });
    this.later(9000, () => this.item({ id: 'A-i1', session_id: 'S-A', kind: 'info', agent: 'Explorer', agent_id: 'A-ast', step: 2, title: "Found last quarter's loader",
      body: '- `loader/loader_v3.py` (incurred-month basis)\n- Schema matches except two renamed columns\n- No tests exist for it' }));
    this.every(2000, () => this.tick());
  }

  /* planner helpers */
  think(n: number): void { this.agent(this.pid, { status: 'working' }); this.burn(this.pid, n, 0); this.total(); this.emit({ type: 'typing', session_id: this.current, on: true }); }
  say(text: string, sid = this.current): void { this.emit({ type: 'planner_message', session_id: sid, text }); this.agent(this.pid, { status: 'idle' }); this.burn(this.pid, 1400, 0); }
  nextRound(): void {
    this.roundNo++;
    const rounds: Record<number, Ev[]> = {
      1: [{ id: 'a', title: 'Readmissions on a 30-day window?', body: 'Standard and comparable year over year.', rec: 'Yes, 30 days' },
          { id: 'b', title: 'Same manager audience as last time?', rec: 'Yes. Format and commentary depth stay the same.' }],
      2: [{ id: 'a', title: 'Readmissions as its own tab, after utilization?', rec: 'Yes. Keeps the existing flow intact.' },
          { id: 'b', title: 'Show readmissions by facility?', rec: 'Top 10 only', options: ['Top 10 only', 'All facilities', 'No facility split'] },
          { id: 'c', title: 'Sign-off before commentary is written?', rec: 'Yes. You review the numbers first.' }],
    };
    const qs = rounds[this.roundNo];
    if (!qs) { this.say('That covers it. Here is the draft plan:'); this.draftC(); return; }
    this.emit({ type: 'question_round', session_id: this.current, id: 'r' + this.roundNo, round: this.roundNo, questions: qs });
    this.emit({ type: 'crew', agents: [{ name: 'Planner', role: 'planner', status: 'waiting', session_id: this.current }] });
  }
  draftC(): void {
    const B = { agent: null, agent_display: 'Builder', agent_purpose: 'building' };
    const steps = [{ n: 1, title: 'Pull the Q3 claims extract', ...B }, { n: 2, title: 'Refresh the trend tabs', ...B },
      { n: 3, title: 'Build the readmissions tab', agent: 'sql-builder', agent_display: 'Sql builder', agent_purpose: 'building' },
      { n: 4, title: 'Review the readmissions SQL', agent: 'sql-reviewer', agent_display: 'Sql reviewer', agent_purpose: 'reviewing' },
      { n: 5, title: 'Draft commentary after your sign-off', ...B }];
    this.drafts['S-C'] = { steps, markdown: DRAFT_C_MARKDOWN, name: 'Q3 inpatient trend refresh' };
    this.later(900, () => { this.emit({ type: 'plan_meta', session_id: 'S-C', status: 'Ready for review' }); this.emitDraft('S-C', 'plans/q3-inpatient-refresh/plan.md', DRAFT_C_MARKDOWN, steps); this.agent(this.pid, { status: 'idle' }); });
  }
  emitDraft(sid: string, path: string, markdown: string, steps: Ev[]): void {
    this.rev[sid] = (this.rev[sid] || 0) + 1;
    this.fsWrite(this.sdir[sid] || 'd1', path, markdown, { validates_as: /^---/.test(markdown) ? 'plan' : null, applies: 'new_sessions' });
    this.emit({ type: 'plan_draft', session_id: sid, path, markdown, steps: withAgents(steps), revision: this.rev[sid], previous_runs: this.runs[sid] || 0 });
  }
  draftFollowUp(sid: string, name: string): void {
    const steps = [{ n: 1, title: 'Close the open follow-up from the report' }, { n: 2, title: 'Re-check the outputs and update the hand-off' }];
    const title = `Follow-up: ${name}`;
    const markdown = `---\nplan: "${title}"\nstatus: "draft"\ndate: "2026-11-13"\nsession: "${sid}"\nsteps:\n- {n: 1, title: "${steps[0].title}", skill: null, after: [], status: "todo"}\n- {n: 2, title: "${steps[1].title}", skill: null, after: [1], status: "todo"}\n---\n# ${title}\n\n## Goal\nFinish what the first run left open.\n\n## Steps\n\n### Step 1: ${steps[0].title}\nUse the report's follow-up list.\n\n### Step 2: ${steps[1].title}\nDone when the hand-off note mentions the fix.`;
    this.drafts[sid] = { steps, markdown, name: title };
    this.later(900, () => { this.emit({ type: 'plan_meta', session_id: sid, name: title, mode: 'Plan', status: 'Draft' }); this.emitDraft(sid, `${this.folders[sid]}/plan.md`, markdown, steps); });
  }
  draftGeneric(sid: string): void {
    const ask = this.first[sid] || 'the new piece of work';
    const name = 'Plan: ' + (ask.length > 48 ? ask.slice(0, 48) + '…' : ask);
    const steps = [{ n: 1, title: 'Gather the inputs' }, { n: 2, title: 'Build the first version' }, { n: 3, title: 'Check it and write the hand-off' }];
    const markdown = `# ${name}\n\n## Goal\n${ask}\n\n## Steps\n1. Gather the inputs\n2. Build the first version\n3. Check it and write the hand-off\n\n## Done when\n- [ ] Output saved in the session folder\n- [ ] Hand-off note written`;
    this.drafts[sid] = { steps, markdown, name };
    this.later(900, () => { this.emit({ type: 'plan_meta', session_id: sid, name, mode: 'Plan', status: 'Ready for review' }); this.emitDraft(sid, `${this.folders[sid]}/plan.md`, markdown, steps); });
  }

  /* scripted progress for runs A and B */
  advanceA(): void {
    const S = 'S-A';
    this.agent('A-b2', { paused: false, status: 'working' });
    this.later(4000, () => { if (this.stopped[S]) return;
      this.step(S, 2, 'done', { built: ['loader/load_claims.py', 'loader/schema.sql'], report_path: `${this.folders[S]}/step-2.md` });
      this.agent('A-b2', { status: 'done' }); this.step(S, 3, 'in_progress'); this.agent('A-o', { step: 3 });
      this.agent('A-b3', { session_id: S, role: 'builder', name: 'reconciler', step: 3, status: 'working' }); });
    this.later(12000, () => { if (this.stopped[S]) return;
      this.step(S, 3, 'done', { built: ['qa/row_count_recon.md'], report_path: `${this.folders[S]}/step-3.md` });
      this.agent('A-b3', { status: 'done' }); this.step(S, 4, 'in_progress'); this.agent('A-o', { step: 4 });
      this.agent('A-b4', { session_id: S, role: 'builder', name: 'note-writer', step: 4, status: 'working' }); this.agent('A-ast', { step: 4, status: 'working' }); });
    this.later(15000, () => { if (!this.stopped[S]) this.agent('A-ast', { status: 'idle' }); });
    this.later(19000, () => { if (this.stopped[S]) return;
      this.step(S, 4, 'done', { built: ['handoff.md'], report_path: `${this.folders[S]}/step-4.md` });
      const q1 = this.answered['A-q1'] || 'service_from_dt';
      this.finish(S, 'done', `# Run A report · Claims loader rebuild
**Status:** done · **Steps:** 4 of 4 · **Cost:** {COST}

## What was built
| Step | Built | Notes |
|---|---|---|
| 1. Profile the source extract | \`profile/claims_extract_profile.md\` | 41 columns, 3 date fields |
| 2. Build the loader | \`loader/load_claims.py\`, \`loader/schema.sql\` | Incurred month = **${q1}** |
| 3. Reconcile row counts | \`qa/row_count_recon.md\` | Matches source within 0.02% |
| 4. Write the hand-off note | \`handoff.md\` | Ready for the nightly job |

## Decisions made during the run
- Incurred month uses \`${q1}\`
- Rows with a \`<NULL>\` facility were dropped (212 rows)

## Follow-ups
- [ ] Review the reconciliation note before Friday
- [x] Loader script runs end to end on the Q3 extract`); });
  }
  tryB(): void {
    if (!(this.flags.bPerm && this.flags.bQ) || this.flags.bGo) return;
    this.flags.bGo = true; const S = 'S-B';
    this.later(3000, () => { if (this.stopped[S]) return;
      this.step(S, 1, 'done', { built: ['sql/readmissions_30d.sql', 'sql/facility_map.sql'], report_path: `${this.folders[S]}/step-1.md` });
      this.agent('B-b1', { status: 'done' }); this.step(S, 2, 'in_progress'); this.agent('B-o', { step: 2 });
      this.agent('B-b2', { session_id: S, role: 'builder', name: 'tab-builder', step: 2, status: 'working' });
      this.agent('B-ast', { session_id: S, role: 'astronaut', name: 'Explorer', model: 'haiku', step: 2, status: 'working' }); });
    this.later(8000, () => { if (!this.stopped[S]) this.agent('B-ast', { status: 'done' }); });
    this.later(12000, () => { if (this.stopped[S]) return;
      this.step(S, 2, 'done', { built: ['workbook/readmissions_tab.xlsx'], report_path: `${this.folders[S]}/step-2.md` });
      this.agent('B-b2', { status: 'done' }); this.step(S, 3, 'in_progress'); this.agent('B-o', { step: 3 });
      this.agent('B-b3', { session_id: S, role: 'builder', name: 'Sql reviewer', useName: 'sql-reviewer', step: 3, status: 'working' }); });
    this.later(19000, () => { if (this.stopped[S]) return;
      this.step(S, 3, 'done', { built: ['qa/readmissions_vs_q2.md'], report_path: `${this.folders[S]}/step-3.md` });
      this.finish(S, 'done', `# Run B report · Readmissions tab\n**Status:** done · **Cost:** {COST}\n\n## Built\n- \`sql/readmissions_30d.sql\` and \`sql/facility_map.sql\`\n- \`workbook/readmissions_tab.xlsx\` (top 10 facilities)\n- \`qa/readmissions_vs_q2.md\`\n\n## Answers you gave\n- Facility key: **${this.answered['B-q2'] || 'Use NPI-based facility_id'}**\n- Claims pull: ${this.answered['B-p1'] || 'allow'}\n\n## Watch\nThe 30-day rate rose from 11.8% to 12.6%; QA notes say it is real, not a data artefact.`); });
  }

  /* generic run for approved demo plans (C and new sessions) */
  runPlan(sid: string): void {
    const d = this.drafts[sid], steps = d.steps, o = sid + '-o', names = ['data-puller', 'trend-builder', 'tab-builder', 'note-writer', 'qa-checker'];
    this.agent(o, { session_id: sid, role: 'orchestrator', name: 'Orchestrator', step: steps[0].n, status: 'working' }); this.burn(o, 3000, 2);
    const run = (k: number): void => {
      if (this.stopped[sid]) return;
      if (k >= steps.length) {
        this.finish(sid, 'done', `# ${d.name} · report\n**Status:** done · **Cost:** {COST}\n\n## Built\n${steps.map(st => `- ${st.n}. ${st.title}: \`out/step-${st.n}.md\``).join('\n')}\n\n## Next\nReady for your review.`);
        return;
      }
      const st = steps[k], b = `${sid}-b${st.n}`, name = st.agent ? (st.agent_display || st.agent) : names[k % names.length];
      this.step(sid, st.n, 'in_progress'); this.agent(o, { step: st.n });
      this.agent(b, { session_id: sid, role: 'builder', name, step: st.n, status: 'working', ...(st.agent ? { useName: st.agent } : {}) });
      const done = () => { if (this.stopped[sid]) return;
        this.agent(b, { paused: false }); this.step(sid, st.n, 'done', { built: [`out/step-${st.n}.md`], report_path: `${this.folders[sid]}/step-${st.n}.md` });
        this.agent(b, { status: 'done' }); this.later(900, () => run(k + 1)); };
      if (k === 1) {
        const qid = `${sid}-q${st.n}-${++this.actN}`;
        this.pending[qid] = () => { this.later(3000, done); };
        this.later(2500, () => { if (this.stopped[sid]) return; this.agent(b, { paused: true });
          this.timed({ id: qid, session_id: sid, agent: name, agent_id: b, step: st.n, title: 'Show the trend chart by month or by quarter?',
            body: 'Last package used months. Quarters read cleaner for managers but hide the summer spike.', rec: 'By month', options: ['By month', 'By quarter'] }, 30); });
      } else this.later(7000, done);
    };
    this.later(1200, () => run(0));
  }
  onAnswer(id: string, value: any, msg: Ev = {}): void {
    if (id === 'A-q1') this.advanceA();
    else if (id === 'B-p1' && !this.pending[id]) {
      const b = this.agents['B-b1'];
      this.agent('B-b1', { paused: false });
      const ev = { type: 'activity', id: 'act-perm-B', session_id: 'S-B', agent_id: 'B-b1', role: 'builder', name: b.name, step: 1, tool: 'Bash', summary: 'python scripts/pull_claims.py --period 2026Q3 --out data/claims_q3.parquet' };
      if (value === 'deny') this.emit({ ...ev, status: 'denied', ts: new Date().toISOString() });
      else this.later(1600, () => this.emit({ ...ev, status: 'done', ...(msg.auto ? { auto: true } : {}), ts: new Date().toISOString() }));
      this.flags.bPerm = true;
      if (value === 'deny') {
        this.emit({ type: 'system', session_id: 'S-B', text: 'Run B: sql-builder could not pull the claims extract (permission denied), so step 1 is blocked.' });
        this.step('S-B', 1, 'blocked');
        this.later(2500, () => { if (!this.stopped['S-B'] && this.running['S-B']) this.finish('S-B', 'blocked', '# Run B report · Readmissions tab\n**Status:** ended blocked at step 1\n\n## Why\nThe claims pull was denied, so the readmission SQL could not be built.\n\n## Next\nAllow the pull, or point the step at the existing extract.'); });
      } else this.tryB();
    }
    else if (id === 'B-q2') { this.step('S-B', 1, 'in_progress'); this.flags.bQ = true; this.tryB(); }
    else if (this.pending[id]) { const f = this.pending[id]; delete this.pending[id]; delete this.openPerms[id]; f(msg, value); }
  }

  /** A UI message, with a little network delay so the UI's "sent" state shows. */
  receive(msg: UiMessage): void { setTimeout(() => this.on(msg as Ev), 150 / this.speed); }
  on(msg: Ev): void {
    switch (msg.type) {
      case 'user_message': {
        const draft = /draft now/i.test(msg.text);
        if (!this.first[this.current]) this.first[this.current] = msg.text;
        this.think(900);
        this.later(1000, () => {
          if (draft) { this.say('Drafting the plan now.'); if (this.current === 'S-C') this.draftC(); else this.draftGeneric(this.current); }
          else if (/revise|again|change/i.test(msg.text) && this.drafts[this.current] && !this.running[this.current] && this.runs[this.current]) {
            this.say('Revised. Here is the new draft.'); this.draftFollowUp(this.current, (this.drafts[this.current].name || 'plan').replace(/^Follow-up: /, '').replace(/ \(rev \d+\)/g, '') + ` (rev ${(this.rev[this.current] || 0) + 1})`);
          }
          else if (this.current === 'S-C' && this.visPicked) { this.say(`Noted your pick for the trend chart: **${this.visPicked}**. I'll put it in the plan.`); this.visPicked = null; }
          else if (this.current === 'S-C') this.say('Good question. I’ll fold that in. Your open round is still waiting whenever you’re ready.');
          else this.say('Got it. Tell me more, or say **draft now** and I’ll write a plan you can approve.');
        });
        break;
      }
      case 'round_answer':
        if (msg.skipped) break;
        this.think(700);
        this.later(1100, () => {
          this.say('Noted.');
          if (this.roundNo === 1 && this.current === 'S-C' && !this.agents['P-C'].promotedDemo) {   // turn 2: the criteria fire
            this.agents['P-C'].promotedDemo = true; this.agent('P-C', { model: 'opus' });
            this.emit({ type: 'planner_model', session_id: 'S-C', model: 'opus', promoted: true, by: 'criteria',
              reason: 'Three outputs (trend tabs, readmissions SQL, commentary) and a sign-off point: a multi-part analysis plan.' });
          }
          if (this.roundNo === 1 && this.current === 'S-C' && !this.vsets['vs-1']) {
            this.say("Quick design questions first: how should the readmissions trend look (ECharts by default, plus Chart.js, D3 and the team notebook's matplotlib style), and what palette and hero card should the report use? I asked the Visualizer for sketches on made-up data. They're in the panel beside the chat; pick any, or tweak them.");
            this.visualDemo('S-C');
          }
          this.nextRound();
        });
        break;
      case 'queue_response': {
        if (this.answered[msg.id] != null) break;          // the timer got there first
        const v = msg.answer ?? msg.decision;
        this.answered[msg.id] = v;
        this.emit({ type: 'queue_resolved', id: msg.id, answer: v, by: 'user' });
        this.onAnswer(msg.id, v, msg);
        break;
      }
      case 'plan_approve': {
        const d = this.drafts[msg.session_id];
        if (!d) { this.emit({ type: 'system', session_id: msg.session_id, text: 'No draft plan to approve yet.' }); break; }
        if (this.running[msg.session_id]) { this.emit({ type: 'system', session_id: msg.session_id, text: "This session's run is already going." }); break; }
        if ((this.launchedRev[msg.session_id] || 0) >= (this.rev[msg.session_id] || 0)) { this.emit({ type: 'system', session_id: msg.session_id, text: 'There is no new draft to approve: the latest one already ran.' }); break; }
        this.launchedRev[msg.session_id] = this.rev[msg.session_id] || 0; this.running[msg.session_id] = true;
        this.later(600, () => {
          const sid = msg.session_id;
          this.runs[sid] = (this.runs[sid] || 0) + 1;
          this.emit({ type: 'run_started', session_id: sid, name: d.name, steps: withAgents(d.steps).map(st => ({ ...st, status: 'todo' })), autopilot: !!this.autopilot[sid], run: this.runs[sid], revision: this.rev[sid] || 0 });
          this.emit({ type: 'plan_meta', session_id: msg.session_id, name: d.name, mode: 'Run', status: 'Running' });
          this.runPlan(msg.session_id);
        });
        break;
      }
      case 'new_session': {
        const id = `S-N${++this.n}`;
        this.session(id, `.launchpad/new-plan-${this.n}`, null, msg.dir_id);
        this.current = id; this.pid = 'P-' + id;
        this.agent(this.pid, { session_id: id, role: 'planner', name: 'Planner', model: 'sonnet', status: 'idle' });
        this.emit({ type: 'planner_model', session_id: id, model: 'sonnet', promoted: false, reason: null, by: null });
        this.emit({ type: 'plan_meta', session_id: id, name: 'New session', mode: 'Chat', status: 'Ready' });
        this.later(500, () => this.say('Fresh page. What are we planning? Say **draft now** any time and I’ll write a plan you can approve.'));
        break;
      }
      case 'report_to_planner': {
        const sid = msg.session_id, name = this.names[sid] || this.drafts[sid]?.name || 'that run';
        this.current = sid;                                   // like the server: that session's planner becomes current
        this.pid = Object.values(this.agents).find(a => a.role === 'planner' && a.session_id === sid)?.agent_id || 'P-' + sid;
        if (!this.agents[this.pid]) this.agent(this.pid, { session_id: sid, role: 'planner', name: 'Planner', model: 'opus', status: 'idle' });
        this.think(2200);
        this.later(1400, () => {
          this.say(`I've read the [report](${this.folders[sid]}/report.md) for **${name}**.\n\n- Everything in the plan was built\n- One follow-up is still open (see the report)\n\nI've drafted a short follow-up plan for it below; approve it to run it in this same session.`);
          this.draftFollowUp(sid, name);
        });
        break;
      }
      case 'run_stop': {
        const sid = msg.session_id; if (this.stopped[sid]) break;
        this.stopped[sid] = true;
        this.later(500, () => this.finish(sid, 'stopped', '# Run stopped\n\nStopped by you. Steps already done were kept; the step in progress was abandoned and nothing was rolled back.'));
        break;
      }
      case 'get_crew': this.later(300, () => this.emit(this.crewList(msg.dir_id))); break;
      case 'agent_draft': this.agentDraft(msg); break;
      case 'agent_create': this.agentCreate(msg); break;
      case 'agent_remove': this.agentRemove(msg); break;
      case 'chat_from_plan': this.chatFromPlan(msg.session_id); break;
      case 'chat_new': this.later(250, () => this.chatStart(msg.dir_id)); break;
      case 'get_settings': case 'set_settings': case 'add_directory': case 'remove_directory': case 'pick_directory':
      case 'list_dir': case 'read_file': case 'save_file': case 'list_backups': case 'restore_backup': this.fsOn(msg); break;
      case 'set_autopilot': this.setAutopilot(msg.session_id, !!msg.on); break;
      case 'planner_promote': {
        const pid = Object.values(this.agents).find(a => a.role === 'planner' && a.session_id === msg.session_id)?.agent_id;
        this.later(400, () => { if (pid) this.agent(pid, { model: 'opus' }); this.emit({ type: 'planner_model', session_id: msg.session_id, model: 'opus', promoted: true, by: 'user', reason: null }); });
        break;
      }
      case 'visual_pick': { const vs = this.vsets[msg.set_id]; if (vs) { vs.picked_id = msg.option_id; this.visPicked = (vs.options.find((o: Ev) => o.id === msg.option_id) || {}).label || null; this.visEmit(vs.set_id); } break; }
      case 'visual_tweak': this.visRedo(msg, String(msg.text || '')); break;
      case 'visual_retry': this.visRedo(msg, ''); break;
      case 'chat_message': this.chatTurnRun(msg.chat_id, String(msg.text || '')); break;
      case 'chat_set_mode': this.chatMode[msg.chat_id] = msg.mode; this.emit({ type: 'chat_mode', chat_id: msg.chat_id, mode: msg.mode }); break;
      case 'chat_stop': this.chatStopTurn(msg.chat_id); break;
    }
  }

  /* ---- Claude Code demo: scripted Claude Code chats ---- */
  chatLater(cid: string, ms: number, fn: () => void): void { const t = this.chatTurns[cid]; this.later(ms, () => { if (this.chatTurns[cid] === t) fn(); }); }
  chatStart(dirId?: string, mode = 'default', fromSession?: string): string {
    const id = 'chat-' + (++this.chatN), d = this.fsDirs.find(x => x.dir_id === dirId) || this.fsDirs.find(x => x.is_default) || this.fsDirs[0];
    this.chatMode[id] = mode; this.chatCount[id] = 0; this.chatTurns[id] = 0; this.chatCalls[id] = [];
    this.emit({ type: 'chat_started', chat_id: id, mode, model: 'sonnet', cwd: d ? d.path : '', dir_id: d ? d.dir_id : null, ...(fromSession ? { from_session_id: fromSession } : {}) });
    this.agent('pilot-' + id, { session_id: null, chat_id: id, role: 'pilot', name: 'Claude Code', model: 'sonnet', status: 'idle' });
    this.total();
    return id;
  }
  chatStream(cid: string, text: string, then?: () => void): void {
    const parts = text.match(/\S+\s*/g) || [text]; let k = 0;
    const step = () => {
      if (k >= parts.length) { this.emit({ type: 'chat_message', chat_id: cid, role: 'assistant', markdown: text }); if (then) then(); return; }
      this.emit({ type: 'chat_delta', chat_id: cid, text: parts.slice(k, k + 3).join('') }); k += 3;
      this.chatLater(cid, 60, step);
    };
    step();
  }
  chatTool(cid: string, tool: string, summary: string, dur: number, then?: () => void, final = 'done'): Ev | null {
    const pid = 'pilot-' + cid, ev = this.call(pid, tool, summary, null);
    if (ev) this.chatCalls[cid].push(ev);
    this.chatLater(cid, dur, () => {
      this.chatCalls[cid] = this.chatCalls[cid].filter(x => x !== ev);
      if (ev) this.emit({ ...ev, status: final, ts: new Date().toISOString() }); this.burn(pid, 1200, 1); this.total();
      if (then) then();
    });
    return ev;
  }
  chatAsk(cid: string, o: Ev, onAnswer: (msg: Ev) => void): void {
    const id = 'cq-' + (++this.cqN);
    this.chatOpen[id] = cid;
    this.pending[id] = msg => { delete this.chatOpen[id]; onAnswer(msg); };
    this.emit({ type: 'queue_item', id, chat_id: cid, session_id: null, agent: 'Claude Code', agent_id: 'pilot-' + cid, step: null, title: '', body: '', rec: null,
      blocking: true, timeout_s: null, expires_at: null, ...o });
  }
  chatTurnRun(cid: string, text: string, fromPlan?: { name: string; steps: Ev[] }): void {
    if (!(cid in this.chatTurns)) return;
    this.chatTurns[cid]++;
    const n = ++this.chatCount[cid], pid = 'pilot-' + cid;
    this.agent(pid, { status: 'working' });
    this.emit({ type: 'chat_typing', chat_id: cid, on: true });
    const done = () => { this.emit({ type: 'chat_typing', chat_id: cid, on: false }); this.agent(pid, { status: 'idle' }); this.burn(pid, 1800, 0); this.total(); this.emit({ type: 'chat_done', chat_id: cid, status: 'ok' }); };
    if (this.chatMode[cid] === 'plan') this.chatPlanTurn(cid, done, fromPlan);
    else if (n === 1 || /fix|edit|change|loader|go\b/i.test(text)) this.chatEditTurn(cid, done);
    else this.chatQuestionTurn(cid, done);
  }
  chatEditTurn(cid: string, done: () => void): void {
    const L = (ms: number, fn: () => void) => this.chatLater(cid, ms, fn), pid = 'pilot-' + cid;
    const afterEdit = () => this.chatTool(cid, 'Bash', 'python -m pytest tests/ -q', 1300, () =>
      this.chatStream(cid, '**Done.**\n\n- `loader/load_claims.py`: the incurred month now comes from `service_from_dt`\n- Tests: 14 passed\n\nWant me to backfill earlier months with the corrected bucketing too?', done));
    L(500, () => this.chatStream(cid, "I'll start by reading the loader and its tests.", () =>
      this.chatTool(cid, 'Read', 'loader/load_claims.py', 600, () =>
      this.chatTool(cid, 'Grep', '"incurred_month" in loader/', 500, () =>
      this.chatStream(cid, 'Found it: `incurred_month` is built from `paid_dt`, so late claims land in the wrong month. I\'ll switch it to `service_from_dt`.', () => {
        const ev = this.call(pid, 'Edit', 'loader/load_claims.py', null);
        const finish = (st: string) => { if (ev) this.emit({ ...ev, status: st, ts: new Date().toISOString() }); };
        if (this.chatMode[cid] === 'accept_edits' || this.chatAlways[cid]) { L(700, () => { finish('done'); this.burn(pid, 900, 1); afterEdit(); }); return; }
        if (ev) this.chatCalls[cid].push(ev);
        this.chatAsk(cid, { kind: 'permission', tool: 'Edit', title: 'Edit loader/load_claims.py?',
          body: 'loader/load_claims.py\n- incurred_month = df.paid_dt.dt.to_period("M")\n+ incurred_month = df.service_from_dt.dt.to_period("M")',
          suggestions: [{ label: 'Yes, allow all edits during this session', remember: 'session' }, { label: "Yes, and don't ask again for edits in this project", remember: 'project_local' }] }, msg => {
          this.chatCalls[cid] = this.chatCalls[cid].filter(x => x !== ev);
          if (msg.decision === 'deny') { finish('denied'); this.chatStream(cid, msg.message ? `OK, no edit. You said: “${msg.message}”. I'll wait for your next instruction.` : "OK, I won't make that edit. What would you like me to do instead?", done); return; }
          if (msg.decision === 'always') {
            this.chatAlways[cid] = true;
            if (msg.remember === 'session') { this.chatMode[cid] = 'accept_edits'; this.emit({ type: 'chat_mode', chat_id: cid, mode: 'accept_edits' }); }
          }
          finish('done'); this.burn(pid, 900, 1); afterEdit();
        });
      })))));
  }
  chatPlanTurn(cid: string, done: () => void, fromPlan?: { name: string; steps: Ev[] }): void {
    const intro = fromPlan ? `Plan mode. I've read the plan **${fromPlan.name}**; I'll check the folder read-only and turn it into my own working plan.` : "Plan mode: I'll look around read-only and propose a plan.";
    const card = fromPlan
      ? { kind: 'plan', title: `Plan: ${fromPlan.name}`, markdown: `## Plan\n${fromPlan.steps.map(s => `${s.n}. ${s.title}${s.agent ? ` (the plan gave this to ${s.agent_display || s.agent}; I'll do it myself)` : ''}`).join('\n')}\n\n_I'll ask before each edit unless you choose auto-accept._` }
      : { kind: 'plan', title: 'Plan: fix the incurred month', markdown: '## Plan\n1. Change `incurred_month` in `loader/load_claims.py` to use `service_from_dt`\n2. Add a test for a claim paid two months after service\n3. Run the test suite\n\n_Nothing else changes._' };
    this.chatLater(cid, 500, () => this.chatStream(cid, intro, () =>
      this.chatTool(cid, 'Glob', fromPlan ? '**/*.sql' : 'loader/**/*.py', 500, () =>
      this.chatTool(cid, 'Read', fromPlan ? 'packages/2026Q2/inpatient_trend.xlsx' : 'loader/schema.sql', 600, () =>
      this.chatAsk(cid, card, msg => {
        if (msg.decision === 'deny') { this.chatStream(cid, `Understood${msg.message ? `: “${msg.message}”` : ''}. Still in plan mode; I'll revise when you're ready.`, done); return; }
        const m = msg.mode === 'accept_edits' ? 'accept_edits' : 'default';
        this.chatMode[cid] = m; this.emit({ type: 'chat_mode', chat_id: cid, mode: m });
        this.chatEditTurn(cid, done);
      })))));
  }
  chatQuestionTurn(cid: string, done: () => void): void {
    this.chatLater(cid, 400, () => { this.chatTool(cid, 'Read', 'tests/test_loader.py', 600, () =>
      this.chatAsk(cid, { kind: 'question', title: 'Which months should the backfill cover?', body: 'The fix changes how claims are bucketed. I can recompute earlier months too.', options: ['Q2 only', 'Q1 and Q2', 'Everything since 2025'] }, msg =>
        this.chatStream(cid, `Got it: **${msg.answer}**. Say "go" when you want me to start the backfill.`, done))); });
  }
  chatStopTurn(cid: string): void {
    if (!(cid in this.chatTurns)) return;
    this.chatTurns[cid]++;                                   // cancels everything scheduled for the old turn
    for (const [id, c] of Object.entries(this.chatOpen)) if (c === cid) { delete this.chatOpen[id]; delete this.pending[id]; this.answered[id] = 'stopped'; this.emit({ type: 'queue_resolved', id, answer: null, by: 'user' }); }
    for (const ev of this.chatCalls[cid] || []) this.emit({ ...ev, status: 'failed', ts: new Date().toISOString() });
    this.chatCalls[cid] = [];
    this.agent('pilot-' + cid, { status: 'idle' });
    this.emit({ type: 'chat_typing', chat_id: cid, on: false });
    this.emit({ type: 'chat_done', chat_id: cid, status: 'stopped' });
  }

  /* ---- Visuals demo: five sets, as the planner would ask for them. vs-1 ECharts (default): bar, stacked bar, line
     that fails until Retry, a KPI tile; vs-2 Chart.js; vs-3 D3; vs-4 asked for matplotlib, drawn in ECharts and
     labelled "styled like matplotlib"; vs-5 design briefs: a colour palette and a hero card. Chart.js / D3 draw for
     real when the page is served by Launchpad (they come from /vendor/lib); under npm run dev they show a note ---- */
  visChart(opt: Ev): string { return '<div id="c" style="width:100%;height:100%"></div><script>var ch=echarts.init(document.getElementById("c"));ch.setOption(' + visJs(opt) + ');<\/script>'; }
  visHtml(id: string, tweak = ''): string {
    const M = this.visMonths, rate = [11.2, 11.5, 11.4, 11.9, 12.1, 12.0, 12.4, 12.8, 12.6];
    const title = (t: string) => ({ text: t, subtext: tweak ? 'Tweak: ' + tweak : '', left: 8, top: 4, textStyle: { fontSize: 12, fontWeight: 600, color: '#22243A' }, subtextStyle: { fontSize: 10 } });
    const horiz = /horizontal|sideways/i.test(tweak);
    const axes = horiz ? { xAxis: { type: 'value' }, yAxis: { type: 'category', data: M } } : { xAxis: { type: 'category', data: M }, yAxis: { type: 'value' } };
    const grid = { left: horiz ? 46 : 40, right: 14, top: tweak ? 52 : 40, bottom: 26 };
    const extra = visExtra(id, tweak, M, rate);
    if (extra) return extra;
    if (id === 'bar') return this.visChart({ color: ['#3B3FB6'], title: title('30-day readmission rate, %'), grid, tooltip: { trigger: 'axis' }, ...axes, series: [{ type: 'bar', data: rate }] });
    if (id === 'stack') return this.visChart({ color: ['#B9B7E6', '#7E81D8', '#3B3FB6'], title: title('Readmissions by age band'), legend: { top: 4, right: 8, textStyle: { fontSize: 10 } }, grid, tooltip: { trigger: 'axis' }, ...axes,
      series: ([['18-44', [180, 175, 190, 185, 200, 196, 205, 210, 207]], ['45-64', [320, 330, 325, 340, 345, 350, 362, 371, 366]], ['65+', [510, 522, 518, 540, 552, 548, 566, 590, 584]]] as [string, number[]][]).map(([name, data]) => ({ name, type: 'bar', stack: 'all', data })) });
    if (id === 'line') return this.visChart({ color: ['#E8664A'], title: title('30-day readmission rate, %'), grid, tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: M }, yAxis: { type: 'value', min: 10 },
      series: [{ type: 'line', data: rate, symbolSize: 6, lineStyle: { width: 3 } }] });
    if (id === 'tile') return `<div style="padding:14px;height:100%;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;gap:4px">
      <div style="font-size:12px;color:#5E6278">30-day readmissions · Q3</div><div style="font:700 34px system-ui;color:#22243A">12.6%</div>
      <div style="font-size:12px;color:#9C3520;font-weight:600">&#9650; 0.8 pts vs Q2</div>
      <svg viewBox="0 0 100 24" style="width:100%;height:40px;margin-top:6px"><polyline points="0,20 12,18 25,19 37,14 50,12 62,13 75,9 87,5 100,7" fill="none" stroke="#3B3FB6" stroke-width="2.5" stroke-linejoin="round"/></svg>
      ${tweak ? `<div style="font-size:11px;color:#5E6278">Tweak: ${esc(tweak)}</div>` : ''}</div>`;
    if (id === 'probe') return `<div id="r" style="padding:12px;font:13px system-ui;line-height:1.6"></div><script>
      var out=[]; function show(){document.getElementById('r').innerHTML=out.join('<br>');parent.postMessage({lpVisual:1,kind:'probe',results:out.slice()},'*');}
      try{var t=parent.document.title;out.push('read parent page: ALLOWED ('+t+')');}catch(e){out.push('read parent page: blocked');}
      try{top.location.href='https://example.com/';out.push('navigate top window: attempted');}catch(e){out.push('navigate top window: blocked');}
      try{var f=document.createElement('form');f.method='post';f.action='https://example.com/';document.body.appendChild(f);f.submit();out.push('form post: attempted');}catch(e){out.push('form post: blocked');}
      try{fetch('https://example.com/').then(function(){out.push('fetch outside URL: ALLOWED');show();},function(){out.push('fetch outside URL: blocked');show();});}catch(e){out.push('fetch outside URL: blocked');show();}
      show();<\/script>`;
    if (id === 'navprobe') return '<p style="padding:12px;font:13px system-ui">This option tries to navigate its own frame to example.com in a moment.</p><script>setTimeout(function(){location.href="https://example.com/";},400);<\/script>';
    return '<p>?</p>';
  }
  visEmit(setId: string): void { const vs = this.vsets[setId]; if (vs) this.emit({ type: 'visual_set', ...JSON.parse(JSON.stringify(vs)) }); }
  visSet(setId: string, id: string, patch: Ev): void {
    const vs = this.vsets[setId], o = vs && vs.options.find((x: Ev) => x.id === id);
    if (o) { Object.assign(o, patch); if (patch.status !== 'failed') delete o.error; this.visEmit(setId); }
  }
  visualDemo(sid: string): void {
    const vid = 'V-' + sid, libraries = ['echarts', 'chartjs', 'd3'];
    const mk = (setId: string, brief: string, library: string | null, drawn: string, note: string | null, opts: [string, string][]) => {
      this.vsets[setId] = { session_id: sid, set_id: setId, brief, picked_id: null, library, drawn_with: drawn, libraries, library_note: note,
        options: opts.map(([id, label]) => ({ id, label, status: 'rendering', drawn_with: drawn })) };
    };
    mk('vs-1', 'How should the 30-day readmissions trend look?', null, 'echarts', null,
      [['bar', 'Bar'], ['stack', 'Stacked bar by age band'], ['line', 'Line'], ['tile', 'KPI tile (not a chart)']]);
    if (this.vistest) this.vsets['vs-1'].options.push({ id: 'probe', label: 'Security probe', status: 'rendering', drawn_with: 'echarts' }, { id: 'navprobe', label: 'Navigation probe', status: 'rendering', drawn_with: 'echarts' });
    mk('vs-2', 'Readmissions by discharge destination', 'chartjs', 'chartjs', null, [['cj-doughnut', 'Doughnut'], ['cj-bars', 'Grouped bars']]);
    mk('vs-3', 'Readmissions by facility', 'd3', 'd3', null, [['d3-bubble', 'Bubble chart'], ['d3-bars', 'Bars with labels']]);
    mk('vs-4', 'Monthly rate, as the team notebook shows it', 'matplotlib', 'echarts', 'drawn in ECharts, styled like matplotlib', [['mpl-line', 'Line with markers'], ['mpl-bar', 'Bar']]);
    mk('vs-5', 'Report look: colours and hero', null, 'echarts', null, [['palette', 'Colour palette'], ['hero', 'Hero card']]);
    this.agent(vid, { session_id: sid, role: 'visual', name: 'Visualizer', model: 'haiku', status: 'working' });
    for (const k of Object.keys(this.vsets)) this.visEmit(k);
    /* each visual drawn counts as one use of the Visualizer (as the hub does per render) */
    const ready = (setId: string, id: string, ms: number) => this.later(ms, () => { this.call(vid, 'Write', `visuals/${setId}/${id}.html`, 'done', 300); this.burn(vid, 900, 1); this.bump(ROLE_FILE.visual); this.visSet(setId, id, { status: 'ready', html: this.visHtml(id), path: `visuals/${setId}/${id}.html` }); });
    ready('vs-1', 'bar', 1200); ready('vs-1', 'stack', 1900); ready('vs-1', 'tile', 3000);
    this.later(2500, () => { this.call(vid, 'Write', 'visuals/vs-1/line.html', 'failed', 300); this.visSet('vs-1', 'line', { status: 'failed', error: 'The chart script threw: series[0].data is undefined' }); });
    if (this.vistest) { ready('vs-1', 'probe', 3200); ready('vs-1', 'navprobe', 3300); }
    ready('vs-2', 'cj-doughnut', 1500); ready('vs-2', 'cj-bars', 2100);
    ready('vs-3', 'd3-bubble', 1700); ready('vs-3', 'd3-bars', 2300);
    ready('vs-4', 'mpl-line', 2000); ready('vs-4', 'mpl-bar', 2600);
    ready('vs-5', 'palette', 1400); ready('vs-5', 'hero', 2200);
    this.later(3400, () => this.agent(vid, { status: 'idle' }));
  }
  visRedo(msg: Ev, tweak: string): void {
    const vs = this.vsets[msg.set_id]; if (!vs) return;
    const id = msg.option_id, vid = 'V-' + vs.session_id, setId = vs.set_id;
    this.agent(vid, { status: 'working' });
    this.visSet(setId, id, { status: 'rendering' });
    this.later(1500, () => { this.call(vid, 'Write', `visuals/${setId}/${id}.html`, 'done', 300); this.burn(vid, 700, 1); this.bump(ROLE_FILE.visual); this.visSet(setId, id, { status: 'ready', html: this.visHtml(id, tweak) }); this.agent(vid, { status: 'idle' }); });
  }
  /** The crew_list event: the six built-ins, then the agents in .claude/agents/ of the folder (demo: only d1 has any). */
  crewList(dirId?: string): Ev {
    this.fsInit();
    const dir = dirId || 'd1';
    const builtins = crewBase().map(a => {
      const p = agentPath(a.role), k = `app|${p}`, f = this.fs!.get(k);
      const out: Ev = { ...a, root: 'app', path: p, source_path: p, editable: !!f, uses: this.uses[a.name] || 0 };
      if (f) out.instructions = this.fsBody(k);
      if (a.promotion) out.promotion = { ...a.promotion, root: 'app', editable: true, criteria_path: PROMOTION_PATH, criteria: this.fsBody(`app|${PROMOTION_PATH}`) };
      return out;
    });
    const d = this.fsDirs.find(x => x.dir_id === dir);
    const folder = dir !== 'd1' ? [] : this.folderAgents.map(a => {
      const p = `.claude/agents/${a.name}.md`;
      return { ...a, root: dir, path: p, source_path: `${d ? d.path : ''}/${p}`, editable: true, uses: this.uses[a.name] || 0, instructions: this.fsBody(`${dir}|${p}`) };
    });
    return { type: 'crew_list', dir_id: dir, tool_choices: [...TOOL_CHOICES], agents: [...builtins, ...folder] };
  }

  /* ---- Crew: draft / create / remove a folder agent ---- */
  agentDraft(msg: Ev): void {
    const text = String(msg.text || '').trim(), dir = msg.dir_id;
    this.agent('drafter-' + (++this.n), { session_id: null, chat_id: null, role: 'drafter', name: 'Agent drafter', model: 'haiku', status: 'working' });
    this.later(1600, () => {
      if (/\b(fail|nonsense|asdf)\b/i.test(text) || text.length < 8) {
        this.emit({ type: 'agent_drafted', ok: false, dir_id: dir, error: 'The drafter could not tell what this agent should do. Say what it looks at and what it hands back.' });
        return;
      }
      const purpose = /review|check|audit|verify|\bqa\b/i.test(text) ? 'reviewing' : /\b(find|look|explore|search|map|locate)\b/i.test(text) ? 'exploring' : 'building';
      const stop = new Set(['the', 'and', 'for', 'that', 'with', 'from', 'into', 'every', 'each', 'new', 'before', 'after', 'checks', 'check', 'reviews', 'review', 'finds', 'find', 'writes', 'write', 'agent', 'should', 'which', 'this', 'when', 'our', 'any', 'all', 'are', 'its']);
      const words = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(w => w.length > 2 && !stop.has(w)).slice(0, 2);
      const base = `${words.join('-') || 'helper'}-${({ reviewing: 'reviewer', exploring: 'scout', building: 'builder' } as Ev)[purpose]}`;
      const names = new Set([...crewBase().map(a => a.name), ...this.folderAgents.map(a => a.name)]);
      let name = base; for (let k = 2; names.has(name); k++) name = `${base}-${k}`;
      const sentence = text.charAt(0).toUpperCase() + text.slice(1).replace(/[.!\s]*$/, '.');
      const title = name.replace(/-/g, ' ').replace(/^./, c => c.toUpperCase());
      this.emit({ type: 'agent_drafted', ok: true, dir_id: dir, fields: {
        name, description: sentence.slice(0, 220), purpose, model: purpose === 'building' ? 'sonnet' : 'haiku',
        tools: purpose === 'building' ? ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash'] : ['Read', 'Glob', 'Grep'],
        instructions: `# ${title}\n\n${sentence}\n\n## How you work\n- Read the step's brief and the files it names first\n- ${purpose === 'building' ? 'Make the change the step asks for, then run the checks' : 'Never change files; report what you found'}\n- Finish with a short list: what you looked at, what you found, anything left open`,
      } });
      const dr = Object.values(this.agents).find(a => a.role === 'drafter' && a.status === 'working');
      if (dr) { this.burn(dr.agent_id, 600, 0); this.agent(dr.agent_id, { status: 'done' }); }
    });
  }
  agentCreate(msg: Ev): void {
    const f = msg.fields || {}, dir = msg.dir_id, name = String(f.name || '').trim();
    const problems: string[] = [];
    if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) problems.push('name: lowercase letters, digits and dashes only');
    else if (name.startsWith('launchpad-') || crewBase().some(a => a.name === name)) problems.push('name: names starting with launchpad- are kept for Launchpad\'s own agents');
    else if (this.folderAgents.some(a => a.name === name)) problems.push(`name: an agent called ${name} already exists in this folder`);
    if (!String(f.description || '').trim()) problems.push("front matter: 'description' missing");
    if (!['exploring', 'building', 'reviewing'].includes(f.purpose)) problems.push('purpose: must be exploring, building or reviewing');
    if (f.model && !/^(opus|sonnet|haiku|inherit|claude-.+)$/.test(f.model)) problems.push(`model: '${f.model}' is not opus, sonnet, haiku, inherit or a claude-... model id`);
    const bad = (f.tools || []).filter((x: string) => !TOOL_CHOICES.includes(x));
    if (bad.length) problems.push(`tools: not a tool name: ${bad.join(', ')}`);
    if (['exploring', 'reviewing'].includes(f.purpose) && (f.tools || []).some((x: string) => ['Write', 'Edit', 'Bash'].includes(x))) problems.push('tools: a read-only agent cannot have Write, Edit or Bash');
    this.later(700, () => {
      if (problems.length) { this.emit({ type: 'agent_saved', ok: false, dir_id: dir, error: 'Not saved: the agent file did not pass the check.', problems }); return; }
      const tools: string[] = (f.tools && f.tools.length) ? f.tools : f.purpose === 'building' ? ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash'] : ['Read', 'Glob', 'Grep'];
      const text = `---\nname: ${name}\ndescription: ${f.description}\npurpose: ${f.purpose}\nmodel: ${f.model || 'inherit'}\ntools: ${tools.join(', ')}\n---\n${f.instructions || ''}`;
      this.fsWrite(dir || 'd1', `.claude/agents/${name}.md`, text, { validates_as: 'agent', applies: 'new_sessions' });
      this.folderAgents.push({ name, display_name: name.replace(/-/g, ' ').replace(/^./, (c: string) => c.toUpperCase()), role: null, purpose: f.purpose, builtin: false, step_worker: true,
        model: f.model || 'inherit', description: f.description, builtin_tools: tools, custom_tools: [{ name: 'report_step', description: 'Write the step report and end the step.' }], mcp_servers: [], disallowed_tools: [], warnings: [] });
      this.uses[name] = 0;
      this.emit({ type: 'agent_saved', ok: true, dir_id: dir, name });
      this.later(150, () => this.emit(this.crewList(dir)));
    });
  }
  agentRemove(msg: Ev): void {
    const name = String(msg.name || ''), dir = msg.dir_id || 'd1';
    this.later(500, () => {
      const k = this.folderAgents.findIndex(a => a.name === name);
      if (k < 0) { this.emit({ type: 'agent_removed', ok: false, dir_id: dir, name, error: crewBase().some(a => a.name === name) ? 'Built-in agents cannot be removed.' : `No agent called ${name} in this folder.` }); return; }
      this.folderAgents.splice(k, 1);
      this.fs!.delete(`${dir}|.claude/agents/${name}.md`);                 // the real server keeps a backup copy
      this.emit({ type: 'agent_removed', ok: true, dir_id: dir, name });
      this.later(150, () => this.emit(this.crewList(dir)));
    });
  }

  /* ---- "Send plan to Claude Code": a chat in the session's folder, Plan mode, the plan as its first message ---- */
  chatFromPlan(sid: string): void {
    const d = this.drafts[sid];
    if (!d) { this.emit({ type: 'system', session_id: sid, text: 'There is no draft plan to send to Claude Code yet.' }); return; }
    this.later(300, () => {
      const cid = this.chatStart(this.sdir[sid], 'plan', sid);
      this.emit({ type: 'chat_message', chat_id: cid, role: 'user', markdown: d.markdown });                   // the plan as the user's first message
      this.later(200, () => this.chatTurnRun(cid, d.markdown, { name: d.name, steps: d.steps }));
    });
  }
}